"""Tests for the synthetic data generator (determinism + structural guarantees)."""
import json

from src.synth import DOMAINS, SLOT_RE, generate, make_articles, make_errors


def test_generator_is_deterministic(tmp_path):
    generate(tmp_path / "a1.jsonl", tmp_path / "e1.jsonl", seed=42)
    generate(tmp_path / "a2.jsonl", tmp_path / "e2.jsonl", seed=42)
    assert (tmp_path / "a1.jsonl").read_bytes() == (tmp_path / "a2.jsonl").read_bytes()
    assert (tmp_path / "e1.jsonl").read_bytes() == (tmp_path / "e2.jsonl").read_bytes()


def test_summary_templates_have_each_slot_once():
    for domain, spec in DOMAINS.items():
        for lang in ("hi", "hg"):
            slots = [m.group(1) for s in spec[lang]["summary"] for m in SLOT_RE.finditer(s)]
            assert sorted(slots) == sorted(["person", "org", "loc", "date", "num", "pol"]), (domain, lang)


def test_summary_entities_appear_in_source():
    for art in make_articles(42):
        for kf in art["key_facts"]:
            if kf["type"] == "entity":                   # entities are never noised or digit-converted
                assert kf["value"] in art["text"], (art["article_id"], kf)


def test_error_rows_change_summary_and_balance():
    arts = make_articles(42)
    rows = make_errors(arts, 42)
    errs = [r for r in rows if r["label"] == "ERROR"]
    assert all(r["candidate_summary"] != r["reference_summary"] for r in errs)
    counts = {}
    for r in errs:
        counts[r["error_type"]] = counts.get(r["error_type"], 0) + 1
    assert max(counts.values()) - min(counts.values()) <= 1        # balanced types
    for a in arts:                                                  # 3 distinct types per article
        types = [r["error_type"] for r in errs if r["article_id"] == a["article_id"]]
        assert len(types) == len(set(types)) == 3


def test_saved_files_have_no_private_fields(tmp_path):
    generate(tmp_path / "a.jsonl", tmp_path / "e.jsonl", seed=42)
    first = json.loads((tmp_path / "a.jsonl").read_text(encoding="utf-8").splitlines()[0])
    assert not any(k.startswith("_") for k in first)
