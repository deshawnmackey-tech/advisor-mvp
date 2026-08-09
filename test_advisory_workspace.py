import unittest

from advisor_workspace import advisory_orchestrator


class AdvisoryWorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.payload = {
            "accounting": {
                "revenue": 1_000_000,
                "cogs": 400_000,
                "ebitda": 150_000,
                "current_assets": 200_000,
                "current_liabilities": 120_000,
            },
            "banking": {"cash_balance": 180_000, "monthly_deposits": [80_000, 90_000, 95_000]},
            "payroll": {"monthly_payroll": 50_000, "employee_count": 12},
            "crm": {
                "open_pipeline": 300_000,
                "win_rate": 0.30,
                "recurring_revenue_ratio": 0.55,
                "top_customer_revenue_share": 0.20,
                "nrr": 108,
            },
            "debt": {"total_debt": 250_000, "monthly_debt_service": 7_500},
        }

    def test_run_all_lenses_on_sandbox(self) -> None:
        result = advisory_orchestrator(self.payload)
        outputs = result["advisory"]["specialist_outputs"]
        self.assertEqual(result["environment"]["name"], "archy-wxo-sandbox")
        self.assertIn("sale_readiness_advisor", outputs)
        self.assertIn("sba_loan_advisor", outputs)
        self.assertIn("investor_readiness_advisor", outputs)

    def test_single_lens_routing(self) -> None:
        result = advisory_orchestrator(self.payload, lens="sale")
        outputs = result["advisory"]["specialist_outputs"]
        self.assertEqual(list(outputs.keys()), ["sale_readiness_advisor"])

    def test_scores_are_bounded(self) -> None:
        payload = {
            "accounting": {"revenue": 0, "cogs": 0, "ebitda": -100, "current_assets": 0, "current_liabilities": 0},
            "banking": {"cash_balance": 0, "monthly_deposits": []},
            "payroll": {"monthly_payroll": 0, "employee_count": 0},
            "crm": {
                "open_pipeline": 0,
                "win_rate": 10,
                "recurring_revenue_ratio": -5,
                "top_customer_revenue_share": 5,
                "nrr": -100,
            },
            "debt": {"total_debt": 0, "monthly_debt_service": 0},
        }
        result = advisory_orchestrator(payload)
        for specialist in result["advisory"]["specialist_outputs"].values():
            self.assertGreaterEqual(specialist["score"], 0)
            self.assertLessEqual(specialist["score"], 100)


if __name__ == "__main__":
    unittest.main()
