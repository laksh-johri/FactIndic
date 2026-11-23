# Claim decomposition results

## Table A. All metrics by method and split

| method | split | n_claims | fact_coverage | facts_per_claim | atomic_rate | context_dep_rate | localised | collateral_facts | touched_share |
|---|---|---|---|---|---|---|---|---|---|
| clause | dev | 3.58 | 100.00 | 1.40 | 68.53 | 20.28 | 100.00 | 0.91 | 30.40 |
| clause | test | 3.65 | 100.00 | 1.37 | 69.16 | 20.87 | 100.00 | 0.83 | 29.31 |
| gold | dev | 5.22 | 100.00 | 1.08 | 75.60 | 0.00 | – | – | – |
| gold | test | 5.26 | 100.00 | 1.07 | 76.46 | 0.00 | – | – | – |
| sentence | dev | 3.00 | 100.00 | 1.67 | 66.67 | 5.00 | 100.00 | 1.25 | 36.51 |
| sentence | test | 3.00 | 100.00 | 1.67 | 66.67 | 3.79 | 100.00 | 1.19 | 35.46 |

## Table B. Test split by language

| method | language | n_claims | fact_coverage | facts_per_claim | atomic_rate | context_dep_rate | localised | collateral_facts | touched_share |
|---|---|---|---|---|---|---|---|---|---|
| clause | hindi | 3.66 | 100.00 | 1.37 | 69.57 | 21.12 | 100.00 | 0.71 | 28.06 |
| clause | hinglish | 3.64 | 100.00 | 1.38 | 68.75 | 20.62 | 100.00 | 0.94 | 30.56 |
| gold | hindi | 5.27 | 100.00 | 1.06 | 76.72 | 0.00 | – | – | – |
| gold | hinglish | 5.25 | 100.00 | 1.07 | 76.19 | 0.00 | – | – | – |
| sentence | hindi | 3.00 | 100.00 | 1.67 | 66.67 | 3.79 | 100.00 | 1.10 | 34.21 |
| sentence | hinglish | 3.00 | 100.00 | 1.67 | 66.67 | 3.79 | 100.00 | 1.27 | 36.71 |

## Table C. Error localisation on test, by error type

| method | error_type | rows | localised | collateral_facts | touched_share |
|---|---|---|---|---|---|
| clause | date_swap | 55 | 100.00 | 2.22 | 42.99 |
| clause | entity_swap | 49 | 100.00 | 1.94 | 39.83 |
| clause | negation | 49 | 100.00 | 0.00 | 21.60 |
| clause | number_swap | 59 | 100.00 | 0.02 | 20.31 |
| clause | unsupported_addition | 52 | 100.00 | 0.00 | 22.40 |
| sentence | date_swap | 55 | 100.00 | 3.00 | 57.17 |
| sentence | entity_swap | 49 | 100.00 | 3.00 | 57.06 |
| sentence | negation | 49 | 100.00 | 0.00 | 21.60 |
| sentence | number_swap | 59 | 100.00 | 0.02 | 20.31 |
| sentence | unsupported_addition | 52 | 100.00 | 0.00 | 22.40 |
