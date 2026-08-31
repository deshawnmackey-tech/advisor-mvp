# Issue #467 local prototype one-pager

## Objective
Prove one path into Archymedes for Deshawn's advisory stack using sandbox agents first, without production cutover.

## Prototype slice selected
**A (default)**: advisory orchestrator path on `archy-wxo-sandbox`.

## What this local prototype includes
- Deterministic `advisory_orchestrator`
- Three specialist advisors:
  - `sale_readiness_advisor`
  - `sba_loan_advisor`
  - `investor_readiness_advisor`
- Shared JSON payload normalization
- Cross-lens risk reconciliation
- Explicit separation rule:
  - Loan Recommendation = product/bank/apply path
  - Advisory Orchestrator = readiness lenses only

## Sandbox vs promote recommendation
### Keep in sandbox (for IBM Lab validation)
- Prompt and orchestration iteration for advisory lenses
- Risk reconciliation UX and advisor narrative tuning
- Non-critical collaborator experiments

### Promote candidate (after validation gates)
- Deterministic scoring contracts for sale/SBA/investor outputs
- Stable API surface for orchestrator routing and lens selection
- Minimal portal/API integration contract for advisory-only entry point

### Defer / do not promote
- `AskOrchestrate`
- `Lead_Orchestrator_Agent_4910k5`
- Any merged "single chat" mixing loan recommendation and advisory readiness workflows

## Local verification commands
```bash
python /home/runner/work/advisor-mvp/advisor-mvp/advisor_workspace.py
python -m unittest -v /home/runner/work/advisor-mvp/advisor-mvp/test_advisory_workspace.py
```
