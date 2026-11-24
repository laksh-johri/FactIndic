"""Exact rule checks for a claim against its evidence sentences.

Each check returns a RuleResult with status "pass", "fail" or "na" (not applicable) and a
human-readable reason, so every decision can be shown to the user.

  numbers   : every number in the claim must occur in the evidence (digits normalised)
  dates     : every (day, month, year) date in the claim must occur in the evidence
  negation  : the claim and its best-matching evidence sentence must have the same polarity
  entities  : the claim must not contain "novel" content tokens - tokens that are absent from
              the evidence AND not in a safe vocabulary learned from DEV reference summaries
              (a heuristic stand-in for NER; see docs/research_log.md, Step 4)
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from src.textnorm import normalize

PUNCT = "।॥.,!?;:\"'()[]{}“”‘’–—-"
NUM_RE = re.compile(r"(?<![\d.])\d[\d,]*(?:\.\d+)?(?![\d])")

MONTHS = {
    1: ["जनवरी", "january", "jan"], 2: ["फ़रवरी", "फरवरी", "february", "feb"],
    3: ["मार्च", "march", "mar"], 4: ["अप्रैल", "april", "apr"], 5: ["मई", "may"],
    6: ["जून", "june", "jun"], 7: ["जुलाई", "july", "jul"], 8: ["अगस्त", "august", "aug"],
    9: ["सितंबर", "सितम्बर", "september", "sep", "sept"], 10: ["अक्टूबर", "अक्तूबर", "october", "oct"],
    11: ["नवंबर", "नवम्बर", "november", "nov"], 12: ["दिसंबर", "दिसम्बर", "december", "dec"],
}
MONTH_OF = {normalize(n): m for m, names in MONTHS.items() for n in names}
DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(sorted(map(re.escape, MONTH_OF), key=len, reverse=True))
                     + r")\s+(\d{4})(?!\d)")

NEGATIONS = {normalize(w) for w in ["नहीं", "नही", "न", "ना", "मत", "nahi", "nahin", "nahī", "nhi", "nai",
                                     "na", "mat", "not", "no", "never"]}

STOPWORDS = {normalize(w) for w in (
    "के का की को में मे से ने पर और भी है हैं था थे थी हुए हुई हुआ गया गई गए किया की कि यह ये वह वे इस उस "
    "एक लिए लिये तक ही तो जो जिसके जिसकी जिसका जहाँ जहां उन्होंने कुल लगभग "
    "ke ka ki ko mein me se ne par aur bhi hai hain tha the thi hue hui hua gaya gayi gaye kiya kia "
    "ek liye lie tak hi to jo jiske jiski jiska jahan unhone total lagbhag is us yeh ye woh"
).split()}


@dataclass
class RuleResult:
    name: str
    status: str                 # pass | fail | na
    reason: str = ""
    details: dict = field(default_factory=dict)


def tokens(text: str) -> list[str]:
    return [t for t in (w.strip(PUNCT) for w in normalize(text).split()) if t]


def numbers(text: str) -> list[str]:
    return [n.replace(",", "") for n in NUM_RE.findall(normalize(text))]


def dates(text: str) -> list[tuple[int, int, int]]:
    return [(int(d), MONTH_OF[m], int(y)) for d, m, y in DATE_RE.findall(normalize(text))]


def has_negation(text: str) -> bool:
    return any(t in NEGATIONS for t in tokens(text))


# ---------------------------------------------------------------------------
def check_numbers(claim: str, evidence: list[str]) -> RuleResult:
    cn = numbers(claim)
    if not cn:
        return RuleResult("numbers", "na", "claim has no numbers")
    ev = set(numbers(" ".join(evidence)))
    missing = [n for n in cn if n not in ev]
    if missing:
        return RuleResult("numbers", "fail", f"number(s) {missing} not found in evidence {sorted(ev)}",
                          {"missing": missing, "evidence_numbers": sorted(ev)})
    return RuleResult("numbers", "pass", f"number(s) {cn} found in evidence")


def check_dates(claim: str, evidence: list[str]) -> RuleResult:
    cd = dates(claim)
    if not cd:
        return RuleResult("dates", "na", "claim has no dates")
    ev = set(dates(" ".join(evidence)))
    missing = [d for d in cd if d not in ev]
    if missing:
        return RuleResult("dates", "fail", f"date(s) {missing} not in evidence dates {sorted(ev)}",
                          {"missing": missing, "evidence_dates": sorted(ev)})
    return RuleResult("dates", "pass", f"date(s) {cd} found in evidence")


def check_negation(claim: str, evidence: list[str]) -> RuleResult:
    """Compare polarity with the FIRST evidence sentence (the best-ranked one)."""
    if not evidence:
        return RuleResult("negation", "na", "no evidence")
    c, e = has_negation(claim), has_negation(evidence[0])
    if c != e:
        return RuleResult("negation", "fail",
                          f"claim is {'negative' if c else 'positive'} but best evidence is "
                          f"{'negative' if e else 'positive'}", {"claim_neg": c, "evidence_neg": e})
    return RuleResult("negation", "pass", f"same polarity ({'negative' if c else 'positive'})")


def check_entities(claim: str, evidence: list[str], safe_vocab: set[str]) -> RuleResult:
    ev = set(tokens(" ".join(evidence)))
    novel = [t for t in tokens(claim)
             if t not in ev and t not in safe_vocab and t not in STOPWORDS
             and not t.isdigit() and t not in MONTH_OF and t not in NEGATIONS]
    if novel:
        return RuleResult("entities", "fail", f"novel content not in evidence: {novel}", {"novel": novel})
    return RuleResult("entities", "pass", "all content tokens supported by evidence or safe vocabulary")


def run_rules(claim: str, evidence: list[str], safe_vocab: set[str],
              enabled: tuple[str, ...] = ("numbers", "dates", "negation", "entities")) -> list[RuleResult]:
    fns = {"numbers": lambda: check_numbers(claim, evidence), "dates": lambda: check_dates(claim, evidence),
           "negation": lambda: check_negation(claim, evidence),
           "entities": lambda: check_entities(claim, evidence, safe_vocab)}
    return [fns[n]() for n in enabled]


# ---------------------------------------------------------------------------
def build_safe_vocab(summaries: list[str], key_facts: list[list[dict]]) -> set[str]:
    """Tokens of known-faithful (DEV reference) summaries, minus their key-fact tokens.

    These are the words a summariser uses that are NOT entities/numbers/dates (paraphrase
    words such as 'लगाया' or 'organise'), so they must not be mistaken for new entities.
    """
    vocab: set[str] = set()
    for s, kfs in zip(summaries, key_facts):
        fact_tokens = {t for kf in kfs for t in tokens(kf["value"])}
        vocab |= {t for t in tokens(s) if t not in fact_tokens}
    return vocab


def to_dicts(results: list[RuleResult]) -> list[dict]:
    return [asdict(r) for r in results]
