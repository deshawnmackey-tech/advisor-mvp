"""
Deterministic investor-readiness scoring.

Zero LLM calls.  Every number traces back to a plain calculation on the
client's own data.  The agent layer only explains and interrogates these
numbers -- it never computes them.

Findings are plain dicts (TypedDict) for serialization safety -- see the
note in scoring/sale_readiness.py.
"""

from scoring.models import Finding, Severity, compute_weighted_score, sort_findings

METRIC_WEIGHTS = {
    "revenue_growth": 22,
    "net_revenue_retention": 18,
    "gross_margin": 16,
    "investor_customer_concentration": 12,
}


def _growth_finding(business: dict) -> Finding:
    growth = float(business.get("yoy_revenue_growth_pct", 0) or 0)
    severity: Severity = "high" if growth < 15 else "medium" if growth < 35 else "low"
    return Finding(
        metric="revenue_growth",
        value=f"{growth}% year-over-year revenue growth",
        severity=severity,
        weight=METRIC_WEIGHTS["revenue_growth"],
        narrative=f"Revenue grew {growth}% year over year.",
        fix_narrative=(
            "Build a clear growth plan tied to repeatable channels, pipeline, "
            "and measurable conversion rates."
        ),
        contract_status=None,
    )


def _margin_finding(business: dict) -> Finding:
    margin = float(business.get("gross_margin_pct", 0) or 0)
    severity: Severity = "high" if margin < 35 else "medium" if margin < 50 else "low"
    return Finding(
        metric="gross_margin",
        value=f"{margin}% gross margin",
        severity=severity,
        weight=METRIC_WEIGHTS["gross_margin"],
        narrative=f"Gross margin is {margin}%, which frames how efficiently revenue scales.",
        fix_narrative=(
            "Identify low-margin work, renegotiate pricing, and standardize "
            "delivery before fundraising."
        ),
        contract_status=None,
    )


def _retention_finding(business: dict) -> Finding:
    nrr = float(business.get("net_revenue_retention_pct", 0) or 0)
    severity: Severity = "high" if nrr < 95 else "medium" if nrr < 110 else "low"
    return Finding(
        metric="net_revenue_retention",
        value=f"{nrr}% net revenue retention",
        severity=severity,
        weight=METRIC_WEIGHTS["net_revenue_retention"],
        narrative=f"Existing customers expand to {nrr}% of prior-period revenue after churn and upsell.",
        fix_narrative="Create a retention and expansion motion before presenting the business as scalable.",
        contract_status=None,
    )


def _customer_concentration_finding(business: dict) -> Finding:
    customers = business.get("customer_revenue", {})
    revenue = float(business.get("annual_revenue", 0) or 0)
    top_customer, top_amount = max(
        ((k, v) for k, v in customers.items() if k != "all_other_customers"),
        key=lambda kv: kv[1],
        default=("unknown_customer", 0),
    )
    pct = round(float(top_amount) / revenue * 100, 1) if revenue > 0 else 0.0
    severity: Severity = "high" if pct >= 25 else "medium" if pct >= 15 else "low"
    return Finding(
        metric="investor_customer_concentration",
        value=f"{top_customer} is {pct}% of revenue",
        severity=severity,
        weight=METRIC_WEIGHTS["investor_customer_concentration"],
        narrative=f"{top_customer} represents {pct}% of revenue, which can weaken the growth story.",
        fix_narrative=(
            "Reduce dependence on the largest account or show a contracted "
            "expansion path across multiple customers."
        ),
        contract_status=None,
    )


def compute_findings(business: dict) -> list[Finding]:
    """Run every metric and return findings ordered by severity, worst first."""
    findings = [
        _growth_finding(business),
        _margin_finding(business),
        _retention_finding(business),
        _customer_concentration_finding(business),
    ]
    return sort_findings(findings)


def compute_score(findings: list[Finding]) -> int:
    return compute_weighted_score(findings)
