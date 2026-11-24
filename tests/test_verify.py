"""Tests for src/rules.py, src/verify.py and src/nli.py (NLI model replaced by a fake)."""
import pytest

from src.nli import NLIModel, nli_label
from src.rules import (build_safe_vocab, check_dates, check_entities, check_negation, check_numbers, dates,
                       numbers, run_rules)
from src.verify import decide, summary_flagged

EV_HI = ["टीम ने पहले बल्लेबाज़ी करते हुए २५३ रन बनाए।", "विपक्षी टीम केवल १२५ रन ही बना सकी।"]


# ---------------- extraction ----------------
def test_numbers_and_dates_extraction():
    assert numbers("सभा में लगभग 18,500 लोग, २०२५") == ["18500", "2025"]
    assert dates("20 जनवरी २०२५ को") == [(20, 1, 2025)]
    assert dates("19 January 2024 ko") == [(19, 1, 2024)]
    assert dates("5 फरवरी 2023") == dates("5 फ़रवरी 2023") == [(5, 2, 2023)]   # nukta variant


# ---------------- rules ----------------
def test_number_rule_handles_devanagari_digits():
    assert check_numbers("टीम ने 253 रन बनाए।", EV_HI).status == "pass"
    r = check_numbers("टीम ने 152 रन बनाए।", EV_HI)
    assert r.status == "fail" and r.details["missing"] == ["152"]
    assert check_numbers("बारिश हुई।", EV_HI).status == "na"


def test_date_rule():
    ev = ["2 अक्टूबर 2023 को नागपुर में खेले गए मुकाबले में ..."]
    assert check_dates("मुकाबला 2 अक्टूबर 2023 को हुआ।", ev).status == "pass"
    assert check_dates("मुकाबला 2 जुलाई 2023 को हुआ।", ev).status == "fail"


def test_negation_rule_uses_best_evidence_and_spelling_variants():
    ev = ["Unhone upcoming election ke liye kisi naye alliance ka announcement nahin kiya."]
    assert check_negation("Unhone kisi naye alliance ka announcement nahi kiya.", ev).status == "pass"
    assert check_negation("Unhone kisi naye alliance ka announcement kiya.", ev).status == "fail"


def test_entity_rule_with_safe_vocab():
    safe = build_safe_vocab(["X Hospital ne camp lagaya, jiske incharge Dr. Amit Verma the."],
                            [[{"type": "entity", "value": "Amit Verma"}, {"type": "entity", "value": "X Hospital"}]])
    assert "lagaya" in safe and "amit" not in safe and "hospital" not in safe
    ev = ["Camp ke incharge Dr. Alok Saxena ne bataya ki total 290 patients ka checkup kiya gaya."]
    assert check_entities("jiske incharge Dr. Alok Saxena the.", ev, safe).status == "pass"
    r = check_entities("jiske incharge Dr. Neha Gupta the.", ev, safe)
    assert r.status == "fail" and r.details["novel"] == ["neha", "gupta"]


def test_run_rules_order():
    assert [r.name for r in run_rules("टीम ने 253 रन बनाए।", EV_HI, set())] == ["numbers", "dates", "negation", "entities"]


# ---------------- decision rule ----------------
P_ENT = {"entailment": 0.9, "neutral": 0.05, "contradiction": 0.05}
P_CON = {"entailment": 0.05, "neutral": 0.05, "contradiction": 0.9}
P_NEU = {"entailment": 0.1, "neutral": 0.8, "contradiction": 0.1}
P_LOW = {"entailment": 0.4, "neutral": 0.3, "contradiction": 0.3}


def test_decision_rule():
    ok = run_rules("टीम ने 253 रन बनाए।", EV_HI, set(), enabled=("numbers",))
    bad = run_rules("टीम ने 152 रन बनाए।", EV_HI, set(), enabled=("numbers",))
    assert decide(P_ENT, ok, 0.5).label == "SUPPORTED"
    assert decide(P_ENT, bad, 0.5).label == "CONTRADICTED"            # rule beats NLI entailment
    assert decide(P_CON, ok, 0.5).label == "CONTRADICTED"
    assert decide(P_NEU, ok, 0.5).label == "UNSUPPORTED"
    assert decide(P_LOW, ok, 0.5).label == "REVIEW"
    assert decide(P_ENT, bad, 0.5, mode="nli_only").label == "SUPPORTED"
    assert decide(None, ok, 0.5, mode="rules_only").label == "SUPPORTED"
    assert decide(None, bad, 0.5, mode="rules_only").label == "CONTRADICTED"
    with pytest.raises(ValueError):
        decide(P_ENT, ok, 0.4)


def test_summary_flag():
    ok = run_rules("x", ["x"], set(), enabled=())
    assert not summary_flagged([decide(P_ENT, ok, 0.5)] * 3)
    assert summary_flagged([decide(P_ENT, ok, 0.5), decide(P_LOW, ok, 0.5)])


# ---------------- NLI wrapper ----------------
def test_nli_cache_with_fake_backend(tmp_path):
    calls = []

    def fake(pairs):
        calls.append(len(pairs))
        return [P_ENT if p == h else P_CON for p, h in pairs]

    m = NLIModel("fake", cache_dir=tmp_path, backend=fake)
    out = m.predict([("a", "a"), ("a", "b"), ("a", "a")])
    assert [nli_label(o) for o in out] == ["entailment", "contradiction", "entailment"]
    assert calls == [2]                                               # duplicate pair computed once
    NLIModel("fake", cache_dir=tmp_path, backend=fake).predict([("a", "b")])
    assert calls == [2]                                               # served from disk
