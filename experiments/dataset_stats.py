"""Produce the dataset-description tables + figure for the paper.

Outputs (results/dataset_stats/):
  01_articles_lang_domain_split.csv   02_errors_type_lang_split.csv
  03_length_by_language.csv           04_gold_claims.csv
  05_source_conditions.csv            06_key_fact_types.csv
  dataset_stats.md                    error_types_by_language.png
  run_meta.json  (timestamp, config, data-file hashes)

Run:  python -m experiments.dataset_stats
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from src.config import load_config, set_seed, timestamp  # noqa: E402
from src.data import load_articles, load_errors  # noqa: E402

OUT = ROOT / "results" / "dataset_stats"
ERROR_ORDER = ["number_swap", "date_swap", "entity_swap", "negation", "unsupported_addition"]
LANG_COLORS = {"hindi": "#2a78d6", "hinglish": "#eb6834"}   # validated categorical slots 1, 2
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"


def words(s: str) -> int:
    return len(s.split())


def md_table(df: pd.DataFrame, index: bool = True) -> str:
    d = df.reset_index() if index else df
    cols = [str(c) for c in d.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join(["---"] * len(cols)) + "|"]
    for row in d.itertuples(index=False):
        lines.append("| " + " | ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in row) + " |")
    return "\n".join(lines)


def table_articles(a: pd.DataFrame) -> pd.DataFrame:
    t = pd.crosstab([a["language"], a["domain"]], a["split"], margins=True, margins_name="total")
    return t[["dev", "test", "total"]]


def table_errors(e: pd.DataFrame) -> pd.DataFrame:
    t = pd.crosstab(e["error_type"], [e["language"], e["split"]], margins=True, margins_name="total")
    t = t.reindex(["none"] + ERROR_ORDER + ["total"])
    t.columns = [c if isinstance(c, str) else "_".join(x for x in c if x) for c in t.columns]
    return t


def table_lengths(a: pd.DataFrame) -> pd.DataFrame:
    d = a.assign(article_words=a["text"].map(words), article_chars=a["text"].str.len(),
                 summary_words=a["summary"].map(words), summary_chars=a["summary"].str.len())
    cols = ["article_words", "article_chars", "summary_words", "summary_chars"]
    t = d.groupby("language")[cols].mean()
    t.loc["all"] = d[cols].mean()
    t["compression_ratio_words"] = t["article_words"] / t["summary_words"]
    return t.round(1)


def table_claims(a: pd.DataFrame) -> pd.DataFrame:
    n = a["gold_claims"].map(len)
    g = n.groupby(a["language"]).agg(["mean", "min", "max", "sum"])
    g.loc["all"] = [n.mean(), n.min(), n.max(), n.sum()]
    g.columns = ["mean_claims", "min_claims", "max_claims", "total_claims"]
    return g.astype({"min_claims": int, "max_claims": int, "total_claims": int}).round(2)


def table_conditions(a: pd.DataFrame) -> pd.DataFrame:
    g = a.groupby("language").agg(
        articles=("article_id", "count"),
        devanagari_digits=("source_digit_script", lambda s: int((s == "devanagari").sum())),
        spelling_noise=("source_spelling_noise", lambda s: int(s.sum())),
    )
    g.loc["all"] = g.sum()
    return g


def table_key_facts(a: pd.DataFrame) -> pd.DataFrame:
    rows = [{"language": r.language, "type": kf["type"]} for r in a.itertuples() for kf in r.key_facts]
    kf = pd.DataFrame(rows)
    t = pd.crosstab(kf["type"], kf["language"], margins=True, margins_name="total")
    t["share_%"] = (100 * t["total"] / t.loc["total", "total"]).round(1)
    return t


def plot_errors(e: pd.DataFrame, path: Path) -> None:
    err = e[e["label"] == "ERROR"]
    counts = pd.crosstab(err["error_type"], err["language"]).reindex(ERROR_ORDER)
    langs = list(counts.columns)
    fig, ax = plt.subplots(figsize=(7.2, 3.8), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    width, gap = 0.36, 0.03                       # small surface gap between adjacent bars
    for i, lang in enumerate(langs):
        for j, v in enumerate(counts[lang]):
            x = j + (i - (len(langs) - 1) / 2) * (width + gap) - width / 2
            ax.add_patch(FancyBboxPatch((x, 0), width, v, boxstyle="round,pad=0,rounding_size=0.04",
                                        mutation_aspect=12, linewidth=0, facecolor=LANG_COLORS[lang],
                                        label=lang.capitalize() if j == 0 else None))
    ax.set_xlim(-0.6, len(ERROR_ORDER) - 0.4)
    ax.set_ylim(0, counts.values.max() * 1.18)
    ax.set_xticks(range(len(ERROR_ORDER)))
    ax.set_xticklabels([t.replace("_", " ") for t in ERROR_ORDER], color=INK2, fontsize=9)
    ax.set_ylabel("Error rows (dev + test)", color=INK2, fontsize=9)
    ax.tick_params(axis="y", colors=INK2, labelsize=8, length=0)
    ax.tick_params(axis="x", length=0)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for s in ["top", "right", "left"]:
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(INK2)
    ax.set_title("Injected error types by language", loc="left", color=INK, fontsize=11)
    ax.legend(frameon=False, fontsize=9, loc="upper right", ncols=2, labelcolor=INK2)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    cfg = load_config()
    set_seed(cfg["seed"])
    OUT.mkdir(parents=True, exist_ok=True)
    a, e = load_articles(), load_errors()

    tables = {
        "01_articles_lang_domain_split": ("Table 1. Articles per language x domain x split", table_articles(a)),
        "02_errors_type_lang_split": ("Table 2. Summary rows per error type x language x split", table_errors(e)),
        "03_length_by_language": ("Table 3. Mean article and summary length", table_lengths(a)),
        "04_gold_claims": ("Table 4. Gold atomic claims per reference summary", table_claims(a)),
        "05_source_conditions": ("Table 5. Source-side robustness conditions (article counts)", table_conditions(a)),
        "06_key_fact_types": ("Table 6. Key-fact type distribution", table_key_facts(a)),
    }
    md = [f"# FactIndic dataset statistics\n\nGenerated {timestamp()} from "
          f"`{cfg['data']['articles']}` ({len(a)} articles) and `{cfg['data']['errors']}` ({len(e)} rows).\n"]
    for name, (title, df) in tables.items():
        df.to_csv(OUT / f"{name}.csv", encoding="utf-8")
        md.append(f"## {title}\n\n{md_table(df)}\n")
        print(f"\n{title}\n{df.to_string()}")
    md.append("## Figure 1. Injected error types by language\n\n![error types](error_types_by_language.png)\n")
    (OUT / "dataset_stats.md").write_text("\n".join(md), encoding="utf-8")
    plot_errors(e, OUT / "error_types_by_language.png")

    meta = {"timestamp": timestamp(), "config": cfg,
            "data_sha256": {k: sha256(ROOT / v) for k, v in cfg["data"].items()}}
    (OUT / "run_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"\nSaved {len(tables)} CSV tables, dataset_stats.md, figure and run_meta.json to {OUT}")


if __name__ == "__main__":
    main()
