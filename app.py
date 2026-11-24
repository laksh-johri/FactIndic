"""FactIndic demo (Streamlit): verify and repair a Hindi / Hinglish summary claim by claim.

Run:  streamlit run app.py        (venv\\Scripts\\streamlit run app.py on Windows)

Uses src/pipeline.py, i.e. exactly the components and config.yaml settings of the experiments.
No API key is needed: the summary is given (benchmark example or pasted by the user).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from src.config import load_config  # noqa: E402
from src.data import load_errors  # noqa: E402
from src.pipeline import FactIndicPipeline  # noqa: E402
from src.render import RULE_ICON, badge, diff_html, highlight_claims  # noqa: E402

st.set_page_config(page_title="FactIndic demo", page_icon="🔎", layout="wide")

ACTION_LABEL = {"replace_number": "replace number", "replace_date": "replace date",
                "replace_entity": "replace name", "flip_negation": "fix negation",
                "delete": "delete claim", "review": "no edit → human review"}
DEFAULT_ID = "hg002-E3"          # Hinglish location swap (dev split) used as the free-text example


@st.cache_resource(show_spinner="Loading FactIndic pipeline …")
def get_pipeline() -> FactIndicPipeline:
    return FactIndicPipeline()


@st.cache_data
def get_errors() -> pd.DataFrame:
    return load_errors()


def latest(pattern: str) -> Path | None:
    runs = sorted((ROOT / "results").glob(pattern))
    return runs[-1] if runs else None


# ---------------------------------------------------------------------------
def sidebar_input(errors: pd.DataFrame):
    st.sidebar.header("Input")
    mode = st.sidebar.radio("Source of the summary", ["Benchmark example", "Your own text"], key="mode")
    if mode == "Benchmark example":
        split = st.sidebar.selectbox("Split", ["test", "dev"], key="split")
        lang = st.sidebar.selectbox("Language", ["hindi", "hinglish"], key="lang")
        types = ["any"] + sorted(errors.error_type.unique())
        etype = st.sidebar.selectbox("Error type", types, key="etype")
        sub = errors[(errors.split == split) & (errors.language == lang)]
        if etype != "any":
            sub = sub[sub.error_type == etype]
        sid = st.sidebar.selectbox("Sample", sub.sample_id.tolist(), key="sample")
        row = errors.set_index("sample_id").loc[sid]
        return row.source_text, row.candidate_summary, row, sid
    ex = errors.set_index("sample_id").loc[DEFAULT_ID]
    st.sidebar.caption("Paste a source article and a summary (Hindi, Hinglish or mixed). "
                       "The first run loads the NLI model (≈30 s on CPU).")
    src = st.sidebar.text_area("Source article", ex.source_text, height=260, key="src")
    summ = st.sidebar.text_area("Summary to check", ex.candidate_summary, height=140, key="summ")
    return src, summ, None, None


def show_gold(row, sid: str, output: str) -> None:
    from experiments.run_repair import gold_outcome
    with st.expander("🎯 Gold answer (benchmark only – hidden from the system)"):
        if row.label == "CORRECT":
            st.write("This summary is **correct** (no error injected).")
        else:
            st.write(f"Injected error: **{row.error_type}** in slot `{row.error_slot}`: "
                     f"`{row.original_value}` → `{row.injected_value}`")
        st.markdown("**Reference summary**")
        st.write(row.reference_summary)
        outcome = gold_outcome(row.reference_summary, output)
        msg = {"complete": "✅ complete – output identical to the reference",
               "lossy": "🟡 lossy – faithful, but some reference content was deleted",
               "erroneous": "❌ erroneous – output still differs from the reference",
               "empty": "⚪ empty – everything was deleted"}[outcome]
        st.markdown(f"**Gold outcome of the final output:** {msg}")
        st.caption(f"{sid} · {row.language} · {row.domain} · split={row.split}")


def claim_table(claims) -> pd.DataFrame:
    return pd.DataFrame([{"#": i, "claim": c.text, "verdict": c.verdict,
                          "entail": round(c.nli["entailment"], 2), "neutral": round(c.nli["neutral"], 2),
                          "contra": round(c.nli["contradiction"], 2),
                          "failed rules": ", ".join(n for n, r in c.rules.items() if r["status"] == "fail") or "–",
                          "reason": c.reason} for i, c in enumerate(claims, 1)])


def show_claim_details(claims, premise_mode: str) -> None:
    for i, c in enumerate(claims, 1):
        with st.expander(f"#{i} · {c.verdict} · {c.text}"):
            st.markdown(f"**Verdict:** {badge(c.verdict)} &nbsp; {c.reason}", unsafe_allow_html=True)
            left, right = st.columns([3, 2])
            with left:
                st.markdown("**Evidence retrieved from the source (top-k)**")
                st.dataframe(pd.DataFrame([{"rank": e["rank"], "score": round(e["score"], 3),
                                            "sentence #": e["sent_idx"] + 1, "evidence sentence": e["text"]}
                                           for e in c.evidence]), hide_index=True, width="stretch")
                st.caption(f"NLI premise = {'rank-1 sentence' if premise_mode == 'top1' else 'top-k sentences joined'}; "
                           "hypothesis = the claim.")
            with right:
                st.markdown("**Rule checks**")
                st.dataframe(pd.DataFrame([{"rule": n, "result": RULE_ICON.get(r["status"], r["status"]),
                                            "detail": r["reason"]} for n, r in c.rules.items()]),
                             hide_index=True, width="stretch")
                st.markdown("**NLI probabilities**")
                for lab in ("entailment", "neutral", "contradiction"):
                    st.progress(float(c.nli[lab]), text=f"{lab}: {c.nli[lab]:.2f}")


def show_result(res, premise_mode: str) -> None:
    st.subheader("① Claims and verdicts")
    st.markdown(highlight_claims(res.summary, res.claims), unsafe_allow_html=True)
    st.markdown(" ".join(badge(v) for v in ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "REVIEW")),
                unsafe_allow_html=True)
    if not res.claims:
        st.warning("The summary contains no claims.")
        return
    st.dataframe(claim_table(res.claims), hide_index=True, width="stretch")

    st.subheader("② Evidence, rule checks and NLI per claim")
    show_claim_details(res.claims, premise_mode)

    st.subheader("③ Selective repair")
    edits = res.repair.edits
    if not edits:
        st.success("Nothing to repair: every claim is SUPPORTED.")
    else:
        st.dataframe(pd.DataFrame([{"claim": int(e.claim_id.rsplit("#", 1)[-1]) if "#" in e.claim_id else e.claim_id,
                                    "action": ACTION_LABEL.get(e.action, e.action),
                                    "old": e.old or "–", "new": e.new or "–", "why": e.reason} for e in edits]),
                     hide_index=True, width="stretch")
        st.markdown("**Changes** (red = removed, green = inserted)")
        st.markdown(diff_html(res.summary, res.repair.repaired), unsafe_allow_html=True)

    st.subheader("④ Re-check of the output")
    if res.recheck:
        st.markdown(highlight_claims(res.repair.repaired, res.recheck), unsafe_allow_html=True)
        with st.expander("Re-check details"):
            st.dataframe(claim_table(res.recheck), hide_index=True, width="stretch")
    if res.status == "accepted":
        st.success("**Auto-accepted** – every claim of the final summary is SUPPORTED.")
    else:
        bad = [c for c in res.recheck if c.verdict != "SUPPORTED"]
        why = (f"{len(bad)} claim(s) still not SUPPORTED after repair" if res.recheck
               else "the output is empty")
        st.warning(f"**Sent to human review** – {why}.")


def show_benchmark_tab() -> None:
    st.markdown("Headline TEST-set numbers from the latest experiment runs (`results/`).")
    v = latest("verification/run_*/test_main.csv")
    r = latest("repair/run_*/test_main.csv")
    if v:
        st.markdown(f"**Detection (Step 4)** – `{v.parent.name}`")
        st.dataframe(pd.read_csv(v, index_col=0).round(1), width="stretch")
    if r:
        st.markdown(f"**Repair + re-check (Steps 5–6)** – `{r.parent.name}`")
        st.dataframe(pd.read_csv(r, index_col=0).round(1), width="stretch")
    if not (v or r):
        st.info("No results yet – run the experiments first.")


# ---------------------------------------------------------------------------
def main() -> None:
    cfg = load_config()
    vc = cfg["verification"]
    st.title("🔎 FactIndic")
    st.caption("Claim-level fact checking and selective repair of Hindi / Hinglish summaries, "
               "with source evidence for every decision.")
    errors = get_errors()
    source, summary, row, sid = sidebar_input(errors)
    st.sidebar.divider()
    st.sidebar.caption(f"Settings (config.yaml, tuned on DEV): decomposition = {cfg['decomposition']['method']}, "
                       f"retrieval = {cfg['retrieval']['method']} (top-{cfg['retrieval']['top_k']}), "
                       f"NLI premise = {vc['nli_premise']}, τ = {vc['nli_threshold']}, rules = {', '.join(vc['rules'])}")

    tab_demo, tab_bench, tab_how = st.tabs(["Check a summary", "Benchmark results", "How it works"])
    with tab_demo:
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Source article**")
            st.write(source)
        with c2:
            st.markdown("**Summary to check**")
            st.write(summary)
        if not source.strip() or not summary.strip():
            st.info("Enter both a source article and a summary.")
        else:
            with st.spinner("Verifying claims …"):
                try:
                    res = get_pipeline().run(source, summary)
                except ValueError as e:
                    st.error(str(e))
                    res = None
            if res is not None:
                show_result(res, vc["nli_premise"])
                if row is not None:
                    show_gold(row, sid, res.repair.repaired)
                st.download_button("Download full result (JSON)",
                                   json.dumps(res.to_dict(), ensure_ascii=False, indent=2),
                                   file_name=f"factindic_{sid or 'custom'}.json", mime="application/json")
    with tab_bench:
        show_benchmark_tab()
    with tab_how:
        st.markdown("""
1. **Decompose** the summary into atomic claims (clause splitting, each claim keeps its character span).
2. **Retrieve** the top-k most similar source sentences for each claim (character n-gram TF-IDF after
   digit / nukta / case normalisation).
3. **Verify** each claim: multilingual NLI (mDeBERTa-v3 XNLI) with the evidence as premise, plus exact
   rule checks for numbers, dates, negation and named entities.
   *SUPPORTED* only if NLI says entailment **and** every rule passes; a failed rule or NLI contradiction →
   *CONTRADICTED*; NLI neutral → *UNSUPPORTED*; low confidence → *REVIEW*.
4. **Repair** only flagged claims, inside their span: copy the right number / date / name from the evidence,
   fix the negation, or delete unsupported content. Claims flagged only by NLI are never edited.
5. **Re-check** the repaired summary; if every claim is SUPPORTED it is auto-accepted, otherwise a human reviews it.
""")


main()
