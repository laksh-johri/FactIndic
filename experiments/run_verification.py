"""Step 4 experiment: claim verification (NLI + rules) and the decision rule.

Pipeline per candidate summary (all 512 rows):
  clause decomposition (Step 2) -> top-3 evidence, lexical+norm (Step 3)
  -> rule checks (numbers, dates, negation, entities) -> NLI on 2 premise variants
  -> decision rule with threshold tau -> summary flagged if any claim is not SUPPORTED.

Tuning on DEV only (pre-registered, written before looking at any dev/test numbers):
  search  premise in {concat (top-3 sentences in source order), top1}, tau in {0.50,...,0.95}
  select  1) highest summary-level balanced accuracy  2) lowest REVIEW rate
          3) premise 'concat' before 'top1'           4) lowest tau
  nli_only is tuned the same way (fair ablation); rules_only has no parameters.
Report on TEST.

Run:  python -m experiments.run_verification
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import get_split, load_articles, load_errors  # noqa: E402
from src.decompose import claims_overlapping, decompose  # noqa: E402
from src.nli import NLIModel  # noqa: E402
from src.retrieve import Retriever  # noqa: E402
from src.rules import RuleResult, build_safe_vocab, run_rules  # noqa: E402
from src.verify import decide  # noqa: E402

TAUS = [round(t, 2) for t in np.arange(0.50, 0.951, 0.05)]
PREMISES = ["concat", "top1"]
RULES = ("numbers", "dates", "negation", "entities")
ERROR_ORDER = ["number_swap", "date_swap", "entity_swap", "negation", "unsupported_addition"]


# ---------------------------------------------------------------------------
def prepare(cfg: dict) -> tuple[pd.DataFrame, set[str]]:
    articles, errors = load_articles(), load_errors()
    dev_art = get_split(articles, "dev")
    safe = build_safe_vocab(dev_art["summary"].tolist(), dev_art["key_facts"].tolist())
    art = articles.set_index("article_id")
    retriever = Retriever()
    method = cfg["decomposition"]["method"]

    recs, pairs = [], []
    for r in errors.itertuples():
        claims = decompose(r.candidate_summary, method, prefix=r.sample_id)
        err_ids = ({c.claim_id for c in claims_overlapping(claims, r.span_start, r.span_end)}
                   if r.label == "ERROR" else set())
        evs = retriever.retrieve_many([c.text for c in claims], r.source_text)
        for c, ev in zip(claims, evs):
            ev_texts = [e.text for e in ev]
            concat = " ".join(e.text for e in sorted(ev, key=lambda e: e.sent_idx))
            rules = run_rules(c.text, ev_texts, safe)
            is_err = c.claim_id in err_ids
            expected = ("UNSUPPORTED" if r.error_type == "unsupported_addition" else "CONTRADICTED") if is_err \
                else "SUPPORTED"
            recs.append(dict(
                sample_id=r.sample_id, article_id=r.article_id, split=r.split, language=r.language,
                domain=r.domain, label=r.label, error_type=r.error_type,
                digits=art.loc[r.article_id, "source_digit_script"], noise=bool(art.loc[r.article_id, "source_spelling_noise"]),
                claim_id=c.claim_id, claim=c.text, claim_start=c.start, claim_end=c.end,
                is_error_claim=is_err, expected=expected,
                evidence=[e.to_dict() for e in ev], premise_concat=concat, premise_top1=ev_texts[0],
                rules={x.name: {"status": x.status, "reason": x.reason} for x in rules}))
            pairs += [(concat, c.text), (ev_texts[0], c.text)]

    nli = NLIModel(verbose=True)
    print(f"{len(recs)} claims from {errors.shape[0]} summaries; running NLI on {len(set(pairs))} unique pairs ...")
    probs = nli.predict(pairs)
    for i, rec in enumerate(recs):
        rec["nli_concat"], rec["nli_top1"] = probs[2 * i], probs[2 * i + 1]
    return pd.DataFrame(recs), safe


def rule_objs(rules: dict, enabled: tuple[str, ...]) -> list[RuleResult]:
    return [RuleResult(n, rules[n]["status"], rules[n]["reason"]) for n in enabled]


def apply(df: pd.DataFrame, mode: str, premise: str = "concat", tau: float = 0.5,
          enabled: tuple[str, ...] = RULES) -> pd.DataFrame:
    out = df.copy()
    v = [decide(row[f"nli_{premise}"], rule_objs(row["rules"], enabled), tau, mode)
         for row in df[["rules", f"nli_{premise}"]].to_dict("records")]
    out["verdict"] = [x.label for x in v]
    out["reason"] = [x.reason for x in v]
    return out


def summary_level(claims: pd.DataFrame) -> pd.DataFrame:
    g = claims.groupby("sample_id")
    s = g.agg(split=("split", "first"), language=("language", "first"), label=("label", "first"),
              error_type=("error_type", "first"), digits=("digits", "first"), noise=("noise", "first"),
              flagged=("verdict", lambda v: bool((v != "SUPPORTED").any())),
              n_claims=("verdict", "size"), n_review=("verdict", lambda v: int((v == "REVIEW").sum())))
    err = claims[claims.is_error_claim].groupby("sample_id")["verdict"].agg(lambda v: bool((v != "SUPPORTED").any()))
    other = claims[~claims.is_error_claim].groupby("sample_id")["verdict"].agg(lambda v: int((v != "SUPPORTED").sum()))
    s["error_claim_flagged"] = err.reindex(s.index)
    s["other_claims_flagged"] = other.reindex(s.index).fillna(0).astype(int)
    return s


def metrics(s: pd.DataFrame) -> dict:
    pos, neg = s[s.label == "ERROR"], s[s.label == "CORRECT"]
    tp, fn = int(pos.flagged.sum()), int((~pos.flagged).sum())
    fp, tn = int(neg.flagged.sum()), int((~neg.flagged).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    spec = tn / (tn + fp) if tn + fp else 0.0
    det = pos[pos.flagged]
    return {"n": len(s), "precision": 100 * prec, "recall": 100 * rec,
            "f1": 100 * (2 * prec * rec / (prec + rec) if prec + rec else 0.0),
            "specificity": 100 * spec, "balanced_acc": 100 * (rec + spec) / 2,
            "review_rate": 100 * s.n_review.sum() / s.n_claims.sum(),
            "loc_error_claim_flagged": 100 * det.error_claim_flagged.mean() if len(det) else float("nan"),
            "loc_exact": 100 * (det.error_claim_flagged & (det.other_claims_flagged == 0)).mean() if len(det) else float("nan")}


def by(s: pd.DataFrame, col: str) -> pd.DataFrame:
    return pd.DataFrame({k: metrics(g) for k, g in s.groupby(col)}).T


def per_type(s: pd.DataFrame) -> pd.Series:
    """Detection rate per error type (for 'none' = false-alarm rate on correct summaries)."""
    return (100 * s.groupby("error_type").flagged.mean()).reindex(["none"] + ERROR_ORDER)


def md_table(df: pd.DataFrame, digits: int = 1) -> str:
    d = df.reset_index()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    for row in d.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:.{digits}f}" if isinstance(v, (float, np.floating)) else str(v)
                                         for v in row) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
def tune(dev: pd.DataFrame, mode: str) -> tuple[dict, pd.DataFrame]:
    rows = []
    for p in PREMISES:
        for t in TAUS:
            m = metrics(summary_level(apply(dev, mode, p, t)))
            rows.append({"mode": mode, "premise": p, "tau": t, **m})
    grid = pd.DataFrame(rows)
    grid["premise_order"] = grid.premise.map({"concat": 0, "top1": 1})
    best = grid.sort_values(["balanced_acc", "review_rate", "premise_order", "tau"],
                            ascending=[False, True, True, True]).iloc[0]
    return {"premise": best.premise, "tau": float(best.tau)}, grid.drop(columns="premise_order")


def main() -> None:
    cfg = load_config()
    set_seed(cfg["seed"])
    claims, safe = prepare(cfg)
    dev, test = claims[claims.split == "dev"], claims[claims.split == "test"]

    best_full, grid_full = tune(dev, "full")
    best_nli, grid_nli = tune(dev, "nli_only")
    print(f"DEV-selected full system: {best_full}   |   DEV-selected NLI-only: {best_nli}")

    systems = {
        "rules_only": apply(test, "rules_only"),
        "nli_only": apply(test, "nli_only", **best_nli),
        "full (NLI + rules)": apply(test, "full", **best_full),
    }
    for r in RULES:   # leave-one-rule-out ablation of the full system
        systems[f"full - {r}"] = apply(test, "full", enabled=tuple(x for x in RULES if x != r), **best_full)
    sums = {k: summary_level(v) for k, v in systems.items()}
    main_tab = pd.DataFrame({k: metrics(s) for k, s in sums.items()}).T
    type_tab = pd.DataFrame({k: per_type(s) for k, s in sums.items()}).T

    full_c, full_s = systems["full (NLI + rules)"], sums["full (NLI + rules)"]
    lang_tab = by(full_s, "language")
    cond_tab = pd.DataFrame({f"{l}/{d}/{'noisy' if n else 'clean'}": metrics(g)
                             for (l, d, n), g in full_s.groupby(["language", "digits", "noise"])}).T
    confusion = pd.crosstab(full_c.expected, full_c.verdict, margins=True)
    # which component catches the error claim? (test, error claims only)
    ec = full_c[full_c.is_error_claim].copy()
    ec["rule_fail"] = ec.rules.map(lambda r: any(v["status"] == "fail" for v in r.values()))
    ec["nli_not_entail"] = ec[f"nli_{best_full['premise']}"].map(lambda p: p["entailment"] < best_full["tau"])
    catch = pd.crosstab(ec.error_type, [ec.rule_fail, ec.nli_not_entail]).reindex(ERROR_ORDER)
    catch.columns = [f"rule={'fail' if a else 'pass'}/nli={'non-ent' if b else 'ent'}" for a, b in catch.columns]
    rule_fail_rates = pd.DataFrame({r: full_c.groupby("is_error_claim").rules.apply(
        lambda s, r=r: 100 * np.mean([x[r]["status"] == "fail" for x in s])) for r in RULES}).T
    rule_fail_rates.columns = ["fail% on correct claims", "fail% on error claims"]

    # ---- save
    out = ROOT / cfg["paths"]["results"] / "verification" / f"run_{timestamp()}"
    out.mkdir(parents=True, exist_ok=True)
    claims.to_json(out / "claims_all_raw.jsonl", orient="records", lines=True, force_ascii=False)
    full_c.drop(columns=["premise_concat", "premise_top1"]).to_json(
        out / "test_full_system_claims.jsonl", orient="records", lines=True, force_ascii=False)
    pd.concat([grid_full, grid_nli]).to_csv(out / "dev_grid.csv", index=False, encoding="utf-8")
    for name, t in [("test_main", main_tab), ("test_detection_by_error_type", type_tab), ("test_full_by_language", lang_tab),
                    ("test_full_by_condition", cond_tab), ("test_full_claim_confusion", confusion),
                    ("test_full_which_component_catches", catch), ("test_rule_fail_rates", rule_fail_rates)]:
        t.to_csv(out / f"{name}.csv", encoding="utf-8")
    (out / "config.json").write_text(json.dumps({"timestamp": timestamp(), "selected_full": best_full,
                                                 "selected_nli_only": best_nli, "safe_vocab_size": len(safe),
                                                 "config": cfg}, indent=2, ensure_ascii=False), encoding="utf-8")
    sel = grid_full[(grid_full.premise == best_full["premise"])].set_index("tau")
    md = ["# Verification results\n", f"DEV-selected full system: `{best_full}`; NLI-only: `{best_nli}`\n",
          "## DEV grid (full system, selected premise)\n", md_table(sel[["balanced_acc", "recall", "specificity", "review_rate"]]),
          "\n## TEST – summary-level detection\n", md_table(main_tab),
          "\n## TEST – detection rate by error type (none = false-alarm rate)\n", md_table(type_tab),
          "\n## TEST – full system by language\n", md_table(lang_tab),
          "\n## TEST – full system by source condition\n", md_table(cond_tab),
          "\n## TEST – claim-level confusion (expected x predicted)\n", md_table(confusion, 0),
          "\n## TEST – which component flags the error claim\n", md_table(catch, 0),
          "\n## TEST – rule failure rates\n", md_table(rule_fail_rates)]
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pd.set_option("display.width", 220)
    pd.set_option("display.precision", 1)
    print("\nDEV grid (full, selected premise)\n", sel[["balanced_acc", "recall", "specificity", "review_rate"]].to_string())
    for title, t in [("TEST main", main_tab), ("TEST by error type", type_tab), ("TEST full by language", lang_tab),
                     ("TEST full by condition", cond_tab), ("TEST claim confusion", confusion),
                     ("TEST which component catches error claim", catch), ("TEST rule fail rates", rule_fail_rates)]:
        print(f"\n{title}\n{t.to_string()}")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
