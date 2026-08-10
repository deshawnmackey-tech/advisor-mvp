# The Advisory Room Bible
## User Manual — Processes, Procedures & Field Reference

> **Full interactive manual:** Open `MANUAL.html` in any browser for the complete formatted reference.

---

## Quick Reference

| Task | Command |
|---|---|
| Run baseline report (all lenses) | `.venv/bin/python main.py --goal all` |
| Run sale rehearsal | `.venv/bin/python main.py --goal sale --rehearsal` |
| Run loan rehearsal | `.venv/bin/python main.py --goal loan --rehearsal` |
| Run investor rehearsal | `.venv/bin/python main.py --goal investor --rehearsal` |
| Start local API server | `.venv/bin/python -m uvicorn orchestrator.api:app --host 0.0.0.0 --port 8000 --reload` |
| Re-import Orchestrate tools | `orchestrate tools import --kind openapi --file tools_spec/advisory_api.yaml` |
| Re-import Orchestrate agents | `orchestrate agents import -f agent.yaml` (then sba, investor, orchestrator) |

## Production URLs
- **API:** https://advisor-mvp.onrender.com
- **Health check:** https://advisor-mvp.onrender.com/health
- **watsonx Orchestrate:** archy-wxo workspace

## Score Guide
| Score | Status | Action |
|---|---|---|
| 85–100 | STRONG | Ready for market |
| 65–84 | READY | Address HIGH findings first |
| 45–64 | DEVELOPING | 6–18 months of prep recommended |
| 0–44 | NOT READY | Fundamental issues must be resolved |

## Severity Penalties
- **HIGH** = 100% of metric weight deducted
- **MEDIUM** = 50% of metric weight deducted  
- **LOW** = 0 points deducted

## Required API Keys
| Key | Required For |
|---|---|
| `OPENAI_API_KEY` | Agent loop + rehearsal questions |
| `POSTGRES_DSN` | Rehearsal state persistence (Supabase) |
| `ANTHROPIC_API_KEY` | Optional fallback LLM |
| `AWS_ACCESS_KEY_ID` / `SECRET` | Optional PDF export to S3 |

---

*See `MANUAL.html` for the complete reference including all field definitions, scoring logic, onboarding procedures, and compliance requirements.*

---

## Section 06 — Human Advisor Review (MANDATORY)

The platform sets `advisor_review_required = true` automatically whenever any finding is HIGH severity. **No report with this flag should be presented to a client without a qualified advisor reviewing it first.**

### Pre-Presentation Checklist
Before presenting any report to a client, the advisor must confirm:

1. All revenue figures match the most recent tax return or reviewed financials
2. Customer revenue breakdown is accurate — verified against AR aging or QuickBooks
3. `documentation_completeness_pct` reflects documents actually in hand, not intent
4. `annual_debt_service` includes ALL P+I payments in the next 12 months
5. No HIGH finding is the result of a data entry error
6. Any context that changes a finding's meaning has been noted
7. Verbal disclaimer is prepared (see Section 12)

### What a Human Advisor Adds That the AI Cannot
- **Data quality judgment** — the AI trusts the numbers; the advisor questions whether they're right
- **Forward-looking context** — the platform scores the current snapshot; the advisor knows what is about to change
- **Market and relationship knowledge** — who the likely buyers/lenders are, what they care about
- **Emotional calibration** — the advisor frames difficult findings in a way the owner can hear and act on
- **Legal and ethical accountability** — the advisor is the professional of record; the AI is a tool, not a fiduciary

> `advisor_review_required` is set in `agent/orchestrator.py` line 129:
> `advisor_review_required = any(f["severity"] == "high" for f in findings)`
