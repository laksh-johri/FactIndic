# FactIndic – Project Instructions for Claude Code

## What this project is
FactIndic detects and repairs factual errors in AI-generated summaries of Hindi and
Hinglish (Hindi–English code-mixed) text, and shows source evidence for every decision.

Pipeline: (1) Generate summary → (2) Decompose into atomic claims → (3) Retrieve top-k
evidence sentences from the source → (4) Verify each claim with (a) multilingual NLI and
(b) exact rule checks for numbers, dates, negation and named entities → (5) Repair ONLY
the flagged claim → (6) Re-check; uncertain → human review.

Decision rule: a claim is SUPPORTED only if NLI = entailment AND all rule checks pass.
NLI = contradiction OR any rule fails → CONTRADICTED. NLI = neutral with no rule
failure → UNSUPPORTED. Low confidence → REVIEW.

Research question: Can claim-level verification plus selective correction reduce
factual errors in Hindi/Hinglish summaries while preserving content?

## Data (in data/)
- factindic_synth_articles.jsonl: 128 articles (64 Hindi, 64 Hinglish), fields:
  article_id, language, script, domain, split, title, text, summary, gold_claims,
  key_facts, source_digit_script, source_spelling_noise
- factindic_synth_errors.jsonl: 512 rows (128 correct + 384 with ONE injected error),
  fields: sample_id, article_id, language, domain, split, source_text,
  reference_summary, candidate_summary, label (CORRECT/ERROR), error_type
  (none/number_swap/date_swap/entity_swap/negation/unsupported_addition),
  error_slot, span_start, span_end, original_value, injected_value, expected_nli
- Split is BY ARTICLE (dev ≈30%, test ≈70%). Tune ONLY on dev. Report on test.

## Tech stack
Python 3.10+, transformers, sentence-transformers (LaBSE), NLI model
MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7, Gemini API for LLM calls,
Streamlit for the demo, pandas. CPU must be enough.

## Coding rules
- Every LLM call goes through src/llm.py and is cached on disk (results must be reproducible).
- Never hard-code API keys; read from .env.
- All experiment outputs are saved to results/ as CSV/JSON with a timestamp and config.
- Fixed random seeds. Model names and versions in config.yaml, not scattered in code.
- Write small unit tests in tests/ for every module, and run them before finishing a step.
- Work ONE step at a time. When a step is done, STOP and wait for me.

## MANDATORY after every step: explain and document
I am writing a research paper on this project and need to understand everything.
After finishing each step, do BOTH:

### A) Reply to me in chat with this structure
1. **What I built**: one-paragraph plain-language summary.
2. **Files created/changed**: a table of file → purpose → key functions.
3. **How it works**: walk through the logic step by step, with one small worked
   example from our dataset (show the input and the output).
4. **Design decisions & why**: every non-obvious choice, the alternatives I
   considered, and why I rejected them.
5. **How to verify it yourself**: exact commands to run and the expected output.
6. **Results/numbers**, if any were produced.
7. **For the research paper**: which paper section this belongs to (Dataset /
   Methodology / Experimental Setup / Results / Limitations), plus 3–6 draft sentences
   in academic style that I can adapt.
8. **Limitations / things to watch**: honest weaknesses of this step.
9. **Concepts to understand**: explain any ML/NLP concept used (e.g. NLI, cosine
   similarity, precision/recall) in simple language, as if teaching a student.

### B) Append the same content to docs/research_log.md
Use a heading `## Step N – <name> (<date>)` so the file becomes a running lab notebook
I can turn into the paper.

Use simple English. I am a student; teach me, don't just report.
