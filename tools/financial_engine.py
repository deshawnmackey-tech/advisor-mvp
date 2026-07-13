from typing import Dict, Tuple

import pandas as pd
from feast import FeatureStore


class FinancialEngine:
    """Deterministic financial calculations sourced from Feast features."""

    def __init__(self, client_id: str):
        self.client_id = client_id
        self.store = FeatureStore(repo_path="feature_repo/")

    @staticmethod
    def _first_value(values, default: float = 0.0) -> float:
        """Normalize Feast online feature payloads to scalar floats."""
        if values is None:
            return default
        if isinstance(values, list):
            if not values:
                return default
            values = values[0]
        try:
            return float(values)
        except (TypeError, ValueError):
            return default

    def _load_features(self) -> Dict[str, float]:
        raw = self.store.get_online_features(
            entity_rows=[{"client_id": self.client_id}],
            features=[
                "business_profile_fv:revenue_ttm",
                "business_profile_fv:ebitda_ttm",
                "business_profile_fv:debt_service",
                "business_profile_fv:working_capital_ratio",
                "business_profile_fv:customer_concentration",
                "business_profile_fv:revenue_growth_yoy",
                "business_profile_fv:doc_completeness",
                "business_profile_fv:clinical_revenue",
                "business_profile_fv:payer_mix_score",
            ],
        ).to_dict()

        return {
            "revenue_ttm": self._first_value(raw.get("revenue_ttm")),
            "ebitda_ttm": self._first_value(raw.get("ebitda_ttm")),
            "debt_service": self._first_value(raw.get("debt_service"), 1e-6),
            "working_capital_ratio": self._first_value(raw.get("working_capital_ratio")),
            "customer_concentration": self._first_value(raw.get("customer_concentration")),
            "revenue_growth_yoy": self._first_value(raw.get("revenue_growth_yoy")),
            "doc_completeness": self._first_value(raw.get("doc_completeness")),
            "clinical_revenue": self._first_value(raw.get("clinical_revenue")),
            "payer_mix_score": self._first_value(raw.get("payer_mix_score")),
        }

    def compute_ratios(self) -> Tuple[Dict[str, float], float]:
        f = self._load_features()
        dscr = f["ebitda_ttm"] / max(f["debt_service"], 1e-6)

        health = (
            0.3 * dscr
            + 0.2 * f["working_capital_ratio"]
            + 0.2 * (1 - f["customer_concentration"])
            + 0.2 * f["doc_completeness"]
            + 0.1 * f.get("payer_mix_score", 0.0)
        )

        ratios = {
            "dscr": round(dscr, 2),
            "working_capital_ratio": round(f["working_capital_ratio"], 2),
            "customer_concentration": round(f["customer_concentration"], 2),
            "doc_completeness": round(f["doc_completeness"], 2),
        }

        return ratios, min(max(health, 0.0), 1.0)

    def forecast_cashflow(self, months: int = 12) -> Tuple[pd.DataFrame, float]:
        f = self._load_features()
        growth = f["revenue_growth_yoy"]
        ebitda = f["ebitda_ttm"]

        dates = pd.date_range(start=pd.Timestamp.today(), periods=months, freq="M")
        fcff = [
            ebitda * ((1 + growth) ** i) * 0.75
            for i in range(1, months + 1)
        ]

        df = pd.DataFrame({"date": dates, "fcff": fcff})
        confidence = 0.9 if growth >= 0 else 0.6
        return df, confidence
