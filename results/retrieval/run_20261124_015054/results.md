# Evidence retrieval results

Selected on dev: **lexical** (by full_recall@3, tie-break MRR)

## Dev sweep

| config | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n | stress_full_recall@3 | stress_mrr | simplicity_rank |
|---|---|---|---|---|---|---|---|---|---|---|
| lexical | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 99.2 | 0.866 | 0 |
| lexical+norm | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 99.2 | 0.887 | 1 |
| hybrid+norm a=0.1 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 99.2 | 0.891 | 4 |
| hybrid+norm a=0.2 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 99.2 | 0.891 | 5 |
| hybrid+norm a=0.3 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 98.7 | 0.888 | 6 |
| hybrid+norm a=0.4 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 98.7 | 0.886 | 7 |
| hybrid+norm a=0.5 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 98.7 | 0.884 | 8 |
| hybrid+norm a=0.6 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 98.3 | 0.884 | 9 |
| hybrid+norm a=0.7 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 98.3 | 0.884 | 10 |
| hybrid+norm a=0.8 | 95.4 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 239 | 97.5 | 0.882 | 11 |
| hybrid+norm a=0.9 | 95.0 | 100.0 | 100.0 | 100.0 | 99.6 | 0.998 | 239 | 97.5 | 0.88 | 12 |
| labse | 94.6 | 100.0 | 100.0 | 100.0 | 99.2 | 0.996 | 239 | 97.9 | 0.873 | 2 |
| labse+norm | 94.1 | 100.0 | 100.0 | 100.0 | 98.7 | 0.994 | 239 | 97.5 | 0.875 | 3 |

## Test – main comparison

| config | kind | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|
| lexical | error | 95.3 | 99.1 | 100.0 | 100.0 | 99.5 | 0.998 | 212 |
| lexical | reference | 96.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 321 |
| lexical+norm | error | 95.3 | 99.1 | 100.0 | 100.0 | 99.5 | 0.998 | 212 |
| lexical+norm | reference | 96.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 321 |
| labse | error | 93.4 | 99.1 | 100.0 | 100.0 | 97.6 | 0.987 | 212 |
| labse | reference | 96.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 321 |
| labse+norm | error | 93.9 | 98.6 | 100.0 | 100.0 | 98.1 | 0.991 | 212 |
| labse+norm | reference | 96.9 | 98.8 | 100.0 | 100.0 | 100.0 | 1.0 | 321 |
| hybrid+norm a=0.5 | error | 95.8 | 99.5 | 100.0 | 100.0 | 100.0 | 1.0 | 212 |
| hybrid+norm a=0.5 | reference | 96.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 321 |

## Test – selected config by claim type

| kind | ftype | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|
| error | date | 90.3 | 97.8 | 100.0 | 100.0 | 100.0 | 1.0 | 93 |
| error | entity | 90.9 | 100.0 | 100.0 | 100.0 | 90.9 | 0.955 | 11 |
| error | number | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 59 |
| error | polarity | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 49 |
| reference | date | 88.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 88 |
| reference | entity | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 57 |
| reference | number | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 88 |
| reference | polarity | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 88 |

## Test – selected config, error claims by error type

| error_type | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|
| date_swap | 90.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 55 |
| entity_swap | 89.8 | 95.9 | 100.0 | 100.0 | 98.0 | 0.99 | 49 |
| negation | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 49 |
| number_swap | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 59 |

## Test – selected config by language / source condition

| language | digits | noise | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|---|
| hindi | devanagari | False | 95.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 80 |
| hindi | devanagari | True | 98.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 51 |
| hindi | western | False | 93.7 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 63 |
| hindi | western | True | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 74 |
| hinglish | western | False | 96.7 | 99.2 | 100.0 | 100.0 | 99.2 | 0.996 | 122 |
| hinglish | western | True | 95.1 | 99.3 | 100.0 | 100.0 | 100.0 | 1.0 | 143 |

## Test – LaBSE raw vs normalised, by source digit script

| config | digits | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|
| labse | devanagari | 94.7 | 99.2 | 100.0 | 100.0 | 98.5 | 0.991 | 131 |
| labse | western | 95.8 | 99.8 | 100.0 | 100.0 | 99.3 | 0.996 | 402 |
| labse+norm | devanagari | 95.4 | 100.0 | 100.0 | 100.0 | 99.2 | 0.996 | 131 |
| labse+norm | western | 95.8 | 98.3 | 100.0 | 100.0 | 99.3 | 0.996 | 402 |

## Test – STRESS (pooled same language x domain x split)

| config | kind | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|
| lexical | error | 41.5 | 55.2 | 67.0 | 92.5 | 45.8 | 0.618 | 212 |
| lexical | reference | 72.6 | 84.7 | 93.1 | 99.4 | 75.7 | 0.847 | 321 |
| lexical+norm | error | 42.0 | 55.2 | 66.5 | 92.0 | 46.2 | 0.619 | 212 |
| lexical+norm | reference | 78.8 | 90.3 | 96.3 | 100.0 | 81.9 | 0.891 | 321 |
| labse | error | 45.3 | 55.2 | 67.0 | 88.2 | 49.5 | 0.639 | 212 |
| labse | reference | 76.3 | 86.9 | 93.1 | 98.4 | 79.4 | 0.873 | 321 |
| labse+norm | error | 45.8 | 55.7 | 64.6 | 89.6 | 49.5 | 0.64 | 212 |
| labse+norm | reference | 76.0 | 87.2 | 93.5 | 98.1 | 79.1 | 0.872 | 321 |
| hybrid+norm a=0.5 | error | 43.9 | 56.1 | 65.1 | 93.4 | 48.1 | 0.633 | 212 |
| hybrid+norm a=0.5 | reference | 78.8 | 89.4 | 95.3 | 100.0 | 81.9 | 0.891 | 321 |

## Test – STRESS by claim type

| config | ftype | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n |
|---|---|---|---|---|---|---|---|---|
| lexical | date | 85.6 | 95.6 | 98.9 | 98.9 | 96.1 | 0.979 | 181 |
| lexical | entity | 85.3 | 94.1 | 94.1 | 97.1 | 85.3 | 0.909 | 68 |
| lexical | number | 52.4 | 61.2 | 74.1 | 95.2 | 52.4 | 0.667 | 147 |
| lexical | polarity | 22.6 | 45.3 | 65.0 | 94.9 | 22.6 | 0.482 | 137 |
| lexical+norm | date | 86.7 | 96.7 | 98.9 | 98.9 | 97.2 | 0.985 | 181 |
| lexical+norm | entity | 85.3 | 94.1 | 94.1 | 97.1 | 85.3 | 0.909 | 68 |
| lexical+norm | number | 64.6 | 71.4 | 79.6 | 95.9 | 64.6 | 0.751 | 147 |
| lexical+norm | polarity | 23.4 | 46.0 | 65.7 | 94.9 | 23.4 | 0.488 | 137 |
| labse | date | 87.8 | 91.2 | 94.5 | 94.5 | 98.3 | 0.99 | 181 |
| labse | entity | 88.2 | 95.6 | 95.6 | 95.6 | 88.2 | 0.924 | 68 |
| labse | number | 61.9 | 71.4 | 81.6 | 93.2 | 61.9 | 0.737 | 147 |
| labse | polarity | 22.6 | 44.5 | 62.0 | 94.9 | 22.6 | 0.478 | 137 |
| labse+norm | date | 89.0 | 92.3 | 93.9 | 94.5 | 98.9 | 0.994 | 181 |
| labse+norm | entity | 79.4 | 86.8 | 91.2 | 95.6 | 79.4 | 0.861 | 68 |
| labse+norm | number | 64.6 | 74.8 | 79.6 | 94.6 | 64.6 | 0.756 | 147 |
| labse+norm | polarity | 22.6 | 45.3 | 64.2 | 94.9 | 22.6 | 0.481 | 137 |
| hybrid+norm a=0.5 | date | 87.8 | 93.4 | 95.6 | 98.9 | 98.3 | 0.991 | 181 |
| hybrid+norm a=0.5 | entity | 85.3 | 94.1 | 95.6 | 98.5 | 85.3 | 0.91 | 68 |
| hybrid+norm a=0.5 | number | 66.0 | 74.8 | 79.6 | 97.3 | 66.0 | 0.765 | 147 |
| hybrid+norm a=0.5 | polarity | 23.4 | 46.0 | 65.0 | 94.9 | 23.4 | 0.487 | 137 |
