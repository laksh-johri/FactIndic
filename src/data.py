"""Data loading, split selection and integrity validation for the FactIndic benchmark."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from src.config import ROOT, load_config

ARTICLE_COLUMNS = [
    "article_id", "language", "script", "domain", "split", "title", "text", "summary",
    "gold_claims", "key_facts", "source_digit_script", "source_spelling_noise",
]
ERROR_COLUMNS = [
    "sample_id", "article_id", "language", "domain", "split", "source_text", "reference_summary",
    "candidate_summary", "label", "error_type", "error_slot", "span_start", "span_end",
    "original_value", "injected_value", "expected_nli",
]
VALID_SPLITS = ("dev", "test")


def _resolve(path: str | Path | None, key: str) -> Path:
    if path is not None:
        return Path(path)
    return ROOT / load_config()["data"][key]


def load_articles(path: str | Path | None = None) -> pd.DataFrame:
    """Load the article file (one JSON object per line) into a DataFrame."""
    return pd.read_json(_resolve(path, "articles"), lines=True, dtype=False)


def load_errors(path: str | Path | None = None) -> pd.DataFrame:
    """Load the error-injected summary file into a DataFrame."""
    return pd.read_json(_resolve(path, "errors"), lines=True, dtype=False)


def get_split(df: pd.DataFrame, split: str) -> pd.DataFrame:
    """Return only the rows of one split ('dev' or 'test'), with a fresh index."""
    if split not in VALID_SPLITS:
        raise ValueError(f"split must be one of {VALID_SPLITS}, got {split!r}")
    return df[df["split"] == split].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    failures: list = field(default_factory=list)


def _check_columns(df: pd.DataFrame, required: list[str], name: str) -> CheckResult:
    missing = [c for c in required if c not in df.columns]
    return CheckResult(f"{name}: required columns present", not missing,
                       f"missing={missing}" if missing else f"{len(required)} columns ok", missing)


def validate(articles: pd.DataFrame | None = None, errors: pd.DataFrame | None = None,
             verbose: bool = True) -> list[CheckResult]:
    """Run integrity checks and print a PASS/FAIL report. Returns the list of results."""
    articles = load_articles() if articles is None else articles
    errors = load_errors() if errors is None else errors
    results = [_check_columns(articles, ARTICLE_COLUMNS, "articles"),
               _check_columns(errors, ERROR_COLUMNS, "errors")]

    if all(r.passed for r in results):
        # 1) every ERROR row: candidate[span_start:span_end] == injected_value
        err = errors[errors["label"] == "ERROR"]
        bad = [r.sample_id for r in err.itertuples()
               if r.candidate_summary[r.span_start:r.span_end] != r.injected_value]
        results.append(CheckResult("ERROR rows: candidate[span] == injected_value", not bad,
                                   f"{len(err) - len(bad)}/{len(err)} ok", bad))

        # 2) every CORRECT row: candidate == reference
        cor = errors[errors["label"] == "CORRECT"]
        bad = cor.loc[cor["candidate_summary"] != cor["reference_summary"], "sample_id"].tolist()
        results.append(CheckResult("CORRECT rows: candidate == reference", not bad,
                                   f"{len(cor) - len(bad)}/{len(cor)} ok", bad))

        # 3) no article in both dev and test (in either file)
        for name, df in [("articles", articles), ("errors", errors)]:
            dev_ids = set(df.loc[df["split"] == "dev", "article_id"])
            test_ids = set(df.loc[df["split"] == "test", "article_id"])
            overlap = sorted(dev_ids & test_ids)
            results.append(CheckResult(f"{name}: no article_id in both dev and test", not overlap,
                                       f"dev={len(dev_ids)} test={len(test_ids)} overlap={len(overlap)}",
                                       overlap))

        # 4) extra sanity checks (cheap, catch silent corruption)
        bad_split = sorted(set(articles["split"]) - set(VALID_SPLITS))
        results.append(CheckResult("articles: split values are dev/test", not bad_split,
                                   f"values={sorted(set(articles['split']))}", bad_split))
        dup = errors["sample_id"][errors["sample_id"].duplicated()].tolist()
        results.append(CheckResult("errors: sample_id unique", not dup, f"{len(dup)} duplicates", dup))
        art_split = dict(zip(articles["article_id"], articles["split"]))
        bad = [r.sample_id for r in errors.itertuples() if art_split.get(r.article_id) != r.split]
        results.append(CheckResult("errors: split matches parent article", not bad,
                                   f"{len(errors) - len(bad)}/{len(errors)} ok", bad))

    if verbose:
        print("=" * 72)
        print("FactIndic data validation report")
        print("=" * 72)
        for r in results:
            print(f"[{'PASS' if r.passed else 'FAIL'}] {r.name:<55} {r.detail}")
            if r.failures:
                print(f"        first failures: {r.failures[:5]}")
        n_pass = sum(r.passed for r in results)
        print("-" * 72)
        print(f"{n_pass}/{len(results)} checks passed -> {'ALL PASS' if n_pass == len(results) else 'FAILED'}")
    return results


if __name__ == "__main__":
    validate()
