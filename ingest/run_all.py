import argparse
import csv
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "sample_business.json"
OUTPUT_DIR = ROOT / "feature_repo" / "data"
OUTPUT_FILE = OUTPUT_DIR / "client_profiles.csv"


def _load_business(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _top_customer_concentration(business: dict) -> float:
    customer_revenue = business.get("customer_revenue", {})
    annual_revenue = float(business.get("annual_revenue", 0.0) or 0.0)
    top_customer = max(
        (float(value or 0.0) for key, value in customer_revenue.items() if key != "all_other_customers"),
        default=0.0,
    )
    if annual_revenue <= 0:
        return 0.0
    return round(top_customer / annual_revenue, 4)


def _monthly_rows(client_id: str, business: dict) -> list[dict]:
    annual_revenue = float(business.get("annual_revenue", 0.0) or 0.0)
    ebitda = float(business.get("ebitda", 0.0) or 0.0)
    doc_completeness = float(business.get("documentation_completeness_pct", 0.0) or 0.0) / 100.0
    concentration = _top_customer_concentration(business)
    debt_service = round(ebitda / 1.5, 2) if ebitda > 0 else 1.0
    recurring_revenue = float(business.get("recurring_revenue_pct", 0.0) or 0.0) / 100.0
    working_capital_ratio = round(1.0 + recurring_revenue * 0.5, 4)
    growth_yoy = 0.08
    industry = str(business.get("industry", "")).lower()
    clinical_revenue = recurring_revenue if "health" in industry or "medical" in industry else 0.0
    payer_mix_score = 0.8 if clinical_revenue else 0.5

    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=330)
    rows = []
    for month in range(12):
        factor = 1.0 + (growth_yoy / 12.0) * month
        event_timestamp = (start + timedelta(days=30 * month)).isoformat().replace("+00:00", "Z")
        rows.append(
            {
                "event_timestamp": event_timestamp,
                "client_id": client_id,
                "revenue_ttm": round(annual_revenue * factor, 2),
                "ebitda_ttm": round(ebitda * factor, 2),
                "debt_service": debt_service,
                "working_capital_ratio": working_capital_ratio,
                "customer_concentration": concentration,
                "revenue_growth_yoy": growth_yoy,
                "doc_completeness": round(doc_completeness, 4),
                "clinical_revenue": round(clinical_revenue, 4),
                "payer_mix_score": payer_mix_score,
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate deterministic seed profile data for Feast ingestion.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Path to a business JSON payload.")
    parser.add_argument("--client-id", default="demo_client", help="Client identifier to attach to exported rows.")
    args = parser.parse_args()

    business = _load_business(Path(args.input))
    rows = _monthly_rows(args.client_id, business)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_FILE.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    print(f"Wrote {len(rows)} rows to {OUTPUT_FILE}")
    print("Next step: add Feast repo definitions under feature_repo/ before materialization.")


if __name__ == "__main__":
    main()