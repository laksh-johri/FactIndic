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

---

## Step 4 – Claim verification: NLI + rule checks + decision rule (2026-11-24)

> Results folder: `results/verification/run_20261124_125224/`. No API key used. NLI model
> `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` on CPU (1,592 unique
> premise–claim pairs; slow on CPU the first time, then cached in `cache/nli_*.pkl`, so re-runs take seconds).

### 1. What I built
The verifier takes every claim (Step 2) with its top-3 evidence sentences (Step 3) and decides
SUPPORTED / CONTRADICTED / UNSUPPORTED / REVIEW. It combines two judges: a **multilingual NLI
model**, which reads the evidence and the claim and says whether the evidence *entails*,
*contradicts* or is *neutral* about the claim, and four **exact rule checks** (numbers, dates,
negation, entities) that compare specific values. The decision rule from CLAUDE.md combines
them: a claim is SUPPORTED only if NLI says entailment *and* all rules pass. A summary is
flagged as erroneous if any of its claims is not SUPPORTED. Two settings (which evidence to
give NLI, and the confidence threshold τ) were tuned on dev; everything is reported on test,
together with ablations (NLI only, rules only, full system minus one rule).

### 2. Files created / changed
| File | Purpose | Key functions |
|---|---|---|
| `src/nli.py` | NLI model wrapper, disk cache, saves every 128 pairs | `NLIModel.predict()`, `nli_label()` |
| `src/rules.py` | Exact checks with human-readable reasons | `check_numbers()`, `check_dates()`, `check_negation()`, `check_entities()`, `run_rules()`, `build_safe_vocab()`, `numbers()`, `dates()` |
| `src/verify.py` | The decision rule + ablation modes | `decide()`, `summary_flagged()`, `Verdict` |
| `experiments/run_verification.py` | Full pipeline on 512 summaries, dev grid, test metrics, ablations | `prepare()`, `apply()`, `summary_level()`, `metrics()`, `tune()` |
| `tests/test_verify.py` | 9 tests (number/date extraction incl. Devanagari digits and nukta month names, each rule, decision rule incl. ablation modes, NLI cache with fake model) | |
| `config.yaml` | `verification.nli_threshold: 0.5`, `nli_premise: top1`, `rules: [...]` | |

### 3. How it works
1. **Rule checks** (all on the top-3 evidence; text normalised first):
   * *numbers*: every number in the claim must appear in the evidence (२५३ = 253);
   * *dates*: every "day month year" in the claim must appear in the evidence (Hindi and English
     month names, spelling variants such as फरवरी/फ़रवरी);
   * *negation*: the claim and the best evidence sentence must both contain, or both lack, a
     negation word (नहीं, न, मत, nahi, nahin, not, …);
   * *entities*: no "novel" content word may appear – a word that is in neither the evidence
     nor a **safe vocabulary**. The safe vocabulary is learned from the 40 dev reference
     summaries (all their words except their key-fact values), i.e. the summariser's normal
     paraphrase words such as *लगाया* or *organise*. A swapped name like *नेहा गुप्ता* is in
     neither, so it fails. (This replaces a named-entity recogniser, which we do not have for
     romanised Hinglish.)
2. **NLI**: premise = evidence, hypothesis = claim → probabilities for entailment / neutral /
   contradiction. Two premise options: `top1` (best evidence sentence) or `concat` (the 3
   evidence sentences in source order).
3. **Decision rule** with threshold τ: any rule fails → CONTRADICTED; else P(entail) ≥ τ →
   SUPPORTED; P(contradict) ≥ τ → CONTRADICTED; P(neutral) ≥ τ → UNSUPPORTED; else REVIEW.
4. **Tuning on dev** (rule fixed before running): grid premise ∈ {concat, top1} × τ ∈ {0.50,
   0.55, …, 0.95}; pick highest summary-level *balanced accuracy*, then lowest REVIEW rate,
   then concat, then lowest τ. Selected: **top1, τ = 0.50** (both for the full system and for
   NLI-only).

**Worked example (`hi013`, sports, Hindi, test; source written in Devanagari digits).**

| Row | Claim | Best evidence | NLI e/n/c | Rules failed | Verdict |
|---|---|---|---|---|---|
| hi013-E3 | टीम ने **152** रन बनाए। | टीम ने पहले बल्लेबाज़ी करते हुए **२५३** रन बनाए। | 0.19 / 0.03 / 0.78 | numbers: "[152] not found in evidence ['125','253']" | **CONTRADICTED** ✅ |
| hi013-C | टीम ने 253 रन बनाए। | (same) | 0.95 / 0.04 / 0.02 | – | **SUPPORTED** ✅ |
| hi013-C & E3 | 27 जनवरी 2024 को रांची में हुए मुकाबले में सनराइज़ क्लब की कप्तानी नेहा गुप्ता ने की। | २७ जनवरी २०२४ को रांची में खेले गए मुकाबले में सनराइज़ क्लब ने शानदार प्रदर्शन किया। | 0.14 / 0.31 / 0.55 | – | **CONTRADICTED** ❌ (false alarm) |

The number error is caught by *both* judges. The third row is a false alarm: the captain's name
is in a *different* source sentence (S1), and with the `top1` premise the NLI model never sees
it, so it reads "Neha Gupta captained" as contradicting a sentence that does not mention her.
Because of this one claim, the correct summary `hi013-C` is wrongly flagged.

### 4. Design decisions & why
| Decision | Alternatives | Why |
|---|---|---|
| Rules override NLI when they fail | Vote; NLI overrides rules | Required by the CLAUDE.md decision rule, and rules are exact: if the number is not in the evidence, no fluent sentence can make the claim true. |
| Single τ for all three NLI labels, τ ≥ 0.5 | Separate thresholds; argmax | With τ ≥ 0.5 at most one label can pass, so the rule is unambiguous and has one parameter to tune on 160 dev summaries. Below threshold → REVIEW implements "low confidence → human". |
| Balanced accuracy as the dev objective | F1 on ERROR; accuracy | 75 % of summaries contain an error; F1/accuracy would reward flagging *everything*. Balanced accuracy weighs catching errors and passing correct summaries equally. |
| Entity check = novel words outside a dev-learned safe vocabulary | NER model (IndicNER); capitalisation | No NER handles romanised Hinglish; capitalisation does not exist in Devanagari. Learning the safe vocabulary from dev *reference* summaries (known faithful) only uses dev labels. |
| Negation compared with the top-1 evidence sentence only | Any of the top-3 | Another evidence sentence may legitimately contain a negation about something else. |
| Count REVIEW as "flagged" | Count REVIEW as passed | A REVIEW claim goes to a human, so the summary is not auto-approved. |
| Fair ablations: NLI-only tuned on dev in the same way | Reuse full-system settings | Otherwise the NLI-only baseline would be handicapped. |
| NLI cache saved every 128 pairs | Save at the end | The first run was killed after ~10 min and lost everything; chunked saving makes runs resumable. |

### 5. How to verify it yourself
```bash
venv\Scripts\python -m pytest -q                         # 51 passed
venv\Scripts\python -m experiments.run_verification      # slow the first time (NLI on CPU), seconds afterwards (cached)
#  1932 claims from 512 summaries; running NLI on 1592 unique pairs ...
#  DEV-selected full system: {'premise': 'top1', 'tau': 0.5} | NLI-only: {'premise': 'top1', 'tau': 0.5}
#  TEST main ... full (NLI + rules) 352 88.6 100.0 94.0 61.4 80.7 ...
```

### 6. Results (TEST: 352 summaries = 88 correct + 264 with one error; 1,336 claims)
**Summary-level detection** (positive class = ERROR; REVIEW counts as flagged).
| System | Precision | Recall | F1 | Specificity | Balanced acc. | REVIEW rate (claims) | Error claim flagged | Exact localisation |
|---|---|---|---|---|---|---|---|---|
| Rules only | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |
| NLI only (top1, τ=0.5) | 88.6 | 99.6 | 93.8 | 61.4 | 80.5 | 5.3 | 100.0 | 67.7 |
| **Full: NLI + rules** | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 4.7 | 100.0 | 67.8 |
| Full − numbers / − dates / − entities | identical to full (other judges catch the same errors) | | | | | | | |
| Full − negation | 88.6 | 99.6 | 93.8 | 61.4 | 80.5 | 4.7 | 100.0 | 67.7 |

**Detection rate by error type** (none = false-alarm rate on correct summaries).
| System | none | number | date | entity | negation | addition |
|---|---|---|---|---|---|---|
| Rules only | 0.0 | 100 | 100 | 100 | 100 | 100 |
| NLI only | 38.6 | 100 | 100 | 100 | 98.0 | 100 |
| Full | 38.6 | 100 | 100 | 100 | 100 | 100 |

**By language (full).** Hindi: specificity 52.3, balanced acc. 76.1. Hinglish: specificity 70.5,
balanced acc. 85.2. Recall is 100 % in both.

**Claim-level confusion (full; rows = expected, columns = predicted).**
| expected \ predicted | CONTRADICTED | REVIEW | SUPPORTED | UNSUPPORTED |
|---|---|---|---|---|
| CONTRADICTED (212) | **212** | 0 | 0 | 0 |
| SUPPORTED (1,072) | 22 | 63 | **914** | 73 |
| UNSUPPORTED (52) | 52 | 0 | **0** | 0 |

**Which judge catches the error claim?** Rules fail on all 264 error claims; NLI also rejects
263 of them (the exception is one negation claim). Rule failure rates on *correct* claims: 0.0 %
for all four rules.

**Interpretation – the main finding of this step.**
1. **Every injected error is detected** (recall 100 %), and the error claim is always among the
   flagged claims.
2. **All false alarms come from NLI.** The rules never fire on correct claims, but NLI rejects
   14.7 % of correct claims (158 / 1,072), which makes 38.6 % of correct summaries flagged.
   Because the CLAUDE.md rule requires NLI entailment for SUPPORTED, adding NLI to the rules
   *lowers* balanced accuracy from 100 to 80.7 on this benchmark.
3. **The false alarms are concentrated, not random.** By domain: health, environment and
   technology 0 %; infrastructure 4.6 %; education 8.7 %; business 31.1 %; sports 53.6 %;
   politics 55.8 %. They come from only **43 distinct claim strings**. Two causes are visible:
   (a) *multi-sentence claims* with the `top1` premise (e.g. the sports captain is in a
   different sentence, so NLI says contradiction); (b) a *template-specific NLI failure*:
   "सभा में लगभग N लोग शामिल हुए" against its almost identical source sentence gets
   neutral ≈ 0.93. Two hypotheses I tested and **rejected**: reported-speech evidence
   ("आयोजकों के अनुसार…": 16.1 % vs 14.2 % false alarms) and Devanagari digits in the evidence
   (27.6 % vs 31.5 % on Hindi number claims) – neither explains the errors.
4. **Unsupported additions get the wrong *type* of verdict.** All 52 are flagged, but as
   CONTRADICTED (a rule – usually entities – fails, and the rule says "rule fails →
   CONTRADICTED"), never as the expected UNSUPPORTED.
5. **The rules' 100 % is an upper bound by construction.** The errors were injected by swapping
   exactly the things the rules check, and the safe vocabulary is learned from same-template
   dev summaries. Do not present it as general rule performance.

### 7. For the research paper → **Methodology** (verification), **Experimental Setup** (tuning), **Results**, **Error Analysis**
1. Each claim is verified against its retrieved evidence by a multilingual NLI model
   (mDeBERTa-v3-base fine-tuned on XNLI and multilingual NLI data) and by four deterministic
   checks for numbers, dates, negation and novel entities, the latter using a vocabulary of
   non-entity summary words learned from development-set reference summaries.
2. A claim is labelled SUPPORTED only if the NLI entailment probability exceeds a threshold τ and
   all checks pass; any failed check yields CONTRADICTED, and claims for which no NLI label
   exceeds τ are routed to human review.
3. The premise construction and τ were selected on the development set by maximising
   summary-level balanced accuracy, yielding the single best evidence sentence as premise and
   τ = 0.5.
4. On the test set the full system detects all 264 corrupted summaries (recall 100 %) and
   always flags the corrupted claim, but it also flags 38.6 % of faithful summaries (precision
   88.6 %, balanced accuracy 80.7 %); all false alarms originate from the NLI component, as the
   rule checks never fire on faithful claims.
5. False alarms are concentrated in three of eight domains (31–56 % of faithful claims in
   politics, sports and business versus 0 % in health, environment and technology), arising
   from claims whose support spans two source sentences and from template-specific NLI
   failures on near-verbatim paraphrases.
6. Because the rule checks target exactly the error types used for corruption, their perfect
   scores should be read as an upper bound for this synthetic benchmark rather than as an
   estimate of real-world performance.

### 8. Limitations / things to watch
* **The benchmark is too easy for the rules** (by construction). Real hallucinations
  (paraphrased wrong facts, wrong relations between correct entities, partial truths) would
  slip past them; that is where NLI should help, and this dataset cannot show it.
* **The decision rule, not the components, limits the score here.** Requiring NLI entailment for
  SUPPORTED turns every NLI miss into a false alarm. This is a design question for you (see
  "Open question" below), not something I changed.
* **τ = 0.5 is at the edge of the allowed range**, so the optimum may be lower than the rule
  permits.
* **top1 vs concat was decided by one dev summary** (balanced acc. 77.5 vs 76.2); the two are
  practically equivalent. top1 hurts multi-sentence claims, concat dilutes others.
* **Small, correlated test set.** 88 correct summaries; false alarms come from 43 distinct
  claim strings in 3 templates, so the effective sample size is much smaller than 1,336 claims.
  A different template set could give very different specificity.
* **Entity check is a heuristic**, not NER: on real summaries any new paraphrase word would be
  "novel" and cause false alarms; the safe vocabulary only works because test summaries reuse
  dev templates.
* **Additions are labelled CONTRADICTED instead of UNSUPPORTED**; for *detection* this does not
  matter, but a repair step that treats contradictions and additions differently would need the
  type to be right.
* NLI input is the raw (un-normalised) evidence text; we did not test normalising the premise
  (doing it now would use knowledge gained from test – it must be tested on dev first).

**Open question for the author (affects Step 5+).** Options for the decision rule:
(a) keep it as specified (current); (b) let NLI *non-entailment without a rule failure* become
REVIEW instead of CONTRADICTED/UNSUPPORTED, so humans check them; (c) use `concat` premise for
claims whose key facts span several sentences. Any change must be re-tuned on dev only.

### 9. Concepts to understand
* **NLI (Natural Language Inference):** a model reads a *premise* (evidence) and a *hypothesis*
  (claim) and outputs three probabilities: *entailment* (if the premise is true, the claim must
  be true), *contradiction* (the claim must be false) and *neutral* (can't tell). Ours is
  mDeBERTa-v3, a multilingual transformer trained on millions of NLI examples in ~100 languages.
* **Rule-based vs learned checks:** rules are exact and explainable but only catch what they were
  written for; learned models generalise to new phrasings but make unpredictable mistakes. Hybrid
  systems try to get the best of both.
* **Threshold (τ):** the minimum probability we accept before trusting a label. Higher τ = more
  cautious = more REVIEW.
* **Confusion matrix:** a table of *expected* vs *predicted* labels; the diagonal is correct.
* **Precision / recall / F1:** precision = of the summaries we flagged, how many really had an
  error; recall = of the summaries that had an error, how many we flagged; F1 = their harmonic
  mean (high only if both are high).
* **Specificity:** of the *correct* summaries, how many we left alone. A detector that flags
  everything has recall 100 % but specificity 0 %.
* **Balanced accuracy:** (recall + specificity) / 2 – fair when classes are imbalanced (here
  75 % errors).
* **Ablation:** remove one component and re-measure to learn what it contributes ("full −
  negation").
* **False alarm (false positive):** flagging a correct summary as wrong. Costly in practice:
  users stop trusting a tool that cries wolf.
* **Upper bound by construction:** a score that is perfect because the test was built in the
  same way as the method, not because the method is generally that good.
* **Correlated errors / effective sample size:** 158 wrong claims that are really 43 repeated
  sentences carry much less evidence than 158 independent mistakes.

**Decision recorded (2026-11-24).** The author chose option **(a)**: keep the decision rule
exactly as specified in CLAUDE.md (SUPPORTED requires NLI entailment AND all rules passing).
Options (b) "NLI-only rejections → REVIEW" and (c) "concat premise for multi-sentence claims"
were considered and not adopted; they can be mentioned in the paper as future work. All later
steps use the Step 4 configuration (`config.yaml: verification`).

---

## Step 5 – Selective repair and re-check (pipeline steps 5 + 6) (2026-11-24)

> No API key: repair is rule-based and copies values from the retrieved evidence. Decision rule
> unchanged (option a). Results: `results/repair/run_20261124_131002/`.

### 1. What I built
A repair module that fixes **only the claims the verifier flagged**, and only inside their exact
character span in the summary. What it does depends on *which* rule check failed: a wrong number,
date or name is replaced with the matching value copied from the evidence; a wrong negation is
flipped by inserting or removing नहीं / *nahi*; content that has no counterpart in the source is
deleted. If no rule failed (the claim was flagged only by NLI) or no safe replacement exists,
the text is left unchanged and marked for human review. Then every output summary is verified
again with the full Step 4 pipeline (pipeline step 6): if all claims are SUPPORTED it is
auto-accepted, otherwise it goes to a human. Outputs are judged against the gold reference
summary, and compared with "no repair", a crude "delete every flagged claim" baseline, and our
repair given *perfect* detection (oracle).

### 2. Files created / changed
| File | Purpose | Key functions |
|---|---|---|
| `src/repair.py` | Evidence-based selective repair | `repair_summary()`, `repair_entity()`, `repair_date()`, `repair_numbers()`, `repair_negation()`, `delete_claim()`, `apply_edits()`, `pick()`, `render_date()` |
| `experiments/run_repair.py` | 4 systems × 512 summaries, gold outcome, content metrics, re-check | `run_systems()`, `gold_outcome()`, `add_content_metrics()`, `recheck()`, `summarise()` |
| `experiments/run_verification.py` | `prepare()` now accepts any set of summaries (needed for re-checking) | `prepare(cfg, errors=None, premises=...)` |
| `tests/test_repair.py` | 13 tests: each repair type in both scripts, decoy number not chosen, May/मई rendering, deletion, NLI-only flags untouched, adjacent deletions merged, gold-outcome definition | |

### 3. How it works
1. For each flagged claim, look at the failed rules.
2. **Find a replacement in the evidence.** Candidates (numbers, dates, or "entity-like" word runs
   that are not ordinary summary/source words) are scored by **context**: does the word before
   and/or after the candidate in the evidence match the word before/after the wrong value in the
   claim? Ties are broken by evidence rank. No context match, or a tie → no guess.
3. **Write the value in the summary's style:** ASCII digits even when the source uses २५३;
   month names in the claim's script (जनवरी vs January).
4. **Delete** a claim when its unsupported content is not a single replaceable name (typical for
   added sentences) or when no evidence entity fits.
5. **Re-check:** decompose, retrieve, rules + NLI again on the edited summary.

**Worked example (`hi013-E3`, number swap, source in Devanagari digits).**

| | Text |
|---|---|
| Input | 27 जनवरी 2024 को रांची में हुए मुकाबले में सनराइज़ क्लब की कप्तानी नेहा गुप्ता ने की। टीम ने **152** रन बनाए। बारिश के कारण मैच को बीच में रोका नहीं गया। |
| Edits | claim #2: `replace_number 152 → 253` ("number copied from evidence": टीम ने पहले बल्लेबाज़ी करते हुए **२५३** रन बनाए। – not the decoy १२५, because "रन" matches and its evidence rank is higher); claim #1: `review` (flagged by NLI only – the Step 4 false alarm) |
| Output | 27 जनवरी 2024 को … नेहा गुप्ता ने की। टीम ने **253** रन बनाए। बारिश … रोका नहीं गया। |
| Gold outcome | **complete** (identical to the reference) |
| Re-check | **human review** – claim #1 is still rejected by NLI |
| Delete-flagged baseline | "बारिश के कारण मैच को बीच में रोका नहीं गया।" – faithful, but 2 of 3 facts lost |

**A conservative failure (`hi028-E1`, location swap जयपुर ← गोरखपुर).** In the summary the city
sits between "को … में", in the source it starts the sentence ("गोरखपुर के स्वस्थ भारत ट्रस्ट
ने …"), so no context word matches. The repair refuses to guess and deletes the first clause:
the output is faithful but loses facts, and starts with a dangling "जिसके प्रभारी डॉ. पूजा
रस्तोगी थे।".

### 4. Design decisions & why
| Decision | Alternatives | Why |
|---|---|---|
| Repair driven by the failed rule | Rewrite the whole claim; LLM rewrite | No API key; the failed rule tells us *what* is wrong, so the edit can be minimal and explained. |
| Values copied only from evidence, chosen by context + rank | Take "the" number in the top sentence; use the gold answer | The evidence often contains a decoy number (Step 3); using gold would be cheating. |
| Ambiguity → no edit (review) / delete | Always guess | A wrong guess *creates* a new error; for a fact checker, saying "I don't know" is safer. |
| NLI-only flags are never edited | Delete them | NLI flags have no pinpointed cause and 14.7 % of correct claims are NLI false alarms (Step 4); editing them would damage correct summaries. |
| Strict gold outcome: "lossy" = whole claims removed | "Output can be made by deleting characters" | Found during this step: deleting characters can delete नहीं and reverse the meaning; the first definition wrongly counted 30 un-repaired error summaries as faithful. |
| Separate "empty" outcome | Count as lossy or erroneous | An empty summary has no false facts but is useless; it is reported on its own. |
| Oracle-detection variant | Only the real system | Separates "is detection the bottleneck?" from "is repair the bottleneck?". |

**Bugs found and fixed in this step (by tests and sanity checks):** (1) "May" has only three
letters and crashed the English month renderer; (2) when two neighbouring claims were deleted,
their spans overlapped by one space and one deletion was silently dropped – in the baseline this
left the erroneous claim in place; overlapping deletions are now merged.

### 5. How to verify it yourself
```bash
venv\Scripts\python -m pytest -q                     # 64 passed
venv\Scripts\python -m experiments.run_repair        # fast (NLI cached); prints TEST/DEV tables
#  TEST main ... selective  352  0.0  98.1  100.0  0.0  100.0  0.0  99.2  99.7  3.4  61.4  100.0
```

### 6. Results (TEST: 352 summaries; DEV in `dev_main.csv`, same pattern)
| System | Erroneous summaries % | Errors fixed exactly % (ERROR rows) | Faithful % (ERROR rows) | Empty % | Correct summaries untouched % | Key-fact retention % | Similarity to reference % | Chars changed % | Auto-accepted after re-check % | Faithful among auto-accepted % |
|---|---|---|---|---|---|---|---|---|---|---|
| No repair | **75.0** | 0.0 | 0.0 | 0.0 | 100 | 90.7 | 96.9 | 0.0 | 15.3 | 100 |
| Delete flagged claims | 0.0 | 12.1 | 92.8 | 6.8 | 61.4 | 61.8 | 74.4 | 27.3 | 92.9 | 100 |
| **Selective repair (ours)** | **0.0** | **98.1** | **100** | 0.0 | **100** | **99.2** | **99.7** | **3.4** | 61.4 | 100 |
| Selective + oracle detection | 0.0 | 98.1 | 100 | 0.0 | 100 | 99.2 | 99.7 | 3.4 | 61.4 | 100 |

**Per error type (selective, test):** exact fix 100 % for number, date, negation and addition
errors; **89.8 % for entity swaps** – the other 10.2 % (5 summaries, location/organisation swaps
in a different syntactic position) were deleted instead (faithful, lossy). Actions taken:
59 number replacements, 55 date replacements, 44 entity replacements, 49 negation flips,
57 deletions (52 additions + 5 entity fallbacks), and 158 "review" marks (all NLI-only flags,
which never change text). By language: exact fix 98.5 % Hindi, 97.7 % Hinglish; auto-accepted
52.3 % Hindi vs 70.5 % Hinglish.

**Interpretation – answer to the research question on this benchmark.**
1. **Selective correction removes all injected errors (75 % → 0 % erroneous) while preserving
   content:** 99.2 % of key facts kept, only 3.4 % of characters changed, and every correct
   summary left exactly as it was.
2. **Being selective matters.** Deleting every flagged claim also removes the errors, but keeps
   only 61.8 % of key facts, changes 27 % of the text, damages 39 % of the correct summaries and
   produces 24 empty summaries.
3. **Detection is not the bottleneck for repair here:** the oracle-detection variant gives
   identical outputs, because NLI false alarms are never edited and the rules flag exactly the
   error claims.
4. **The remaining cost is human review:** after re-check 38.6 % of summaries still go to a
   human, all because of the NLI false alarms from Step 4 (option a keeps NLI as a hard
   requirement). Every auto-accepted summary is faithful (100 %).
5. **Repair is conservative by design:** when unsure it deletes or defers; it never introduced a
   new error in any output (0 erroneous outputs).

### 7. For the research paper → **Methodology** (4.5 repair, 4.6 re-check), **Results** (6.2), **Limitations**
1. Flagged claims are repaired in place, within their character span, by operations determined by
   the failed check: numbers, dates and entities are replaced with the context-matching value from
   the retrieved evidence, negation is inserted or removed to match the evidence polarity, and
   content without a counterpart in the evidence is deleted; claims flagged only by NLI are not
   edited but routed to human review.
2. Repaired summaries are re-verified with the same pipeline and auto-accepted only if every claim
   is supported.
3. On the test set, selective repair reduces the proportion of erroneous summaries from 75.0 % to
   0.0 %, restores 98.1 % of corrupted summaries exactly to their reference, retains 99.2 % of key
   facts and changes 3.4 % of characters, while leaving all faithful summaries unchanged.
4. In contrast, deleting all flagged claims also removes the errors but retains only 61.8 % of key
   facts and leaves 6.8 % of summaries empty.
5. Repair with oracle detection yields identical results, indicating that on this benchmark the
   remaining cost lies in the 38.6 % of summaries that are routed to human review because of NLI
   false alarms rather than in detection or correction errors.

### 8. Limitations / things to watch
* **Very favourable setting.** Each summary has exactly one error, of a type the rules detect,
  and the correct value is always in the retrieved evidence (Step 3). Real errors (paraphrased,
  multiple, or with no counterpart in the source) would be much harder; these numbers are an
  upper bound.
* **Context heuristic is template-friendly.** It relies on the neighbouring words of the wrong
  value matching the source. It failed for 5 location/organisation swaps where the source phrases
  the sentence differently; I found this on test data and did **not** tune for it.
* **Deleting a leading clause can leave ungrammatical text** (a dangling "जिसके …" / "jiske …").
  Faithful, but not fluent; an LLM rewrite step would fix this.
* **Unsupported additions are deleted, not marked** – right for a summary, but the user does not
  see what was removed unless the edit log is shown (the demo should show it).
* **Exact-match evaluation** works only because the dataset gives a reference summary that differs
  from the candidate in one span; real repairs would need human or NLI-based evaluation.
* **38.6 % human-review load** is high and comes from the decision rule + NLI false alarms, not
  from repair.

### 9. Concepts to understand
* **Selective (targeted) correction:** change only what is proven wrong, keep everything else –
  the opposite of regenerating the whole summary.
* **Edit / character span:** a change described as "(for example) replace characters 63–66 with '253'". Because
  every claim knows its span (Step 2), edits never touch other claims.
* **Context matching:** choosing between candidate values by looking at their neighbouring words –
  a tiny version of how alignment works in machine translation.
* **Oracle experiment:** replace one component with a perfect version to see how much the rest of
  the system loses because of that component.
* **Precision over recall in repair:** for a fact-checker, a wrong "fix" is worse than no fix, so the
  system abstains (review) or deletes when uncertain.
* **Content preservation metrics:** key-fact retention (are the important facts still there?),
  similarity to reference, and percentage of characters changed (how invasive was the repair?).
* **Human-in-the-loop:** the system handles what it is sure about and sends the rest to a person;
  "auto-accepted %" vs "human review %" measures the workload.

---

## Step 6 – Interactive Streamlit demo (2026-11-24)

> No API key, no new tuning: the demo calls the same code and `config.yaml` settings as Steps 2–5.
> No new experiment numbers; the check is that it reproduces Step 5 exactly.

### 1. What I built
A web app (`app.py`, Streamlit) that shows the whole FactIndic pipeline on one summary at a
time. You either pick a benchmark example (filter by split, language, error type) or paste your
own source article and summary. The app then shows, step by step:
- the summary with every claim coloured by its verdict;
- for each claim, the top-3 evidence sentences, the four rule checks and the NLI probabilities;
- the repair edits as a table and as a red/green word diff;
- the re-check of the repaired summary, with the final decision: auto-accepted or human review.

For benchmark examples, a hidden-by-default "Gold answer" box shows the injected error, the
reference summary and whether the final output is complete / lossy / erroneous.

To keep the demo honest, I put the single-summary logic into its own module
(`src/pipeline.py`), and a test checks that it gives *exactly* the Step 5 outputs for all 512
summaries.

### 2. Files created / changed
| File | Purpose | Key functions |
|---|---|---|
| `src/pipeline.py` | Steps 2–6 for ONE (source, summary) pair, same components + config as the experiments | `FactIndicPipeline.verify()`, `.run()`, `ClaimResult`, `PipelineResult.to_dict()` |
| `src/render.py` | HTML helpers: claim highlighting, verdict badges, word-level diff (all text HTML-escaped) | `highlight_claims()`, `diff_html()`, `badge()` |
| `app.py` | Streamlit UI: input sidebar, 4 result sections, gold box, JSON download, benchmark-results tab, "how it works" tab | `sidebar_input()`, `show_result()`, `show_claim_details()`, `show_gold()`, `show_benchmark_tab()` |
| `tests/test_pipeline.py` | 5 tests incl. **exact reproduction of all 512 Step 5 outputs** | |
| `tests/test_render.py` | 3 tests incl. HTML-escaping of user text | |
| `tests/test_app.py` | 3 headless app tests (Streamlit `AppTest`): default example, a number swap, own-text mode | |
| `docs/paper_outline.md` | new §4.7 Interactive demonstrator | |

### 3. How it works
`FactIndicPipeline.run(source, summary)`:
1. `verify()`: clause decomposition → top-3 evidence (lexical+norm) → rule checks → NLI with the
   rank-1 evidence sentence as premise → decision rule with τ = 0.5. All settings are read from
   `config.yaml`, and the safe vocabulary is learned from DEV only, as in Steps 4–5.
2. `repair_summary()` on the flagged claims (Step 5).
3. `verify()` again on the repaired text (Step 6) → `accepted` if every claim is SUPPORTED, else
   `human_review`. An empty output also goes to human review.

The app caches the pipeline object (`st.cache_resource`), so the models load once.
Benchmark examples hit the NLI disk cache and appear instantly. New text needs the NLI model:
the first run loaded it in a few seconds, and the full run took about 24 s on CPU.

**Worked example in the app (`hi013-E3`, test, Hindi, number swap):**
- ① **Claims and verdicts:** 3 claims; #1 CONTRADICTED, #2 CONTRADICTED, #3 SUPPORTED.
  - Claim #2: "टीम ने 152 रन बनाए।" The numbers rule fails: 152 is not in the evidence ['125', '253'].
  - Claim #1: CONTRADICTED by NLI alone (contradiction 0.55), while all four rules pass. This is the
    known NLI false alarm from Step 4.
- ② **Evidence for claim #2:** rank 1 = "टीम ने पहले बल्लेबाज़ी करते हुए २५३ रन बनाए।".
  - Rule table: numbers ❌ fail, dates ➖ n/a, negation ✅ pass, entities ✅ pass.
- ③ **Repair:** one row `replace number | 152 | 253 | number copied from evidence`; the diff shows
  ~~152~~ **253**.
  - Claim #1 shows "no edit → human review".
- ④ **Re-check:** claims #2 and #3 are SUPPORTED, but #1 is still CONTRADICTED by NLI → "Sent to human review".
  - Gold box: "complete – output identical to the reference".

**Example with new text (not in the dataset), run with the real NLI model:**
- **Source:** "Indore mein 5 April 2025 ko ek blood donation camp lagaya gaya. Camp mein 410 logon
  ne blood donate kiya. … Organisers ne bataya ki kisi bhi donor se fee nahi li gayi."
- **Summary:** "… Camp mein **140** logon ne blood donate kiya. **Donors se fee li gayi.**"
- **Verdicts:**
  - 140 → CONTRADICTED (numbers rule fails).
  - "Donors se fee li gayi." → CONTRADICTED. The negation rule fails, and NLI gives contradiction
    0.95.
- **Output:** "… Camp mein **410** logon ne blood donate kiya. **donor** se fee **nahi** li gayi."
  → re-check: accepted.
- **Two imperfections visible here (see Limitations):**
  - The entity rule treated the plural "Donors" as an unknown name and replaced it with "donor".
  - The sentence now starts with a lowercase letter.

### 4. Design decisions & why
| Decision | Alternatives | Why |
|---|---|---|
| New `src/pipeline.py` used by the app | Write the logic inside `app.py`; reuse the batch experiment code | UI code is hard to test; the batch code works on DataFrames of 512 rows. A small single-pair module can be unit-tested and checked against Step 5. |
| Exact-reproduction test on all 512 summaries | Test a few examples | Proves the demo shows *the system evaluated in the paper*, not a slightly different copy. The test uses only the NLI cache (a backend that raises proves no new model call). |
| Settings read-only in the sidebar (no τ slider) | Let the user change τ, retriever, rules | τ and the retriever were chosen on DEV by pre-registered rules; a slider would invite "tuning by eye". This could be added later as a clearly labelled "what-if" mode. |
| Gold answer hidden in an expander, benchmark only | Always show it | The system never sees the gold answer; hiding it first lets a viewer judge the output like a human reviewer would. |
| HTML-escape all text | Render raw text | The app accepts free text; un-escaped text could inject HTML/JS into the page. |
| Semi-transparent colours | Solid colours | Readable in both light and dark Streamlit themes. |
| Default free-text example = `hg002-E3` (Hinglish location swap) | Empty boxes | Shows a working Hinglish example immediately and hits the NLI cache (fast). |
| No summary generation (pipeline step 1) in the demo | Call Gemini | No API key; CLAUDE.md forbids hard-coded keys. When a key is added, `src/llm.py` can generate the summary first. |
| JSON download of the full result | – | Lets a human reviewer keep the evidence + edit log; also handy for the paper's qualitative examples. |

### 5. How to verify it yourself
```bash
venv\Scripts\python -m pytest -q                 # 75 passed (64 old + 11 new)
venv\Scripts\streamlit run app.py                # opens http://localhost:8501
```
In the browser, try these:
- Sidebar → Benchmark example → test / hindi / number_swap → `hi013-E3`. You should see 152 → 253
  and gold outcome "complete".
- "Your own text" → change a number in the summary → the number is flagged and repaired.
- Tab "Benchmark results" → the Step 4 and Step 5 test tables.

### 6. Results
- **No new metrics.** This step is a tool, not an experiment.
- **Consistency check:** the demo pipeline reproduces the Step 5 repaired text, the list of edit
  actions and the final status (accepted / human review) for **512 / 512** summaries
  (`tests/test_pipeline.py`).
- **Runtime on CPU:**
  - Benchmark examples are instant (NLI cache).
  - New text loaded the NLI model in a few seconds; the whole run, including model load, took
    about 24 s.

### 7. For the research paper → **Methodology §4.7** (or a "System demonstration" paragraph / appendix)
1. The full pipeline is exposed in a browser-based demonstrator that accepts either a benchmark
   example or a user-supplied source–summary pair.
2. For every claim it displays the verdict, the retrieved evidence sentences with their retrieval
   scores, the outcome of each rule check and the NLI class probabilities, followed by the applied
   edits as a word-level diff and the re-verification result.
3. The demonstrator calls the same code and configuration as the experiments and reproduces the
   stored repair outputs and routing decisions for all 512 benchmark summaries exactly.
4. It runs on a CPU without any external API, which makes the evidence behind every decision
   inspectable by a human reviewer.

### 8. Limitations / things to watch
* **The demo shows the system's weaknesses on real text.**
  - The entity rule uses a safe vocabulary learned from our templates, so ordinary words it has
    not seen (a plural like "Donors") count as "new entities".
  - Repair can then lower-case the first word of a sentence.
  - On real news text, expect many more false flags than on the benchmark.
* **No summary generation:** pipeline step 1 needs an LLM API key, so the demo starts from a
  given summary.
* **First run on new text is slow:** the NLI model has to load (a few seconds here). It is cached
  afterwards, so later runs are faster.
* **Not a user study:** we did not measure whether the evidence display actually helps human
  reviewers. That would be future work.
* **Single user, local:** the NLI disk cache is written by the app; this is fine for a demo, but
  not a production server.

### 9. Concepts to understand
* **Demo vs. experiment:**
  - An experiment measures the system on many examples.
  - A demo shows one example in detail, so people can *see* why the system decided something.
  - Both must use the same code, or the demo shows a different system than the paper.
* **Reproducibility / consistency test:** running the same inputs through two code paths and
  checking that the outputs are identical. Here that is the batch experiment vs. the single-summary
  pipeline.
* **Caching:** storing results that are expensive to compute (model loading, NLI predictions) so
  they are not recomputed.
  - `st.cache_resource` keeps the loaded model in memory.
  - The NLI disk cache keeps predictions between runs.
* **Explainability through evidence:** instead of a black-box "wrong", the system shows *which*
  source sentence, *which* rule and *which* NLI score led to the verdict. This is what "shows
  source evidence for every decision" in our project goal means.
* **HTML escaping:** converting characters like `<` into `&lt;` so user text is displayed as
  text and never executed as web code.
* **Headless UI testing:** Streamlit's `AppTest` runs the app without a browser and lets a test
  click widgets and read what is displayed.
