"""Smoke tests for the Streamlit demo (app.py) with Streamlit's headless AppTest.

They use the NLI disk cache for benchmark examples, so they are skipped when the cache is missing.
"""
import pytest

from src.config import ROOT
from src.nli import NLIModel

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
pytestmark = pytest.mark.skipif(not NLIModel().cache_path.exists(), reason="needs the NLI cache")


def run_app(**widgets):
    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=120)
    at.run()
    for key, value in widgets.items():
        widget = at.selectbox(key=key) if key in ("etype", "sample") else at.segmented_control(key=key)
        widget.set_value(value)
        at.run()
    assert not at.exception, at.exception
    return at


def all_text(at) -> str:
    return " ".join(str(x.value) for x in [*at.markdown, *at.success, *at.warning, *at.caption])


def test_default_benchmark_example_runs():
    at = run_app()
    t = all_text(at)
    assert "Claims and verdicts" in t and "Impact &amp; metrics" in t
    assert "Gold outcome" in t
    assert any("fi-flow" in str(h.proto.body) for h in at.html)        # pipeline trace rendered


def test_number_swap_is_repaired_in_app():
    at = run_app(split="test", lang="hindi", etype="number_swap")
    at.selectbox(key="sample").set_value("hi013-E3")
    at.run()
    assert not at.exception
    t = all_text(at)
    assert "253" in t and "complete" in t          # 152 -> 253, identical to the reference


def test_own_text_mode_default_example():
    at = run_app(mode="Own text")
    t = all_text(at)
    assert "Prayagraj" in t and "Gold outcome" not in t


def test_benchmark_tab_reads_results():
    at = run_app()
    bodies = " ".join(str(h.proto.body) for h in at.html)
    assert "fi-meter" in bodies and "98.1%" in bodies               # exact-fix meter from results/
