"""complianceAgent (SRS §7.6): trademark/IP scanning against the editable blocklist."""
import re
from dataclasses import dataclass, field

from ..config import compliance_config


@dataclass
class ComplianceResult:
    blocked: bool = False
    needs_ai_disclosure: bool = False
    flags: list[dict] = field(default_factory=list)

    @property
    def risk_score(self) -> float:
        """0-100 ipRiskScore contribution: blocked terms dominate, soft flags add up."""
        score = 0.0
        for f in self.flags:
            score += 100.0 if f["severity"] == "blocked" else 25.0
        return min(score, 100.0)


def _word_match(term: str, text: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term)}(?!\w)", text) is not None


def scan_text(*texts: str) -> ComplianceResult:
    cfg = compliance_config()
    joined = " ".join(t for t in texts if t).lower()
    result = ComplianceResult()

    for category, terms in cfg.get("blocked_terms", {}).items():
        for term in terms:
            if _word_match(term.lower(), joined):
                result.flags.append({"term": term, "category": category, "severity": "blocked"})
                result.blocked = True

    for pattern in cfg.get("flag_patterns", []):
        if pattern.lower() in joined:
            result.flags.append({"term": pattern, "category": "pattern", "severity": "flag"})

    for trigger in cfg.get("ai_disclosure_triggers", []):
        if trigger.lower() in joined:
            result.needs_ai_disclosure = True

    return result
