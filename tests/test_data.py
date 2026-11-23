"""Tests for src/data.py (loaders, get_split, validate)."""
import pandas as pd
import pytest

from src.data import ARTICLE_COLUMNS, ERROR_COLUMNS, get_split, load_articles, load_errors, validate


@pytest.fixture(scope="module")
def articles():
    return load_articles()


@pytest.fixture(scope="module")
def errors():
    return load_errors()


def test_articles_shape_and_columns(articles):
    assert len(articles) == 128
    assert set(ARTICLE_COLUMNS) <= set(articles.columns)
    assert articles["language"].value_counts().to_dict() == {"hindi": 64, "hinglish": 64}


def test_errors_shape_and_labels(errors):
    assert len(errors) == 512
    assert set(ERROR_COLUMNS) <= set(errors.columns)
    assert errors["label"].value_counts().to_dict() == {"ERROR": 384, "CORRECT": 128}
    assert set(errors["error_type"]) == {"none", "number_swap", "date_swap", "entity_swap",
                                         "negation", "unsupported_addition"}


def test_nested_fields_are_lists(articles):
    assert all(isinstance(c, list) and c for c in articles["gold_claims"])
    assert all(isinstance(k, list) and k for k in articles["key_facts"])


def test_get_split(articles):
    dev, test = get_split(articles, "dev"), get_split(articles, "test")
    assert len(dev) + len(test) == len(articles)
    assert set(dev["split"]) == {"dev"} and set(test["split"]) == {"test"}
    assert 0.25 <= len(dev) / len(articles) <= 0.35          # "dev ~= 30 %"
    assert list(dev.index) == list(range(len(dev)))          # index is reset


def test_get_split_rejects_bad_name(articles):
    with pytest.raises(ValueError):
        get_split(articles, "train")


def test_validate_passes_on_real_data(articles, errors):
    results = validate(articles, errors, verbose=False)
    assert all(r.passed for r in results), [r.name for r in results if not r.passed]


def test_validate_detects_wrong_span(articles, errors):
    bad = errors.copy()
    i = bad.index[bad["label"] == "ERROR"][0]
    bad.loc[i, "span_start"] += 1
    results = {r.name: r for r in validate(articles, bad, verbose=False)}
    r = results["ERROR rows: candidate[span] == injected_value"]
    assert not r.passed and bad.loc[i, "sample_id"] in r.failures


def test_validate_detects_modified_correct_row(articles, errors):
    bad = errors.copy()
    i = bad.index[bad["label"] == "CORRECT"][0]
    bad.loc[i, "candidate_summary"] += " extra"
    results = {r.name: r for r in validate(articles, bad, verbose=False)}
    assert not results["CORRECT rows: candidate == reference"].passed


def test_validate_detects_split_leak(articles, errors):
    leak = pd.concat([articles, articles.iloc[[0]].assign(split="test" if articles.iloc[0]["split"] == "dev" else "dev")])
    results = {r.name: r for r in validate(leak, errors, verbose=False)}
    assert not results["articles: no article_id in both dev and test"].passed


def test_validate_detects_missing_column(articles, errors):
    results = validate(articles.drop(columns=["key_facts"]), errors, verbose=False)
    assert not results[0].passed and "key_facts" in results[0].failures
