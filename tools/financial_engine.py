import json
import os
from pathlib import Path
from typing import Dict, Tuple

import pandas as pd


class FinancialEngine:
    """
    Deterministic financial calculations.

    Data source priority:
      1. Feast online store (if feast is installed and the store is materialized)
      2. JSON file at data/sample_business.json (local dev fallback)
    """

    # Fields mapped from the business JSON to the Feast feature names
    _JSON_MAP = {
        "revenue_ttm":          ("annual_revenue", 0.0),
        "ebitda_ttm":           ("ebitda", 0.0),
        "debt_service":         ("annual_debt_service", 1e-6),
        "working_capital_ratio": (None, 1.2),   # derived below
        "customer_concentration": (None, 0.0),  # derived below
        "revenue_growth_yoy":   ("yoy_revenue_growth_pct", 0.0),
        "doc_completeness":     ("documentation_completeness_pct", 0.0),
        "clinical_revenue":     (None, 0.0),
        "payer_mix_score":      (None, 0.5),
    }

    def __init__(self, client_id: str):
        self.client_id = client_id
        self._feast_store = None
        self._feast_available = False

        try:
            from feast import FeatureStore
            repo = Path("feature_repo/")
            if repo.exists():
                self._feast_store = FeatureStore(repo_path=str(repo))
                self._feast_available = True
        except Exception:
            pass

    @staticmethod
    def _first_value(values, default: float = 0.0) -> float:
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

    def _load_from_json(self) -> Dict[str, float]:
        """Load features from data/sample_business.json as a local dev fallback."""
        candidates = [
            Path("data/sample_business.json"),
            Path(__file__).resolve().parents[1] / "data" / "sample_business.json",
        ]
        biz: dict = {}
        for p in candidates:
            if p.exists():
                biz = json.loads(p.read_text())
                break

        # Derive concentration from customer_revenue
        customers = biz.get("customer_revenue", {})
        revenue = float(biz.get("annual_revenue", 1) or 1)
        top = max(
            (float(v or 0) for k, v in customers.items() if k != "all_other_customers"),
            default=0.0,
        )
        concentration = round(top / revenue, 4) if revenue > 0 else 0.0

        # Derive working_capital_ratio from cash + recurring rev
        recurring = float(biz.get("recurring_revenue_pct", 0) or 0) / 100.0
        wcr = round(1.0 + recurring * 0.5, 4)

        growth = float(biz.get("yoy_revenue_growth_pct", 0) or 0) / 100.0

        industry = str(biz.get("industry", "")).lower()
        clinical = recurring if ("health" in industry or "medical" in industry) else 0.0

        return {
            "revenue_ttm":           float(biz.get("annual_revenue", 0) or 0),
            "ebitda_ttm":            float(biz.get("ebitda", 0) or 0),
            "debt_service":          max(float(biz.get("annual_debt_service", 0) or 0), 1e-6),
            "working_capital_ratio": wcr,
            "customer_concentration": concentration,
            "revenue_growth_yoy":    growth,
            "doc_completeness":      float(biz.get("documentation_completeness_pct", 0) or 0) / 100.0,
            "clinical_revenue":      clinical,
            "payer_mix_score":       0.8 if clinical else 0.5,
        }

    def _load_features(self) -> Dict[str, float]:
        if self._feast_available:
            try:
                raw = self._feast_store.get_online_features(
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
                    "revenue_ttm":           self._first_value(raw.get("revenue_ttm")),
                    "ebitda_ttm":            self._first_value(raw.get("ebitda_ttm")),
                    "debt_service":          self._first_value(raw.get("debt_service"), 1e-6),
                    "working_capital_ratio": self._first_value(raw.get("working_capital_ratio")),
                    "customer_concentration": self._first_value(raw.get("customer_concentration")),
                    "revenue_growth_yoy":    self._first_value(raw.get("revenue_growth_yoy")),
                    "doc_completeness":      self._first_value(raw.get("doc_completeness")),
                    "clinical_revenue":      self._first_value(raw.get("clinical_revenue")),
                    "payer_mix_score":       self._first_value(raw.get("payer_mix_score")),
                }
            except Exception:
                pass  # fall through to JSON

        return self._load_from_json()

    def compute_ratios(self) -> Tuple[Dict[str, float], float]:
        f = self._load_features()
        dscr = f["ebitda_ttm"] / max(f["debt_service"], 1e-6)

        health = (
            0.3 * min(dscr / 2.0, 1.0)           # normalise DSCR contribution
            + 0.2 * min(f["working_capital_ratio"], 1.0)
            + 0.2 * (1 - f["customer_concentration"])
            + 0.2 * f["doc_completeness"]
            + 0.1 * f.get("payer_mix_score", 0.5)
        )

        ratios = {
            "dscr":                  round(dscr, 2),
            "working_capital_ratio": round(f["working_capital_ratio"], 2),
            "customer_concentration": round(f["customer_concentration"], 2),
            "doc_completeness":      round(f["doc_completeness"], 2),
            "revenue_ttm":           round(f["revenue_ttm"], 2),
            "ebitda_ttm":            round(f["ebitda_ttm"], 2),
            "revenue_growth_yoy":    round(f["revenue_growth_yoy"], 4),
        }

        return ratios, min(max(health, 0.0), 1.0)

    def forecast_cashflow(self, months: int = 12) -> Tuple[pd.DataFrame, float]:
        f = self._load_features()
        growth = f["revenue_growth_yoy"]
        ebitda = f["ebitda_ttm"]

        dates = pd.date_range(start=pd.Timestamp.today(), periods=months, freq="ME")
        fcff = [ebitda * ((1 + growth) ** i) * 0.75 for i in range(1, months + 1)]

        df = pd.DataFrame({"date": dates, "fcff": fcff})
        confidence = 0.9 if growth >= 0 else 0.6
        return df, confidence
