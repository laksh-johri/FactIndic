"""Claim verification = NLI + rule checks + the FactIndic decision rule.

Decision rule (threshold tau = config verification.nli_threshold, tuned on DEV):
  1. any rule check fails                  -> CONTRADICTED   (rules are exact, so they win)
  2. P(entailment)    >= tau               -> SUPPORTED
  3. P(contradiction) >= tau               -> CONTRADICTED
  4. P(neutral)       >= tau               -> UNSUPPORTED
  5. no label reaches tau (low confidence) -> REVIEW         (send to a human)
With tau >= 0.5 at most one NLI label can pass the threshold, so the order of 2-4 never matters.
SUPPORTED therefore requires NLI entailment AND all rules passing, as specified in CLAUDE.md.

Ablations: mode="nli_only" skips step 1; mode="rules_only" ignores NLI
(SUPPORTED if all rules pass/na, else CONTRADICTED).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.rules import RuleResult

VERDICTS = ("SUPPORTED", "CONTRADICTED", "UNSUPPORTED", "REVIEW")


@dataclass
class Verdict:
    label: str
    reason: str
    nli: dict = field(default_factory=dict)
    failed_rules: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def decide(nli: dict | None, rules: list[RuleResult], tau: float, mode: str = "full") -> Verdict:
    if mode not in ("full", "nli_only", "rules_only"):
        raise ValueError(mode)
    if not 0.5 <= tau <= 1.0 and mode != "rules_only":
        raise ValueError("tau must be in [0.5, 1] so that at most one NLI label passes")
    failed = [r for r in rules if r.status == "fail"]
    if mode != "nli_only" and failed:
        return Verdict("CONTRADICTED", "; ".join(f"{r.name}: {r.reason}" for r in failed), nli or {},
                       [r.name for r in failed])
    if mode == "rules_only":
        return Verdict("SUPPORTED", "all rule checks passed or not applicable", nli or {}, [])
    p = nli
    if p["entailment"] >= tau:
        return Verdict("SUPPORTED", f"NLI entailment {p['entailment']:.2f} >= {tau}", p)
    if p["contradiction"] >= tau:
        return Verdict("CONTRADICTED", f"NLI contradiction {p['contradiction']:.2f} >= {tau}", p)
    if p["neutral"] >= tau:
        return Verdict("UNSUPPORTED", f"NLI neutral {p['neutral']:.2f} >= {tau}", p)
    top = max(p, key=p.get)
    return Verdict("REVIEW", f"low confidence: best NLI label {top} = {p[top]:.2f} < {tau}", p)


def summary_flagged(verdicts: list[Verdict]) -> bool:
    """A summary is flagged as containing an error if any claim is not SUPPORTED."""
    return any(v.label != "SUPPORTED" for v in verdicts)
