"""
Multi-lens orchestrator.

Runs the deterministic specialist scoring modules (sale, loan, investor)
and reconciles their findings into a single AdvisoryReport.  No LLM calls
are made here.  The agent layer in agents/ only explains and interrogates
these numbers -- it never computes them.
"""

from dataclasses import dataclass, field
from typing import Literal

from scoring import investor_readiness, loan_readiness, sale_readiness
from scoring.models import Finding, Lens

Goal = Literal["sale", "loan", "investor", "all"]

SPECIALISTS = {
    "sale": (sale_readiness.compute_findings, sale_readiness.compute_score),
    "loan": (loan_readiness.compute_findings, loan_readiness.compute_score),
    "investor": (investor_readiness.compute_findings, investor_readiness.compute_score),
}


@dataclass
class LensReport:
    lens: Lens
    score: int
    findings: list[Finding]
    summary: str


@dataclass
class AdvisoryReport:
    business_name: str
    goal: Goal
    lens_reports: list[LensReport]
    prioritized_actions: list[Finding]
    reconciled_risks: list[str]
    advisor_review_required: bool


def _summary_for(lens: Lens, score: int, findings: list[Finding]) -> str:
    severe = [f for f in findings if f["severity"] == "high"]
    if not severe:
        return f"{lens.replace('_', ' ').title()} readiness is strong; current gaps are mostly maintenance items."
    top = severe[0]
    return (
        f"{lens.replace('_', ' ').title()} readiness is constrained most by "
        f"{top['metric'].replace('_', ' ')}: {top['value']}."
    )


def _run_lens(lens: Lens, business: dict) -> LensReport:
    compute_findings, compute_score = SPECIALISTS[lens]
    findings = compute_findings(business)
    score = compute_score(findings)
    return LensReport(
        lens=lens,
        score=score,
        findings=findings,
        summary=_summary_for(lens, score, findings),
    )


def _target_lenses(goal: Goal) -> list[Lens]:
    if goal == "all":
        return ["sale", "loan", "investor"]
    return [goal]


def _action_rank(finding: Finding) -> tuple[int, int, int]:
    severity_rank = {"high": 0, "medium": 1, "low": 2}
    effort_rank = {"low": 0, "medium": 1, "high": 2}
    return (
        severity_rank[finding["severity"]],
        effort_rank.get(finding.get("effort", "medium"), 1),
        -finding["weight"],
    )


def _dedupe_actions(findings: list[Finding]) -> list[Finding]:
    seen: set[str] = set()
    actions: list[Finding] = []
    for finding in sorted(findings, key=_action_rank):
        key = finding["metric"].replace("investor_", "")
        if key in seen:
            continue
        seen.add(key)
        actions.append(finding)
    return actions


def _reconciled_risks(findings: list[Finding]) -> list[str]:
    concentration = [
        f for f in findings
        if "concentration" in f["metric"] and f["severity"] in {"high", "medium"}
    ]
    documentation = [
        f for f in findings
        if "documentation" in f["metric"] or "reconciliation" in f["metric"]
    ]

    risks: list[str] = []
    if len(concentration) > 1:
        risks.append(
            "Customer concentration appears in multiple lenses, so it should be treated "
            "as a strategic risk, not only a valuation issue."
        )
    if any(f["severity"] == "high" for f in documentation):
        risks.append(
            "Documentation gaps affect customer-facing readiness and should go through "
            "advisor review before release."
        )
    return risks


def build_report(business: dict, goal: Goal = "all", action_limit: int = 3) -> AdvisoryReport:
    lens_reports = [_run_lens(lens, business) for lens in _target_lenses(goal)]
    findings = [f for report in lens_reports for f in report.findings]
    severe_findings = [f for f in findings if f["severity"] in {"high", "medium"}]
    actions = _dedupe_actions(severe_findings)[:action_limit]
    return AdvisoryReport(
        business_name=business["name"],
        goal=goal,
        lens_reports=lens_reports,
        prioritized_actions=actions,
        reconciled_risks=_reconciled_risks(findings),
        advisor_review_required=any(f["severity"] == "high" for f in findings),
    )
