"""
Deterministic sale-readiness scoring.

This module intentionally contains zero LLM calls. Every number a customer
sees traces back to a plain arithmetic calculation on their own data, so it
can be audited, unit-tested, and never hallucinates. The agent layer (see
agents/graph.py) only *explains* and *interrogates* these numbers -- it
never computes them.

Findings are plain dicts (typed via `Finding`, a TypedDict) rather than
dataclass instances. This matters beyond style: LangGraph checkpointers
serialize graph state, and watsonx Orchestrate's imported-agent runtime
only reliably preserves message-shaped state between conversation turns --
custom class instances are exactly the thing to avoid putting in state.
"""

from typing import Literal, TypedDict

Severity = Literal["high", "medium", "low"]

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
PENALTY_FRACTION = {"high": 1.0, "medium": 0.5, "low": 0.0}
METRIC_WEIGHTS = {
    "customer_concentration": 18,
    "owner_dependency": 16,
    "recurring_revenue": 10,
    "documentation_completeness": 8,
}


class Finding(TypedDict):
    metric: str
    value: str
    severity: Severity
    weight: int  # points deducted from a 100-point baseline, at "high" severity
    narrative: str
    fix_narrative: str
    contract_status: str | None


def _to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clamp_pct(value: float) -> float:
    return max(0.0, min(100.0, value))


def _severity_high_bad(value: float, high_min: float, medium_min: float) -> Severity:
    """Higher values are worse (example: concentration %)."""
    if value >= high_min:
        return "high"
    if value >= medium_min:
        return "medium"
    return "low"


def _severity_low_bad(value: float, high_max: float, medium_max: float) -> Severity:
    """Lower values are worse (example: recurring revenue %)."""
    if value < high_max:
        return "high"
    if value < medium_max:
        return "medium"
    return "low"


def _concentration_finding(business: dict) -> Finding:
    customers = business.get("customer_revenue", {})
    revenue = _to_float(business.get("annual_revenue"), default=0.0)
    top_customer, top_amount = max(
        ((k, v) for k, v in customers.items() if k != "all_other_customers"),
        key=lambda kv: kv[1],
        default=("unknown_customer", 0),
    )
    pct = round(_clamp_pct((_to_float(top_amount) / revenue * 100) if revenue > 0 else 0.0), 1)
    severity: Severity = _severity_high_bad(pct, high_min=30.0, medium_min=20.0)

    has_contract = top_customer in business.get("customers_with_multiyear_contracts", [])
    contract_status = "multi-year contract on file" if has_contract else "no contract on file"

    return Finding(
        metric="customer_concentration",
        value=f"{top_customer} is {pct}% of revenue",
        severity=severity if not has_contract else ("medium" if severity == "high" else severity),
        weight=METRIC_WEIGHTS["customer_concentration"],
        narrative=(
            f"{top_customer} accounts for {pct}% of annual revenue "
            f"({contract_status})."
        ),
        fix_narrative=(
            "Diversifying this customer below 20% of revenue, or securing a signed "
            "multi-year agreement, typically adds 0.5-1.0x to a sale multiple within "
            "12-18 months."
        ),
        contract_status=contract_status,
    )


def _owner_dependency_finding(business: dict) -> Finding:
    processes = business.get("owner_dependent_processes", [])
    count = _to_int(len(processes))
    severity: Severity = "high" if count >= 3 else "medium" if count >= 1 else "low"
    return Finding(
        metric="owner_dependency",
        value=f"{count} undocumented owner-only processes",
        severity=severity,
        weight=METRIC_WEIGHTS["owner_dependency"],
        narrative=(
            "Contract renewals, crew scheduling, and vendor pricing all run through "
            "the owner personally, with no documented process behind them."
            if count
            else "Operations run without the owner personally being a single point of failure."
        ),
        fix_narrative=(
            "Documenting these processes and cross-training a second person on each "
            "removes the biggest reason buyers discount owner-run businesses."
        ),
        contract_status=None,
    )


def _recurring_revenue_finding(business: dict) -> Finding:
    pct = round(_clamp_pct(_to_float(business.get("recurring_revenue_pct"), default=0.0)), 1)
    severity: Severity = _severity_low_bad(pct, high_max=50.0, medium_max=70.0)
    return Finding(
        metric="recurring_revenue",
        value=f"{pct}% of revenue is recurring",
        severity=severity,
        weight=METRIC_WEIGHTS["recurring_revenue"],
        narrative=f"{pct}% of revenue comes from recurring service contracts.",
        fix_narrative="Converting more one-off work into recurring contracts raises earnings quality.",
        contract_status=None,
    )


def _documentation_finding(business: dict) -> Finding:
    pct = round(_clamp_pct(_to_float(business.get("documentation_completeness_pct"), default=0.0)), 1)
    severity: Severity = _severity_low_bad(pct, high_max=60.0, medium_max=85.0)
    return Finding(
        metric="documentation_completeness",
        value=f"{pct}% of standard diligence documents are ready",
        severity=severity,
        weight=METRIC_WEIGHTS["documentation_completeness"],
        narrative=f"Only {pct}% of the documents a buyer will request are currently organized.",
        fix_narrative="Assembling contracts, financials, and org charts into one place now avoids a scramble later.",
        contract_status=None,
    )


def compute_findings(business: dict) -> list[Finding]:
    """Run every metric and return findings ordered by severity, worst first."""
    findings = [
        _concentration_finding(business),
        _owner_dependency_finding(business),
        _recurring_revenue_finding(business),
        _documentation_finding(business),
    ]
    return sorted(findings, key=lambda f: SEVERITY_ORDER[f["severity"]])


def compute_score(findings: list[Finding]) -> int:
    """Weighted 0-100 baseline score. High severity costs full weight, medium half, low none."""
    score = 100
    for f in findings:
        score -= f["weight"] * PENALTY_FRACTION[f["severity"]]
    return max(0, round(score))
