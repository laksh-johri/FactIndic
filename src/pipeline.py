"""End-to-end FactIndic pipeline for ONE (source, summary) pair – used by the demo (app.py).

It chains exactly the components and config.yaml settings used in the experiments:
  (2) clause decomposition -> (3) top-k evidence (lexical+norm) -> (4) rule checks + NLI ->
  decision rule -> (5) selective repair of flagged claims -> (6) re-verification of the output.
Final status: 'accepted' if every claim of the (repaired) summary is SUPPORTED, else 'human_review'.
(Step 1, summary generation, needs an LLM API key, so the demo starts from a given summary.)

tests/test_pipeline.py checks that this module reproduces the stored Step 5 outputs exactly.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

from src.config import load_config, set_seed
from src.data import get_split, load_articles
from src.decompose import decompose
from src.nli import NLIModel
from src.repair import RepairResult, repair_summary
from src.retrieve import Retriever, split_source
from src.rules import RuleResult, build_safe_vocab, run_rules
from src.verify import decide


@dataclass
class ClaimResult:
    claim_id: str
    text: str
    start: int
    end: int
    evidence: list = field(default_factory=list)   # [{rank, sent_idx, text, score, start, end}]
    premise: str = ""                               # text given to NLI as premise
    rules: dict = field(default_factory=dict)       # name -> {"status", "reason"}
    nli: dict = field(default_factory=dict)         # {"entailment", "neutral", "contradiction"}
    verdict: str = ""
    reason: str = ""

    def repair_input(self) -> dict:
        return {"claim_id": self.claim_id, "start": self.start, "end": self.end, "verdict": self.verdict,
                "rules": {k: v["status"] for k, v in self.rules.items()},
                "evidence": [e["text"] for e in self.evidence]}


@dataclass
class PipelineResult:
    source: str
    summary: str
    claims: list                 # list[ClaimResult] for the input summary
    repair: RepairResult
    recheck: list                # list[ClaimResult] for the repaired summary
    status: str                  # accepted | human_review

    @property
    def flagged(self) -> bool:
        return any(c.verdict != "SUPPORTED" for c in self.claims)

    def to_dict(self) -> dict:
        return {"source": self.source, "summary": self.summary, "flagged": self.flagged,
                "claims": [asdict(c) for c in self.claims], "repair": self.repair.to_dict(),
                "recheck": [asdict(c) for c in self.recheck], "status": self.status}


class FactIndicPipeline:
    def __init__(self, cfg: dict | None = None, nli: NLIModel | None = None, retriever: Retriever | None = None,
                 safe: set[str] | None = None, safe_union: set[str] | None = None):
        self.cfg = cfg or load_config()
        set_seed(self.cfg["seed"])
        vc = self.cfg["verification"]
        self.tau, self.premise_mode, self.rules = vc["nli_threshold"], vc["nli_premise"], tuple(vc["rules"])
        self.method = self.cfg["decomposition"]["method"]
        if safe is None or safe_union is None:      # learned from DEV only, exactly as in Steps 4-5
            dev = get_split(load_articles(), "dev")
            safe = build_safe_vocab(dev["summary"].tolist(), dev["key_facts"].tolist())
            safe_union = safe | build_safe_vocab(dev["text"].tolist(), dev["key_facts"].tolist())
        self.safe, self.safe_union = safe, safe_union
        self.retriever = retriever or Retriever()
        self.nli = nli or NLIModel()

    def _premise(self, evidence: list) -> str:
        if self.premise_mode == "top1":
            return evidence[0].text
        return " ".join(e.text for e in sorted(evidence, key=lambda e: e.sent_idx))   # concat

    def verify(self, source: str, summary: str, prefix: str = "c") -> list[ClaimResult]:
        """Steps 2-4: decompose, retrieve evidence, rule checks + NLI, decision rule."""
        if not split_source(source):
            raise ValueError("The source text contains no sentences.")
        claims = decompose(summary, self.method, prefix=prefix)
        if not claims:
            return []
        evs = self.retriever.retrieve_many([c.text for c in claims], source)
        out = []
        for c, ev in zip(claims, evs):
            rules = run_rules(c.text, [e.text for e in ev], self.safe, enabled=self.rules)
            out.append(ClaimResult(c.claim_id, c.text, c.start, c.end, [e.to_dict() for e in ev],
                                   self._premise(ev), {r.name: {"status": r.status, "reason": r.reason} for r in rules}))
        probs = self.nli.predict([(c.premise, c.text) for c in out])
        for c, p in zip(out, probs):
            v = decide(p, [RuleResult(n, r["status"], r["reason"]) for n, r in c.rules.items()], self.tau, "full")
            c.nli, c.verdict, c.reason = p, v.label, v.reason
        return out

    def run(self, source: str, summary: str) -> PipelineResult:
        """Steps 2-6 on one summary."""
        claims = self.verify(source, summary)
        rep = repair_summary(summary, [c.repair_input() for c in claims], self.safe, self.safe_union)
        recheck = self.verify(source, rep.repaired, prefix="r") if rep.repaired.strip() else []
        ok = bool(recheck) and all(c.verdict == "SUPPORTED" for c in recheck)
        return PipelineResult(source, summary, claims, rep, recheck, "accepted" if ok else "human_review")
