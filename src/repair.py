"""Selective, evidence-based repair of flagged claims (no LLM).

Only claims whose verdict is not SUPPORTED are touched, and only inside their character span in
the summary. Every replacement value is copied from the claim's retrieved evidence; the gold
answer is never used.

Per flagged claim, driven by which rule check failed:
  entities fail -> exactly one novel token run AND an evidence entity with matching context
                   -> replace it ("replace_entity"); otherwise the claim is unsupported content
                   -> delete the claim ("delete")
  dates fail    -> replace the claim date with the evidence date      ("replace_date")
  numbers fail  -> replace the wrong number with the context-matching evidence number
                   ("replace_number")
  negation fail -> insert / remove the negation word to match the evidence ("flip_negation")
  no rule failed (NLI-only flag) or no safe candidate -> leave text unchanged ("review")
Candidates are ranked by (context match with the claim, evidence rank); ties -> review.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from src.rules import MONTH_OF, MONTHS, NEGATIONS, PUNCT, STOPWORDS
from src.textnorm import DEV_TO_ASCII, normalize

TERMINATORS = "।॥.!?"
DEVANAGARI = re.compile(r"[ऀ-ॿ]")
_RAW_MONTHS = sorted({n.lower() for names in MONTHS.values() for n in names}, key=len, reverse=True)
RAW_DATE_RE = re.compile(r"(?<!\d)(\d{1,2})\s+(" + "|".join(map(re.escape, _RAW_MONTHS)) + r")\s+(\d{4})(?!\d)")
ASCII_TO_DEV = str.maketrans("0123456789", "०१२३४५६७८९")
ENGLISH_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"]


@dataclass
class Tok:
    start: int
    end: int
    norm: str
    raw: str


@dataclass
class Edit:
    claim_id: str
    action: str
    start: int = -1          # span in the ORIGINAL summary that is replaced (-1 = no text change)
    end: int = -1
    old: str = ""
    new: str = ""
    reason: str = ""


@dataclass
class RepairResult:
    original: str
    repaired: str
    edits: list = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return self.original != self.repaired

    def to_dict(self) -> dict:
        return {"original": self.original, "repaired": self.repaired, "edits": [asdict(e) for e in self.edits]}


# ---------------------------------------------------------------------------
# Token helpers (keep character offsets, compare on normalised form)
# ---------------------------------------------------------------------------
def tok_spans(text: str, base: int = 0) -> list[Tok]:
    out = []
    for m in re.finditer(r"\S+", text):
        a, b = m.start(), m.end()
        while a < b and text[a] in PUNCT:
            a += 1
        while b > a and text[b - 1] in PUNCT:
            b -= 1
        if a < b:
            out.append(Tok(base + a, base + b, normalize(text[a:b]), text[a:b]))
    return out


def is_content(norm: str, safe: set[str]) -> bool:
    return (norm not in safe and norm not in STOPWORDS and not norm.replace(",", "").isdigit()
            and norm not in MONTH_OF and norm not in NEGATIONS)


def runs(toks: list[Tok], keep) -> list[tuple[int, int]]:
    """Maximal runs [i, j) of consecutive tokens satisfying keep(tok)."""
    out, i = [], 0
    while i < len(toks):
        if keep(toks[i]):
            j = i
            while j < len(toks) and keep(toks[j]):
                j += 1
            out.append((i, j))
            i = j
        else:
            i += 1
    return out


def context(toks: list[Tok], i: int, j: int) -> tuple[str | None, str | None]:
    return (toks[i - 1].norm if i > 0 else None, toks[j].norm if j < len(toks) else None)


def ctx_score(a: tuple, b: tuple) -> int:
    return int(a[0] is not None and a[0] == b[0]) + int(a[1] is not None and a[1] == b[1])


def pick(cands: list[tuple[int, int, str]], need_context: bool = True) -> str | None:
    """cands = (context score, evidence rank, value). Best = max score, then best rank; tie -> None."""
    if not cands:
        return None
    best = {}
    for score, rank, val in cands:                       # best (score, -rank) per distinct value
        key = (score, -rank)
        if val not in best or key > best[val]:
            best[val] = key
    ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)
    top_val, top_key = ranked[0]
    if need_context and top_key[0] < 1:
        return None
    if len(ranked) > 1 and ranked[1][1] == top_key:
        return None
    return top_val


def date_spans(text: str, base: int = 0) -> list[tuple[int, int, tuple[int, int, int]]]:
    low = text.translate(DEV_TO_ASCII).lower()           # same length as text
    return [(base + m.start(), base + m.end(), (int(m.group(1)), MONTH_OF[normalize(m.group(2))], int(m.group(3))))
            for m in RAW_DATE_RE.finditer(low)]


def render_date(d: tuple[int, int, int], like: str) -> str:
    day, month, year = d
    if DEVANAGARI.search(like):
        name = MONTHS[month][0]
    else:
        name = ENGLISH_MONTHS[month - 1]
    s = f"{day} {name} {year}"
    return s.translate(ASCII_TO_DEV) if re.search("[०-९]", like) else s


# ---------------------------------------------------------------------------
# Per-rule repairs (return Edit or None)
# ---------------------------------------------------------------------------
def repair_entity(cid, summary, s, e, evidence, safe_summary, safe_union) -> Edit:
    ctoks = tok_spans(summary[s:e], s)
    ev_norm = {t.norm for sent in evidence for t in tok_spans(sent)}
    claim_norm = {t.norm for t in ctoks}
    novel = runs(ctoks, lambda t: is_content(t.norm, safe_summary) and t.norm not in ev_norm)
    if len(novel) != 1:
        return delete_claim(cid, summary, s, e, f"{len(novel)} runs of unsupported content")
    i, j = novel[0]
    c_ctx = context(ctoks, i, j)
    cands = []
    for rank, sent in enumerate(evidence):
        et = tok_spans(sent)
        for a, b in runs(et, lambda t: is_content(t.norm, safe_union)):
            if any(t.norm in claim_norm for t in et[a:b]):
                continue
            cands.append((ctx_score(c_ctx, context(et, a, b)), rank, sent[et[a].start:et[b - 1].end]))
    new = pick(cands)
    old_a, old_b = ctoks[i].start, ctoks[j - 1].end
    if new is None:
        return delete_claim(cid, summary, s, e, "unsupported entity with no matching evidence entity")
    return Edit(cid, "replace_entity", old_a, old_b, summary[old_a:old_b], new, "entity copied from evidence")


def repair_date(cid, summary, s, e, evidence) -> Edit | None:
    cds = date_spans(summary[s:e], s)
    ev_dates = [(rank, d) for rank, sent in enumerate(evidence) for _, _, d in date_spans(sent)]
    for a, b, d in cds:
        if any(d == x for _, x in ev_dates):
            continue
        new = pick([(0, rank, x) for rank, x in ev_dates if x != d], need_context=False)
        if new is None:
            return None
        return Edit(cid, "replace_date", a, b, summary[a:b], render_date(new, summary[a:b]), "date copied from evidence")
    return None


def repair_numbers(cid, summary, s, e, evidence) -> list[Edit] | None:
    in_date = [(a, b) for a, b, _ in date_spans(summary[s:e], s)]
    ctoks = tok_spans(summary[s:e], s)
    ev = []
    for rank, sent in enumerate(evidence):
        et = tok_spans(sent)
        dspan = [(a, b) for a, b, _ in date_spans(sent)]
        ev += [(rank, et, k) for k, t in enumerate(et) if t.norm.replace(",", "").isdigit()
               and not any(a <= t.start < b for a, b in dspan)]
    ev_vals = {et[k].norm.replace(",", "") for _, et, k in ev}
    claim_vals = {t.norm.replace(",", "") for t in ctoks if t.norm.replace(",", "").isdigit()}
    edits = []
    for k, t in enumerate(ctoks):
        v = t.norm.replace(",", "")
        if not v.isdigit() or v in ev_vals or any(a <= t.start < b for a, b in in_date):
            continue
        c_ctx = context(ctoks, k, k + 1)
        cands = [(ctx_score(c_ctx, context(et, kk, kk + 1)), rank, et[kk].norm.replace(",", ""))
                 for rank, et, kk in ev if et[kk].norm.replace(",", "") not in claim_vals]
        new = pick(cands)
        if new is None:
            return None
        if re.search("[०-९]", t.raw):
            new = new.translate(ASCII_TO_DEV)
        edits.append(Edit(cid, "replace_number", t.start, t.end, t.raw, new, "number copied from evidence"))
    return edits or None


def repair_negation(cid, summary, s, e, evidence) -> Edit | None:
    ctoks = tok_spans(summary[s:e], s)
    neg_idx = [k for k, t in enumerate(ctoks) if t.norm in NEGATIONS]
    if neg_idx:                                          # claim negative, evidence positive -> remove
        t = ctoks[neg_idx[-1]]
        b = t.end + 1 if t.end < len(summary) and summary[t.end] == " " else t.end
        return Edit(cid, "flip_negation", t.start, b, summary[t.start:b], "", "negation removed to match evidence")
    et = tok_spans(evidence[0])                          # claim positive, evidence negative -> insert
    k = next((k for k, t in enumerate(et) if t.norm in NEGATIONS), None)
    if k is None:
        return None
    after = et[k + 1].norm if k + 1 < len(et) else None
    target = next((t for t in reversed(ctoks) if t.norm == after), None) or (ctoks[-1] if ctoks else None)
    if target is None:
        return None
    word = "नहीं" if DEVANAGARI.search(summary[s:e]) else "nahi"
    return Edit(cid, "flip_negation", target.start, target.start, "", word + " ", "negation inserted to match evidence")


def delete_claim(cid, summary, s, e, reason) -> Edit:
    if summary[s - 2:s] == ", ":                         # trailing clause: drop ", clause", keep terminator
        b = e - 1 if summary[e - 1] in TERMINATORS else e
        return Edit(cid, "delete", s - 2, b, summary[s - 2:b], "", reason)
    if summary[e:e + 2] == ", ":                         # leading clause: drop "clause, "
        return Edit(cid, "delete", s, e + 2, summary[s:e + 2], "", reason)
    a, b = s, e                                          # whole sentence: also drop one adjacent space
    if b < len(summary) and summary[b] == " ":
        b += 1
    elif a > 0 and summary[a - 1] == " ":
        a -= 1
    return Edit(cid, "delete", a, b, summary[a:b], "", reason)


# ---------------------------------------------------------------------------
def repair_summary(summary: str, claims: list[dict], safe_summary: set[str], safe_union: set[str]) -> RepairResult:
    """claims: dicts with claim_id, start, end, verdict, rules {name: status}, evidence [texts by rank]."""
    edits: list[Edit] = []
    for c in claims:
        cid, s, e = c["claim_id"], c["start"], c["end"]
        if c["verdict"] == "SUPPORTED":
            continue
        failed = [n for n, st in c["rules"].items() if st == "fail"]
        ev = c["evidence"]
        if not failed:
            edits.append(Edit(cid, "review", reason="flagged by NLI only; no rule pinpoints the error"))
            continue
        claim_edits: list[Edit] = []
        if "entities" in failed:
            ed = repair_entity(cid, summary, s, e, ev, safe_summary, safe_union)
            if ed.action == "delete":
                edits.append(ed)
                continue
            claim_edits.append(ed)
        if "dates" in failed:
            ed = repair_date(cid, summary, s, e, ev)
            if ed is None:
                edits.append(Edit(cid, "review", reason="date rule failed but no evidence date to copy"))
                continue
            claim_edits.append(ed)
        if "numbers" in failed:
            eds = repair_numbers(cid, summary, s, e, ev)
            if eds is None and "dates" not in failed:
                edits.append(Edit(cid, "review", reason="number rule failed but no unambiguous evidence number"))
                continue
            claim_edits += eds or []
        if "negation" in failed:
            ed = repair_negation(cid, summary, s, e, ev)
            if ed is None:
                edits.append(Edit(cid, "review", reason="negation mismatch but no insertion point"))
                continue
            claim_edits.append(ed)
        edits += claim_edits
    return RepairResult(summary, apply_edits(summary, edits), edits)


def apply_edits(text: str, edits: list[Edit]) -> str:
    """Apply edits right-to-left. Overlapping DELETIONS are merged (adjacent deleted sentences share
    a space); any other overlap keeps the later edit only, so no edit is applied to stale offsets."""
    spans = sorted([(e.start, e.end, e.new) for e in edits if e.start >= 0], reverse=True)
    merged: list[list] = []
    for a, b, new in spans:
        if merged and b > merged[-1][0]:                 # overlaps the edit to its right
            if new == "" and merged[-1][2] == "":
                merged[-1][0] = min(a, merged[-1][0])    # merge two deletions into one span
            continue
        merged.append([a, b, new])
    for a, b, new in merged:
        text = text[:a] + new + text[b:]
    return text.strip() if any(new == "" for _, _, new in merged) else text
