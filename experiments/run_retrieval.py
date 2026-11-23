"""Step 3 experiment: evaluate evidence retrieval and tune the hybrid weight on DEV.

Claims: clause-level claims (Step 2) of the 128 REFERENCE summaries, plus the erroneous claim
of every ERROR row except unsupported additions (which have no evidence by definition).

Gold evidence (derived, synthetic-data specific):
  * a claim's facts = key-fact values it contains (for an error claim: the ORIGINAL value too)
  * relevant sentences for a fact = source sentences containing it (digits normalised)
  * a claim with no key fact is the polarity claim -> the source sentence built from the
    "{pol}" template sentence (index looked up in src.synth.DOMAINS)
Metrics per claim (ranked list of source sentences):
  full_recall@k : every fact of the claim is covered by the top-k sentences  (main metric)
  hit@k         : at least one relevant sentence in the top-k
  mrr           : 1 / rank of the first relevant sentence

Run:  python -m experiments.run_retrieval
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import load_articles, load_errors  # noqa: E402
from src.decompose import claims_overlapping, decompose  # noqa: E402
from src.retrieve import Retriever, split_source  # noqa: E402
from src.synth import DOMAINS  # noqa: E402
from src.textnorm import normalize_digits  # noqa: E402

KS = [1, 2, 3, 5]
ALPHAS = [round(a, 1) for a in np.arange(0, 1.01, 0.1)]


def contains(text: str, value: str) -> bool:
    """Substring match that does not let '50' match inside '2050' or '1 मई' inside '21 मई'."""
    pat = ("(?<!\\d)" if value[:1].isdigit() else "") + re.escape(value) + ("(?!\\d)" if value[-1:].isdigit() else "")
    return re.search(pat, normalize_digits(text)) is not None


def fact_type(kind_by_value: dict, facts: list[str]) -> str:
    kinds = {kind_by_value[f] for f in facts}
    if not facts:
        return "polarity"
    return "number" if "number" in kinds else "date" if "date" in kinds else "entity"


def build_items(articles: pd.DataFrame, errors: pd.DataFrame, method: str) -> list[dict]:
    items = []
    by_id = {r.article_id: r for r in articles.itertuples()}
    for a in articles.itertuples():
        sents = split_source(a.text)
        lang = "hi" if a.language == "hindi" else "hg"
        pol_idx = next(i for i, s in enumerate(DOMAINS[a.domain][lang]["source"]) if "{pol}" in s)
        kind = {kf["value"]: kf["type"] for kf in a.key_facts}
        for c in decompose(a.summary, method, prefix=a.article_id):
            facts = [v for v in kind if contains(c.text, v)]
            items.append(dict(item_id=c.claim_id, kind="reference", article_id=a.article_id, split=a.split,
                              language=a.language, digits=a.source_digit_script, noise=a.source_spelling_noise,
                              claim=c.text, facts=facts, ftype=fact_type(kind, facts), error_type="none",
                              pol_idx=pol_idx, sents=[s.text for s in sents], source=a.text))
    for e in errors[(errors.label == "ERROR") & (errors.error_type != "unsupported_addition")].itertuples():
        a = by_id[e.article_id]
        kind = {kf["value"]: kf["type"] for kf in a.key_facts}
        c = claims_overlapping(decompose(e.candidate_summary, method, prefix=e.sample_id), e.span_start, e.span_end)[0]
        facts = [v for v in kind if contains(c.text, v)]
        if e.error_slot in {"person", "org", "loc", "num", "date"}:
            facts.append(e.original_value)
        base = next(i for i in items if i["article_id"] == e.article_id)
        items.append(dict(item_id=c.claim_id, kind="error", article_id=e.article_id, split=e.split,
                          language=e.language, digits=a.source_digit_script, noise=a.source_spelling_noise,
                          claim=c.text, facts=facts, ftype=fact_type(kind, facts), error_type=e.error_type,
                          pol_idx=base["pol_idx"], sents=base["sents"], source=a.text))
    return items


def relevant_sets(item: dict) -> list[set[int]]:
    """One set of acceptable sentence indices per fact (or the polarity sentence)."""
    if not item["facts"]:
        return [{item["pol_idx"]}]
    return [{i for i, s in enumerate(item["sents"]) if contains(s, f)} for f in item["facts"]]


def build_pools(articles: pd.DataFrame) -> dict[str, tuple[list[str], int]]:
    """Stress test: candidate sentences = all sentences of the articles in the same
    language x domain x split cell. Returns article_id -> (pool sentences, offset of own article)."""
    pools = {}
    for _, cell in articles.groupby(["language", "domain", "split"]):
        sents, offsets = [], {}
        for a in cell.itertuples():
            offsets[a.article_id] = len(sents)
            sents += [s.text for s in split_source(a.text)]
        for aid, off in offsets.items():
            pools[aid] = (sents, off)
    return pools


def score_items(items: list[dict], retriever: Retriever, pools: dict | None = None) -> pd.DataFrame:
    """pools=None: candidates are the claim's own source sentences (the real pipeline setting)."""
    rows = []
    by_article: dict[str, list[dict]] = {}
    for it in items:
        by_article.setdefault((it["article_id"], it["kind"]), []).append(it)
    for (aid, _), group in by_article.items():
        cands, off = pools[aid] if pools else (group[0]["sents"], 0)
        scores = retriever.score([g["claim"] for g in group], cands)
        for it, row_scores in zip(group, scores):
            order = list(np.argsort(-row_scores, kind="stable"))
            rel = [{i + off for i in r} for r in relevant_sets(it)]
            union = set().union(*rel)
            first = next((r for r, i in enumerate(order, 1) if i in union), None)
            row = {k: it[k] for k in ("item_id", "kind", "article_id", "split", "language", "digits", "noise",
                                      "ftype", "error_type", "claim")}
            row.update(n_facts=len(it["facts"]), mrr=1 / first if first else 0.0, top1=cands[order[0]],
                       ranking=[int(i) - off for i in order[:5]], top1_score=float(row_scores[order[0]]))
            for k in KS:
                top = set(order[:k])
                row[f"full_recall@{k}"] = all(r & top for r in rel)
                row[f"hit@{k}"] = bool(union & top)
            rows.append(row)
    return pd.DataFrame(rows)


METRIC_COLS = [f"full_recall@{k}" for k in KS] + ["hit@1", "mrr"]


def agg(df: pd.DataFrame, by: list[str] | None = None) -> pd.DataFrame:
    f = {c: (c, "mean") for c in METRIC_COLS}
    f["n"] = ("item_id", "count")
    out = df.groupby(by).agg(**f) if by else df.agg({**{c: "mean" for c in METRIC_COLS}, "item_id": "count"}).to_frame().T
    out = out.rename(columns={"item_id": "n"})
    for c in METRIC_COLS:
        out[c] = (100 * out[c].astype(float)).round(1) if c != "mrr" else out[c].astype(float).round(3)
    return out


def md_table(df: pd.DataFrame) -> str:
    d = df.reset_index()
    lines = ["| " + " | ".join(map(str, d.columns)) + " |", "|" + "---|" * len(d.columns)]
    lines += ["| " + " | ".join(str(v) for v in row) + " |" for row in d.itertuples(index=False)]
    return "\n".join(lines)


def main() -> None:
    cfg = load_config()
    set_seed(cfg["seed"])
    articles, errors = load_articles(), load_errors()
    items = build_items(articles, errors, cfg["decomposition"]["method"])
    n_bad = sum(len(i["sents"]) != 7 for i in items)
    print(f"{len(items)} claims ({sum(i['kind'] == 'reference' for i in items)} reference, "
          f"{sum(i['kind'] == 'error' for i in items)} error); articles with !=7 source sentences: {n_bad}")

    configs = {f"lexical{'+norm' if n else ''}": dict(method="lexical", normalize_text=n) for n in (False, True)}
    configs.update({f"labse{'+norm' if n else ''}": dict(method="labse", normalize_text=n) for n in (False, True)})
    configs.update({f"hybrid+norm a={a}": dict(method="hybrid", normalize_text=True, alpha=a) for a in ALPHAS[1:-1]})

    from src.retrieve import Embedder
    emb = Embedder()
    pools = build_pools(articles)
    results, stress = {}, {}
    for name, kw in configs.items():
        r = Retriever(embedder=emb, **kw)
        results[name] = score_items(items, r).assign(config=name)
        stress[name] = score_items(items, r, pools).assign(config=name)
        print(f"[done] {name}")
    allres = pd.concat(results.values(), ignore_index=True)
    allstress = pd.concat(stress.values(), ignore_index=True)

    # ---- select on DEV. Pre-registered order of criteria:
    #   1) full_recall@k (own source)  2) MRR (own source)  3) full_recall@k in the pooled stress test
    #   4) simplicity (fewer components / no model download wins)
    k = cfg["retrieval"]["top_k"]
    simplicity = {name: i for i, name in enumerate(configs)}          # lexical < lexical+norm < labse < ...
    dev = agg(allres[allres.split == "dev"], ["config"])
    dev_stress = agg(allstress[allstress.split == "dev"], ["config"])
    dev[f"stress_full_recall@{k}"] = dev_stress[f"full_recall@{k}"]
    dev["stress_mrr"] = dev_stress["mrr"]
    dev["simplicity_rank"] = [simplicity[n] for n in dev.index]
    dev = dev.sort_values([f"full_recall@{k}", "mrr", f"stress_full_recall@{k}", "simplicity_rank"],
                          ascending=[False, False, False, True])
    best = dev.index[0]
    print("\nDEV selection table:\n", dev.to_string())
    print(f"\n==> selected on dev: {best}")

    test = allres[allres.split == "test"]
    main_names = list(dict.fromkeys(["lexical", "lexical+norm", "labse", "labse+norm", best, "hybrid+norm a=0.5"]))
    main_tab = agg(test[test.config.isin(main_names)], ["config", "kind"]).reindex(main_names, level=0)
    best_test = test[test.config == best]
    by_type = agg(best_test, ["kind", "ftype"])
    by_err = agg(best_test[best_test.kind == "error"], ["error_type"])
    by_cond = agg(best_test, ["language", "digits", "noise"])
    raw_vs_norm = agg(test[test.config.isin(["labse", "labse+norm"])], ["config", "digits"])
    tstress = allstress[allstress.split == "test"]
    stress_tab = agg(tstress[tstress.config.isin(main_names)], ["config", "kind"]).reindex(main_names, level=0)
    stress_by_type = agg(tstress[tstress.config.isin(main_names)], ["config", "ftype"]).reindex(main_names, level=0)

    out = ROOT / cfg["paths"]["results"] / "retrieval" / f"run_{timestamp()}"
    out.mkdir(parents=True, exist_ok=True)
    dev.to_csv(out / "dev_config_sweep.csv", encoding="utf-8")
    main_tab.to_csv(out / "test_main.csv", encoding="utf-8")
    by_type.to_csv(out / "test_best_by_claim_type.csv", encoding="utf-8")
    by_err.to_csv(out / "test_best_by_error_type.csv", encoding="utf-8")
    by_cond.to_csv(out / "test_best_by_condition.csv", encoding="utf-8")
    raw_vs_norm.to_csv(out / "test_labse_raw_vs_norm_by_digits.csv", encoding="utf-8")
    stress_tab.to_csv(out / "test_stress_main.csv", encoding="utf-8")
    stress_by_type.to_csv(out / "test_stress_by_claim_type.csv", encoding="utf-8")
    best_test.drop(columns=["config"]).to_json(out / "test_best_per_claim.jsonl", orient="records",
                                               lines=True, force_ascii=False)
    (out / "config.json").write_text(json.dumps({"timestamp": timestamp(), "selected": best,
                                                 "selected_kwargs": configs[best], "config": cfg},
                                                indent=2, ensure_ascii=False), encoding="utf-8")
    md = ["# Evidence retrieval results\n", f"Selected on dev: **{best}** (by full_recall@{k}, tie-break MRR)\n",
          "## Dev sweep\n", md_table(dev), "\n## Test – main comparison\n", md_table(main_tab),
          "\n## Test – selected config by claim type\n", md_table(by_type),
          "\n## Test – selected config, error claims by error type\n", md_table(by_err),
          "\n## Test – selected config by language / source condition\n", md_table(by_cond),
          "\n## Test – LaBSE raw vs normalised, by source digit script\n", md_table(raw_vs_norm),
          "\n## Test – STRESS (pooled same language x domain x split)\n", md_table(stress_tab),
          "\n## Test – STRESS by claim type\n", md_table(stress_by_type)]
    (out / "results.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    pd.set_option("display.width", 220)
    for title, t in [("TEST main", main_tab), ("TEST best by claim type", by_type),
                     ("TEST best error claims by error type", by_err), ("TEST best by condition", by_cond),
                     ("TEST labse raw vs norm by digits", raw_vs_norm), ("TEST STRESS main", stress_tab),
                     ("TEST STRESS by claim type", stress_by_type)]:
        print(f"\n{title}\n{t.to_string()}")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
