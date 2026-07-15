"""
Shared scoring utilities.

Findings are plain dicts (typed via the Finding TypedDict in
sale_readiness.py) rather than dataclass instances.  This is intentional:
LangGraph checkpointers serialize graph state, and watsonx Orchestrate's
imported-agent runtime only reliably preserves message-shaped state between
conversation turns -- custom class instances are exactly the thing to avoid
putting in state that has to survive a serialize/restore cycle.
"""

from typing import Literal

# Re-export Finding and Severity from the canonical definition so other
# modules can import from here without creating a circular dependency.
from scoring.sale_readiness import Finding, Severity  # noqa: F401

Lens = Literal["sale", "loan", "investor"]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PENALTY_FRACTION = {"high": 1.0, "medium": 0.5, "low": 0.0}


def compute_weighted_score(findings: list[Finding]) -> int:
    """Weighted 0-100 baseline score.  High costs full weight, medium half, low none."""
    score = 100
    for f in findings:
        score -= f["weight"] * PENALTY_FRACTION[f["severity"]]
    return max(0, round(score))


def sort_findings(findings: list[Finding]) -> list[Finding]:
    effort_order = {"low": 0, "medium": 1, "high": 2}
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER[f["severity"]], effort_order.get(f.get("effort", "medium"), 1), -f["weight"]),
    )
