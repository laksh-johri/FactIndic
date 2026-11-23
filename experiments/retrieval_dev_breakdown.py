"""Step 3b: DEV-only comparison of LaBSE vs lexical+norm per language (and noisy vs clean
Hinglish), then apply the pre-registered selection rule per language.

Rule (fixed in Step 3, applied within each language on DEV):
  1) full_recall@3 (own source)  2) MRR (own source)  3) full_recall@3 in the pooled stress test
  4) simplicity (lexical+norm < labse: no model needed)
Decision:
  same winner in Hindi AND Hinglish -> that winner becomes the default retriever
  otherwise                         -> hybrid = mean of min-max-normalised LaBSE and lexical scores
The loser (and the hybrid) are kept as reported baselines.

Run:  python -m experiments.retrieval_dev_breakdown
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402

from experiments.run_retrieval import agg, build_items, build_pools, md_table, score_items  # noqa: E402
from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import load_articles, load_errors  # noqa: E402
from src.retrieve import Embedder, Retriever  # noqa: E402

CANDIDATES = {
    "lexical+norm": dict(method="lexical", normalize_text=True),
    "labse": dict(method="labse", normalize_text=False),
}
REPORTED = {
    **CANDIDATES,
    "labse+norm": dict(method="labse", normalize_text=True),
    "hybrid-minmax+norm": dict(method="hybrid", normalize_text=True, alpha=0.5, score_norm="minmax"),
}
SIMPLICITY = {"lexical+norm": 0, "labse": 1}
COLS = ["full_recall@1", "full_recall@2", "full_recall@3", "full_recall@5", "hit@1", "mrr", "n"]


def main() -> None:
    cfg = load_config()
    set_seed(cfg["seed"])
    k = cfg["retrieval"]["top_k"]
    articles, errors = load_articles(), load_errors()
    dev_art = articles[articles.split == "dev"]
    items = [i for i in build_items(articles, errors, cfg["decomposition"]["method"]) if i["split"] == "dev"]
    pools = build_pools(dev_art)
    emb = Embedder()

    own, stress = [], []
    for name, kw in REPORTED.items():
        r = Retriever(embedder=emb, **kw)
        own.append(score_items(items, r).assign(config=name))
        stress.append(score_items(items, r, pools).assign(config=name))
    own, stress = pd.concat(own), pd.concat(stress)
    own["group"] = own.language
    stress["group"] = stress.language
    hg_noise = own[own.language == "hinglish"].assign(
        group=lambda d: d.noise.map({True: "hinglish-noisy", False: "hinglish-clean"}))
    hg_noise_s = stress[stress.language == "hinglish"].assign(
        group=lambda d: d.noise.map({True: "hinglish-noisy", False: "hinglish-clean"}))

    by_lang = agg(own, ["group", "config"])[COLS]
    by_lang[f"stress_full_recall@{k}"] = agg(stress, ["group", "config"])[f"full_recall@{k}"]
    by_lang["stress_mrr"] = agg(stress, ["group", "config"])["mrr"]
    by_noise = agg(hg_noise, ["group", "config"])[COLS]
    by_noise[f"stress_full_recall@{k}"] = agg(hg_noise_s, ["group", "config"])[f"full_recall@{k}"]
    by_noise["stress_mrr"] = agg(hg_noise_s, ["group", "config"])["mrr"]

    # ---- pre-registered rule, per language, LaBSE vs lexical+norm only
    winners = {}
    for lang in ("hindi", "hinglish"):
        t = by_lang.loc[lang].loc[list(CANDIDATES)].copy()
        t["simplicity"] = [SIMPLICITY[n] for n in t.index]
        t = t.sort_values([f"full_recall@{k}", "mrr", f"stress_full_recall@{k}", "simplicity"],
                          ascending=[False, False, False, True])
        winners[lang] = t.index[0]
        decisive = next((c for c in [f"full_recall@{k}", "mrr", f"stress_full_recall@{k}", "simplicity"]
                         if t.iloc[0][c] != t.iloc[1][c]), "none (full tie)")
        winners[lang + "_decided_by"] = decisive
    decision = winners["hindi"] if winners["hindi"] == winners["hinglish"] else "hybrid-minmax+norm"
    winners["decision"] = decision
    winners["decision_kwargs"] = REPORTED[decision]

    out = ROOT / cfg["paths"]["results"] / "retrieval" / f"dev_breakdown_{timestamp()}"
    out.mkdir(parents=True, exist_ok=True)
    by_lang.to_csv(out / "dev_by_language.csv", encoding="utf-8")
    by_noise.to_csv(out / "dev_hinglish_noisy_vs_clean.csv", encoding="utf-8")
    (out / "decision.json").write_text(json.dumps({"timestamp": timestamp(), **winners}, indent=2), encoding="utf-8")
    (out / "results.md").write_text(
        "# DEV retrieval breakdown\n\n## By language\n\n" + md_table(by_lang)
        + "\n\n## Hinglish noisy vs clean\n\n" + md_table(by_noise)
        + f"\n\n## Decision\n\n```\n{json.dumps(winners, indent=2)}\n```\n", encoding="utf-8")

    pd.set_option("display.width", 220)
    print("DEV by language\n", by_lang.to_string())
    print("\nDEV Hinglish noisy vs clean\n", by_noise.to_string())
    print("\nDecision:", json.dumps(winners, indent=2))
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
