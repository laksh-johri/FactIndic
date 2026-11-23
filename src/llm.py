"""Single entry point for every LLM (Gemini) call in FactIndic.

Features
  * on-disk cache (cache/llm_cache.json) keyed by sha256(model | temperature | prompt)
    -> re-running an experiment gives identical outputs and costs nothing;
  * retry with exponential backoff on rate-limit / temporary server errors;
  * one CSV log line per call in results/llm_calls.csv
    (time, prompt hash, model, latency, tokens, cache hit/miss, status);
  * the API key is read from .env (GEMINI_API_KEY) and is only needed on a cache MISS,
    so importing this module never fails and cached experiments run without a key.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from src.config import ROOT, load_config

LOG_FIELDS = ["timestamp", "prompt_hash", "model", "temperature", "latency_s",
              "input_tokens", "output_tokens", "cache", "status"]
RETRYABLE_CODES = {429, 500, 502, 503, 504}


class LLMConfigError(RuntimeError):
    """Raised when an LLM call is needed but no API key is configured."""


def prompt_hash(model: str, prompt: str, temperature: float) -> str:
    key = json.dumps({"model": model, "temperature": float(temperature), "prompt": prompt},
                     ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


class LLMClient:
    def __init__(self, model: str | None = None, cache_path: str | Path | None = None,
                 log_path: str | Path | None = None, max_retries: int | None = None,
                 backoff_base: float | None = None, max_output_tokens: int | None = None,
                 backend: Callable[[str, str, float, int], dict] | None = None,
                 sleep: Callable[[float], None] = time.sleep):
        cfg = load_config()
        lc = cfg["llm"]
        self.model = model or cfg["models"]["llm"]
        self.cache_path = Path(cache_path) if cache_path else ROOT / lc["cache_path"]
        self.log_path = Path(log_path) if log_path else ROOT / lc["log_path"]
        self.max_retries = lc["max_retries"] if max_retries is None else max_retries
        self.backoff_base = lc["backoff_base_seconds"] if backoff_base is None else backoff_base
        self.max_output_tokens = max_output_tokens or lc["max_output_tokens"]
        self._backend = backend          # injectable for tests; default = real Gemini
        self._sleep = sleep
        self._cache: dict[str, Any] | None = None
        self._client = None

    # ---------------- cache ----------------
    def _load_cache(self) -> dict:
        if self._cache is None:
            if self.cache_path.exists():
                with open(self.cache_path, encoding="utf-8") as f:
                    self._cache = json.load(f)
            else:
                self._cache = {}
        return self._cache

    def _save_cache(self) -> None:
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, ensure_ascii=False, indent=1)
        os.replace(tmp, self.cache_path)       # atomic: never leaves a half-written cache

    # ---------------- logging ----------------
    def _log(self, **row) -> None:
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        new = not self.log_path.exists()
        with open(self.log_path, "a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=LOG_FIELDS)
            if new:
                w.writeheader()
            w.writerow({"timestamp": datetime.now().isoformat(timespec="seconds"), **row})

    # ---------------- real backend ----------------
    def _gemini(self, model: str, prompt: str, temperature: float, max_tokens: int) -> dict:
        if self._client is None:
            from dotenv import load_dotenv
            load_dotenv(ROOT / ".env")
            key = os.getenv("GEMINI_API_KEY", "").strip()
            if not key:
                raise LLMConfigError(
                    "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key. "
                    "(Cached prompts still work without a key.)")
            from google import genai
            self._client = genai.Client(api_key=key)
        from google.genai import types
        resp = self._client.models.generate_content(
            model=model, contents=prompt,
            config=types.GenerateContentConfig(temperature=temperature, max_output_tokens=max_tokens))
        usage = getattr(resp, "usage_metadata", None)
        return {"text": resp.text or "",
                "input_tokens": getattr(usage, "prompt_token_count", None),
                "output_tokens": getattr(usage, "candidates_token_count", None)}

    @staticmethod
    def _is_retryable(err: Exception) -> bool:
        code = getattr(err, "code", None) or getattr(err, "status_code", None)
        if code is not None:                 # an HTTP status is authoritative
            return code in RETRYABLE_CODES
        msg = str(err).lower()               # fallback when the SDK gives no status code
        return "rate limit" in msg or "resource_exhausted" in msg or "429" in msg

    # ---------------- public ----------------
    def call(self, prompt: str, temperature: float = 0.0) -> str:
        h = prompt_hash(self.model, prompt, temperature)
        cache = self._load_cache()
        if h in cache:
            e = cache[h]
            self._log(prompt_hash=h[:16], model=self.model, temperature=temperature, latency_s=0.0,
                      input_tokens=e.get("input_tokens"), output_tokens=e.get("output_tokens"),
                      cache="hit", status="ok")
            return e["text"]

        backend = self._backend or self._gemini
        last_err: Exception | None = None
        for attempt in range(self.max_retries + 1):
            t0 = time.perf_counter()
            try:
                out = backend(self.model, prompt, temperature, self.max_output_tokens)
            except LLMConfigError:
                self._log(prompt_hash=h[:16], model=self.model, temperature=temperature,
                          latency_s=0.0, input_tokens=None, output_tokens=None,
                          cache="miss", status="no_api_key")
                raise
            except Exception as err:  # noqa: BLE001 - we re-raise non-retryable errors
                last_err = err
                latency = round(time.perf_counter() - t0, 3)
                retry = self._is_retryable(err) and attempt < self.max_retries
                self._log(prompt_hash=h[:16], model=self.model, temperature=temperature,
                          latency_s=latency, input_tokens=None, output_tokens=None, cache="miss",
                          status=f"retry:{type(err).__name__}" if retry else f"error:{type(err).__name__}")
                if not retry:
                    raise
                self._sleep(self.backoff_base * (2 ** attempt) + random.uniform(0, 1))
                continue
            latency = round(time.perf_counter() - t0, 3)
            cache[h] = {"model": self.model, "temperature": temperature, "prompt": prompt,
                        "text": out["text"], "input_tokens": out.get("input_tokens"),
                        "output_tokens": out.get("output_tokens"),
                        "created": datetime.now().isoformat(timespec="seconds")}
            self._save_cache()
            self._log(prompt_hash=h[:16], model=self.model, temperature=temperature, latency_s=latency,
                      input_tokens=out.get("input_tokens"), output_tokens=out.get("output_tokens"),
                      cache="miss", status="ok")
            return out["text"]
        raise last_err  # pragma: no cover


_default: LLMClient | None = None


def call_llm(prompt: str, temperature: float = 0.0) -> str:
    """Call the configured Gemini model (cached). Raises LLMConfigError if no key and cache miss."""
    global _default
    if _default is None:
        _default = LLMClient()
    return _default.call(prompt, temperature)
