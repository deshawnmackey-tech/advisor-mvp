import json
from copy import deepcopy
from typing import Any, Dict, List


ENVIRONMENTS = {
    "archy-wxo-sandbox": {
        "env_id": "670ff27d-94e7-4dad-b1b3-c7f4ddc0b175",
        "role": "Lab / Deshawn advisor work",
    },
    "archy-wxo": {
        "env_id": "cbc891ba-fa06-48f9-bd87-9e121c566a4a",
        "role": "Shared / production loan agent path",
    },
}

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
        "recurring_revenue_ratio": 0.0,
        "top_customer_revenue_share": 0.0,
        "nrr": 100.0,
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


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _score_100(value: float) -> int:
    return int(round(_clamp(value, 0.0, 100.0)))


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
    normalized["crm"]["win_rate"] = _clamp(_to_float(normalized["crm"]["win_rate"]), 0.0, 1.0)
    normalized["crm"]["recurring_revenue_ratio"] = _clamp(_to_float(normalized["crm"]["recurring_revenue_ratio"]), 0.0, 1.0)
    normalized["crm"]["top_customer_revenue_share"] = _clamp(
        _to_float(normalized["crm"]["top_customer_revenue_share"]), 0.0, 1.0
    )
    normalized["crm"]["nrr"] = _clamp(_to_float(normalized["crm"]["nrr"]), 0.0, 200.0)

    normalized["debt"]["total_debt"] = _to_float(normalized["debt"]["total_debt"])
    normalized["debt"]["monthly_debt_service"] = _to_float(normalized["debt"]["monthly_debt_service"])
    return normalized


def sale_readiness_advisor(normalized: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    accounting = normalized["accounting"]
    crm = normalized["crm"]

    revenue = accounting["revenue"]
    gross_margin = _safe_div(revenue - accounting["cogs"], revenue)
    recurring = crm["recurring_revenue_ratio"]
    concentration = crm["top_customer_revenue_share"]

    score = _score_100((gross_margin * 45.0) + (recurring * 40.0) + ((1.0 - concentration) * 15.0))
    risks: List[str] = []
    if concentration > 0.35:
        risks.append("Customer concentration risk is high for a sale process.")
    if recurring < 0.40:
        risks.append("Recurring revenue is low for private-equity style readiness.")
    if gross_margin < 0.35:
        risks.append("Gross margin is below typical sale-readiness targets.")

    return {
        "advisor": "sale_readiness_advisor",
        "score": score,
        "metrics": {
            "gross_margin": gross_margin,
            "recurring_revenue_ratio": recurring,
            "top_customer_revenue_share": concentration,
        },
        "risks": risks,
        "verdict": "keep",
    }


def sba_loan_advisor(normalized: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    accounting = normalized["accounting"]
    banking = normalized["banking"]
    payroll = normalized["payroll"]
    debt = normalized["debt"]

    ebitda = accounting["ebitda"]
    annual_debt_service = debt["monthly_debt_service"] * 12.0
    dscr = _safe_div(ebitda, annual_debt_service)
    cash_buffer_months = _safe_div(banking["cash_balance"], payroll["monthly_payroll"])
    current_ratio = _safe_div(accounting["current_assets"], accounting["current_liabilities"])

    score = _score_100((dscr * 40.0) + (cash_buffer_months * 10.0) + (current_ratio * 20.0))
    risks: List[str] = []
    if dscr < 1.25:
        risks.append("DSCR below SBA comfort band.")
    if cash_buffer_months < 2.0:
        risks.append("Cash buffer is thin for underwriting resilience.")
    if current_ratio < 1.20:
        risks.append("Current ratio indicates potential working-capital pressure.")

    return {
        "advisor": "sba_loan_advisor",
        "score": score,
        "metrics": {
            "dscr_proxy": dscr,
            "cash_buffer_months": cash_buffer_months,
            "current_ratio": current_ratio,
        },
        "risks": risks,
        "verdict": "keep",
    }


def investor_readiness_advisor(normalized: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    accounting = normalized["accounting"]
    crm = normalized["crm"]

    revenue = accounting["revenue"]
    ebitda_margin = _safe_div(accounting["ebitda"], revenue)
    pipeline_coverage = _safe_div(crm["open_pipeline"], max(revenue, 1.0))
    nrr = crm["nrr"]

    score = _score_100(
        (ebitda_margin * 35.0)
        + (_clamp(pipeline_coverage, 0.0, 2.0) * 20.0)
        + (_clamp((nrr - 80.0) / 40.0, 0.0, 1.0) * 45.0)
    )
    risks: List[str] = []
    if ebitda_margin < 0.15:
        risks.append("EBITDA margin is below typical institutional expectations.")
    if pipeline_coverage < 0.30:
        risks.append("Pipeline coverage is low for near-term growth confidence.")
    if nrr < 100.0:
        risks.append("Net revenue retention below 100% may reduce investor appetite.")

    return {
        "advisor": "investor_readiness_advisor",
        "score": score,
        "metrics": {
            "ebitda_margin": ebitda_margin,
            "pipeline_coverage": pipeline_coverage,
            "nrr": nrr,
        },
        "risks": risks,
        "verdict": "keep",
    }


def run_rule_engine(normalized: Dict[str, Dict[str, Any]], lens: str = "all") -> Dict[str, Any]:
    advisors = {
        "sale": sale_readiness_advisor,
        "sba": sba_loan_advisor,
        "investor": investor_readiness_advisor,
    }
    if lens == "all":
        selected = list(advisors.keys())
    else:
        if lens not in advisors:
            raise ValueError("lens must be one of: all, sale, sba, investor")
        selected = [lens]

    results: Dict[str, Dict[str, Any]] = {}
    for name in selected:
        advisor_result = advisors[name](normalized)
        results[advisor_result["advisor"]] = advisor_result
    all_risks: List[str] = []
    for result in results.values():
        all_risks.extend(result["risks"])

    shared_risk_count = len(all_risks)
    return {
        "orchestrator": "advisory_orchestrator",
        "active_lens": selected,
        "specialist_outputs": results,
        "cross_lens": {
            "risk_count": shared_risk_count,
            "needs_human_review": shared_risk_count >= 3,
        },
    }


def advisory_orchestrator(payload: Any, lens: str = "all", environment: str = "archy-wxo-sandbox") -> Dict[str, Any]:
    if environment not in ENVIRONMENTS:
        raise ValueError("environment must be one of: archy-wxo-sandbox, archy-wxo")

    raw = ingest_payload(payload)
    normalized = normalize_payload(raw)
    advisory = run_rule_engine(normalized, lens=lens)
    return {
        "prototype_issue": 467,
        "default_priority": "A",
        "environment": {"name": environment, **ENVIRONMENTS[environment]},
        "separation_rule": (
            "Loan Recommendation agent remains separate from Advisory Orchestrator; "
            "advisory provides readiness lenses only."
        ),
        "inventory_snapshot": {
            "primary_target": "advisory_orchestrator",
            "keep": ["sale_readiness_advisor", "sba_loan_advisor", "investor_readiness_advisor"],
            "defer_or_kill": ["Lead_Orchestrator_Agent_4910k5", "AskOrchestrate"],
        },
        "normalized": normalized,
        "advisory": advisory,
    }


def run_advisory_workspace(payload: Any) -> Dict[str, Any]:
    return advisory_orchestrator(payload=payload, lens="all", environment="archy-wxo-sandbox")


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
        "crm": {
            "open_pipeline": 420_000,
            "win_rate": 0.34,
            "recurring_revenue_ratio": 0.58,
            "top_customer_revenue_share": 0.22,
            "nrr": 112,
        },
        "debt": {"total_debt": 350_000, "monthly_debt_service": 9_600},
    }
    print(json.dumps(run_advisory_workspace(sample_payload), indent=2))
