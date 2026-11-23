# FactIndic – Research Log (lab notebook)

Running record of every step: what was built, why, how to reproduce it, and draft paper text.

---

## Dataset – provenance and file inventory (updated 2026-11-24)

**There is exactly ONE dataset in this project, and every step uses it.**

| File | Rows | Size | SHA-256 | Created by |
|---|---|---|---|---|
| `data/factindic_synth_articles.jsonl` | 128 articles | 267,900 bytes | `8428bec7…2fd92` | `python -m src.synth` (seed 42), Step 1 |
| `data/factindic_synth_errors.jsonl` | 512 summary rows | 926,492 bytes | `acbd2854…e3a3` | same run |

* **Origin.** The files were *not* supplied with the project: `data/` was empty when Step 1
  started. On the author's instruction ("do it by yourself") they were **generated** by the
  template-based generator `src/synth.py` (8 domains × 2 languages × 8 articles; 1 correct + 3
  single-error summaries per article). Re-running the generator reproduces them byte for byte
  (`tests/test_synth.py::test_generator_is_deterministic`).
* **Unchanged since Step 1.** The hashes above equal those stored in
  `results/dataset_stats/run_meta.json`, and git shows no change to `data/` after commit
  `593d923`.
* **No other or harder dataset exists.** The Step 3 "pooled stress test" is an *evaluation
  setting*, not a dataset: at evaluation time it groups the sentences of all articles in the same
  language × domain × split into one candidate pool (35–42 sentences on test, 14–21 on dev).
  Nothing is written to `data/`.
* **Sample IDs used as examples** (all from these files): `hi001` (Step 1), `hi025-E3` (Step 2;
  test split, entity swap विकास यादव → नेहा गुप्ता, Sanjeevani Medical College, Gwalior),
  `hi013-E3` (Step 3).
* **If an external FactIndic release becomes available**, put it in `data/` under the same file
  names and re-run `python -m src.data`, `python -m experiments.dataset_stats` and every later
  experiment; all tables in this log would need to be regenerated, and the derived gold evidence
  in Step 3 relies on generator templates (`src.synth.DOMAINS`), which an external dataset
  would not have.

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

---

## Step 2 – Claim decomposition without an LLM (2026-11-24)

> Run without a Gemini API key, by decision of the author. The `llm` method is implemented
> and unit-tested with a fake backend, but was **not evaluated**; it skips with a clear message.
> Results folder: `results/decomposition/run_20261124_012257/`.

### 1. What I built
A module that breaks a summary into small claims that can each be checked against the source.
It has four interchangeable methods: `sentence` (one claim per sentence, the simplest baseline),
`clause` (sentences further split at ", + connective word" such as *जिसके / jiske / जहाँ /
yeh*), `gold` (the hand-made claims in the dataset, used as an "oracle" upper bound), and `llm`
(Gemini, for later). Rule-based claims remember their exact character position in the summary,
so later steps can say *which* claim holds the error and repair only that span. An experiment
script measures how atomic, complete and self-contained the claims are, and whether each
injected error lands in exactly one claim.

### 2. Files created / changed
| File | Purpose | Key functions |
|---|---|---|
| `src/decompose.py` | Claim decomposition | `decompose()` (dispatcher), `sentence_spans()`, `clause_spans()`, `decompose_sentence/clause/gold/llm()`, `is_context_dependent()`, `claims_overlapping()`, `Claim` dataclass |
| `experiments/run_decomposition.py` | Compare methods; write tables | `reference_rows()`, `error_rows()`, `summarise()` |
| `tests/test_decompose.py` | 13 tests (abbreviations, decimals, clause split, span alignment, every error localised, LLM path with fake backend) | |
| `config.yaml` | new `decomposition.method: clause` | |
| `results/decomposition/run_<ts>/` | `claims_reference.jsonl`, `error_localisation.jsonl`, 3 CSV tables, `results.md`, `config.json` | |

### 3. How it works
1. **Sentence split.** Walk through the text; a `।`, `॥`, `.`, `!` or `?` followed by a space
   (or the end) ends a sentence, *unless* the "." belongs to an abbreviation (`Dr.`, `डॉ.`,
   `Prof.`, …) or a single-letter initial (`A. K. Singh`). Decimals such as `3.5` are safe
   because no space follows the dot. This matters: `Dr.`/`डॉ.` occur 48 times in our data.
2. **Clause split.** Inside each sentence, split at a comma followed by a connective word from
   a fixed list of Hindi and romanised connectives (relative words *जिसके, जिसकी, जहाँ, जो /
   jiske, jiski, jahan, jo*; conjunctions *और, लेकिन, जबकि / aur, lekin, jabki*; demonstrative
   *यह / yeh*). A comma *without* a connective (e.g. the list "Rajesh, Sunita aur Amit") is not
   split. The first part gets a sentence terminator added (`।` if the text contains Devanagari,
   else `.`).
3. Each claim stores `(start, end)` in the summary. For an error row, the claim(s) overlapping
   `[span_start, span_end)` are the error claim(s).

**Worked example (`hi025-E3`, entity swap, test split).** The candidate summary says the camp
in-charge was डॉ. **नेहा गुप्ता**, but the source says डॉ. **विकास यादव**.

| Method | Claims (error claim marked ⚠) |
|---|---|
| sentence | #1 (0–118) संजीवनी मेडिकल कॉलेज ने 18 सितंबर 2024 को ग्वालियर में मुफ़्त स्वास्थ्य शिविर लगाया, जिसके प्रभारी डॉ. नेहा गुप्ता थे। ⚠ · #2 शिविर में 1080 मरीज़ों की जाँच की गई। · #3 किसी गंभीर बीमारी का मामला सामने नहीं आया। |
| clause | #1 (0–83) संजीवनी मेडिकल कॉलेज ने 18 सितंबर 2024 को ग्वालियर में मुफ़्त स्वास्थ्य शिविर लगाया। · #2 (85–118) जिसके प्रभारी डॉ. नेहा गुप्ता थे। ⚠ · #3 … · #4 … |

With `sentence`, the error claim also carries the college, the date and the city, so NLI must
judge four facts at once and a repair would rewrite 59 % of the summary. With `clause`, the
error claim contains only the wrong name (17 % of the text). `डॉ.` did not cause a false
sentence break. The price: claim #2 starts with *जिसके* ("whose"), so on its own it does not
say *whose* in-charge – it is context-dependent.

### 4. Design decisions & why
| Decision | Alternatives | Why |
|---|---|---|
| Rule-based `clause` as default | LLM decomposition; dependency parser (Stanza/spaCy) | No API key (author's choice). Parsers for romanised Hinglish are unreliable and add a heavy dependency; a connective list works for both scripts and is fully transparent. |
| Keep character spans | Return plain strings | Needed for localising errors and for "repair ONLY the flagged claim". LLM/gold claims are rewritten text, so they get `start=end=-1`. |
| Split only at comma + connective | Split at every comma; split at every *और/aur* | Every-comma splitting breaks lists; splitting on bare *और* breaks noun phrases ("हिंदी और अंग्रेज़ी"). |
| Abbreviation list incl. `डॉ.` | Naive split on "." | Hindi uses "।" for sentences but "." in `डॉ.`; Hinglish uses "." for both. A naive split would cut 24 summaries in the middle of a name. |
| Do not resolve pronouns | Replace *उन्होंने/Unhone* with the previous subject | Finding the right antecedent needs NER/coreference; a wrong guess would *create* an error. We measure the problem instead (`context_dep_rate`) and let retrieval + NLI see the evidence. |
| Include `gold` as an oracle | Only compare system methods | Shows the ceiling and how far rule-based splitting is from truly atomic claims. |
| Report dev and test | Report test only | Nothing is tuned in this step, so both are clean; test is the headline. |

### 5. How to verify it yourself
```bash
venv\Scripts\python -m pytest tests/test_decompose.py -v        # 13 passed
venv\Scripts\python -m experiments.run_decomposition --methods sentence clause gold llm
#  [ok] sentence: 384 claims | [ok] clause: 464 claims | [ok] gold: 672 claims
#  [skip] method=llm: LLMConfigError: GEMINI_API_KEY is not set ...
venv\Scripts\python -m pytest -q                                 # 33 passed (whole project)
```

### 6. Results (test split: 88 reference summaries, 264 error summaries)
| Method | claims / summary | facts / claim | atomic (≤1 fact) % | fact coverage % | context-dependent % | error localised % | collateral facts in error claim | text touched by repair % |
|---|---|---|---|---|---|---|---|---|
| sentence | 3.00 | 1.67 | 66.7 | 100 | 3.8 | 100 | 1.19 | 35.5 |
| **clause** | 3.65 | 1.37 | 69.2 | 100 | 20.9 | 100 | 0.83 | 29.3 |
| gold (oracle) | 5.26 | 1.07 | 76.5 | 100 | 0.0 | – | – | – |

By error type (test, sentence → clause): for **date swaps** collateral facts drop 3.00 → 2.22
and text touched 57 % → 43 %; for **entity swaps** 3.00 → 1.94 and 57 % → 40 %. Number,
negation and addition errors already sit in short sentences (≈0 collateral facts, ≈21 % of
text) under both methods. Dev numbers are within ±1 point of test; Hindi and Hinglish behave
almost identically.

**Interpretation.** Both rule-based methods lose no information (100 % coverage) and put every
error into exactly one claim. Clause splitting makes claims more focused but makes 1 in 5
claims context-dependent. Neither reaches the oracle: the first sentence of each summary packs
organisation + person + date + place into one clause, which cannot be separated without
*rewriting* the sentence – exactly what an LLM decomposer would add.

### 7. For the research paper → **Methodology** (claim decomposition) and **Results** (ablation)
1. We decompose each summary into claims with a rule-based splitter that first segments
   sentences using script-aware terminators (।, ., ?, !) with an abbreviation list covering
   both Latin (*Dr.*) and Devanagari (*डॉ.*) forms, and then splits sentences at clause
   boundaries defined as a comma followed by a Hindi or romanised-Hindi connective (e.g.,
   *जिसके/jiske*, *जहाँ/jahan*, *यह/yeh*).
2. Each claim retains its character offsets in the summary, which allows errors to be
   localised to a single claim and enables span-restricted repair.
3. We compare this clause-level splitter with a sentence-level baseline and with the gold
   atomic claims as an oracle upper bound.
4. On the test set, clause-level decomposition yields 3.65 claims per summary (vs. 3.00 for
   sentences and 5.26 for gold claims), preserves all key facts, and localises every injected
   error to exactly one claim, while reducing the number of unrelated key facts sharing the
   erroneous claim from 1.19 to 0.83.
5. However, 20.9 % of clause-level claims begin with a pronoun or relative marker and are
   therefore not self-contained, which motivates retrieving evidence from the full source
   rather than verifying claims in isolation.

### 8. Limitations / things to watch
* **Built for our templates.** The connective list comes from general Hindi grammar, but I
  inspected sample summaries (from both splits) before writing it, and our synthetic summaries
  happen to use exactly these constructions. Results are optimistic; real LLM summaries will
  have more varied clause boundaries (no commas, participle clauses, *ki* clauses).
* **Not truly atomic.** 1.37 facts per claim vs 1.07 for gold; date/entity errors still share
  their claim with ~2 other facts, so NLI must judge a multi-fact claim.
* **"Atomic ≤ 1 fact" is an imperfect measure.** Relational claims ("X is president of Y")
  legitimately contain two facts – that is why even gold scores only 76 %.
* **Pronouns unresolved** (20.9 % context-dependent claims). A claim like "जिसके प्रभारी डॉ. X
  थे" can only be verified if retrieval brings back the right source sentence.
* **100 % localisation is partly by construction:** each injected error lies inside one
  template sentence. Real errors may span several claims.
* Fact matching uses exact substrings of key-fact values; fine for rule-based claims (copied
  text) but would undercount an LLM decomposer that paraphrases or transliterates names.
* Two generator phrasings are slightly unnatural Hindi ("कोई शुल्क लिया जाता नहीं है"); harmless
  for decomposition, but worth fixing if the dataset is regenerated.
* The `llm` method is untested on real model outputs.

### 9. Concepts to understand
* **Claim decomposition / atomic facts:** checking a long sentence is hard because one wrong
  part makes the whole sentence "wrong" but you don't know *which* part. Cutting it into small
  claims gives fine-grained verdicts. This idea comes from FActScore (Min et al., 2023).
* **Sentence segmentation:** sounds trivial but isn't – a "." can end a sentence, an
  abbreviation (`Dr.`) or a number (`3.5`). Hindi uses the *danda* `।` as its full stop.
* **Clause:** a part of a sentence with its own verb. "The camp was held, *whose in-charge was
  Dr. X*" has two clauses → two claims.
* **Connective:** a word that links clauses (*and, but, which, where* / *और, लेकिन, जिसके,
  जहाँ*).
* **Decontextualisation & coreference:** "*He* did not announce an alliance" – to check it
  alone you need to know who "he" is. Replacing pronouns with the person they refer to is
  called coreference resolution; we measure the problem but do not solve it yet.
* **Oracle / upper bound:** using the perfect answer (gold claims) to see the best possible
  result. If even the oracle performs poorly later, the bottleneck is not decomposition.
* **Ablation:** comparing versions of a system that differ in one component (here: how claims
  are made) to measure that component's effect.
* **Localisation:** pointing to *where* the error is. "Claim #2 is wrong" is far more useful
  than "this summary is wrong", and it is what makes selective repair possible.

---

## Step 3 – Evidence retrieval (2026-11-24)

> Results folder: `results/retrieval/run_20261124_015054/`. No API key needed (LaBSE runs locally).

### 1. What I built
For every claim, the retriever ranks the sentences of the source article and returns the top-k
(k = 3) as evidence, each with its score and character position in the source. Three scorers
are implemented: **lexical** (character n-gram TF-IDF – compares surface spelling), **LaBSE**
(multilingual sentence embeddings – compares meaning) and **hybrid** (a weighted mix). A shared
text normaliser (`src/textnorm.py`) can convert Devanagari digits to 0-9, drop the nukta and
lowercase before scoring; it will be reused by the rule checks. The experiment evaluates 13
configurations on dev, picks one with a rule fixed in advance, reports test results, and adds a
harder "pooled" stress test because the normal setting turned out to be too easy.

### 2. Files created / changed
| File | Purpose | Key functions |
|---|---|---|
| `src/textnorm.py` | Script-aware normalisation | `normalize()`, `normalize_digits()`, `strip_nukta()` |
| `src/retrieve.py` | Retrieval | `Retriever.retrieve()`, `.retrieve_many()`, `.score()`, `Embedder.encode()` (disk-cached LaBSE), `lexical_scores()`, `split_source()`, `Evidence` |
| `experiments/run_retrieval.py` | Gold-evidence derivation, metrics, dev selection, stress test | `build_items()`, `relevant_sets()`, `build_pools()`, `score_items()`, `agg()` |
| `tests/test_retrieve.py` | 8 tests (normaliser, 7 sentences per source, lexical ranking, embedding cache, Devanagari-digit retrieval for all 3 methods) – uses a fake embedding model, so no download | |
| `config.yaml` | `retrieval.method: lexical`, `normalize: false`, `alpha: 0.5` (selected on dev) | |
| `cache/embeddings_sentence-transformers__LaBSE.pkl` | LaBSE vectors cache (git-ignored) | |

### 3. How it works
1. **Split the source** into sentences with the Step 2 splitter (every article → exactly 7
   sentences: 5 template sentences + 2 fillers; checked by a test).
2. **Score** every (claim, sentence) pair:
   * *lexical*: break both texts into overlapping 2–4-character pieces ("टीम", "ीम ", …), weight
     rare pieces higher (TF-IDF), compare with cosine similarity;
   * *LaBSE*: turn each text into a 768-number vector that captures meaning, compare with cosine;
   * *hybrid*: `alpha · LaBSE + (1 − alpha) · lexical`.
3. **Rank** sentences by score and return the top-k.

**Gold evidence (how we know the right answer).** The dataset has no evidence labels, so they are
derived: a claim's *facts* are the key-fact values it contains (for an error claim the *original*
value is added, because retrieval should find the sentence that disproves it). A sentence is
relevant for a fact if it contains it (digits normalised). Claims with no key fact are polarity
claims ("…घोषणा नहीं की"); their relevant sentence is the one generated from the `{pol}` template
sentence. **full_recall@k** = all of a claim's facts are covered by the top-k sentences (some
claims need two sentences, e.g. in sports the date/place/team are in S0 but the captain is in S1).

**Worked example (`hi013-E3`, number swap, source written in Devanagari digits).**
Claim: *टीम ने 152 रन बनाए।* (the source says २५३ runs).

| Rank | lexical score | LaBSE score | Sentence |
|---|---|---|---|
| 1 | 0.372 | 0.725 | S2 टीम ने पहले बल्लेबाज़ी करते हुए **२५३** रन बनाए। ✅ (the evidence that disproves the claim) |
| 2 | 0.226 | 0.711 | S3 विपक्षी टीम केवल **१२५** रन ही बना सकी। (distractor number) |
| 3 | 0.145 | 0.508 | S1 कप्तान नेहा गुप्ता ने टीम का नेतृत्व किया। |

Both methods rank the right sentence first, but the distractor is second, and LaBSE separates
them by only 0.014. The verifier (next step) must therefore look at the *right* sentence, not
just "any number in the top-3".

### 4. Design decisions & why
| Decision | Alternatives | Why |
|---|---|---|
| Char 2–4-gram TF-IDF as the lexical scorer | BM25 on words | Words break on spelling noise (*mein/me*, *बेरोज़गारी/बेरोजगारी*) and on unsegmented Hinglish; character pieces still overlap. No tokenizer needed for either script. |
| IDF fitted per article (its sentences + its claims) | One global IDF | Self-contained and deterministic; no information from other articles or from test data. |
| Evaluate error claims too | Reference claims only | In the real pipeline we retrieve evidence for *wrong* claims; a swapped name could pull retrieval to the wrong sentence. |
| Pre-registered selection order: full_recall@3 → MRR → stress recall@3 → simplicity | Pick the best number | 10 of 13 configs tied on dev; without a fixed rule the "winner" would be arbitrary (the first run picked α = 0.1 only because of table order). I wrote the rule before seeing stress results. |
| Pooled stress test | Only the normal setting | The normal setting has a ceiling (7 candidate sentences, all methods 100 % at k = 3). Pooling all same-language × domain × split articles creates near-duplicate distractors (same template, different names/numbers), which shows *how* methods differ. Pools never mix dev and test. |
| Keep k = 3 | k = 1 | full_recall@1 is capped below 100 % because ~12 % of date claims need two sentences. |
| Cache LaBSE vectors by sha256(text) | Re-encode each run | Re-running all 13 configs costs seconds instead of minutes; same text → same vector. |

### 5. How to verify it yourself
```bash
venv\Scripts\python -m pytest tests/test_retrieve.py -v       # 8 passed (no model download)
venv\Scripts\python -m pytest -q                               # 41 passed
venv\Scripts\python -m experiments.run_retrieval               # ~3 min first time (LaBSE), then fast
#  772 claims (464 reference, 308 error); articles with !=7 source sentences: 0
#  ==> selected on dev: lexical
venv\Scripts\python -c "from src.retrieve import Retriever; [print(e.rank, round(e.score,3), e.text) for e in Retriever().retrieve('टीम ने 152 रन बनाए।', 'टीम ने पहले बल्लेबाज़ी करते हुए २५३ रन बनाए। विपक्षी टीम केवल १२५ रन ही बना सकी।')]"
```

### 6. Results
**Dev selection (239 claims).** All lexical and hybrid (α ≤ 0.8) configs tie at
full_recall@3 = 100 %, MRR = 1.000; LaBSE alone is marginally lower (MRR 0.996, hit@1 99.2 %).
Stress recall@3 ties at 99.2 % for lexical, lexical+norm, hybrid α = 0.1/0.2 → simplicity picks
**lexical**.

**Test – own source (pipeline setting; 321 reference + 212 error claims).**
| Config | full_recall@1 (ref / err) | full_recall@3 (ref / err) | hit@1 err | MRR err |
|---|---|---|---|---|
| **lexical (selected)** | 96.9 / 95.3 | 100 / 100 | 99.5 | 0.998 |
| lexical+norm | 96.9 / 95.3 | 100 / 100 | 99.5 | 0.998 |
| labse | 96.9 / 93.4 | 100 / 100 | 97.6 | 0.987 |
| labse+norm | 96.9 / 93.9 | 100 / 100 | 98.1 | 0.991 |
| hybrid+norm α=0.5 | 96.9 / 95.8 | 100 / 100 | 100 | 1.000 |

No condition (language, Devanagari digits, spelling noise) drops below 100 % full_recall@3.

**Test – pooled stress test (5–6 near-duplicate articles per pool, 35–42 candidate sentences).**
| Config | full_recall@3 ref | full_recall@3 err | MRR ref | number claims R@1 | polarity claims R@3 |
|---|---|---|---|---|---|
| lexical | 93.1 | 67.0 | 0.847 | 52.4 | 65.0 |
| lexical+norm | **96.3** | 66.5 | **0.891** | 64.6 | 65.7 |
| labse | 93.1 | 67.0 | 0.873 | 61.9 | 62.0 |
| labse+norm | 93.5 | 64.6 | 0.872 | 64.6 | 64.2 |
| hybrid+norm α=0.5 | 95.3 | 65.1 | 0.891 | 66.0 | 65.0 |

**Interpretation.**
* In the real pipeline setting retrieval is *not* a bottleneck: with k = 3 every claim gets all
  the evidence it needs, for every method. Any later errors come from verification, not retrieval.
* The stress test shows where methods differ: **digit normalisation** helps lexical retrieval of
  number claims (R@1 52.4 → 64.6) because "२५३" and "253" share no characters otherwise.
  LaBSE handles digit scripts somewhat on its own (61.9 without normalisation).
* **Error claims are much harder** in the stress setting (≈65–67 % vs 93–96 %): a claim containing
  a wrong value pulls retrieval towards other articles' sentences. In the normal setting this
  does not happen because all candidates come from the right article.
* Polarity claims are almost impossible to tell apart in pools (same template, only नहीं differs),
  which is expected and not a weakness of any method.

### 7. For the research paper → **Methodology** (evidence retrieval), **Experimental Setup**, **Results**
1. For each claim we rank the sentences of the source document and retain the top-k (k = 3) as
   evidence, comparing a character 2–4-gram TF-IDF scorer, LaBSE sentence embeddings, and a
   linear interpolation of both, each with and without script normalisation (Devanagari-to-ASCII
   digits, nukta removal, lowercasing).
2. Because the benchmark has no evidence annotations, we derive gold evidence from key-fact
   overlap, using the original value for corrupted claims and the polarity sentence for claims
   without key facts.
3. Configurations were selected on the development set using a pre-specified order of criteria
   (full recall@3, MRR, recall@3 in a pooled stress test, and simplicity), which selected the
   lexical scorer.
4. On the test set, all configurations retrieve complete evidence for every claim at k = 3
   (full recall@3 = 100 %), indicating that retrieval is not a bottleneck when candidates are
   restricted to the source document.
5. In a harder pooled setting with near-duplicate distractor articles, digit normalisation
   improves top-1 recall for numeric claims from 52.4 % to 64.6 % for the lexical scorer, and
   recall for corrupted claims drops to roughly 65–67 % for all methods, showing that erroneous
   content can mislead retrieval when distractors are present.

### 8. Limitations / things to watch
* **Ceiling effect.** 7-sentence sources make the main setting trivial; the benchmark cannot
  separate retrieval methods there. Real articles are longer and paraphrased – LaBSE's
  advantage (meaning over spelling) is expected to matter more on real data and is under-tested
  here.
* **Selected method is "lexical" without normalisation**, but lexical+norm ties on every dev
  criterion except stress MRR (0.887 vs 0.866), and is clearly better for numbers in the stress
  test. Since our rule did not include stress MRR, we keep the rule's result; switching later
  is a one-line config change and would not change pipeline results at k = 3.
* **Gold evidence is derived automatically** from key facts and template positions; it is exact
  for this synthetic data but would need human annotation on real data.
* Hybrid scores mix two different scales (TF-IDF cosine ≈ 0.1–0.4, LaBSE cosine ≈ 0.5–0.9), so α
  is not an intuitive "percentage of LaBSE".
* Differences of < 1 point on 212–321 claims are 1–3 claims and not meaningful.
* LaBSE download (1.8 GB) is needed once; afterwards runs offline.

### 9. Concepts to understand
* **Information retrieval & ranking:** given a query (the claim), order a collection (source
  sentences) by relevance. We keep the top-k.
* **Recall@k:** "is the right answer among the first k results?" Our *full* recall@k requires
  *all* needed sentences to be there (a claim may need two).
* **MRR (Mean Reciprocal Rank):** if the first relevant result is at rank 1 you score 1, at rank 2
  you score ½, rank 3 → ⅓, … averaged over claims. 1.0 = always first.
* **TF-IDF:** a way to turn text into numbers: count pieces (TF = term frequency) and down-weight
  pieces that appear everywhere (IDF = inverse document frequency), so distinctive pieces matter
  more.
* **Character n-grams:** overlapping chunks of n characters. "kiya" and "kia" share "ki", so
  spelling variants still look similar – useful for noisy Hinglish.
* **Sentence embeddings & LaBSE:** a neural network maps a sentence to a vector (here 768
  numbers) so that sentences with similar meaning get similar vectors – even across languages
  and scripts. LaBSE (Language-agnostic BERT Sentence Embedding, Feng et al., 2022) was trained
  on translation pairs in 109 languages.
* **Cosine similarity:** the angle between two vectors: 1 = same direction (very similar), 0 =
  unrelated. It ignores length, so long and short sentences can still match.
* **Ceiling effect:** when a test is so easy that every method scores ~100 %, it cannot tell them
  apart. The fix is a harder test (our stress test).
* **Pre-registration of selection criteria:** deciding *before* looking at results how you will
  pick the winner, so you cannot (even unconsciously) choose the rule that makes your favourite
  look best.
* **Hard negatives / distractors:** wrong candidates that look very similar to the right one (same
  template, different number). They are what makes retrieval difficult in practice.

---

## Step 3b – Per-language retriever selection on DEV (2026-11-24)

> Requested review: compare LaBSE vs lexical+norm on DEV per language (and noisy vs clean
> Hinglish), apply the pre-registered rule; if no single winner in both languages, use a hybrid
> (mean of normalised scores). Results: `results/retrieval/dev_breakdown_20261124_021128/`.

**Change to the hybrid.** "Average of the two normalised scores" is now implemented literally:
`retrieval.score_norm: minmax` rescales each scorer to [0, 1] across a claim's candidate
sentences, then averages (α = 0.5). This also removes the scale mismatch noted in Step 3
(TF-IDF ≈ 0.1–0.4 vs LaBSE ≈ 0.5–0.9). New function `src.retrieve.minmax_rows()` + 1 test.

**DEV results (own source; stress = pooled same-language × domain × dev articles).**

| Group | Config | full R@1 | full R@3 | hit@1 | MRR | n | stress R@3 | stress MRR |
|---|---|---|---|---|---|---|---|---|
| Hindi | **lexical+norm** | 94.9 | 100 | 100 | **1.000** | 118 | 98.3 | 0.894 |
| Hindi | labse | 94.1 | 100 | 99.2 | 0.996 | 118 | 100 | 0.873 |
| Hindi | labse+norm *(baseline)* | 94.1 | 100 | 99.2 | 0.996 | 118 | 100 | 0.881 |
| Hindi | hybrid-minmax+norm *(baseline)* | 94.9 | 100 | 100 | 1.000 | 118 | 100 | 0.884 |
| Hinglish | **lexical+norm** | 95.9 | 100 | 100 | **1.000** | 121 | 100 | 0.880 |
| Hinglish | labse | 95.0 | 100 | 99.2 | 0.996 | 121 | 95.9 | 0.873 |
| Hinglish | labse+norm *(baseline)* | 94.2 | 100 | 98.3 | 0.992 | 121 | 95.0 | 0.868 |
| Hinglish | hybrid-minmax+norm *(baseline)* | 95.9 | 100 | 100 | 1.000 | 121 | 98.3 | 0.883 |

| Hinglish subset | Config | full R@1 | full R@3 | hit@1 | MRR | n | stress R@3 | stress MRR |
|---|---|---|---|---|---|---|---|---|
| clean | lexical+norm | 92.3 | 100 | 100 | 1.000 | 52 | 100 | 0.891 |
| clean | labse | 90.4 | 100 | 98.1 | 0.990 | 52 | 90.4 | 0.886 |
| noisy | lexical+norm | 98.6 | 100 | 100 | 1.000 | 69 | 100 | 0.872 |
| noisy | labse | 98.6 | 100 | 100 | 1.000 | 69 | 100 | 0.862 |

**Rule applied (DEV only).** Criteria in order: full R@3 → MRR → stress R@3 → simplicity.
Hindi: tie on R@3, **lexical+norm wins on MRR** (1.000 vs 0.996). Hinglish: tie on R@3,
**lexical+norm wins on MRR** (1.000 vs 0.996). Same winner in both languages → **default =
lexical+norm** (`config.yaml: method: lexical, normalize: true`). LaBSE, LaBSE+norm and the
min-max hybrid remain reported baselines.

**Honest reading.** The deciding margin is one claim per language (MRR 0.996 = one claim with
its evidence at rank 2). The two retrievers are practically equivalent on this data; the choice
is defensible (pre-registered, simpler, no 1.8 GB model) but not evidence that lexical retrieval
is generally better. Interesting detail: spelling noise did *not* hurt either method on dev
(noisy Hinglish full R@1 98.6 % vs clean 90–92 %). The gap is explained by claim mix, not
noise: 4 of 52 clean claims (7.7 %) need two sentences, which caps R@1 at 92.3 % – exactly what
lexical+norm reaches – versus 1 of 69 noisy claims (cap 98.6 %, also reached).

**For the paper (Experimental Setup).** "The retriever was selected on the development set
separately for each language using a pre-specified order of criteria; lexical retrieval with
script normalisation was preferred in both Hindi and Hinglish (MRR 1.000 vs 0.996 for LaBSE),
and LaBSE and a min–max-normalised hybrid are reported as baselines."
