from feast import FeatureStore
import pandas as pd
from prophet import Prophet


def run_growth_projection(client_id: str) -> dict:
    """Simple 12-month revenue forecast using Prophet."""
    store = FeatureStore(repo_path="feature_repo/")
    df = store.get_historical_features(
        entity_rows=[{"client_id": client_id}],
        features=["business_profile_fv:revenue_ttm"],
    ).to_df()

    if df.empty:
        return {"forecast": [], "confidence": 0.0}

    value_col = "revenue_ttm" if "revenue_ttm" in df.columns else "value"
    if value_col not in df.columns or "event_timestamp" not in df.columns:
        raise ValueError("Historical feature frame must include event_timestamp and revenue values")

    ts = df.copy()
    ts["ds"] = pd.to_datetime(ts["event_timestamp"])
    ts["y"] = pd.to_numeric(ts[value_col], errors="coerce")
    ts = ts[["ds", "y"]].dropna().sort_values("ds")

    if ts.empty:
        return {"forecast": [], "confidence": 0.0}

    monthly = (
        ts.set_index("ds")
        .resample("M")
        .mean()
        .ffill()
        .bfill()
        .reset_index()
    )

    model = Prophet(yearly_seasonality=True, weekly_seasonality=False)
    model.fit(monthly[["ds", "y"]])

    future = model.make_future_dataframe(periods=12, freq="M")
    forecast = model.predict(future)
    forward = forecast.tail(12)[["ds", "yhat"]]

    return {
        "forecast": [
            {"date": str(r["ds"]), "revenue": round(float(r["yhat"]), 2)}
            for _, r in forward.iterrows()
        ],
        "confidence": 0.85,
    }
