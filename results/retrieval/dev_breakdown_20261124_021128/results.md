# DEV retrieval breakdown

## By language

| group | config | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n | stress_full_recall@3 | stress_mrr |
|---|---|---|---|---|---|---|---|---|---|---|
| hindi | hybrid-minmax+norm | 94.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 118 | 100.0 | 0.884 |
| hindi | labse | 94.1 | 100.0 | 100.0 | 100.0 | 99.2 | 0.996 | 118 | 100.0 | 0.873 |
| hindi | labse+norm | 94.1 | 100.0 | 100.0 | 100.0 | 99.2 | 0.996 | 118 | 100.0 | 0.881 |
| hindi | lexical+norm | 94.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 118 | 98.3 | 0.894 |
| hinglish | hybrid-minmax+norm | 95.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 121 | 98.3 | 0.883 |
| hinglish | labse | 95.0 | 100.0 | 100.0 | 100.0 | 99.2 | 0.996 | 121 | 95.9 | 0.873 |
| hinglish | labse+norm | 94.2 | 100.0 | 100.0 | 100.0 | 98.3 | 0.992 | 121 | 95.0 | 0.868 |
| hinglish | lexical+norm | 95.9 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 121 | 100.0 | 0.88 |

## Hinglish noisy vs clean

| group | config | full_recall@1 | full_recall@2 | full_recall@3 | full_recall@5 | hit@1 | mrr | n | stress_full_recall@3 | stress_mrr |
|---|---|---|---|---|---|---|---|---|---|---|
| hinglish-clean | hybrid-minmax+norm | 92.3 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 52 | 98.1 | 0.907 |
| hinglish-clean | labse | 90.4 | 100.0 | 100.0 | 100.0 | 98.1 | 0.99 | 52 | 90.4 | 0.886 |
| hinglish-clean | labse+norm | 88.5 | 100.0 | 100.0 | 100.0 | 96.2 | 0.981 | 52 | 90.4 | 0.866 |
| hinglish-clean | lexical+norm | 92.3 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 52 | 100.0 | 0.891 |
| hinglish-noisy | hybrid-minmax+norm | 98.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 69 | 98.6 | 0.865 |
| hinglish-noisy | labse | 98.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 69 | 100.0 | 0.862 |
| hinglish-noisy | labse+norm | 98.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 69 | 98.6 | 0.87 |
| hinglish-noisy | lexical+norm | 98.6 | 100.0 | 100.0 | 100.0 | 100.0 | 1.0 | 69 | 100.0 | 0.872 |

## Decision

```
{
  "hindi": "lexical+norm",
  "hindi_decided_by": "mrr",
  "hinglish": "lexical+norm",
  "hinglish_decided_by": "mrr",
  "decision": "lexical+norm",
  "decision_kwargs": {
    "method": "lexical",
    "normalize_text": true
  }
}
```
