# FactIndic – Paper Outline

Working title: *FactIndic: Claim-Level Verification and Selective Repair of Factual Errors in
Hindi and Hinglish Summaries*

## Abstract
[TODO – write last: problem, method (claim decomposition → evidence retrieval → NLI + rule
checks → selective repair), dataset, headline numbers, takeaway.]

## 1. Introduction
[TODO – hallucination in LLM summaries; low-resource / code-mixed gap for Hindi and Hinglish;
research question; contributions list.]

## 2. Related Work
[TODO – factual consistency metrics (QAGS, SummaC, FactCC, AlignScore); claim-level
verification (FActScore); post-hoc correction; multilingual NLI; Indic and code-mixed NLP.]

## 3. Dataset

We construct FactIndic-Synth, a controlled benchmark of 128 news-style articles (64 Hindi in
Devanagari script and 64 Hindi–English code-mixed in Latin script) spanning eight domains
(politics, sports, business, health, education, environment, technology, infrastructure), each
paired with a reference summary and 5–6 gold atomic claims. Articles are generated from
domain-specific templates whose slots (persons, organisations, locations, quantities, dates and a
polarity phrase) are sampled with a fixed seed, which yields exact character-level gold
annotations for every key fact. Each source additionally contains a distractor quantity that does
not appear in the summary.

For each article we derive one faithful summary and three corrupted summaries, each containing
exactly one injected error of a distinct type (number swap, date swap, entity swap, negation flip
or unsupported addition), resulting in 512 summary instances balanced across error types (76–77
instances per type). To approximate real-world input noise, a subset of source documents contains
Devanagari numerals (29 of 64 Hindi articles) or informal spelling variation (66 of 128
articles), while summaries remain in standard orthography. The data is split by article into a
development set (40 articles, 160 summaries) used exclusively for threshold tuning and a held-out
test set (88 articles, 352 summaries) used for all reported results, which prevents leakage
between faithful and corrupted versions of the same article.

#### Table 1. Articles per language x domain x split

| language | domain | dev | test | total |
|---|---|---|---|---|
| hindi | business | 3 | 5 | 8 |
| hindi | education | 2 | 6 | 8 |
| hindi | environment | 3 | 5 | 8 |
| hindi | health | 2 | 6 | 8 |
| hindi | infrastructure | 2 | 6 | 8 |
| hindi | politics | 3 | 5 | 8 |
| hindi | sports | 3 | 5 | 8 |
| hindi | technology | 2 | 6 | 8 |
| hinglish | business | 2 | 6 | 8 |
| hinglish | education | 3 | 5 | 8 |
| hinglish | environment | 2 | 6 | 8 |
| hinglish | health | 2 | 6 | 8 |
| hinglish | infrastructure | 3 | 5 | 8 |
| hinglish | politics | 3 | 5 | 8 |
| hinglish | sports | 3 | 5 | 8 |
| hinglish | technology | 2 | 6 | 8 |
| total |  | 40 | 88 | 128 |

#### Table 2. Summary rows per error type x language x split

| error_type | hindi_dev | hindi_test | hinglish_dev | hinglish_test | total |
|---|---|---|---|---|---|
| none | 20 | 44 | 20 | 44 | 128 |
| number_swap | 9 | 32 | 9 | 27 | 77 |
| date_swap | 10 | 26 | 12 | 29 | 77 |
| entity_swap | 14 | 22 | 14 | 27 | 77 |
| negation | 14 | 27 | 14 | 22 | 77 |
| unsupported_addition | 13 | 25 | 11 | 27 | 76 |
| total | 80 | 176 | 80 | 176 | 512 |

#### Table 3. Mean article and summary length

| language | article_words | article_chars | summary_words | summary_chars | compression_ratio_words |
|---|---|---|---|---|---|
| hindi | 77.1 | 396.5 | 35.4 | 186.0 | 2.2 |
| hinglish | 77.4 | 443.0 | 35.2 | 204.8 | 2.2 |
| all | 77.2 | 419.7 | 35.3 | 195.4 | 2.2 |

#### Table 4. Gold atomic claims per reference summary

| language | mean_claims | min_claims | max_claims | total_claims |
|---|---|---|---|---|
| hindi | 5.2 | 5 | 6 | 336 |
| hinglish | 5.2 | 5 | 6 | 336 |
| all | 5.2 | 5 | 6 | 672 |

#### Table 5. Source-side robustness conditions (article counts)

| language | articles | devanagari_digits | spelling_noise |
|---|---|---|---|
| hindi | 64 | 29 | 31 |
| hinglish | 64 | 0 | 35 |
| all | 128 | 29 | 66 |

#### Table 6. Key-fact type distribution

| type | hindi | hinglish | total | share_% |
|---|---|---|---|---|
| date | 64 | 64 | 128 | 20.0 |
| entity | 192 | 192 | 384 | 60.0 |
| number | 64 | 64 | 128 | 20.0 |
| total | 320 | 320 | 640 | 100.0 |

#### Figure 1. Injected error types by language

![error types](../results/dataset_stats/error_types_by_language.png)

## 4. Methodology
[TODO – overview figure of the pipeline.]

### 4.1 Summary generation
[TODO – not used in the main experiments: candidate summaries are given by the benchmark.]

### 4.2 Claim decomposition
We decompose each summary into claims with a rule-based splitter that first segments sentences
using script-aware terminators (।, ., ?, !) with an abbreviation list covering both Latin (*Dr.*)
and Devanagari (*डॉ.*) forms, and then splits sentences at clause boundaries defined as a comma
followed by a Hindi or romanised-Hindi connective (e.g., *जिसके/jiske*, *जहाँ/jahan*,
*यह/yeh*). Each claim retains its character offsets in the summary, which allows errors to be
localised to a single claim and enables span-restricted repair. We compare this clause-level
splitter with a sentence-level baseline and with the gold atomic claims as an oracle upper bound;
an LLM-based decomposer is implemented but not evaluated, since all experiments run without
access to a commercial API.

| Method (test) | claims/summary | facts/claim | fact coverage % | context-dependent % | error localised % | collateral facts | text touched % |
|---|---|---|---|---|---|---|---|
| sentence | 3.00 | 1.67 | 100 | 3.8 | 100 | 1.19 | 35.5 |
| clause | 3.65 | 1.37 | 100 | 20.9 | 100 | 0.83 | 29.3 |
| gold (oracle) | 5.26 | 1.07 | 100 | 0.0 | – | – | – |

### 4.3 Evidence retrieval
For each claim we rank the sentences of the source document and retain the top-k (k = 3) as
evidence, comparing a character 2–4-gram TF-IDF scorer, LaBSE sentence embeddings (Feng et al.,
2022), and a linear interpolation of both, each with and without script normalisation
(Devanagari-to-ASCII digits, nukta removal, lowercasing). Because the benchmark has no evidence
annotations, gold evidence is derived from key-fact overlap, using the original value for
corrupted claims and the polarity sentence for claims without key facts. Configurations were
selected on the development set with a pre-specified order of criteria (full recall@3, MRR,
recall@3 in a pooled stress test, simplicity), which selected the lexical scorer.

| Test (own source) | full R@1 ref/err | full R@3 ref/err | MRR err |
|---|---|---|---|
| lexical (selected) | 96.9 / 95.3 | 100 / 100 | 0.998 |
| LaBSE | 96.9 / 93.4 | 100 / 100 | 0.987 |
| hybrid+norm α=0.5 | 96.9 / 95.8 | 100 / 100 | 1.000 |

| Test (pooled stress) | full R@3 ref | full R@3 err | number claims R@1 |
|---|---|---|---|
| lexical | 93.1 | 67.0 | 52.4 |
| lexical+norm | 96.3 | 66.5 | 64.6 |
| LaBSE | 93.1 | 67.0 | 61.9 |
| hybrid+norm α=0.5 | 95.3 | 65.1 | 66.0 |

### 4.4 Verification
Each claim is verified against its retrieved evidence by a multilingual NLI model (mDeBERTa-v3-base
fine-tuned on XNLI and multilingual NLI data) and by four deterministic checks for numbers, dates,
negation and novel entities; the entity check flags content words that occur neither in the
evidence nor in a vocabulary of non-entity summary words learned from development-set reference
summaries. A claim is labelled SUPPORTED only if the NLI entailment probability reaches a
threshold τ and all checks pass; any failed check yields CONTRADICTED, NLI contradiction or
neutral above τ yields CONTRADICTED or UNSUPPORTED, and claims for which no NLI label reaches τ
are routed to human review (REVIEW). A summary is flagged if any of its claims is not SUPPORTED.
The NLI premise (best evidence sentence vs. concatenated top-3) and τ ∈ {0.50,…,0.95} were
selected on the development set by summary-level balanced accuracy (selected: best sentence,
τ = 0.5).

### 4.5 Selective repair
[TODO]

### 4.6 Re-verification and human-review routing
[TODO]

## 5. Experimental Setup
[TODO – models and versions (config.yaml), hardware (CPU), dev-only tuning protocol, baselines
and ablations, metrics (precision/recall/F1 per error type, balanced accuracy, content
preservation).]

## 6. Results

### 6.1 Error detection (test, 352 summaries)
| System | Precision | Recall | F1 | Specificity | Bal. acc. | REVIEW % | Exact loc. |
|---|---|---|---|---|---|---|---|
| Rules only | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 |
| NLI only | 88.6 | 99.6 | 93.8 | 61.4 | 80.5 | 5.3 | 67.7 |
| NLI + rules (full) | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 4.7 | 67.8 |

On the test set the full system detects all 264 corrupted summaries and always flags the
corrupted claim, but it also flags 38.6 % of faithful summaries; all false alarms originate from
the NLI component, as the rule checks never fire on faithful claims. Specificity is higher for
Hinglish (70.5 %) than for Hindi (52.3 %). Because the rule checks target exactly the error types
used for corruption, their perfect scores are an upper bound for this synthetic benchmark.

[TODO – repair results.]

## 7. Error Analysis
NLI false alarms (158 of 1,072 faithful test claims, from only 43 distinct claim strings) are
concentrated in three of eight domains: 31–56 % of faithful claims in politics, sports and
business versus 0 % in health, environment and technology. Two causes are identifiable: claims
whose support spans two source sentences (with a single-sentence premise the model predicts
contradiction), and template-specific NLI failures on near-verbatim paraphrases (e.g. neutral
≈ 0.93 for "सभा में लगभग N लोग शामिल हुए" against its source sentence). Reported-speech evidence
and Devanagari numerals did not explain the errors. Unsupported additions are always detected but
labelled CONTRADICTED rather than UNSUPPORTED, because a failed entity check takes precedence.

## 8. Limitations
[TODO – synthetic template-based data; single injected error; lexical negation only; romanised
Hinglish only; dependence on a commercial LLM API.]

## 9. Conclusion
[TODO]
