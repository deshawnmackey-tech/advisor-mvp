import json
from copy import deepcopy
from typing import Any, Dict


DEFAULT_PAYLOAD: Dict[str, Dict[str, Any]] = {
    "accounting": {
        "revenue": 0.0,
        "cogs": 0.0,
        "ebitda": 0.0,
        "current_assets": 0.0,
        "current_liabilities": 0.0,
    },
    "banking": {
        "cash_balance": 0.0,
        "monthly_deposits": [],
    },
    "payroll": {
        "monthly_payroll": 0.0,
        "employee_count": 0,
    },
    "crm": {
        "open_pipeline": 0.0,
        "win_rate": 0.0,
    },
    "debt": {
        "total_debt": 0.0,
        "monthly_debt_service": 0.0,
    },
}


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_div(numerator: float, denominator: float) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def ingest_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, str):
        return json.loads(payload)
    if isinstance(payload, dict):
        return payload
    raise TypeError("Payload must be a dict or a JSON string.")


def normalize_payload(payload: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    normalized = deepcopy(DEFAULT_PAYLOAD)

    for section in normalized:
        if isinstance(payload.get(section), dict):
            normalized[section].update(payload[section])

    normalized["accounting"]["revenue"] = _to_float(normalized["accounting"]["revenue"])
    normalized["accounting"]["cogs"] = _to_float(normalized["accounting"]["cogs"])
    normalized["accounting"]["ebitda"] = _to_float(normalized["accounting"]["ebitda"])
    normalized["accounting"]["current_assets"] = _to_float(normalized["accounting"]["current_assets"])
    normalized["accounting"]["current_liabilities"] = _to_float(normalized["accounting"]["current_liabilities"])

    normalized["banking"]["cash_balance"] = _to_float(normalized["banking"]["cash_balance"])
    deposits = normalized["banking"].get("monthly_deposits")
    if not isinstance(deposits, list):
        deposits = []
    normalized["banking"]["monthly_deposits"] = [_to_float(v) for v in deposits]

    normalized["payroll"]["monthly_payroll"] = _to_float(normalized["payroll"]["monthly_payroll"])
    normalized["payroll"]["employee_count"] = int(_to_float(normalized["payroll"]["employee_count"]))

    normalized["crm"]["open_pipeline"] = _to_float(normalized["crm"]["open_pipeline"])
    win_rate = _to_float(normalized["crm"]["win_rate"])
    normalized["crm"]["win_rate"] = min(max(win_rate, 0.0), 1.0)

    normalized["debt"]["total_debt"] = _to_float(normalized["debt"]["total_debt"])
    normalized["debt"]["monthly_debt_service"] = _to_float(normalized["debt"]["monthly_debt_service"])

    return normalized


def run_rule_engine(normalized: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    accounting = normalized["accounting"]
    banking = normalized["banking"]
    payroll = normalized["payroll"]
    crm = normalized["crm"]
    debt = normalized["debt"]

    revenue = accounting["revenue"]
    cogs = accounting["cogs"]
    ebitda = accounting["ebitda"]
    current_assets = accounting["current_assets"]
    current_liabilities = accounting["current_liabilities"]
    monthly_payroll = payroll["monthly_payroll"]
    monthly_debt_service = debt["monthly_debt_service"]
    monthly_deposits = banking["monthly_deposits"]
    win_rate = crm["win_rate"]
    open_pipeline = crm["open_pipeline"]
    total_debt = debt["total_debt"]

    gross_profit = revenue - cogs
    annualized_deposits = (sum(monthly_deposits) / len(monthly_deposits) * 12) if monthly_deposits else 0.0
    blended_base_revenue = max(revenue, annualized_deposits)

    forecast_uplift = min(0.35, win_rate * 0.4 + _safe_div(open_pipeline, max(revenue, 1.0)) * 0.1)
    forecast_low = blended_base_revenue * 0.95
    forecast_high = blended_base_revenue * (1.0 + forecast_uplift)

    valuation_revenue_low = blended_base_revenue * 1.2
    valuation_revenue_high = blended_base_revenue * 2.4
    valuation_ebitda_low = ebitda * 4.0
    valuation_ebitda_high = ebitda * 7.0

    return {
        "ratios": {
            "gross_margin": _safe_div(gross_profit, revenue),
            "current_ratio": _safe_div(current_assets, current_liabilities),
            "debt_to_revenue": _safe_div(total_debt, max(revenue, 1.0)),
            "debt_service_coverage_proxy": _safe_div(gross_profit, monthly_debt_service * 12.0 + monthly_payroll),
        },
        "forecast": {
            "annual_revenue_low": forecast_low,
            "annual_revenue_high": forecast_high,
        },
        "valuation": {
            "enterprise_value_low": max(valuation_revenue_low, valuation_ebitda_low),
            "enterprise_value_high": max(valuation_revenue_high, valuation_ebitda_high),
        },
    }


def run_advisory_workspace(payload: Any) -> Dict[str, Any]:
    raw = ingest_payload(payload)
    normalized = normalize_payload(raw)
    advisory = run_rule_engine(normalized)
    return {"normalized": normalized, "advisory": advisory}


if __name__ == "__main__":
    sample_payload = {
        "accounting": {
            "revenue": 1_200_000,
            "cogs": 480_000,
            "ebitda": 180_000,
            "current_assets": 310_000,
            "current_liabilities": 160_000,
        },
        "banking": {"cash_balance": 195_000, "monthly_deposits": [98_000, 102_000, 99_000]},
        "payroll": {"monthly_payroll": 62_000, "employee_count": 18},
        "crm": {"open_pipeline": 420_000, "win_rate": 0.34},
        "debt": {"total_debt": 350_000, "monthly_debt_service": 9_600},
    }
    print(json.dumps(run_advisory_workspace(sample_payload), indent=2))
