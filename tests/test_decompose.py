"""Tests for src/decompose.py."""
import pytest

from src.data import load_articles, load_errors
from src.decompose import (claims_overlapping, decompose, decompose_clause, decompose_llm,
                           decompose_sentence, is_context_dependent, parse_json_list, sentence_spans)
from src.llm import LLMClient

HI = ("संजीवनी मेडिकल कॉलेज ने 18 सितंबर 2024 को ग्वालियर में मुफ़्त स्वास्थ्य शिविर लगाया, "
      "जिसके प्रभारी डॉ. विकास यादव थे। शिविर में 1080 मरीज़ों की जाँच की गई। "
      "किसी गंभीर बीमारी का मामला सामने नहीं आया।")
HG = ("Sanjeevani Medical College ne 9 July 2023 ko Gwalior mein free health camp lagaya, "
      "jiske incharge Dr. Alok Saxena the. Camp mein 290 patients ka checkup kiya gaya. "
      "Kisi serious bimari ka case saamne aaya.")


@pytest.mark.parametrize("text", [HI, HG])
def test_sentence_split_respects_abbreviations(text):
    claims = decompose_sentence(text)
    assert len(claims) == 3
    assert any(("डॉ. विकास" in c.text) or ("Dr. Alok" in c.text) for c in claims)


def test_sentence_split_keeps_decimals_and_initials():
    spans = sentence_spans("Growth was 3.5 percent. A. K. Singh ne kaha. Done")
    assert len(spans) == 3


@pytest.mark.parametrize("text", [HI, HG])
def test_clause_split_on_relative_clause(text):
    claims = decompose_clause(text)
    assert len(claims) == 4
    assert claims[0].text.endswith("।" if text is HI else ".")    # terminator added
    assert claims[1].text.split()[0].lower() in {"जिसके", "jiske"}


@pytest.mark.parametrize("text", [HI, HG])
def test_spans_point_back_into_summary(text):
    for c in decompose_clause(text):
        assert text[c.start:c.end].strip().rstrip("।.") in c.text


def test_no_split_on_comma_without_connective():
    assert len(decompose_clause("Rajesh, Sunita aur Amit ne match dekha.")) == 1


def test_context_dependence():
    assert is_context_dependent("उन्होंने किसी नए गठबंधन की घोषणा नहीं की।")
    assert is_context_dependent("jiske founder Harsh Bhatnagar hain.")
    assert not is_context_dependent("Team ne 156 runs banaye.")


def test_every_error_is_localised_by_clause_method():
    errs = load_errors()
    errs = errs[errs.label == "ERROR"]
    for r in errs.itertuples():
        hit = claims_overlapping(decompose_clause(r.candidate_summary), r.span_start, r.span_end)
        assert len(hit) == 1, r.sample_id


def test_gold_method_and_dispatch():
    a = load_articles().iloc[0]
    claims = decompose(a.summary, "gold", gold_claims=a.gold_claims)
    assert [c.text for c in claims] == a.gold_claims and claims[0].start == -1
    with pytest.raises(ValueError):
        decompose(a.summary, "gold")
    with pytest.raises(ValueError):
        decompose(a.summary, "magic")


def test_parse_json_list():
    assert parse_json_list('Sure!\n```json\n["a", "b "]\n```') == ["a", "b"]
    with pytest.raises(ValueError):
        parse_json_list("no list here")


def test_llm_method_with_fake_backend(tmp_path):
    fake = lambda model, prompt, t, n: {"text": '["X ने ऐप लॉन्च किया।", "ऐप मुफ़्त है।"]'}
    client = LLMClient(model="fake", cache_path=tmp_path / "c.json", log_path=tmp_path / "l.csv", backend=fake)
    claims = decompose_llm("कुछ भी", prefix="s1", client=client)
    assert [c.claim_id for c in claims] == ["s1#1", "s1#2"] and claims[0].method == "llm"
