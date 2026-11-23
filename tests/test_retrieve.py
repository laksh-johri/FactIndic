"""Tests for src/textnorm.py and src/retrieve.py (LaBSE replaced by a tiny fake model)."""
import numpy as np
import pytest

from src.data import load_articles
from src.retrieve import Embedder, Retriever, lexical_scores, split_source
from src.textnorm import normalize, normalize_digits, strip_nukta


class FakeModel:
    """Bag-of-characters embedding: deterministic, no download."""
    calls = 0

    def encode(self, texts, **kw):
        FakeModel.calls += 1
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for ch in t:
                out[i, ord(ch) % 64] += 1
        return out / np.maximum(np.linalg.norm(out, axis=1, keepdims=True), 1e-9)


def test_normalize():
    assert normalize_digits("२० मई २०२५") == "20 मई 2025"
    assert strip_nukta("बेरोज़गारी") == "बेरोजगारी"
    assert normalize("  Rally   MEIN  १२ ") == "rally mein 12"
    assert normalize("महँगाई") == normalize("महंगाई")


def test_split_source_gives_seven_sentences_per_article():
    for a in load_articles().itertuples():
        assert len(split_source(a.text)) == 7, a.article_id


def test_lexical_prefers_overlapping_sentence():
    s = lexical_scores(["Team ne 156 runs banaye."], ["Captain ne team ko lead kiya.", "Team ne 156 runs banaye."])
    assert s[0, 1] > s[0, 0]


def test_embedder_cache(tmp_path):
    FakeModel.calls = 0
    e = Embedder("fake", cache_dir=tmp_path, model=FakeModel())
    v1 = e.encode(["a b", "c d"])
    v2 = Embedder("fake", cache_dir=tmp_path, model=FakeModel()).encode(["c d", "a b"])
    assert FakeModel.calls == 1                       # second call fully served from disk
    assert np.allclose(v1[0], v2[1])


@pytest.mark.parametrize("method", ["lexical", "labse", "hybrid"])
def test_retrieve_finds_number_sentence_with_devanagari_digits(method, tmp_path):
    src = "टीम ने पहले बल्लेबाज़ी करते हुए २९८ रन बनाए। विपक्षी टीम केवल १२० रन ही बना सकी। मौसम अच्छा था।"
    r = Retriever(method=method, top_k=2, alpha=0.5, normalize_text=True,
                  embedder=Embedder("fake", cache_dir=tmp_path, model=FakeModel()))
    ev = r.retrieve("टीम ने 298 रन बनाए।", src)
    assert len(ev) == 2 and ev[0].rank == 1 and ev[0].score >= ev[1].score
    assert ev[0].sent_idx == 0 and src[ev[0].start:ev[0].end] == ev[0].text


def test_bad_method():
    with pytest.raises(ValueError):
        Retriever(method="bm25")
