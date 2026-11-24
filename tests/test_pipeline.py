"""Tests for src/pipeline.py (the single-summary pipeline used by the demo)."""
import json
from pathlib import Path

import pytest

from src.config import ROOT
from src.data import load_errors
from src.nli import NLIModel
from src.pipeline import FactIndicPipeline


def fake_backend(pairs):
    """Stand-in NLI model: entailment if every claim word appears in the premise, else neutral."""
    out = []
    for premise, claim in pairs:
        words = [w.strip("।.,") for w in claim.lower().split()]
        ok = all(w in premise.lower() for w in words if w)
        out.append({"entailment": 0.9, "neutral": 0.05, "contradiction": 0.05} if ok
                   else {"entailment": 0.1, "neutral": 0.8, "contradiction": 0.1})
    return out


@pytest.fixture(scope="module")
def fake_pipe(tmp_path_factory):
    return FactIndicPipeline(nli=NLIModel(cache_dir=tmp_path_factory.mktemp("nli"), backend=fake_backend))


SOURCE = ("Agra mein 12 March 2024 ko ek health camp lagaya gaya. Camp mein 290 patients ka checkup kiya gaya. "
          "Organisers ne bataya ki koi bhi fee nahi li gayi.")


def test_correct_summary_is_accepted_unchanged(fake_pipe):
    summ = "Agra mein 12 March 2024 ko ek health camp lagaya gaya. Camp mein 290 patients ka checkup kiya gaya."
    r = fake_pipe.run(SOURCE, summ)
    assert [c.verdict for c in r.claims] == ["SUPPORTED", "SUPPORTED"]
    assert r.repair.repaired == summ and r.status == "accepted" and not r.flagged


def test_number_error_is_flagged_repaired_and_rechecked(fake_pipe):
    summ = "Camp mein 920 patients ka checkup kiya gaya."
    r = fake_pipe.run(SOURCE, summ)
    assert r.claims[0].verdict == "CONTRADICTED" and r.claims[0].rules["numbers"]["status"] == "fail"
    assert r.claims[0].evidence[0]["text"].startswith("Camp mein 290")
    assert r.repair.repaired == "Camp mein 290 patients ka checkup kiya gaya."
    assert [c.verdict for c in r.recheck] == ["SUPPORTED"] and r.status == "accepted"


def test_empty_summary_and_empty_source(fake_pipe):
    r = fake_pipe.run(SOURCE, "   ")
    assert r.claims == [] and r.status == "human_review"
    with pytest.raises(ValueError):
        fake_pipe.run("   ", "Camp lagaya gaya.")


def test_to_dict_is_json_serialisable(fake_pipe):
    r = fake_pipe.run(SOURCE, "Camp mein 920 patients ka checkup kiya gaya.")
    d = json.loads(json.dumps(r.to_dict(), ensure_ascii=False))
    assert d["repair"]["edits"][0]["action"] == "replace_number" and d["status"] == "accepted"


# ---------------------------------------------------------------------------
def _latest_repair_run() -> Path | None:
    runs = sorted((ROOT / "results" / "repair").glob("run_*/repairs_all.jsonl"))
    return runs[-1] if runs else None


def test_demo_pipeline_reproduces_step5_outputs_exactly():
    """The demo must give the same repaired text and final status as the Step 5 experiment, for all 512
    summaries. Uses only the NLI disk cache (a backend that raises proves no new NLI call is made)."""
    path = _latest_repair_run()
    nli = NLIModel(backend=lambda pairs: (_ for _ in ()).throw(LookupError("NLI cache miss")))
    if path is None or not nli.cache_path.exists():
        pytest.skip("needs results/repair run and the NLI cache (run experiments.run_repair first)")
    stored = {r["sample_id"]: r for r in map(json.loads, path.open(encoding="utf-8")) if r["system"] == "selective"}
    pipe = FactIndicPipeline(nli=nli)
    mismatches = []
    try:
        for r in load_errors().itertuples():
            res = pipe.run(r.source_text, r.candidate_summary)
            s = stored[r.sample_id]
            if (res.repair.repaired, res.status, [e.action for e in res.repair.edits]) != (s["output"], s["final"], s["actions"]):
                mismatches.append(r.sample_id)
    except LookupError:
        pytest.skip("NLI cache incomplete")
    assert not mismatches, mismatches[:10]
    assert len(stored) == 512
