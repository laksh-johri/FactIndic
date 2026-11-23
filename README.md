# FactIndic

**Claim-level factual-error detection and selective repair for Hindi and Hinglish summaries.**

FactIndic takes a source article and an AI-generated summary, splits the summary into atomic
claims, retrieves evidence sentences from the source (LaBSE), and verifies every claim with a
multilingual NLI model (mDeBERTa-v3 XNLI) plus exact rule checks for numbers, dates, negation and
named entities. Only flagged claims are repaired (Gemini), then re-verified; uncertain cases go to
human review. Every decision is shown with its source evidence.

Research question: *Can claim-level verification plus selective correction reduce factual errors
in Hindi/Hinglish summaries while preserving content?*

## Layout
```
config.yaml        all model names, paths, seeds, thresholds
src/               library code (config, data, llm, synth, ... )
experiments/       runnable scripts that write to results/
results/           experiment outputs (CSV/JSON/PNG, timestamped)
tests/             pytest unit tests
docs/              research_log.md (lab notebook) and paper_outline.md
data/              factindic_synth_articles.jsonl, factindic_synth_errors.jsonl
cache/             on-disk LLM cache (git-ignored)
app.py             Streamlit demo (later step)
```

## Setup (Windows, Python 3.11, CPU only)
```bash
py -3.11 -m venv venv
venv\Scripts\python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env      # then put your GEMINI_API_KEY in .env
```

## Reproduce Step 1
```bash
venv\Scripts\python -m src.synth                    # (re)generate the synthetic dataset, seed 42
venv\Scripts\python -m src.data                     # integrity report
venv\Scripts\python -m experiments.dataset_stats    # tables + figure -> results/dataset_stats/
venv\Scripts\python -m pytest -q
```
