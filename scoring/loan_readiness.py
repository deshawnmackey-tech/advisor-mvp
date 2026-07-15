"""
Deterministic loan-readiness (SBA underwriting) scoring.

Zero LLM calls.  Every number traces back to a plain calculation on the
client's own data.  The agent layer only explains and interrogates these
numbers -- it never computes them.

Findings are plain dicts (TypedDict) for the same reasons documented in
scoring/sale_readiness.py -- they must survive LangGraph and Orchestrate
serialize/restore cycles.
"""

from scoring.models import Finding, Severity, compute_weighted_score, sort_findings

METRIC_WEIGHTS = {
    "debt_service_coverage": 24,
    "cash_buffer": 14,
    "bank_reconciliation": 12,
    "tax_return_readiness": 10,
}


def _debt_service_finding(business: dict) -> Finding:
    ebitda = float(business.get("ebitda", 0) or 0)
    debt_service = float(business.get("annual_debt_service", 0) or 0)
    dscr = round(ebitda / debt_service, 2) if debt_service else 99.0

    if dscr < 1.15:
        severity: Severity = "high"
    elif dscr < 1.35:
        severity = "medium"
    else:
        severity = "low"

    return Finding(
        metric="debt_service_coverage",
        value=f"{dscr}x DSCR",
        severity=severity,
        weight=METRIC_WEIGHTS["debt_service_coverage"],
        narrative=f"EBITDA covers scheduled annual debt service by {dscr}x.",
        fix_narrative=(
            "Raise DSCR above 1.35x by reducing debt service, improving margins, "
            "or documenting recurring cash flow before applying."
        ),
        contract_status=None,
    )


def _cash_buffer_finding(business: dict) -> Finding:
    cash = float(business.get("cash_balance", 0) or 0)
    monthly_expenses = float(business.get("monthly_operating_expenses", 1) or 1)
    months = round(cash / monthly_expenses, 1) if monthly_expenses else 0.0

    if months < 1.5:
        severity: Severity = "high"
    elif months < 3:
        severity = "medium"
    else:
        severity = "low"

    return Finding(
        metric="cash_buffer",
        value=f"{months} months of operating expenses on hand",
        severity=severity,
        weight=METRIC_WEIGHTS["cash_buffer"],
        narrative=f"The business has enough cash to cover {months} months of operating expenses.",
        fix_narrative="Build a three-month cash buffer or secure an unused credit line before underwriting.",
        contract_status=None,
    )


def _bank_reconciliation_finding(business: dict) -> Finding:
    pct = float(business.get("bank_reconciliation_pct", 0) or 0)
    severity: Severity = "high" if pct < 70 else "medium" if pct < 90 else "low"
    return Finding(
        metric="bank_reconciliation",
        value=f"{pct}% of revenue is reconciled to bank deposits",
        severity=severity,
        weight=METRIC_WEIGHTS["bank_reconciliation"],
        narrative=f"{pct}% of reported revenue has been reconciled to bank deposits.",
        fix_narrative="Reconcile monthly deposits to accounting revenue and keep source documents in the loan file.",
        contract_status=None,
    )


def _tax_filing_finding(business: dict) -> Finding:
    years = int(business.get("tax_returns_ready_years", 0) or 0)
    severity: Severity = "high" if years < 2 else "medium" if years < 3 else "low"
    return Finding(
        metric="tax_return_readiness",
        value=f"{years} years of business tax returns are ready",
        severity=severity,
        weight=METRIC_WEIGHTS["tax_return_readiness"],
        narrative=f"The loan file currently has {years} years of business tax returns ready.",
        fix_narrative="Prepare a clean three-year tax-return package with matching financial statements.",
        contract_status=None,
    )


def compute_findings(business: dict) -> list[Finding]:
    """Run every metric and return findings ordered by severity, worst first."""
    findings = [
        _debt_service_finding(business),
        _cash_buffer_finding(business),
        _bank_reconciliation_finding(business),
        _tax_filing_finding(business),
    ]
    return sort_findings(findings)


def compute_score(findings: list[Finding]) -> int:
    return compute_weighted_score(findings)
