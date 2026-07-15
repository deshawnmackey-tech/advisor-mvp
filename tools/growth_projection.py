"""
12-month revenue growth projection.

Primary:  Prophet via Feast feature store (requires .venv-feast311)
Fallback: Linear extrapolation using NumPy — works in the main .venv with
          no extra dependencies.  Used automatically when Feast/Prophet are
          not importable (dev, CI, watsonx Orchestrate).
"""

import numpy as np


def _linear_forecast(base_revenue: float, growth_rate: float, months: int = 12) -> list[dict]:
    """Simple month-over-month linear forecast from a base revenue figure."""
    import datetime
    today = datetime.date.today().replace(day=1)
    results = []
    for i in range(1, months + 1):
        month = (today.month - 1 + i) % 12 + 1
        year  = today.year + (today.month - 1 + i) // 12
        projected = base_revenue * (1 + growth_rate) ** (i / 12)
        results.append({
            "date": f"{year}-{month:02d}-01",
            "revenue": round(projected, 2),
        })
    return results


def run_growth_projection(client_id: str) -> dict:
    """
    Generate a 12-month revenue forecast for the given client.

    Tries Prophet + Feast first; falls back to linear NumPy extrapolation
    if those packages are unavailable or the feature store has no data.
    """
    try:
        from feast import FeatureStore
        from prophet import Prophet
        import pandas as pd

        store = FeatureStore(repo_path="feature_repo/")
        df = store.get_historical_features(
            entity_rows=[{"client_id": client_id}],
            features=["business_profile_fv:revenue_ttm"],
        ).to_df()

        if df.empty:
            raise ValueError("No historical feature data")

        value_col = "revenue_ttm" if "revenue_ttm" in df.columns else "value"
        if value_col not in df.columns or "event_timestamp" not in df.columns:
            raise ValueError("Feature frame missing required columns")

        ts = df.copy()
        ts["ds"] = pd.to_datetime(ts["event_timestamp"])
        ts["y"]  = pd.to_numeric(ts[value_col], errors="coerce")
        ts = ts[["ds", "y"]].dropna().sort_values("ds")

        if ts.empty:
            raise ValueError("No usable time-series data after cleaning")

        monthly = (
            ts.set_index("ds")
            .resample("ME")
            .mean()
            .ffill()
            .bfill()
            .reset_index()
        )

        model = Prophet(yearly_seasonality=True, weekly_seasonality=False)
        model.fit(monthly[["ds", "y"]])

        future   = model.make_future_dataframe(periods=12, freq="ME")
        forecast = model.predict(future)
        forward  = forecast.tail(12)[["ds", "yhat"]]

        return {
            "forecast": [
                {"date": str(r["ds"])[:10], "revenue": round(float(r["yhat"]), 2)}
                for _, r in forward.iterrows()
            ],
            "confidence": 0.85,
            "source": "prophet",
        }

    except Exception:
        # Fall back to linear extrapolation using sample_business.json if available
        try:
            import json, os
            data_path = os.path.join(os.path.dirname(__file__), "..", "data", "sample_business.json")
            with open(data_path) as f:
                biz = json.load(f)
            base    = float(biz.get("revenue_ttm", 4_200_000))
            growth  = float(biz.get("revenue_growth_yoy", 0.05))
        except Exception:
            base, growth = 4_200_000.0, 0.05

        return {
            "forecast": _linear_forecast(base, growth, months=12),
            "confidence": 0.65,
            "source": "linear_fallback",
        }
