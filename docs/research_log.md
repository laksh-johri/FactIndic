# FactIndic – Research Log (lab notebook)

Running record of every step: what was built, why, how to reproduce it, and draft paper text.

---

## Step 1 – Project setup, data loading and dataset analysis (2026-11-24)

> **Important note on data provenance.** The two dataset files were *not* present in `data/`
> when this step started. On instruction ("do it by yourself") the benchmark was **generated
> from scratch** by a deterministic, template-based generator (`src/synth.py`, seed 42). All
> numbers below describe this generated dataset. If an externally supplied version of the
> files is used later, re-run `python -m src.data` and `python -m experiments.dataset_stats`
> and replace the tables.

### 1. What I built
I set up the full project skeleton (folders, pinned dependencies, central `config.yaml`, git),
wrote a seeded generator that creates the FactIndic synthetic benchmark (128 source articles in
Hindi and Hinglish across 8 news domains, plus 512 candidate summaries of which 384 contain
exactly one injected factual error), wrote loaders and a validator that proves the data is
internally consistent, built a cached and logged Gemini wrapper that every future LLM call must
go through, and produced the dataset-description tables and one figure for the paper. Everything
is covered by 20 unit tests that pass.

### 2. Files created / changed
| File | Purpose | Key functions / contents |
|---|---|---|
| `config.yaml` | Single source of truth for models, paths, seed, top-k, NLI threshold | `seed: 42`, `models.embedder/nli/llm`, `retrieval.top_k: 3`, `verification.nli_threshold: 0.5` |
| `src/config.py` | Load config; shared helpers | `load_config()`, `set_seed()`, `timestamp()`, `ROOT` |
| `src/synth.py` | Deterministic dataset generator | `make_articles()`, `make_errors()`, `inject()`, `add_noise()`, `render()`, `generate()` |
| `src/data.py` | Load + split + validate the data | `load_articles()`, `load_errors()`, `get_split()`, `validate()` |
| `src/llm.py` | The only gateway to Gemini; disk cache, retry, CSV log | `call_llm()`, `LLMClient.call()`, `prompt_hash()`, `LLMConfigError` |
| `experiments/dataset_stats.py` | Paper tables + figure | `table_articles()`, `table_errors()`, `table_lengths()`, `table_claims()`, `table_conditions()`, `table_key_facts()`, `plot_errors()` |
| `tests/test_data.py` | Tests for loaders/validator (incl. that it *catches* corrupted data) | 10 tests |
| `tests/test_llm.py` | Tests for cache, retry, missing-key behaviour (fake backend, no network) | 5 tests |
| `tests/test_synth.py` | Tests that generation is deterministic and well-formed | 5 tests |
| `data/*.jsonl` | The generated benchmark | 128 articles, 512 summary rows |
| `results/dataset_stats/` | 6 CSV tables, `dataset_stats.md`, `error_types_by_language.png`, `run_meta.json` | |
| `requirements.txt`, `requirements-lock.txt` | Pinned direct deps; full frozen environment | |
| `README.md`, `.gitignore`, `.env.example`, `pytest.ini`, `app.py` | Project hygiene; `app.py` is an empty placeholder | |

### 3. How it works

**3a. Generating an article.** Each of the 8 domains (politics, sports, business, health,
education, environment, technology, infrastructure) has one hand-written template per language.
A template is a list of sentences with *slots*:
`{person} {org} {loc} {date} {num} {num2} {pol}`. For each article the generator samples a
value for each slot from fixed pools (24 people, 16 cities, 5 organisations per domain, numbers
from a domain-specific range, a date in 2023–2025, and a polarity: positive or negative).
`num` is the key number that appears in the summary; `num2` is a *distractor* number that appears
only in the source (so a verifier cannot just "find any number"). Two generic filler sentences
are appended to the source. The summary template contains each key slot exactly once, and the
gold claims template lists 5–6 atomic facts.

Two robustness conditions are then applied **to the source only**:
* `source_digit_script = devanagari` (≈45 % of Hindi articles): every digit in the source is
  rewritten in Devanagari numerals (२०२५ instead of 2025), while the summary keeps 0-9.
* `source_spelling_noise = True` (≈50 %): informal spelling variants are applied to template words
  (Hinglish: *mein→me, kiya→kia, ke→k, liye→lie*; Hindi: *में→मे, किए→किये*, nukta dropped
  *ज़→ज*). Slot values (names, numbers, dates) are never altered.

**3b. Injecting errors.** Every article yields 4 summary rows: the correct reference
(`-C`) and three rows (`-E1..E3`) each with **one** error of a different type. Types are assigned
by cycling through the 5 types over a shuffled article list, so the totals are balanced
(77/77/77/77/76). Because we know the exact character span of every slot in the summary, the
replacement is surgical and the row records `span_start`, `span_end`, `original_value`,
`injected_value` and the NLI label we expect a perfect verifier to produce
(`contradiction` for swaps and negation, `neutral` for unsupported additions, `entailment` for
correct rows).

**3c. Validation.** `validate()` checks columns, that `candidate[span_start:span_end] ==
injected_value` for all 384 error rows, that the 128 correct rows equal the reference, that no
`article_id` is in both dev and test, plus three extra checks (valid split names, unique
`sample_id`, every summary row has the same split as its article).

**3d. LLM wrapper.** `call_llm(prompt, temperature=0)` computes
`sha256(model | temperature | prompt)`. If that key is in `cache/llm_cache.json` the stored
answer is returned (no API key needed). Otherwise it calls Gemini; on HTTP 429/5xx it waits
`2·2^attempt + jitter` seconds and retries (max 5). Every call – hit, miss, retry, error – is
appended to `results/llm_calls.csv`. If there is no key, it raises a clear `LLMConfigError`;
nothing else in the project imports Gemini, so the rest keeps working.

**Worked example (article `hi001`, politics, Hindi, test split).**

*Source (excerpt):* जन विकास पार्टी के अध्यक्ष सुनीता शर्मा ने 20 जनवरी 2025 को जयपुर में एक
जनसभा को संबोधित किया। आयोजकों के अनुसार इस सभा में लगभग 18500 लोग शामिल हुए। … उन्होंने
आगामी चुनाव के लिए किसी नए गठबंधन की घोषणा नहीं की। पिछली बार इसी मैदान में लगभग 37000 लोग
जुटे थे। …

*Reference summary (`hi001-C`):* जन विकास पार्टी के अध्यक्ष सुनीता शर्मा ने 20 जनवरी 2025 को
जयपुर में जनसभा को संबोधित किया। सभा में लगभग 18500 लोग शामिल हुए। उन्होंने किसी नए गठबंधन
की घोषणा नहीं की।

*Key facts:* entity=सुनीता शर्मा, entity=जन विकास पार्टी, entity=जयपुर, number=18500,
date=20 जनवरी 2025.

| sample_id | error_type | original → injected | expected NLI |
|---|---|---|---|
| hi001-E1 | date_swap | 20 जनवरी 2025 → 20 जुलाई 2025 | contradiction |
| hi001-E2 | entity_swap (org) | जन विकास पार्टी → नव भारत संघ | contradiction |
| hi001-E3 | negation | नहीं की → की | contradiction |

E3 is the hardest kind: the summary now says the alliance *was* announced, one short word away
from the truth. For E2, `validate()` confirms
`candidate_summary[0:11] == "नव भारत संघ"` (spans count Unicode code points, so a
Devanagari vowel sign such as ा counts as its own character).

### 4. Design decisions & why
| Decision | Alternatives considered | Why this choice |
|---|---|---|
| Generate data with templates, seed 42 | (a) wait for external files; (b) ask Gemini to write articles | Files were missing; templates give *exact* gold spans and labels and are 100 % reproducible with no API cost. LLM-written data would need manual checking of every label. Cost: less linguistic variety (see Limitations). |
| One error per summary, balanced types | Several errors per summary; natural error distribution | One error makes evaluation unambiguous (we know exactly what should be flagged) and lets us report per-type recall. Balanced types prevent one type dominating the average. |
| Distractor number `num2` in source | Only one number per article | Forces the number-rule to check the *right* number in context, not just "is some number present". |
| Devanagari digits / spelling noise only in the source | Noise in both; no noise | Mimics real use: summaries from an LLM are clean, sources (news, social media) are messy. Tests whether rule checks normalise digits and spelling. |
| Split by article, stratified by language × domain (dev 40 = 31 %, test 88) | Random row split | A row split would put the correct and error versions of the *same* article into dev and test → information leak. |
| `google-genai` SDK instead of `google-generativeai` | The package named in the brief | `google-generativeai` was deprecated by Google in 2025 and no longer receives updates; `google-genai` is the official successor with the same models. |
| `gemini-2.5-flash` as default model | Pro models | Fast, cheap and enough for claim splitting/repair; changeable in one line of `config.yaml`. |
| Cache key includes model + temperature | Prompt only | Changing the model or temperature must not silently return an old answer. |
| Retry only on 429/5xx | Retry on every error | A 400 (bad request) will fail again; retrying wastes time. (A unit test caught a bug here: an error whose *message* mentioned "rate limit" but had code 400 was retried. Fixed: HTTP code now takes priority.) |
| Python 3.11 venv, CPU torch | System Python 3.14 | Stable wheels for torch/transformers; the CPU-only build keeps the install small (CLAUDE.md: CPU must be enough). |
| Own markdown-table writer | `DataFrame.to_markdown()` | Avoids an extra dependency (`tabulate`). |

### 5. How to verify it yourself
```bash
cd "e:\CLIENT'S\FACTINDIC"
venv\Scripts\python -m src.synth                  # -> Wrote 128 articles / Wrote 512 error rows
venv\Scripts\python -m src.data                   # -> 9/9 checks passed -> ALL PASS
venv\Scripts\python -m experiments.dataset_stats  # -> prints 6 tables, saves results/dataset_stats/
venv\Scripts\python -m pytest -v                  # -> 20 passed
git log --oneline                                 # -> Step 1: setup, data loading, dataset stats
```
Re-running `src.synth` produces byte-identical files (checked by
`test_generator_is_deterministic`); `results/dataset_stats/run_meta.json` stores the SHA-256 of
both data files so you can prove which version a table came from.

### 6. Results / numbers
* 128 articles (64 Hindi, 64 Hinglish), 8 domains × 8 articles per language.
* Split: **dev 40 articles (31.3 %) / test 88 (68.7 %)** → 160 dev rows / 352 test rows.
* 512 summary rows: 128 CORRECT + 384 ERROR (number_swap 77, date_swap 77, entity_swap 77,
  negation 77, unsupported_addition 76).
* Mean length: article 77.2 words (419.7 chars), summary 35.3 words (195.4 chars),
  compression ratio 2.2.
* Gold claims: 5.25 per summary on average (min 5, max 6), 672 in total.
* Source conditions: 29 Hindi articles with Devanagari digits; 66 articles with spelling noise
  (31 Hindi, 35 Hinglish).
* Key facts: 640 total = 384 entity (60 %), 128 number (20 %), 128 date (20 %).
* Validation 9/9 PASS; unit tests 20/20 pass.

Full tables: `results/dataset_stats/dataset_stats.md`; figure:
`results/dataset_stats/error_types_by_language.png`.

### 7. For the research paper → **Dataset** section
Draft sentences:
1. We construct FactIndic-Synth, a controlled benchmark of 128 news-style articles (64 Hindi in
   Devanagari script and 64 Hindi–English code-mixed in Latin script) spanning eight domains,
   each paired with a reference summary and 5–6 gold atomic claims.
2. Articles are generated from domain-specific templates whose slots (persons, organisations,
   locations, quantities, dates and a polarity phrase) are sampled with a fixed seed, which gives
   exact character-level gold annotations for every key fact.
3. For each article we derive one faithful summary and three corrupted summaries, each
   containing exactly one injected error of a distinct type (number swap, date swap, entity swap,
   negation flip or unsupported addition), resulting in 512 summary instances balanced across
   error types (76–77 instances per type).
4. To approximate real-world input noise, a subset of source documents contains Devanagari
   numerals (29 of 64 Hindi articles) or informal spelling variation (66 of 128 articles), while
   summaries remain in standard orthography.
5. The data is split by article into a development set (40 articles, 160 summaries) used
   exclusively for threshold tuning and a held-out test set (88 articles, 352 summaries) used for
   all reported results, which prevents leakage between faithful and corrupted versions of the
   same article.

### 8. Limitations / things to watch
* **Synthetic and template-based.** Only one template per domain × language, so sentence
  structure repeats; models may find the task easier than on real summaries. Results on this
  benchmark are an upper bound and must be described as such. A small real-data evaluation
  (e.g. human-checked LLM summaries of real Hindi news) would strengthen the paper.
* **Errors are clean and single.** Real hallucinations are often partial, paraphrased, or
  multiple per summary.
* **Key-fact distribution is fixed** (3 entities, 1 number, 1 date per article), so the
  60/20/20 split is by construction, not a finding.
* **Spelling noise is rule-based** and covers a small list of variants.
* **Negation is lexical** (adding/removing नहीं / *nahi*); implicit negation ("refused to") is
  not covered.
* **Hinglish is romanised only;** mixed-script Hinglish (Devanagari + Latin in one sentence) is
  absent.
* Split ratio is 31/69 rather than exactly 30/70 because whole articles are assigned per
  language × domain cell.
* `gemini-2.5-flash` availability may change; the cache makes past results reproducible, but
  new calls depend on the API.

### 9. Concepts to understand
* **Atomic claim:** the smallest fact that can be true or false on its own. "Sunita Sharma, president
  of Jan Vikas Party, addressed a rally in Jaipur on 20 Jan" contains several: who she is, where,
  when. Checking them separately tells us *which* part is wrong.
* **Synthetic error injection:** we take a correct summary and deliberately break one fact. Because
  we broke it ourselves, we know the right answer – this is how we get "gold labels" without
  paying human annotators.
* **Dev / test split and data leakage:** we tune settings (like the NLI threshold) on *dev* and
  only report scores on *test*, which the system has never "seen". If the same article appeared in
  both, the system could learn its facts on dev and look better on test than it really is –
  that is *leakage*. Splitting by article prevents it.
* **Stratification:** when splitting, we make sure each language × domain group is represented in
  both dev and test, so neither set is accidentally all-sports or all-Hindi.
* **Random seed / reproducibility:** computers generate "random" numbers from a starting number
  (the seed). Same seed → same "random" choices → same dataset every time.
* **Caching (memoisation):** saving the answer to a question so the second time you ask, you read
  it from disk instead of paying for and waiting on the API again. It also guarantees the
  experiment gives the same output tomorrow.
* **Hash (SHA-256):** a function that turns any text into a fixed 64-character fingerprint. Same
  text → same fingerprint; a one-letter change → a completely different one. We use it as the
  cache key and to fingerprint data files.
* **Exponential backoff:** when the API says "too many requests" (HTTP 429), wait 2 s, then 4 s,
  then 8 s… before retrying, so we don't hammer the server.
* **NLI labels (preview):** Natural Language Inference asks "given the premise (source), is the
  hypothesis (claim) *entailed* (must be true), *contradicted* (must be false), or *neutral*
  (can't tell)?". A swapped date contradicts the source; an added fact the source never mentions
  is neutral. That is why `expected_nli` differs by error type.
* **Compression ratio:** article length ÷ summary length (here ≈2.2×). Higher means the summary
  drops more information.
* **Unit test:** a tiny automatic check of one function ("if I corrupt a span, does `validate()`
  notice?"). We run them after every change so new code can't silently break old code.
