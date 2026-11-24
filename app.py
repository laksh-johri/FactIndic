"""FactIndic demo (Streamlit): verify and repair a Hindi / Hinglish summary claim by claim.

Run:  streamlit run app.py        (venv\\Scripts\\streamlit run app.py on Windows)

Uses src/pipeline.py, i.e. exactly the components and config.yaml settings of the experiments.
No API key is needed: the summary is given (benchmark example or pasted by the user).
Look: .streamlit/config.toml (theme) + assets/factindic.css (cards, meters, flow).
"""
from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import altair as alt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import load_config  # noqa: E402
from src.data import load_errors  # noqa: E402
from src.pipeline import FactIndicPipeline  # noqa: E402
from src.render import (RULE_ICON, badge, diff_html, flow_html, hero_html, highlight_claims,  # noqa: E402
                        kpi_html, meter_html, section_html, small_meter_html)

st.set_page_config(page_title="FactIndic", page_icon=":material/fact_check:", layout="wide")
st.html(ROOT / "assets" / "factindic.css")

ACTION_LABEL = {"replace_number": "replace number", "replace_date": "replace date",
                "replace_entity": "replace name", "flip_negation": "fix negation",
                "delete": "delete claim", "review": "no edit → human review"}
ERROR_LABEL = {"none": "None", "number_swap": "Number", "date_swap": "Date", "entity_swap": "Entity",
               "negation": "Negation", "unsupported_addition": "Addition"}
SHOWCASE_ID = "hi013-E3"        # default benchmark sample: number swap 152 -> 253
DEFAULT_ID = "hg002-E3"          # Hinglish location swap (dev split) used as the free-text example
INDIGO, INDIGO_DARK = "#4338CA", "#2B2BB0"


@st.cache_resource(show_spinner="Loading FactIndic pipeline …")
def get_pipeline() -> FactIndicPipeline:
    return FactIndicPipeline()


@st.cache_data
def get_errors() -> pd.DataFrame:
    return load_errors()


def latest(pattern: str) -> Path | None:
    runs = sorted((ROOT / "results").glob(pattern))
    return runs[-1] if runs else None


def card(key: str):
    """White rounded card (styled via .st-key-card* in assets/factindic.css)."""
    return st.container(key=f"card_{key}")


def section(num: int, title: str, sub: str = "") -> None:
    st.markdown(section_html(num, title, sub), unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Charts
# ---------------------------------------------------------------------------
def pill_area_chart(df: pd.DataFrame, x: str, y: str, pick: int, label: str, domain=(0, 1),
                    height: int = 240, alt_text: str = "") -> alt.LayerChart:
    """Indigo gradient area chart with a white marker and a rounded label pill on row `pick`."""
    enc_x = alt.X(f"{x}:N", sort=None, scale=alt.Scale(padding=0.35), axis=alt.Axis(title=None, labelAngle=0, grid=False, domain=False,
                                                       ticks=False, labelColor="#8A8A93", labelFontSize=13,
                                                       labelPadding=14))
    enc_y = alt.Y(f"{y}:Q", scale=alt.Scale(domain=list(domain)), axis=None)
    base = alt.Chart(df).encode(x=enc_x, y=enc_y)
    area = base.mark_area(
        interpolate="linear", line={"color": INDIGO_DARK, "strokeWidth": 3},
        color=alt.Gradient(gradient="linear", x1=1, x2=1, y1=1, y2=0,
                           stops=[alt.GradientStop(color="rgba(67,56,202,0.02)", offset=0),
                                  alt.GradientStop(color="rgba(67,56,202,0.85)", offset=1)]))
    dividers = base.mark_rule(color="#FFFFFF", opacity=0.35, strokeWidth=1).encode(y2=alt.datum(domain[0]))
    p = df.iloc[[pick]].assign(_label=label)
    hw = (9 * len(label) + 30) / 80                    # pill half-width in symbol units (1 unit = 40 px)
    pill_shape = (f"M{-hw + .375} -.375 H{hw - .375} A.375 .375 0 0 1 {hw - .375} .375 "
                  f"H{-hw + .375} A.375 .375 0 0 1 {-hw + .375} -.375 Z")
    glow = alt.Chart(p).mark_point(filled=True, shape=pill_shape, size=6400, color=INDIGO, opacity=0.18,
                                   yOffset=-40).encode(x=enc_x, y=enc_y)
    pill = alt.Chart(p).mark_point(filled=True, shape=pill_shape, size=5200, color="#5B5BD6", opacity=1,
                                   yOffset=-40).encode(x=enc_x, y=enc_y)
    text = alt.Chart(p).mark_text(color="#FFFFFF", fontSize=15, fontWeight=600, yOffset=-40).encode(
        x=enc_x, y=enc_y, text="_label:N")
    dot = alt.Chart(p).mark_point(filled=True, fill="#FFFFFF", stroke=INDIGO_DARK, strokeWidth=4, size=190,
                                  opacity=1).encode(x=enc_x, y=enc_y)
    return ((area + dividers + glow + pill + text + dot).properties(height=height, background="transparent")
            .configure_view(stroke=None, fill=None))


# ---------------------------------------------------------------------------
# Input
# ---------------------------------------------------------------------------
def sidebar_input(errors: pd.DataFrame):
    st.sidebar.markdown("### Input")
    mode = st.sidebar.segmented_control("Summary source", ["Benchmark", "Own text"], default="Benchmark",
                                        required=True, key="mode", width="stretch")
    if mode == "Benchmark":
        split = st.sidebar.segmented_control("Split", ["test", "dev"], default="test", required=True,
                                             key="split", width="stretch")
        lang = st.sidebar.segmented_control("Language", ["hindi", "hinglish"], default="hindi", required=True,
                                            key="lang", format_func=str.capitalize, width="stretch")
        types = ["any"] + sorted(errors.error_type.unique())
        etype = st.sidebar.selectbox("Error type", types, key="etype",
                                     format_func=lambda t: "Any" if t == "any" else ERROR_LABEL.get(t, t))
        sub = errors[(errors.split == split) & (errors.language == lang)]
        if etype != "any":
            sub = sub[sub.error_type == etype]
        ids = sub.sample_id.tolist()
        sid = st.sidebar.selectbox("Sample", ids, key="sample",
                                   index=ids.index(SHOWCASE_ID) if SHOWCASE_ID in ids else 0)
        row = errors.set_index("sample_id").loc[sid]
        return row.source_text, row.candidate_summary, row, sid
    ex = errors.set_index("sample_id").loc[DEFAULT_ID]
    st.sidebar.caption("Paste a source article and a summary (Hindi, Hinglish or mixed). "
                       "The first run on new text loads the NLI model.")
    src = st.sidebar.text_area("Source article", ex.source_text, height=260, key="src")
    summ = st.sidebar.text_area("Summary to check", ex.candidate_summary, height=140, key="summ")
    return src, summ, None, None


# ---------------------------------------------------------------------------
# Demo tab
# ---------------------------------------------------------------------------
def pct_supported(claims) -> float:
    return 100 * sum(c.verdict == "SUPPORTED" for c in claims) / len(claims) if claims else 0.0


def trace_nodes(res) -> list[dict]:
    n_flag = sum(c.verdict != "SUPPORTED" for c in res.claims)
    acts = [e.action for e in res.repair.edits]
    changes = [a for a in acts if a != "review"]
    kinds = sorted({ACTION_LABEL[a] for a in changes})
    accepted = res.status == "accepted"
    return [
        {"chip": "Step 2 · Decompose", "text": f"{len(res.claims)} atomic claims", "note": "clause splitting, spans kept"},
        {"chip": "Step 3 · Retrieve", "text": "Top-3 evidence per claim", "note": "char n-gram TF-IDF, normalised"},
        {"chip": "Step 4 · Verify", "kind": "bad" if n_flag else "ok",
         "text": f"{len(res.claims) - n_flag} supported · {n_flag} flagged", "note": "NLI + 4 rule checks"},
        {"chip": "Step 5 · Repair", "kind": "warn" if changes else "ok",
         "text": f"{len(changes)} edit{'s' if len(changes) != 1 else ''}" + (f" · {acts.count('review')} for review" if "review" in acts else ""),
         "note": ", ".join(kinds) if kinds else "nothing to change"},
        {"chip": "Step 6 · Re-check", "kind": "ok" if accepted else "warn",
         "text": "Auto-accepted" if accepted else "Human review", "check": "ok" if accepted else "warn",
         "note": "every claim supported" if accepted else "some claims still not supported"},
    ]


def claim_table(claims) -> pd.DataFrame:
    return pd.DataFrame([{"#": i, "Claim": c.text, "Verdict": c.verdict,
                          "Entail": c.nli["entailment"], "Neutral": c.nli["neutral"],
                          "Contra": c.nli["contradiction"],
                          "Failed rules": ", ".join(n for n, r in c.rules.items() if r["status"] == "fail") or "–",
                          "Reason": c.reason} for i, c in enumerate(claims, 1)])


PROB_COL = {k: st.column_config.ProgressColumn(k, min_value=0.0, max_value=1.0, format="%.2f")
            for k in ("Entail", "Neutral", "Contra")}


def show_overview(res) -> None:
    before, after = pct_supported(res.claims), pct_supported(res.recheck)
    changed = 100 * (1 - difflib.SequenceMatcher(None, res.summary, res.repair.repaired, autojunk=False).ratio())
    cols = st.columns(3, gap="medium")
    meters = [(before, f"Claims supported before repair ({sum(c.verdict == 'SUPPORTED' for c in res.claims)} of {len(res.claims)})"),
              (after, f"Claims supported after repair and re-check ({sum(c.verdict == 'SUPPORTED' for c in res.recheck)} of {len(res.recheck)})"),
              (changed, "Of the summary text changed by the repair – lower means more content preserved")]
    for i, (col, (v, d)) in enumerate(zip(cols, meters)):
        with col, card(f"ov{i}"):
            st.html(meter_html(v, d))

    with st.container(key="dots_trace"):
        st.markdown('<div class="fi-label">Pipeline trace for this summary</div>', unsafe_allow_html=True)
        st.html(flow_html(trace_nodes(res)))


def show_support_card(res) -> None:
    n_b = sum(c.verdict == "SUPPORTED" for c in res.claims)
    n_a = sum(c.verdict == "SUPPORTED" for c in res.recheck)
    delta = n_a - n_b
    st.html(kpi_html("Supported claims after repair", f"{n_a} / {len(res.recheck)}",
                     f"{delta:+d} vs before repair  ↗" if delta > 0 else f"{delta:+d} vs before repair"))
    if len(res.recheck) >= 2:
        df = pd.DataFrame({"claim": [f"#{i}" for i in range(1, len(res.recheck) + 1)],
                           "entailment": [c.nli["entailment"] for c in res.recheck]})
        low = int(df.entailment.idxmin())
        st.altair_chart(pill_area_chart(df, "claim", "entailment", low, f"{df.entailment[low]:.2f}"),
                        alt="NLI entailment probability per claim of the repaired summary; "
                            f"lowest for claim #{low + 1}")
        st.caption("NLI entailment per claim of the final summary; the pill marks the weakest claim.")


def show_claims(res, premise_mode: str) -> None:
    section(2, "Claims and verdicts", "each claim coloured by its verdict")
    left, right = st.columns([3, 2], gap="medium")
    with left, card("claims"):
        st.markdown('<div class="fi-label">Summary, claim by claim</div>', unsafe_allow_html=True)
        st.markdown(highlight_claims(res.summary, res.claims), unsafe_allow_html=True)
        st.markdown(" ".join(badge(v) for v in ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "REVIEW")),
                    unsafe_allow_html=True)
    with right, card("support"):
        show_support_card(res)
    with card("claimtable"):
        st.dataframe(claim_table(res.claims), hide_index=True, column_config=PROB_COL)

    section(3, "Evidence and checks", "why each verdict was given")
    for i, c in enumerate(res.claims, 1):
        icon = ":material/check_circle:" if c.verdict == "SUPPORTED" else ":material/error:"
        with st.expander(f"#{i} · {c.verdict} · {c.text}", icon=icon):
            st.markdown(f"{badge(c.verdict)} &nbsp; {c.reason}", unsafe_allow_html=True)
            left, right = st.columns([3, 2], gap="large")
            with left:
                st.markdown('<div class="fi-label">Evidence from the source (top-k)</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame([{"Rank": e["rank"], "Score": round(e["score"], 3),
                                            "Sentence #": e["sent_idx"] + 1, "Evidence sentence": e["text"]}
                                           for e in c.evidence]), hide_index=True)
                st.caption(f"NLI premise = {'rank-1 sentence' if premise_mode == 'top1' else 'top-k sentences joined'}; "
                           "hypothesis = the claim.")
                st.markdown('<div class="fi-label">Rule checks</div>', unsafe_allow_html=True)
                st.dataframe(pd.DataFrame([{"Rule": n, "Result": RULE_ICON.get(r["status"], r["status"]),
                                            "Detail": r["reason"]} for n, r in c.rules.items()]), hide_index=True)
            with right:
                st.markdown('<div class="fi-label">NLI probabilities</div>', unsafe_allow_html=True)
                st.html("".join(small_meter_html(lab.capitalize(), float(c.nli[lab]))
                                for lab in ("entailment", "neutral", "contradiction")))


def show_repair(res) -> None:
    section(4, "Selective repair", "only flagged claims, values copied from evidence")
    with card("repair"):
        edits = res.repair.edits
        if not edits:
            st.success("Every claim is SUPPORTED, so nothing was changed.", title="Nothing to repair",
                       icon=":material/check_circle:")
            return
        st.dataframe(pd.DataFrame([{"Claim": e.claim_id.rsplit("#", 1)[-1] if "#" in e.claim_id else e.claim_id,
                                    "Action": ACTION_LABEL.get(e.action, e.action),
                                    "Old": e.old or "–", "New": e.new or "–", "Why": e.reason} for e in edits]),
                     hide_index=True)
        st.markdown('<div class="fi-label">Changes · red = removed, green = inserted</div>', unsafe_allow_html=True)
        st.markdown(diff_html(res.summary, res.repair.repaired), unsafe_allow_html=True)


def show_recheck(res) -> None:
    section(5, "Re-check", "the repaired summary is verified again")
    with card("recheck"):
        if res.recheck:
            st.markdown(highlight_claims(res.repair.repaired, res.recheck), unsafe_allow_html=True)
        if res.status == "accepted":
            st.success("Every claim of the final summary is SUPPORTED.", title="Auto-accepted",
                       icon=":material/verified:")
        else:
            bad = [c for c in res.recheck if c.verdict != "SUPPORTED"]
            why = f"{len(bad)} claim(s) still not SUPPORTED after repair." if res.recheck else "The output is empty."
            st.warning(why, title="Sent to human review", icon=":material/person_search:")
        if res.recheck:
            with st.expander("Re-check details", icon=":material/table_view:"):
                st.dataframe(claim_table(res.recheck), hide_index=True, column_config=PROB_COL)


def show_gold(row, sid: str, output: str) -> None:
    from experiments.run_repair import gold_outcome
    with st.expander("Gold answer (benchmark only – hidden from the system)", icon=":material/target:"):
        if row.label == "CORRECT":
            st.markdown("This summary is **correct** (no error injected).")
        else:
            st.markdown(f"Injected error: **{row.error_type}** in slot `{row.error_slot}`: "
                        f"`{row.original_value}` → `{row.injected_value}`")
        st.markdown("**Reference summary**")
        st.markdown(row.reference_summary)
        outcome = gold_outcome(row.reference_summary, output)
        msg = {"complete": ":green-badge[complete] output identical to the reference",
               "lossy": ":orange-badge[lossy] faithful, but some reference content was deleted",
               "erroneous": ":red-badge[erroneous] output still differs from the reference",
               "empty": ":gray-badge[empty] everything was deleted"}[outcome]
        st.markdown(f"**Gold outcome of the final output:** {msg}")
        st.caption(f"{sid} · {row.language} · {row.domain} · split={row.split}")


def demo_tab(source: str, summary: str, row, sid, premise_mode: str) -> None:
    c1, c2 = st.columns(2, gap="medium")
    with c1, card("source"):
        st.markdown('<div class="fi-label">Source article</div>', unsafe_allow_html=True)
        st.markdown(source)
    with c2, card("summary"):
        st.markdown('<div class="fi-label">Summary to check</div>', unsafe_allow_html=True)
        st.markdown(summary)
    if not source.strip() or not summary.strip():
        st.info("Enter both a source article and a summary.", icon=":material/edit_note:")
        return
    with st.spinner("Verifying claims …"):
        try:
            res = get_pipeline().run(source, summary)
        except ValueError as e:
            st.error(str(e))
            return
    section(1, "Impact & metrics", "for this summary")
    if not res.claims:
        st.warning("The summary contains no claims.")
        return
    show_overview(res)
    show_claims(res, premise_mode)
    show_repair(res)
    show_recheck(res)
    if row is not None:
        show_gold(row, sid, res.repair.repaired)
    st.download_button("Download full result (JSON)", json.dumps(res.to_dict(), ensure_ascii=False, indent=2),
                       file_name=f"factindic_{sid or 'custom'}.json", mime="application/json",
                       icon=":material/download:")


# ---------------------------------------------------------------------------
# Benchmark tab
# ---------------------------------------------------------------------------
def benchmark_tab() -> None:
    v_path, r_path = latest("verification/run_*/test_main.csv"), latest("repair/run_*/test_main.csv")
    t_path = latest("repair/run_*/test_by_error_type.csv")
    if not (v_path and r_path):
        st.info("No results yet – run the experiments first.")
        return
    det = pd.read_csv(v_path, index_col=0)
    rep = pd.read_csv(r_path, index_col=0)
    full, sel, base = det.loc["full (NLI + rules)"], rep.loc["selective"], rep.loc["no_repair"]
    n = int(sel["n"])

    section(1, "Impact & metrics", f"test set · {n} summaries · selective repair")
    removed = 100 * (base["error_rate_%"] - sel["error_rate_%"]) / base["error_rate_%"]
    meters = [(removed, f"Of injected errors removed – erroneous summaries fell from {base['error_rate_%']:.0f}% "
                        f"to {sel['error_rate_%']:.0f}%"),
              (sel["fixed_complete_%(ERROR rows)"], "Of corrupted summaries restored exactly to the reference, "
                                                    "values copied from the evidence"),
              (sel["keyfact_retention_%"], f"Of key facts kept, while only {sel['chars_changed_%']:.1f}% of "
                                           "characters were changed")]
    for i, (col, (val, d)) in enumerate(zip(st.columns(3, gap="medium"), meters)):
        with col, card(f"bm{i}"):
            st.html(meter_html(round(val, 1), d))

    section(2, "Detection", "claim verification · NLI + rule checks")
    meters = [(full["recall"], "Recall – corrupted summaries that were flagged"),
              (full["precision"], "Precision – flagged summaries that really contain an error"),
              (full["specificity"], "Specificity – faithful summaries left unflagged; all false alarms come from NLI")]
    for i, (col, (val, d)) in enumerate(zip(st.columns(3, gap="medium"), meters)):
        with col, card(f"det{i}"):
            st.html(meter_html(round(val, 1), d))

    section(3, "Where repair works", "exact-fix rate per error type")
    left, right = st.columns([3, 2], gap="medium")
    with left, card("bytype"):
        st.html(kpi_html("Errors fixed exactly", f"{sel['fixed_complete_%(ERROR rows)']:.1f}%",
                         f"+{sel['fixed_complete_%(ERROR rows)'] - base['fixed_complete_%(ERROR rows)']:.1f} pts vs no repair  ↗"))
        if t_path:
            bt = pd.read_csv(t_path, header=[0, 1], index_col=0)
            s = bt[("complete", "selective")].drop(index=["none"], errors="ignore").dropna()
            df = pd.DataFrame({"type": [ERROR_LABEL.get(k, k) for k in s.index], "exact_fix": s.values / 100})
            low = int(df.exact_fix.idxmin())
            st.altair_chart(pill_area_chart(df, "type", "exact_fix", low, f"{100 * df.exact_fix[low]:.1f}%",
                                            domain=(0.5, 1.05)),
                            alt=f"Exact-fix rate by error type; lowest for {df.type[low]} swaps")
            st.caption("Exact-fix rate per error type (y-axis from 50%). Entity swaps that could not be "
                       "matched safely were deleted instead – faithful, but content is lost.")
    with right, card("review"):
        review = 100 - sel["auto_accepted_%"]
        st.html(meter_html(round(review, 1), "Human-review load: summaries still routed to a person after "
                                             "re-check, all because of NLI false alarms"))

    section(4, "All numbers", "straight from results/")
    with st.expander(f"Detection · {v_path.parent.name}", icon=":material/table_view:"):
        st.dataframe(det.round(1))
    with st.expander(f"Repair + re-check · {r_path.parent.name}", icon=":material/table_view:"):
        st.dataframe(rep.round(1))


# ---------------------------------------------------------------------------
def how_tab() -> None:
    section(1, "How it works", "six steps, every decision backed by source evidence")
    nodes = [
        {"chip": "Step 1 · Generate", "kind": "warn", "text": "Summary from an LLM", "note": "needs an API key – skipped in this demo"},
        {"chip": "Step 2 · Decompose", "text": "Split into atomic claims", "note": "each claim keeps its character span"},
        {"chip": "Step 3 · Retrieve", "text": "Top-3 source sentences", "note": "digits, nukta and case normalised"},
        {"chip": "Step 4 · Verify", "text": "NLI + rule checks", "note": "numbers · dates · negation · entities"},
        {"chip": "Step 5 · Repair", "text": "Fix only flagged claims", "note": "copy value from evidence, or delete"},
        {"chip": "Step 6 · Re-check", "text": "Accept or human review", "check": "ok", "note": "accepted only if every claim is supported"},
    ]
    with st.container(key="dots_how"):
        st.html(flow_html(nodes, width=30.0))
    with card("rule"):
        st.markdown('<div class="fi-label">Decision rule</div>', unsafe_allow_html=True)
        st.markdown(f"""
- {badge('SUPPORTED')} NLI says entailment **and** every rule passes
- {badge('CONTRADICTED')} a rule fails, or NLI says contradiction
- {badge('UNSUPPORTED')} NLI says neutral and no rule fails
- {badge('REVIEW')} NLI is not confident (below τ)
""", unsafe_allow_html=True)
        st.caption("Claims flagged only by NLI are never edited – they go to human review.")


def main() -> None:
    cfg = load_config()
    vc = cfg["verification"]
    st.html(hero_html("Fact", "Indic", "Claim-level fact checking and selective repair of Hindi and Hinglish "
                                       "summaries, with source evidence for every decision."))
    errors = get_errors()
    source, summary, row, sid = sidebar_input(errors)
    st.sidebar.caption(f"Settings from config.yaml, tuned on dev: decomposition = {cfg['decomposition']['method']}, "
                       f"retrieval = {cfg['retrieval']['method']} (top-{cfg['retrieval']['top_k']}), "
                       f"NLI premise = {vc['nli_premise']}, τ = {vc['nli_threshold']}, rules = {', '.join(vc['rules'])}")

    tab_demo, tab_bench, tab_how = st.tabs([":material/fact_check: Check a summary",
                                            ":material/monitoring: Benchmark results",
                                            ":material/account_tree: How it works"])
    with tab_demo:
        demo_tab(source, summary, row, sid, vc["nli_premise"])
    with tab_bench:
        benchmark_tab()
    with tab_how:
        how_tab()


main()
