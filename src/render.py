"""Small HTML helpers for the demo: colour claims by verdict, show a word-level diff.

All user text is HTML-escaped (the demo accepts free text). Colours are semi-transparent so they
read on both Streamlit's light and dark themes.
"""
from __future__ import annotations

import difflib
import html
import re

VERDICT_STYLE = {
    "SUPPORTED": ("rgba(46,160,67,0.25)", "✅"),
    "CONTRADICTED": ("rgba(218,54,51,0.30)", "❌"),
    "UNSUPPORTED": ("rgba(219,154,4,0.30)", "⚠️"),
    "REVIEW": ("rgba(110,118,129,0.30)", "👁️"),
}
RULE_ICON = {"pass": "✅ pass", "fail": "❌ fail", "na": "➖ n/a"}


def badge(verdict: str) -> str:
    bg, icon = VERDICT_STYLE.get(verdict, ("transparent", ""))
    return (f'<span style="background:{bg};padding:1px 6px;border-radius:4px;font-size:0.85em">'
            f"{icon} {html.escape(verdict)}</span>")


def highlight_claims(summary: str, claims: list) -> str:
    """Summary text with each claim's span coloured by its verdict and numbered (#1, #2, ...).
    `claims`: objects or dicts with start, end, verdict, reason."""
    get = (lambda c, k: c[k]) if claims and isinstance(claims[0], dict) else getattr
    parts, pos = [], 0
    for n, c in enumerate(sorted(claims, key=lambda c: get(c, "start")), 1):
        s, e, v = get(c, "start"), get(c, "end"), get(c, "verdict")
        if s < pos:                                      # overlapping spans never happen; be safe
            continue
        bg, _ = VERDICT_STYLE.get(v, ("transparent", ""))
        parts.append(html.escape(summary[pos:s]))
        parts.append(f'<span title="{html.escape(v + ": " + get(c, "reason"), quote=True)}" '
                     f'style="background:{bg};border-radius:4px;padding:2px 2px">{html.escape(summary[s:e])}'
                     f'<sup style="font-size:0.7em;opacity:0.8">#{n}</sup></span>')
        pos = e
    parts.append(html.escape(summary[pos:]))
    return f'<div style="line-height:2.0;font-size:1.05em">{"".join(parts)}</div>'


def diff_html(old: str, new: str) -> str:
    """Word-level diff: removed words struck through in red, inserted words in green."""
    a, b = re.findall(r"\S+|\s+", old), re.findall(r"\S+|\s+", new)
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(html.escape("".join(a[i1:i2])))
            continue
        if i2 > i1 and "".join(a[i1:i2]).strip():
            out.append('<del style="background:rgba(218,54,51,0.30);text-decoration:line-through">'
                       f'{html.escape("".join(a[i1:i2]))}</del>')
        if j2 > j1 and "".join(b[j1:j2]).strip():
            out.append(f'<ins style="background:rgba(46,160,67,0.30);text-decoration:none">'
                       f'{html.escape("".join(b[j1:j2]))}</ins>')
        elif j2 > j1:
            out.append(html.escape("".join(b[j1:j2])))
    return f'<div style="line-height:2.0;font-size:1.05em">{"".join(out)}</div>'
