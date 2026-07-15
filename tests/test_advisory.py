"""
Unified test suite for the advisory MVP.

Covers:
  - All three deterministic scoring lenses (no LLM, no API key required)
  - Multi-lens orchestrator report
  - Async agent fallback responses (no API key required -- exercises the
    deterministic compatibility fallback path in AgentBase)
"""

import json
import unittest
from pathlib import Path

import pytest

from agent.orchestrator import AdvisoryReport, build_report
from orchestrator import get_agent
from scoring import investor_readiness, loan_readiness, sale_readiness

ROOT = Path(__file__).resolve().parents[1]


def load_sample() -> dict:
    with open(ROOT / "data" / "sample_business.json") as f:
        return json.load(f)


# ── deterministic scoring tests ───────────────────────────────────────────────

class ScoringTest(unittest.TestCase):

    def setUp(self):
        self.business = load_sample()

    def test_each_lens_returns_a_score_between_zero_and_one_hundred(self):
        for module in (sale_readiness, loan_readiness, investor_readiness):
            findings = module.compute_findings(self.business)
            score = module.compute_score(findings)
            self.assertGreater(len(findings), 0, f"{module.__name__} returned no findings")
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 100)

    def test_sale_findings_are_dicts(self):
        """Findings must be plain dicts (TypedDict) not dataclass instances."""
        findings = sale_readiness.compute_findings(self.business)
        for finding in findings:
            self.assertIsInstance(finding, dict)
            self.assertIn("metric", finding)
            self.assertIn("severity", finding)
            self.assertIn("weight", finding)

    def test_loan_findings_include_dscr(self):
        findings = loan_readiness.compute_findings(self.business)
        metrics = {f["metric"] for f in findings}
        self.assertIn("debt_service_coverage", metrics)

    def test_investor_findings_include_growth(self):
        findings = investor_readiness.compute_findings(self.business)
        metrics = {f["metric"] for f in findings}
        self.assertIn("revenue_growth", metrics)


# ── multi-lens orchestrator tests ─────────────────────────────────────────────

class OrchestratorTest(unittest.TestCase):

    def setUp(self):
        self.business = load_sample()

    def test_builds_three_lens_report_by_default(self):
        report = build_report(self.business)
        self.assertIsInstance(report, AdvisoryReport)
        lenses = [r.lens for r in report.lens_reports]
        self.assertEqual(lenses, ["sale", "loan", "investor"])

    def test_prioritized_actions_capped_at_three(self):
        report = build_report(self.business)
        self.assertLessEqual(len(report.prioritized_actions), 3)

    def test_goal_limits_report_to_requested_lens(self):
        report = build_report(self.business, goal="loan")
        self.assertEqual(len(report.lens_reports), 1)
        self.assertEqual(report.lens_reports[0].lens, "loan")

    def test_advisor_review_required_on_high_severity(self):
        report = build_report(self.business)
        self.assertTrue(report.advisor_review_required)

    def test_reconciled_risks_is_a_list_of_strings(self):
        report = build_report(self.business)
        for risk in report.reconciled_risks:
            self.assertIsInstance(risk, str)


# ── async agent fallback tests (no API key required) ─────────────────────────

@pytest.mark.asyncio
async def test_sale_agent_fallback():
    agent = get_agent("sale", "demo_client", "Am I ready to sell?")
    result = await agent.run()
    assert "snapshot" in result
    assert "actions" in result
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_loan_agent_fallback():
    agent = get_agent("loan", "demo_client", "Can I get an SBA loan?")
    result = await agent.run()
    assert "snapshot" in result
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_investor_agent_fallback():
    agent = get_agent("investor", "demo_client", "What should I include in a seed pitch?")
    result = await agent.run()
    assert "snapshot" in result
    assert "disclaimer" in result


@pytest.mark.asyncio
async def test_general_agent_fallback():
    agent = get_agent("general", "demo_client", "Give me a health overview.")
    result = await agent.run()
    assert "disclaimer" in result


if __name__ == "__main__":
    unittest.main()
