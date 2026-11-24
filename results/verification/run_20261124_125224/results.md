# Verification results

DEV-selected full system: `{'premise': 'top1', 'tau': 0.5}`; NLI-only: `{'premise': 'top1', 'tau': 0.5}`

## DEV grid (full system, selected premise)

| tau | balanced_acc | recall | specificity | review_rate |
|---|---|---|---|---|
| 0.5 | 77.5 | 100.0 | 55.0 | 6.7 |
| 0.6 | 71.2 | 100.0 | 42.5 | 10.7 |
| 0.6 | 66.2 | 100.0 | 32.5 | 13.8 |
| 0.7 | 57.5 | 100.0 | 15.0 | 18.5 |
| 0.7 | 56.2 | 100.0 | 12.5 | 20.8 |
| 0.8 | 56.2 | 100.0 | 12.5 | 21.8 |
| 0.8 | 53.8 | 100.0 | 7.5 | 25.8 |
| 0.8 | 51.2 | 100.0 | 2.5 | 32.2 |
| 0.9 | 50.0 | 100.0 | 0.0 | 41.8 |
| 0.9 | 50.0 | 100.0 | 0.0 | 54.2 |

## TEST – summary-level detection

| index | n | precision | recall | f1 | specificity | balanced_acc | review_rate | loc_error_claim_flagged | loc_exact |
|---|---|---|---|---|---|---|---|---|---|
| rules_only | 352.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |
| nli_only | 352.0 | 88.6 | 99.6 | 93.8 | 61.4 | 80.5 | 5.3 | 100.0 | 67.7 |
| full (NLI + rules) | 352.0 | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 4.7 | 100.0 | 67.8 |
| full - numbers | 352.0 | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 5.2 | 100.0 | 67.8 |
| full - dates | 352.0 | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 4.7 | 100.0 | 67.8 |
| full - negation | 352.0 | 88.6 | 99.6 | 93.8 | 61.4 | 80.5 | 4.7 | 100.0 | 67.7 |
| full - entities | 352.0 | 88.6 | 100.0 | 94.0 | 61.4 | 80.7 | 4.9 | 100.0 | 67.8 |

## TEST – detection rate by error type (none = false-alarm rate)

| index | none | number_swap | date_swap | entity_swap | negation | unsupported_addition |
|---|---|---|---|---|---|---|
| rules_only | 0.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| nli_only | 38.6 | 100.0 | 100.0 | 100.0 | 98.0 | 100.0 |
| full (NLI + rules) | 38.6 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| full - numbers | 38.6 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| full - dates | 38.6 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| full - negation | 38.6 | 100.0 | 100.0 | 100.0 | 98.0 | 100.0 |
| full - entities | 38.6 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |

## TEST – full system by language

| index | n | precision | recall | f1 | specificity | balanced_acc | review_rate | loc_error_claim_flagged | loc_exact |
|---|---|---|---|---|---|---|---|---|---|
| hindi | 176.0 | 86.3 | 100.0 | 92.6 | 52.3 | 76.1 | 5.5 | 100.0 | 61.4 |
| hinglish | 176.0 | 91.0 | 100.0 | 95.3 | 70.5 | 85.2 | 3.9 | 100.0 | 74.2 |

## TEST – full system by source condition

| index | n | precision | recall | f1 | specificity | balanced_acc | review_rate | loc_error_claim_flagged | loc_exact |
|---|---|---|---|---|---|---|---|---|---|
| hindi/devanagari/clean | 52.0 | 88.6 | 100.0 | 94.0 | 61.5 | 80.8 | 0.0 | 100.0 | 71.8 |
| hindi/devanagari/noisy | 32.0 | 82.8 | 100.0 | 90.6 | 37.5 | 68.8 | 12.2 | 100.0 | 45.8 |
| hindi/western/clean | 44.0 | 82.5 | 100.0 | 90.4 | 36.4 | 68.2 | 9.0 | 100.0 | 48.5 |
| hindi/western/noisy | 48.0 | 90.0 | 100.0 | 94.7 | 66.7 | 83.3 | 4.2 | 100.0 | 72.2 |
| hinglish/western/clean | 80.0 | 90.9 | 100.0 | 95.2 | 70.0 | 85.0 | 4.3 | 100.0 | 73.3 |
| hinglish/western/noisy | 96.0 | 91.1 | 100.0 | 95.4 | 70.8 | 85.4 | 3.6 | 100.0 | 75.0 |

## TEST – claim-level confusion (expected x predicted)

| expected | CONTRADICTED | REVIEW | SUPPORTED | UNSUPPORTED | All |
|---|---|---|---|---|---|
| CONTRADICTED | 212 | 0 | 0 | 0 | 212 |
| SUPPORTED | 22 | 63 | 914 | 73 | 1072 |
| UNSUPPORTED | 52 | 0 | 0 | 0 | 52 |
| All | 286 | 63 | 914 | 73 | 1336 |

## TEST – which component flags the error claim

| error_type | rule=fail/nli=ent | rule=fail/nli=non-ent |
|---|---|---|
| number_swap | 0 | 59 |
| date_swap | 0 | 55 |
| entity_swap | 0 | 49 |
| negation | 1 | 48 |
| unsupported_addition | 0 | 52 |

## TEST – rule failure rates

| index | fail% on correct claims | fail% on error claims |
|---|---|---|
| numbers | 0.0 | 39.0 |
| dates | 0.0 | 26.1 |
| negation | 0.0 | 19.7 |
| entities | 0.0 | 38.3 |
