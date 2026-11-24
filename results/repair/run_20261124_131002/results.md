# Repair + re-check results

## TEST

| index | n | error_rate_% | fixed_complete_%(ERROR rows) | faithful_%(ERROR rows) | empty_% | correct_untouched_%(CORRECT rows) | new_errors_%(CORRECT rows) | keyfact_retention_% | sim_to_reference_% | chars_changed_% | auto_accepted_% | faithful_among_accepted_% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no_repair | 352.0 | 75.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 90.7 | 96.9 | 0.0 | 15.3 | 100.0 |
| delete_flagged | 352.0 | 0.0 | 12.1 | 92.8 | 6.8 | 61.4 | 0.0 | 61.8 | 74.4 | 27.3 | 92.9 | 100.0 |
| selective | 352.0 | 0.0 | 98.1 | 100.0 | 0.0 | 100.0 | 0.0 | 99.2 | 99.7 | 3.4 | 61.4 | 100.0 |
| selective_oracle | 352.0 | 0.0 | 98.1 | 100.0 | 0.0 | 100.0 | 0.0 | 99.2 | 99.7 | 3.4 | 61.4 | 100.0 |

## DEV

| index | n | error_rate_% | fixed_complete_%(ERROR rows) | faithful_%(ERROR rows) | empty_% | correct_untouched_%(CORRECT rows) | new_errors_%(CORRECT rows) | keyfact_retention_% | sim_to_reference_% | chars_changed_% | auto_accepted_% | faithful_among_accepted_% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| no_repair | 160.0 | 75.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 91.5 | 96.8 | 0.0 | 13.8 | 100.0 |
| delete_flagged | 160.0 | 0.0 | 9.2 | 90.8 | 8.8 | 55.0 | 0.0 | 56.0 | 70.4 | 31.2 | 91.2 | 100.0 |
| selective | 160.0 | 0.0 | 95.8 | 100.0 | 0.0 | 100.0 | 0.0 | 98.1 | 99.1 | 3.9 | 55.6 | 100.0 |
| selective_oracle | 160.0 | 0.0 | 95.8 | 100.0 | 0.0 | 100.0 | 0.0 | 98.1 | 99.1 | 3.9 | 55.6 | 100.0 |

## TEST by error type (complete / faithful %)

| ('error_type', '') | ('complete', 'no_repair') | ('complete', 'selective') | ('complete', 'selective_oracle') | ('faithful', 'no_repair') | ('faithful', 'selective') | ('faithful', 'selective_oracle') |
|---|---|---|---|---|---|---|
| none | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 | 100.0 |
| number_swap | 0.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |
| date_swap | 0.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |
| entity_swap | 0.0 | 89.8 | 89.8 | 0.0 | 100.0 | 100.0 |
| negation | 0.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |
| unsupported_addition | 0.0 | 100.0 | 100.0 | 0.0 | 100.0 | 100.0 |

## TEST by language

| level_0 | level_1 | n | error_rate_% | fixed_complete_%(ERROR rows) | faithful_%(ERROR rows) | empty_% | correct_untouched_%(CORRECT rows) | new_errors_%(CORRECT rows) | keyfact_retention_% | sim_to_reference_% | chars_changed_% | auto_accepted_% | faithful_among_accepted_% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| hindi | no_repair | 176.0 | 75.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 90.9 | 97.0 | 0.0 | 13.1 | 100.0 |
| hindi | delete_flagged | 176.0 | 0.0 | 9.1 | 90.9 | 9.1 | 52.3 | 0.0 | 56.5 | 71.0 | 30.6 | 90.3 | 100.0 |
| hindi | selective | 176.0 | 0.0 | 98.5 | 100.0 | 0.0 | 100.0 | 0.0 | 99.3 | 99.7 | 3.3 | 52.3 | 100.0 |
| hindi | selective_oracle | 176.0 | 0.0 | 98.5 | 100.0 | 0.0 | 100.0 | 0.0 | 99.3 | 99.7 | 3.3 | 52.3 | 100.0 |
| hinglish | no_repair | 176.0 | 75.0 | 0.0 | 0.0 | 0.0 | 100.0 | 0.0 | 90.6 | 96.8 | 0.0 | 17.6 | 100.0 |
| hinglish | delete_flagged | 176.0 | 0.0 | 15.2 | 94.7 | 4.5 | 70.5 | 0.0 | 67.2 | 77.8 | 24.1 | 95.5 | 100.0 |
| hinglish | selective | 176.0 | 0.0 | 97.7 | 100.0 | 0.0 | 100.0 | 0.0 | 99.1 | 99.6 | 3.5 | 70.5 | 100.0 |
| hinglish | selective_oracle | 176.0 | 0.0 | 97.7 | 100.0 | 0.0 | 100.0 | 0.0 | 99.1 | 99.6 | 3.5 | 70.5 | 100.0 |

## TEST selective: actions by error type

| error_type | delete | flip_negation | replace_date | replace_entity | replace_number | review |
|---|---|---|---|---|---|---|
| none | 0 | 0 | 0 | 0 | 0 | 49 |
| number_swap | 0 | 0 | 0 | 0 | 59 | 16 |
| date_swap | 0 | 0 | 55 | 0 | 0 | 18 |
| entity_swap | 5 | 0 | 0 | 44 | 0 | 21 |
| negation | 0 | 49 | 0 | 0 | 0 | 27 |
| unsupported_addition | 52 | 0 | 0 | 0 | 0 | 27 |

## TEST outcomes

| system | label | complete | empty | erroneous | lossy |
|---|---|---|---|---|---|
| delete_flagged | CORRECT | 54 | 5 | 0 | 29 |
| delete_flagged | ERROR | 32 | 19 | 0 | 213 |
| no_repair | CORRECT | 88 | 0 | 0 | 0 |
| no_repair | ERROR | 0 | 0 | 264 | 0 |
| selective | CORRECT | 88 | 0 | 0 | 0 |
| selective | ERROR | 259 | 0 | 0 | 5 |
| selective_oracle | CORRECT | 88 | 0 | 0 | 0 |
| selective_oracle | ERROR | 259 | 0 | 0 | 5 |
