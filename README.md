# advisor-mvp

Minimal AI advisory workspace prototype that:

1. Ingests a single JSON payload
2. Normalizes accounting, banking, payroll, CRM, and debt inputs
3. Runs a rule-based engine for:
   - Core financial ratios
   - Forecast range
   - Valuation range

## Run

```bash
python /home/runner/work/advisor-mvp/advisor-mvp/advisor_workspace.py
```

## Shared JSON payload contract

All domains are read from one payload:

```json
{
  "accounting": {
    "revenue": 1200000,
    "cogs": 480000,
    "ebitda": 180000,
    "current_assets": 310000,
    "current_liabilities": 160000
  },
  "banking": {
    "cash_balance": 195000,
    "monthly_deposits": [98000, 102000, 99000]
  },
  "payroll": {
    "monthly_payroll": 62000,
    "employee_count": 18
  },
  "crm": {
    "open_pipeline": 420000,
    "win_rate": 0.34
  },
  "debt": {
    "total_debt": 350000,
    "monthly_debt_service": 9600
  }
}
```

The output returns normalized source data plus calculated advisory metrics.
