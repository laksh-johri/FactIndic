"""Evidence retrieval: for each claim, return the top-k most similar source sentences.

Scorers (config.yaml -> retrieval.method):
  lexical : cosine of character 2-4-gram TF-IDF vectors (surface overlap; robust to spelling noise)
  labse   : cosine of LaBSE sentence embeddings (meaning; language/script independent)
  hybrid  : alpha * labse + (1 - alpha) * lexical; with retrieval.score_norm = minmax each
            scorer is first rescaled to [0, 1] per claim (so alpha = 0.5 is a true average)
retrieval.normalize = true applies src.textnorm.normalize() to both sides before scoring
(Devanagari digits -> ASCII, nukta removed, lowercase).

LaBSE embeddings are cached on disk (cache/embeddings_<model>.pkl) keyed by sha256(text).
"""
from __future__ import annotations

import hashlib
import pickle
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer

from src.config import ROOT, load_config
from src.decompose import sentence_spans
from src.textnorm import normalize

METHODS = ("lexical", "labse", "hybrid")


@dataclass
class Evidence:
    rank: int
    sent_idx: int
    text: str
    score: float
    start: int
    end: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Sentence:
    idx: int
    text: str
    start: int
    end: int


def split_source(text: str) -> list[Sentence]:
    return [Sentence(i, text[a:b], a, b) for i, (a, b) in enumerate(sentence_spans(text))]


# ---------------------------------------------------------------------------
# Embeddings with an on-disk cache
# ---------------------------------------------------------------------------
class Embedder:
    def __init__(self, model_name: str | None = None, cache_dir: str | Path | None = None,
                 batch_size: int = 32, model=None):
        cfg = load_config()
        self.model_name = model_name or cfg["models"]["embedder"]
        safe = self.model_name.replace("/", "__")
        self.cache_path = Path(cache_dir or ROOT / cfg["paths"]["cache"]) / f"embeddings_{safe}.pkl"
        self.batch_size = batch_size
        self._model = model                       # injectable (tests)
        self._cache: dict[str, np.ndarray] | None = None

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

    @property
    def model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name, device="cpu")
        return self._model

    def encode(self, texts: list[str]) -> np.ndarray:
        cache = self._load()
        keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        missing = sorted({k: t for k, t in zip(keys, texts) if k not in cache}.items())
        if missing:
            vecs = self.model.encode([t for _, t in missing], batch_size=self.batch_size,
                                     normalize_embeddings=True, show_progress_bar=False)
            for (k, _), v in zip(missing, vecs):
                cache[k] = np.asarray(v, dtype=np.float32)
            self._save()
        return np.stack([cache[k] for k in keys]) if keys else np.zeros((0, 0), dtype=np.float32)


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------
def lexical_scores(claims: list[str], sentences: list[str]) -> np.ndarray:
    """Char 2-4-gram TF-IDF cosine, IDF fitted on this article's sentences + claims."""
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True)
    m = vec.fit_transform(sentences + claims)
    s, c = m[: len(sentences)], m[len(sentences):]
    return (c @ s.T).toarray()                    # rows are L2-normalised -> dot = cosine


def minmax_rows(m: np.ndarray) -> np.ndarray:
    """Rescale each row to [0, 1]; a constant row becomes all zeros."""
    lo, hi = m.min(axis=1, keepdims=True), m.max(axis=1, keepdims=True)
    return (m - lo) / np.where(hi - lo > 1e-12, hi - lo, 1.0)


class Retriever:
    def __init__(self, method: str | None = None, top_k: int | None = None, alpha: float | None = None,
                 normalize_text: bool | None = None, embedder: Embedder | None = None,
                 score_norm: str | None = None):
        rc = load_config()["retrieval"]
        self.method = method or rc.get("method", "labse")
        if self.method not in METHODS:
            raise ValueError(f"unknown retrieval method {self.method!r}")
        self.score_norm = score_norm or rc.get("score_norm", "none")
        if self.score_norm not in ("none", "minmax"):
            raise ValueError(f"unknown score_norm {self.score_norm!r}")
        self.top_k = top_k or rc["top_k"]
        self.alpha = rc.get("alpha", 0.5) if alpha is None else alpha
        self.normalize_text = rc.get("normalize", True) if normalize_text is None else normalize_text
        self._embedder = embedder

    @property
    def embedder(self) -> Embedder:
        if self._embedder is None:
            self._embedder = Embedder()
        return self._embedder

    def _prep(self, texts: list[str]) -> list[str]:
        return [normalize(t) for t in texts] if self.normalize_text else list(texts)

    def score(self, claims: list[str], sentences: list[str]) -> np.ndarray:
        """Return a (n_claims x n_sentences) similarity matrix."""
        c, s = self._prep(claims), self._prep(sentences)
        if self.method == "lexical":
            return lexical_scores(c, s)
        e = self.embedder.encode(s + c)
        sem = e[len(s):] @ e[: len(s)].T
        if self.method == "labse":
            return sem
        lex = lexical_scores(c, s)
        if self.score_norm == "minmax":            # put both scorers on [0, 1] per claim first
            sem, lex = minmax_rows(sem), minmax_rows(lex)
        return self.alpha * sem + (1 - self.alpha) * lex

    def retrieve_many(self, claims: list[str], source: str, k: int | None = None) -> list[list[Evidence]]:
        k = k or self.top_k
        sents = split_source(source)
        if not claims or not sents:
            return [[] for _ in claims]
        scores = self.score(claims, [s.text for s in sents])
        out = []
        for row in scores:
            order = np.argsort(-row, kind="stable")[:k]
            out.append([Evidence(r + 1, int(i), sents[i].text, float(row[i]), sents[i].start, sents[i].end)
                        for r, i in enumerate(order)])
        return out

    def retrieve(self, claim: str, source: str, k: int | None = None) -> list[Evidence]:
        return self.retrieve_many([claim], source, k)[0]
