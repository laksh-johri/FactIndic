"""Tests for src/llm.py using a fake backend (no network, no API key needed)."""
import csv

import pytest

from src.llm import LLMClient, LLMConfigError, prompt_hash


class FakeBackend:
    def __init__(self, fail_times=0, code=429):
        self.calls, self.fail_times, self.code = 0, fail_times, code

    def __call__(self, model, prompt, temperature, max_tokens):
        self.calls += 1
        if self.calls <= self.fail_times:
            err = RuntimeError("rate limit")
            err.code = self.code
            raise err
        return {"text": f"echo:{prompt}", "input_tokens": 3, "output_tokens": 2}


def make(tmp_path, backend, **kw):
    return LLMClient(model="fake-model", cache_path=tmp_path / "c.json", log_path=tmp_path / "log.csv",
                     backend=backend, sleep=lambda s: None, **kw)


def read_log(tmp_path):
    with open(tmp_path / "log.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_hash_depends_on_model_prompt_temperature():
    h = prompt_hash("m", "p", 0)
    assert h == prompt_hash("m", "p", 0.0)
    assert h != prompt_hash("m2", "p", 0) != prompt_hash("m", "p2", 0)
    assert h != prompt_hash("m", "p", 0.7)


def test_cache_miss_then_hit(tmp_path):
    fb = FakeBackend()
    c = make(tmp_path, fb)
    assert c.call("hello") == "echo:hello"
    assert c.call("hello") == "echo:hello"
    assert fb.calls == 1                                    # second call served from cache
    # a fresh client re-reads the cache from disk
    fb2 = FakeBackend()
    assert make(tmp_path, fb2).call("hello") == "echo:hello" and fb2.calls == 0
    log = read_log(tmp_path)
    assert [r["cache"] for r in log] == ["miss", "hit", "hit"]
    assert log[0]["input_tokens"] == "3" and log[0]["status"] == "ok"


def test_retry_on_rate_limit(tmp_path):
    fb = FakeBackend(fail_times=2, code=429)
    assert make(tmp_path, fb, max_retries=3).call("x") == "echo:x"
    assert fb.calls == 3
    statuses = [r["status"] for r in read_log(tmp_path)]
    assert statuses[:2] == ["retry:RuntimeError"] * 2 and statuses[-1] == "ok"


def test_non_retryable_error_raises(tmp_path):
    fb = FakeBackend(fail_times=1, code=400)
    fb_err = make(tmp_path, fb, max_retries=3)
    with pytest.raises(RuntimeError):
        fb_err.call("x")
    assert fb.calls == 1


def test_missing_key_raises_clear_error(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: False)
    c = LLMClient(model="fake-model", cache_path=tmp_path / "c.json", log_path=tmp_path / "log.csv")
    with pytest.raises(LLMConfigError, match="GEMINI_API_KEY"):
        c.call("needs the network")
    assert read_log(tmp_path)[-1]["status"] == "no_api_key"
