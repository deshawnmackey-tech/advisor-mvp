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
