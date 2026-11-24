"""Tests for src/render.py (HTML helpers of the demo)."""
from src.render import badge, diff_html, highlight_claims


def test_highlight_keeps_text_and_numbers_claims():
    s = "टीम ने 152 रन बनाए। मैच रुका।"
    claims = [{"start": 0, "end": 19, "verdict": "CONTRADICTED", "reason": "numbers: 152"},
              {"start": 20, "end": 29, "verdict": "SUPPORTED", "reason": "ok"}]
    h = highlight_claims(s, claims)
    assert "टीम ने 152 रन बनाए।" in h and "#1" in h and "#2" in h and "rgba(218,54,51" in h


def test_user_text_is_escaped():
    s = "<script>alert(1)</script> done."
    h = highlight_claims(s, [{"start": 0, "end": len(s), "verdict": "REVIEW", "reason": '"x" <b>'}])
    assert "<script>" not in h and "&lt;script&gt;" in h and '"x"' not in h
    assert "<script>" not in diff_html(s, "ok") and "<b>" not in badge("<b>")


def test_diff_marks_replacement_and_deletion():
    d = diff_html("टीम ने 152 रन बनाए। मैच रुका।", "टीम ने 253 रन बनाए।")
    assert "<del" in d and "152" in d and "<ins" in d and "253" in d and "मैच" in d
    assert "<del" not in diff_html("same text", "same text")


def test_segment_colors_fill_proportionally():
    from src.render import segment_colors
    c = segment_colors(50)
    assert len(c) == 20 and sum(x != "#E6E6E9" for x in c) == 10 and c[0].endswith("1.00)")
    assert all(x == "#E6E6E9" for x in segment_colors(0)) and "#E6E6E9" not in segment_colors(100)


def test_flow_and_meter_escape_text():
    from src.render import flow_html, meter_html, section_html
    f = flow_html([{"chip": "a", "text": "<b>x</b>"}, {"chip": "b", "text": "y", "check": "ok"}])
    assert "&lt;b&gt;" in f and f.count('class="fi-node"') == 2 and f.count("fi-wire h") == 1
    assert "38%" in meter_html(38, "faster") and "&amp;" in section_html(1, "Impact & metrics")
