"""Claim decomposition: split a summary into small, independently checkable claims.

Methods (choose with config.yaml -> decomposition.method):
  sentence : one claim per sentence (baseline)
  clause   : sentence split + split at ", <connective>" clause boundaries (default, no API key)
  gold     : the gold_claims shipped with the data (oracle upper bound; reference summaries only)
  llm      : ask Gemini via src/llm.py (needs GEMINI_API_KEY unless cached)

Rule-based claims keep their character span in the summary (start, end) so that later steps
can (a) tell which claim contains an error and (b) repair ONLY that span.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

DEVANAGARI = re.compile(r"[ऀ-ॿ]")

# Abbreviations whose final "." is NOT a sentence end.
ABBREVIATIONS = {"dr.", "mr.", "mrs.", "ms.", "prof.", "sh.", "smt.", "st.", "jr.", "sr.", "no.",
                 "vs.", "etc.", "डॉ.", "श्री.", "प्रो.", "सु.", "कु."}

# Words that start a new clause after a comma (Hindi grammar + romanised forms).
CONNECTIVES_HI = ["जिसके", "जिसकी", "जिसका", "जिसने", "जिसमें", "जिन्होंने", "जहाँ", "जहां", "जब",
                  "जो", "और", "तथा", "लेकिन", "परंतु", "किंतु", "जबकि", "क्योंकि", "यह", "इसके",
                  "इससे", "साथ ही"]
CONNECTIVES_HG = ["jiske", "jiski", "jiska", "jisne", "jismein", "jinhone", "jahan", "jahaan",
                  "jab", "jo", "aur", "lekin", "par", "magar", "jabki", "kyunki", "yeh", "ye",
                  "iske", "isse", "saath hi", "and", "but", "while", "which", "where", "who"]
_CONN = sorted(CONNECTIVES_HI + CONNECTIVES_HG, key=len, reverse=True)
# NB: \b is unreliable for Devanagari (vowel signs are not \w), so we use an explicit lookahead.
CLAUSE_BOUNDARY = re.compile(r",\s+(?=(?:" + "|".join(map(re.escape, _CONN)) + r")(?=[\s,।.]|$))",
                             re.IGNORECASE)

# First words that make a claim depend on context ("He announced ..." - who is "he"?).
CONTEXT_DEPENDENT_STARTS = {
    "उन्होंने", "उसने", "उसके", "उसकी", "वह", "वे", "यह", "ये", "इसके", "इसकी", "जिसके", "जिसकी",
    "जिसका", "जिसने", "जहाँ", "जहां", "जो",
    "unhone", "unhonne", "usne", "uske", "uski", "woh", "wo", "ve", "yeh", "ye", "iske", "iski",
    "jiske", "jiski", "jiska", "jisne", "jahan", "jahaan", "jo", "he", "she", "they", "it",
}


@dataclass
class Claim:
    claim_id: str
    text: str
    start: int = -1        # char offsets in the summary (-1 = not span-aligned, e.g. gold/llm)
    end: int = -1
    method: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def terminator(text: str) -> str:
    return "।" if DEVANAGARI.search(text) else "."


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------
def _is_abbreviation(text: str, dot_pos: int) -> bool:
    start = dot_pos
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    token = text[start:dot_pos + 1].lower()
    if token in ABBREVIATIONS:
        return True
    core = token[:-1]
    return len(core) == 1 and core.isalpha()          # initials such as "A." in "A. K. Singh"


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Return (start, end) spans of sentences; end includes the terminator."""
    spans, start = [], 0
    for i, ch in enumerate(text):
        if ch not in "।॥.!?":
            continue
        at_end = i + 1 == len(text) or text[i + 1].isspace()
        if not at_end:
            continue                                    # e.g. "3.5" or "U.P."
        if ch == "." and _is_abbreviation(text, i):
            continue
        spans.append((start, i + 1))
        start = i + 1
        while start < len(text) and text[start].isspace():
            start += 1
    if start < len(text) and text[start:].strip():
        spans.append((start, len(text.rstrip())))
    # trim leading whitespace in every span
    out = []
    for a, b in spans:
        while a < b and text[a].isspace():
            a += 1
        if a < b:
            out.append((a, b))
    return out


def clause_spans(text: str, sent: tuple[int, int]) -> list[tuple[int, int]]:
    """Split one sentence span at ', <connective>' boundaries."""
    a, b = sent
    pieces, cur = [], a
    for m in CLAUSE_BOUNDARY.finditer(text, a, b):
        pieces.append((cur, m.start()))                 # clause ends before the comma
        cur = m.end()                                   # next clause starts at the connective
    pieces.append((cur, b))
    return [(s, e) for s, e in pieces if text[s:e].strip()]


def _claims_from_spans(summary: str, spans: list[tuple[int, int]], prefix: str, method: str) -> list[Claim]:
    term = terminator(summary)
    claims = []
    for k, (s, e) in enumerate(spans, start=1):
        t = summary[s:e].strip()
        if t[-1] not in "।॥.!?":
            t += term
        claims.append(Claim(f"{prefix}#{k}", t, s, e, method))
    return claims


def decompose_sentence(summary: str, prefix: str = "c") -> list[Claim]:
    return _claims_from_spans(summary, sentence_spans(summary), prefix, "sentence")


def decompose_clause(summary: str, prefix: str = "c") -> list[Claim]:
    spans = [c for s in sentence_spans(summary) for c in clause_spans(summary, s)]
    return _claims_from_spans(summary, spans, prefix, "clause")


def decompose_gold(gold_claims: list[str], prefix: str = "c") -> list[Claim]:
    return [Claim(f"{prefix}#{k}", c, -1, -1, "gold") for k, c in enumerate(gold_claims, start=1)]


# ---------------------------------------------------------------------------
# LLM decomposition (only runs with an API key or a cached answer)
# ---------------------------------------------------------------------------
LLM_PROMPT = """You split a summary into atomic factual claims.
Rules:
- Each claim states exactly ONE fact (one who / what / where / when / how many).
- Keep the summary's language and script (Hindi stays in Devanagari, Hinglish stays romanised).
- Replace pronouns with the entity they refer to, so each claim is understandable alone.
- Copy names, numbers and dates exactly; do not add or infer any information.
Return ONLY a JSON list of strings.

Summary:
{summary}
"""


def parse_json_list(text: str) -> list[str]:
    m = re.search(r"\[.*\]", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON list in LLM output: {text[:200]!r}")
    items = json.loads(m.group(0))
    return [str(x).strip() for x in items if str(x).strip()]


def decompose_llm(summary: str, prefix: str = "c", client=None) -> list[Claim]:
    if client is None:
        from src.llm import LLMClient
        client = LLMClient()
    out = client.call(LLM_PROMPT.format(summary=summary), temperature=0.0)
    return [Claim(f"{prefix}#{k}", c, -1, -1, "llm") for k, c in enumerate(parse_json_list(out), start=1)]


# ---------------------------------------------------------------------------
# Dispatcher + helpers used by evaluation
# ---------------------------------------------------------------------------
def decompose(summary: str, method: str = "clause", prefix: str = "c",
              gold_claims: list[str] | None = None, client=None) -> list[Claim]:
    if method == "sentence":
        return decompose_sentence(summary, prefix)
    if method == "clause":
        return decompose_clause(summary, prefix)
    if method == "gold":
        if gold_claims is None:
            raise ValueError("method='gold' needs gold_claims")
        return decompose_gold(gold_claims, prefix)
    if method == "llm":
        return decompose_llm(summary, prefix, client)
    raise ValueError(f"unknown decomposition method {method!r}")


def is_context_dependent(claim_text: str) -> bool:
    first = claim_text.strip().split(" ", 1)[0].strip(",।.").lower()
    return first in CONTEXT_DEPENDENT_STARTS


def claims_overlapping(claims: list[Claim], start: int, end: int) -> list[Claim]:
    """Span-aligned claims that overlap the character range [start, end)."""
    return [c for c in claims if c.start >= 0 and c.start < end and start < c.end]
