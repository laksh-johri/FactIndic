"""Steps 5 + 6 experiment: selective repair of flagged claims, then re-verification.

Systems compared (all start from the Step 4 verdicts, config.yaml settings):
  no_repair       : the candidate summary unchanged
  delete_flagged  : delete every claim that is not SUPPORTED (crude baseline)
  selective       : src.repair.repair_summary (ours)
  selective_oracle: same repair, but with PERFECT detection (only the gold error claim is flagged)
                    -> isolates repair quality from detection quality
Gold outcome of each output summary, compared with the reference summary:
  complete  : identical to the reference (error fixed, nothing lost)
  lossy     : reference with some text deleted (faithful, but content lost)
  erroneous : anything else (error left in, or a new error introduced)
Step 6 (re-check): every output is re-verified with the same pipeline; a summary whose claims are
all SUPPORTED is auto-accepted, otherwise it goes to human review.
No parameters are tuned here, so dev and test are both reported (test = headline).

Run:  python -m experiments.run_repair
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from experiments.run_retrieval import contains  # noqa: E402
from experiments.run_verification import apply, md_table, prepare  # noqa: E402
from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import get_split, load_articles, load_errors  # noqa: E402
from src.decompose import decompose  # noqa: E402
from src.repair import apply_edits, delete_claim, repair_summary  # noqa: E402
from src.rules import build_safe_vocab  # noqa: E402

SYSTEMS = ["no_repair", "delete_flagged", "selective", "selective_oracle"]
ERROR_ORDER = ["none", "number_swap", "date_swap", "entity_swap", "negation", "unsupported_addition"]


def claim_inputs(group: pd.DataFrame, oracle: bool = False) -> list[dict]:
    out = []
    for r in group.itertuples():
        verdict = ("CONTRADICTED" if r.is_error_claim else "SUPPORTED") if oracle else r.verdict
        out.append({"claim_id": r.claim_id, "start": r.claim_start, "end": r.claim_end, "verdict": verdict,
                    "rules": {k: v["status"] for k, v in r.rules.items()},
                    "evidence": [e["text"] for e in r.evidence]})
    return out


def _norm_ws(t: str) -> str:
    return " ".join(t.split())


def gold_outcome(reference: str, output: str) -> str:
    """complete = identical to the reference; lossy = the reference with one or more WHOLE claims
    removed (checked by actually deleting every subset of its clause-level claims); else erroneous.
    (Deleting arbitrary characters is not enough: removing 'नहीं' reverses the meaning.)"""
    out = _norm_ws(output)
    if not out:
        return "empty"                                  # everything deleted: no false facts, but no summary
    if out == _norm_ws(reference):
        return "complete"
    claims = decompose(reference, "clause")
    for mask in range(1, 2 ** len(claims) - 1):
        edits = [delete_claim(c.claim_id, reference, c.start, c.end, "") for k, c in enumerate(claims) if mask >> k & 1]
        if _norm_ws(apply_edits(reference, edits)) == out:
            return "lossy"
    return "erroneous"


def run_systems(verdicts: pd.DataFrame, errors: pd.DataFrame, safe: set[str], safe_union: set[str]) -> pd.DataFrame:
    by_sample = dict(tuple(verdicts.groupby("sample_id", sort=False)))
    rows = []
    for r in errors.itertuples():
        g = by_sample[r.sample_id]
        cl = claim_inputs(g)
        outs = {"no_repair": (r.candidate_summary, [])}
        dels = [delete_claim(c["claim_id"], r.candidate_summary, c["start"], c["end"], "flagged")
                for c in cl if c["verdict"] != "SUPPORTED"]
        outs["delete_flagged"] = (apply_edits(r.candidate_summary, dels), dels)
        res = repair_summary(r.candidate_summary, cl, safe, safe_union)
        outs["selective"] = (res.repaired, res.edits)
        res_o = repair_summary(r.candidate_summary, claim_inputs(g, oracle=True), safe, safe_union)
        outs["selective_oracle"] = (res_o.repaired, res_o.edits)
        for name, (text, edits) in outs.items():
            rows.append(dict(system=name, sample_id=r.sample_id, article_id=r.article_id, split=r.split,
                             language=r.language, label=r.label, error_type=r.error_type,
                             candidate=r.candidate_summary, reference=r.reference_summary, output=text,
                             actions=[e.action for e in edits], edits=[vars(e) for e in edits],
                             outcome=gold_outcome(r.reference_summary, text)))
    return pd.DataFrame(rows)


def add_content_metrics(df: pd.DataFrame, articles: pd.DataFrame) -> pd.DataFrame:
    kf = {r.article_id: [k["value"] for k in r.key_facts] for r in articles.itertuples()}
    df["keyfact_retention"] = [100 * sum(contains(o, v) for v in kf[a]) / len(kf[a])
                               for o, a in zip(df.output, df.article_id)]
    df["sim_to_reference"] = [100 * difflib.SequenceMatcher(None, ref, o, autojunk=False).ratio()
                              for ref, o in zip(df.reference, df.output)]
    df["chars_changed"] = [100 * (1 - difflib.SequenceMatcher(None, c, o, autojunk=False).ratio())
                           for c, o in zip(df.candidate, df.output)]
    return df


def recheck(df: pd.DataFrame, errors: pd.DataFrame, cfg: dict) -> pd.Series:
    """Step 6: re-verify every distinct output text; return 'accepted' / 'human_review' per row."""
    vc = cfg["verification"]
    uniq = df.drop_duplicates(["sample_id", "output"])[["sample_id", "output"]]
    base = errors.set_index("sample_id")
    rows = []
    for i, (sid, text) in enumerate(uniq.itertuples(index=False)):
        b = base.loc[sid]
        rows.append(dict(sample_id=f"{sid}~{i}", article_id=b.article_id, language=b.language, domain=b.domain,
                         split=b.split, source_text=b.source_text, reference_summary=b.reference_summary,
                         candidate_summary=text, label="RECHECK", error_type=b.error_type, error_slot="none",
                         span_start=-1, span_end=-1, original_value="", injected_value="", expected_nli=""))
    claims, _ = prepare(cfg, pd.DataFrame(rows), premises=(vc["nli_premise"],))
    v = apply(claims, "full", vc["nli_premise"], vc["nli_threshold"],
              enabled=tuple(vc["rules"]))
    ok = v.groupby("sample_id").verdict.agg(lambda s: bool((s == "SUPPORTED").all()))
    key = {f"{sid}~{i}": (sid, text) for i, (sid, text) in enumerate(uniq.itertuples(index=False))}
    status = {key[k]: ("accepted" if val else "human_review") for k, val in ok.items()}
    # an empty output (every claim deleted) has no claims to verify -> cannot be auto-accepted
    return pd.Series([status.get((s, o), "human_review") for s, o in zip(df.sample_id, df.output)], index=df.index)


def summarise(df: pd.DataFrame) -> pd.DataFrame:
    out = {}
    for name, g in df.groupby("system", sort=False):
        err, cor = g[g.label == "ERROR"], g[g.label == "CORRECT"]
        acc = g[g.final == "accepted"]
        out[name] = {
            "n": len(g),
            "error_rate_%": 100 * (g.outcome == "erroneous").mean(),
            "fixed_complete_%(ERROR rows)": 100 * (err.outcome == "complete").mean(),
            "faithful_%(ERROR rows)": 100 * err.outcome.isin(["complete", "lossy"]).mean(),
            "empty_%": 100 * (g.outcome == "empty").mean(),
            "correct_untouched_%(CORRECT rows)": 100 * (cor.output == cor.candidate).mean(),
            "new_errors_%(CORRECT rows)": 100 * (cor.outcome == "erroneous").mean(),
            "keyfact_retention_%": g.keyfact_retention.mean(),
            "sim_to_reference_%": g.sim_to_reference.mean(),
            "chars_changed_%": g.chars_changed.mean(),
            "auto_accepted_%": 100 * (g.final == "accepted").mean(),
            "faithful_among_accepted_%": 100 * acc.outcome.isin(["complete", "lossy"]).mean() if len(acc) else float("nan"),
        }
    return pd.DataFrame(out).T


def main() -> None:
    cfg = load_config()
    set_seed(cfg["seed"])
    vc = cfg["verification"]
    articles, errors = load_articles(), load_errors()
    dev_art = get_split(articles, "dev")

    claims, safe = prepare(cfg, premises=(vc["nli_premise"],))
    verdicts = apply(claims, "full", vc["nli_premise"], vc["nli_threshold"], enabled=tuple(vc["rules"]))
    safe_union = safe | build_safe_vocab(dev_art["text"].tolist(), dev_art["key_facts"].tolist())

    df = run_systems(verdicts, errors, safe, safe_union)
    df = add_content_metrics(df, articles)
    df["final"] = recheck(df, errors, cfg)

    test, dev = df[df.split == "test"], df[df.split == "dev"]
    main_test, main_dev = summarise(test), summarise(dev)
    sel = test[test.system.isin(["selective", "selective_oracle", "no_repair"])]
    by_type = (sel.assign(complete=sel.outcome == "complete", faithful=sel.outcome.isin(["complete", "lossy"]))
               .groupby(["system", "error_type"])[["complete", "faithful"]].mean().mul(100).round(1)
               .unstack("system").reindex(ERROR_ORDER))
    by_lang = pd.concat({lang: summarise(g) for lang, g in test.groupby("language")})
    s_test = test[test.system == "selective"]
    actions = (s_test.explode("actions").dropna(subset=["actions"])
               .groupby(["error_type", "actions"]).size().unstack(fill_value=0).reindex(ERROR_ORDER).fillna(0).astype(int))
    outcome_tab = pd.crosstab([test.system, test.label], test.outcome)

    out = ROOT / cfg["paths"]["results"] / "repair" / f"run_{timestamp()}"
    out.mkdir(parents=True, exist_ok=True)
    df.to_json(out / "repairs_all.jsonl", orient="records", lines=True, force_ascii=False)
    for name, t in [("test_main", main_test), ("dev_main", main_dev), ("test_by_error_type", by_type),
                    ("test_by_language", by_lang), ("test_selective_actions", actions), ("test_outcomes", outcome_tab)]:
        t.to_csv(out / f"{name}.csv", encoding="utf-8")
    (out / "config.json").write_text(json.dumps({"timestamp": timestamp(), "systems": SYSTEMS, "config": cfg,
                                                 "safe_vocab_sizes": [len(safe), len(safe_union)]},
                                                indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Repair + re-check results\n", "## TEST\n", md_table(main_test), "\n## DEV\n", md_table(main_dev),
          "\n## TEST by error type (complete / faithful %)\n", md_table(by_type),
          "\n## TEST by language\n", md_table(by_lang), "\n## TEST selective: actions by error type\n",
          md_table(actions, 0), "\n## TEST outcomes\n", md_table(outcome_tab, 0)]
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pd.set_option("display.width", 250)
    pd.set_option("display.precision", 1)
    for title, t in [("TEST main", main_test), ("DEV main", main_dev), ("TEST by error type", by_type),
                     ("TEST by language", by_lang), ("TEST selective actions", actions), ("TEST outcomes", outcome_tab)]:
        print(f"\n{title}\n{t.to_string()}")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
