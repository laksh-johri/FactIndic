"""Multilingual NLI (mDeBERTa-v3 XNLI) with an on-disk cache.

predict([(premise, hypothesis), ...]) -> list of {"entailment": p, "neutral": p, "contradiction": p}
Premise = evidence from the source, hypothesis = the claim.
"""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

from src.config import ROOT, load_config

LABELS = ("entailment", "neutral", "contradiction")


class NLIModel:
    def __init__(self, model_name: str | None = None, cache_dir: str | Path | None = None,
                 batch_size: int = 16, max_length: int = 512, backend=None, verbose: bool = False):
        self.verbose = verbose
        cfg = load_config()
        self.model_name = model_name or cfg["models"]["nli"]
        safe = self.model_name.replace("/", "__")
        self.cache_path = Path(cache_dir or ROOT / cfg["paths"]["cache"]) / f"nli_{safe}.pkl"
        self.batch_size, self.max_length = batch_size, max_length
        self._backend = backend               # injectable for tests: f(pairs) -> list[dict]
        self._tok = self._model = None
        self._cache: dict | None = None

    # ---------------- cache ----------------
    def _key(self, premise: str, hypothesis: str) -> str:
        return hashlib.sha256(f"{self.model_name}\x1f{premise}\x1f{hypothesis}".encode("utf-8")).hexdigest()

    def _load(self) -> dict:
        if self._cache is None:
            self._cache = {}
            if self.cache_path.exists():
                with open(self.cache_path, "rb") as f:
                    self._cache = pickle.load(f)
        return self._cache

    def _save(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.cache_path, "wb") as f:
            pickle.dump(self._cache, f)

    # ---------------- model ----------------
    def _hf(self, pairs: list[tuple[str, str]]) -> list[dict]:
        import torch
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        if self._model is None:
            torch.manual_seed(load_config()["seed"])
            self._tok = AutoTokenizer.from_pretrained(self.model_name)
            self._model = AutoModelForSequenceClassification.from_pretrained(self.model_name).eval()
            self._id2label = {i: l.lower() for i, l in self._model.config.id2label.items()}
        out = []
        for i in range(0, len(pairs), self.batch_size):
            batch = pairs[i:i + self.batch_size]
            enc = self._tok([p for p, _ in batch], [h for _, h in batch], truncation="only_first",
                            max_length=self.max_length, padding=True, return_tensors="pt")
            with torch.no_grad():
                probs = self._model(**enc).logits.softmax(-1).tolist()
            out += [{self._id2label[j]: float(v) for j, v in enumerate(row)} for row in probs]
        return out

    def predict(self, pairs: list[tuple[str, str]]) -> list[dict]:
        cache = self._load()
        keys = [self._key(p, h) for p, h in pairs]
        todo = sorted({k: pr for k, pr in zip(keys, pairs) if k not in cache}.items())
        chunk = 128                                   # save after every chunk -> a crash loses little
        for i in range(0, len(todo), chunk):
            part = todo[i:i + chunk]
            res = (self._backend or self._hf)([pr for _, pr in part])
            for (k, _), r in zip(part, res):
                cache[k] = {lab: r[lab] for lab in LABELS}
            self._save()
            if self.verbose:
                print(f"  NLI {min(i + chunk, len(todo))}/{len(todo)} new pairs done", flush=True)
        return [dict(cache[k]) for k in keys]


def nli_label(probs: dict) -> str:
    return max(LABELS, key=lambda l: probs[l])
