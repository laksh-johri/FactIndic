"""HTML helpers for the demo: claim highlighting, word-level diff, and the design components
(numbered section headers, segmented meters, KPI cards, pipeline flow).

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
            out.append('<del style="background:rgba(218,54,51,0.30);text-decoration:line-through;margin-right:3px">'
                       f'{html.escape("".join(a[i1:i2]))}</del>')
        if j2 > j1 and "".join(b[j1:j2]).strip():
            out.append(f'<ins style="background:rgba(46,160,67,0.30);text-decoration:none">'
                       f'{html.escape("".join(b[j1:j2]))}</ins>')
        elif j2 > j1:
            out.append(html.escape("".join(b[j1:j2])))
    return f'<div style="line-height:2.0;font-size:1.05em">{"".join(out)}</div>'


# ---------------------------------------------------------------------------
# Design components (classes styled in assets/factindic.css)
# ---------------------------------------------------------------------------

ACCENT = (232, 64, 28)          # orange-red of the segmented meters
SEGMENTS = 20


def esc(t) -> str:
    return html.escape(str(t))


def hero_html(brand: str, bold: str, tagline: str) -> str:
    return (f'<div class="fi-hero"><div class="brand">{esc(brand)}<b>{esc(bold)}</b></div>'
            f'<div class="tag">{esc(tagline)}</div></div>')


def section_html(num: int, title: str, sub: str = "") -> str:
    """Numbered section header in the style '01  Impact & metrics'."""
    s = f'<span class="sub">{esc(sub)}</span>' if sub else ""
    return (f'<div class="fi-section"><span class="num">{num:02d}</span>'
            f'<span class="title">{esc(title)}</span>{s}</div>')


def segment_colors(value: float, n: int = SEGMENTS, fade: int = 4) -> list[str]:
    """Colours of the n bars: filled bars solid accent, the last `fade` filled bars fading out, rest grey."""
    v = min(max(float(value), 0.0), 100.0)
    k = round(v / 100 * n)
    r, g, b = ACCENT
    out = []
    for i in range(n):
        if i >= k:
            out.append("#E6E6E9")
            continue
        steps_from_end = k - 1 - i
        a = 1.0 if steps_from_end >= fade else 0.30 + 0.70 * (steps_from_end + 1) / (fade + 1)
        out.append(f"rgba({r},{g},{b},{a:.2f})")
    return out


def meter_html(value: float, desc: str, value_text: str | None = None) -> str:
    """Big segmented meter (0-100) with a large number and a description below."""
    bars = "".join(f'<span style="background:{c}"></span>' for c in segment_colors(value))
    scale = "".join(f"<span>{t}</span>" for t in (0, 25, 50, 75, 100))
    vt = value_text if value_text is not None else f"{value:.0f}%" if float(value).is_integer() else f"{value:.1f}%"
    return (f'<div class="fi-meter"><div class="scale">{scale}</div><div class="bars">{bars}</div>'
            f'<div class="value">{esc(vt)}</div><div class="desc">{esc(desc)}</div></div>')


def small_meter_html(label: str, value: float) -> str:
    """Compact meter for a probability in [0, 1] (e.g. NLI class probabilities)."""
    bars = "".join(f'<span style="background:{c}"></span>' for c in segment_colors(100 * value, fade=2))
    return (f'<div class="fi-meter small"><div class="row"><span>{esc(label)}</span><span>{value:.2f}</span></div>'
            f'<div class="bars">{bars}</div></div>')


def kpi_html(label: str, value: str, pill: str = "") -> str:
    p = f'<div class="fi-pill">{esc(pill)}</div>' if pill else ""
    return f'<div class="fi-kpi"><div class="label">{esc(label)}</div><div class="value">{esc(value)}</div>{p}</div>'


BLOB_COLORS = ["#B9A6FF", "#E4F54B", "#4CC76A", "#F28AE6", "#FF9466", "#7DD3FC"]
BLOB_SHAPES = ["46% 54% 42% 58% / 55% 45% 55% 45%", "58% 42% 55% 45% / 45% 58% 42% 55%",
               "50% 50% 38% 62% / 60% 40% 60% 40%", "40% 60% 60% 40% / 50% 50% 50% 50%"]


def blob_html(color: str, style: int = 0) -> str:
    """A small friendly blob with eyes, drawn with CSS only (st.html strips SVG)."""
    eye = f"e{style % 4}"
    return (f'<div class="fi-blob" style="background:{color};border-radius:{BLOB_SHAPES[style % 4]}">'
            f'<span class="eye {eye} l"></span><span class="eye {eye} r"></span></div>')


def flow_html(nodes: list[dict], row: int = 118, node_h: int = 86, width: float = 34.0) -> str:
    """Diagonal cascade of white step cards joined by pink-to-red elbow connectors (CSS only).
    node keys: chip, text, note (optional), kind ('ok'|'warn'|'bad', chip colour), check (None|'ok'|'warn')."""
    n = len(nodes)
    step = (100 - width) / max(n - 1, 1)
    pos = [(i * step, 12 + i * row) for i in range(n)]
    height = pos[-1][1] + node_h + 16 if nodes else 0
    wires, dots = [], []
    for (x1, y1), (x2, y2) in zip(pos, pos[1:]):
        cx1, cx2 = x1 + width * 0.5, x2 + width * 0.18          # leave the bottom-middle, enter top-left
        yb, yt = y1 + node_h, y2
        ym = (yb + yt) / 2
        wires.append(f'<div class="fi-wire v" style="left:{cx1:.2f}%;top:{yb}px;height:{ym - yb + 1}px"></div>')
        wires.append(f'<div class="fi-wire h" style="left:{cx1:.2f}%;top:{ym}px;width:{cx2 - cx1:.2f}%"></div>')
        wires.append(f'<div class="fi-wire v2" style="left:{cx2:.2f}%;top:{ym}px;height:{yt - ym}px"></div>')
        dots += [(cx1, yb), (cx2, yt)]
    cards = []
    for i, ((x, y), nd) in enumerate(zip(pos, nodes)):
        kind = {"ok": "", "warn": " warn", "bad": " bad"}.get(nd.get("kind", "ok"), "")
        note = f'<div class="note">{esc(nd["note"])}</div>' if nd.get("note") else ""
        check = ""
        if nd.get("check"):
            bg, sym = ("#1F9D55", "✓") if nd["check"] == "ok" else ("#E8401C", "!")
            check = f'<div class="check" style="background:{bg}">{sym}</div>'
        cards.append(f'<div class="fi-node" style="left:{x:.2f}%;top:{y}px;width:{width}%;height:{node_h}px">'
                     f'{blob_html(BLOB_COLORS[i % len(BLOB_COLORS)], i)}'
                     f'<div style="flex:1;min-width:0"><span class="chip{kind}">{esc(nd["chip"])}</span>'
                     f'<div class="text">{esc(nd["text"])}</div>{note}</div>{check}</div>')
    dot_html = "".join(f'<div class="fi-dot" style="left:{x:.2f}%;top:{y}px"></div>' for x, y in dots)
    return f'<div class="fi-flow" style="height:{height}px">{"".join(wires)}{"".join(cards)}{dot_html}</div>'
