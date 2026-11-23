"""Step 2 experiment: compare claim-decomposition methods.

Metrics on REFERENCE summaries (128, one per article)
  n_claims            mean claims per summary
  facts_per_claim     mean number of key facts (person/org/loc/number/date strings) per claim
  atomic_rate         % claims with <= 1 key fact
  fact_coverage       % key facts that appear in at least one claim (information preserved)
  context_dep_rate    % claims that start with a pronoun / relative word (not self-contained)
Metrics on ERROR candidate summaries (384), span-aligned methods only
  localised           % rows where the injected span overlaps exactly ONE claim
  collateral_facts    mean number of other key facts sharing the erroneous claim
  touched_share       mean share (%) of summary characters inside the erroneous claim
                      (= how much text a claim-level repair would rewrite)

No parameters are tuned here, so dev and test are both reported (test = headline numbers).

Run:  python -m experiments.run_decomposition [--methods sentence clause gold llm]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import load_articles, load_errors  # noqa: E402
from src.decompose import claims_overlapping, decompose, is_context_dependent  # noqa: E402

SPAN_METHODS = {"sentence", "clause"}


def fact_values(key_facts: list[dict]) -> list[str]:
    return [kf["value"] for kf in key_facts]


def reference_rows(articles: pd.DataFrame, method: str) -> tuple[list[dict], list[dict]]:
    per_claim, per_summary = [], []
    for r in articles.itertuples():
        claims = decompose(r.summary, method, prefix=r.article_id, gold_claims=r.gold_claims)
        facts = fact_values(r.key_facts)
        for c in claims:
            n = sum(v in c.text for v in facts)
            per_claim.append({"method": method, "article_id": r.article_id, "split": r.split,
                              "language": r.language, **c.to_dict(), "n_facts": n,
                              "context_dependent": is_context_dependent(c.text)})
        covered = sum(any(v in c.text for c in claims) for v in facts)
        per_summary.append({"method": method, "article_id": r.article_id, "split": r.split,
                            "language": r.language, "n_claims": len(claims),
                            "facts_covered": covered, "facts_total": len(facts)})
    return per_claim, per_summary


def error_rows(errors: pd.DataFrame, articles: pd.DataFrame, method: str) -> list[dict]:
    facts_by_article = {r.article_id: fact_values(r.key_facts) for r in articles.itertuples()}
    out = []
    for r in errors[errors["label"] == "ERROR"].itertuples():
        claims = decompose(r.candidate_summary, method, prefix=r.sample_id)
        hit = claims_overlapping(claims, r.span_start, r.span_end)
        row = {"method": method, "sample_id": r.sample_id, "split": r.split, "language": r.language,
               "error_type": r.error_type, "n_overlapping": len(hit), "localised": len(hit) == 1}
        if len(hit) == 1:
            c = hit[0]
            row["error_claim"] = c.text
            row["collateral_facts"] = sum(v in c.text for v in facts_by_article[r.article_id])
            row["touched_share"] = 100 * (c.end - c.start) / len(r.candidate_summary)
        out.append(row)
    return out


def summarise(claims: pd.DataFrame, summaries: pd.DataFrame, errs: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    g_c = claims.groupby(by).agg(facts_per_claim=("n_facts", "mean"),
                                 atomic_rate=("n_facts", lambda s: 100 * (s <= 1).mean()),
                                 context_dep_rate=("context_dependent", lambda s: 100 * s.mean()))
    g_s = summaries.groupby(by).agg(n_claims=("n_claims", "mean"), covered=("facts_covered", "sum"),
                                    total=("facts_total", "sum"))
    g_s["fact_coverage"] = 100 * g_s.pop("covered") / g_s.pop("total")
    res = g_s.join(g_c)
    if len(errs):
        g_e = errs.groupby(by).agg(localised=("localised", lambda s: 100 * s.mean()),
                                   collateral_facts=("collateral_facts", "mean"),
                                   touched_share=("touched_share", "mean"))
        res = res.join(g_e)
    return res.round(2)


def md_table(df: pd.DataFrame) -> str:
    d = df.reset_index()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    for row in d.itertuples(index=False):
        lines.append("| " + " | ".join("–" if pd.isna(v) else (f"{v:.2f}" if isinstance(v, float) else str(v))
                                         for v in row) + " |")
    return "\n".join(lines)


def main() -> None:
    cfg = load_config()
    ap = argparse.ArgumentParser()
    ap.add_argument("--methods", nargs="+", default=["sentence", "clause", "gold"])
    args = ap.parse_args()
    set_seed(cfg["seed"])
    articles, errors = load_articles(), load_errors()

    all_claims, all_summ, all_err = [], [], []
    for m in args.methods:
        try:
            pc, ps = reference_rows(articles, m)
        except Exception as exc:  # e.g. llm without API key
            print(f"[skip] method={m}: {type(exc).__name__}: {exc}")
            continue
        all_claims += pc
        all_summ += ps
        if m in SPAN_METHODS:
            all_err += error_rows(errors, articles, m)
        print(f"[ok] method={m}: {len(ps)} reference summaries -> {len(pc)} claims")

    claims, summ = pd.DataFrame(all_claims), pd.DataFrame(all_summ)
    errs = pd.DataFrame(all_err)
    overall = summarise(claims, summ, errs, ["method", "split"])
    by_lang = summarise(claims[claims.split == "test"], summ[summ.split == "test"],
                        errs[errs.split == "test"] if len(errs) else errs, ["method", "language"])
    by_type = (errs[errs.split == "test"].groupby(["method", "error_type"])
               .agg(rows=("sample_id", "count"), localised=("localised", lambda s: 100 * s.mean()),
                    collateral_facts=("collateral_facts", "mean"), touched_share=("touched_share", "mean"))
               .round(2)) if len(errs) else pd.DataFrame()

    out = ROOT / cfg["paths"]["results"] / "decomposition" / f"run_{timestamp()}"
    out.mkdir(parents=True, exist_ok=True)
    claims.to_json(out / "claims_reference.jsonl", orient="records", lines=True, force_ascii=False)
    if len(errs):
        errs.to_json(out / "error_localisation.jsonl", orient="records", lines=True, force_ascii=False)
    overall.to_csv(out / "metrics_by_split.csv", encoding="utf-8")
    by_lang.to_csv(out / "metrics_test_by_language.csv", encoding="utf-8")
    by_type.to_csv(out / "localisation_test_by_error_type.csv", encoding="utf-8")
    (out / "config.json").write_text(json.dumps({"timestamp": timestamp(), "methods": args.methods,
                                                  "config": cfg}, indent=2), encoding="utf-8")
    md = ["# Claim decomposition results\n",
          "## Table A. All metrics by method and split\n", md_table(overall),
          "\n## Table B. Test split by language\n", md_table(by_lang),
          "\n## Table C. Error localisation on test, by error type\n", md_table(by_type) if len(by_type) else "–"]
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pd.set_option("display.width", 200)
    print("\nTable A. by method x split\n", overall.to_string())
    print("\nTable B. test, by language\n", by_lang.to_string())
    print("\nTable C. test, localisation by error type\n", by_type.to_string())
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
