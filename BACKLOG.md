# Advisory Room MVP — Backlog

> Items captured from watsonx Orchestrate sanity-check script review.
> Scheduled for next sprint. Do not start until the week of 2026-07-21.

---

## Sprint 1 Backlog — Orchestrate Compatibility & Test Hardening

### 1. Fix folder layout expected by Orchestrate sanity-check script

The IBM sanity-check script expects `agents/` — the project uses `agent/` (renamed to avoid the `openai-agents` SDK namespace collision). Need to either:
- Add compatibility shim (`agents/` symlink or re-export package pointing to `agent/`)
- **Or** update the sanity-check script paths to match the actual layout

**Files the script expects vs. actual location:**

| Script expects | Actual location |
|---|---|
| `advisory-mvp/agents/__init__.py` | `agent/__init__.py` |
| `advisory-mvp/agents/base.py` | `agent/base.py` |
| `advisory-mvp/agents/sale_agent.py` | `agent/sale_agent.py` |
| `advisory-mvp/agents/loan_agent.py` | `agent/loan_agent.py` |
| `advisory-mvp/agents/investor_agent.py` | `agent/investor_agent.py` |
| `advisory-mvp/agents/general_agent.py` | `agent/general_agent.py` |

**Recommended fix:** Update the sanity-check script to use `agent/` — do not recreate `agents/` as it collides with the `openai-agents` SDK.

---

### 2. Write a real unit test suite (`tests/test_advisory.py`)

The script runs `python -m unittest discover -s advisory-mvp/tests` — the `tests/` directory exists but has no real test coverage. Need to write tests for:

- [ ] `scoring/sale_readiness.py` — all 4 metric functions, edge cases (zero revenue, no customers, missing fields)
- [ ] `scoring/loan_readiness.py` — DSCR boundary conditions (exactly 1.15x, exactly 1.35x), zero debt service
- [ ] `scoring/investor_readiness.py` — growth rate boundaries, NRR edge cases
- [ ] `scoring/models.py` — `compute_weighted_score()` with known inputs
- [ ] `agent/orchestrator.py` — `build_report()` returns correct `advisor_review_required` flag
- [ ] `agent/llm.py` — `_keyword_evaluate()` fallback with known keywords
- [ ] `orchestrator/api.py` — health endpoint returns 200, `/v1/advise` returns payload key

---

### 3. Fix import checks in sanity-check script

The script checks for `faiss_cpu` (wrong module name — it's `faiss`) and `prophet` which is in `.venv-feast311` not `.venv`. The import check will always fail on `faiss_cpu` and `prophet` in the main venv. Update to:

- [ ] Replace `faiss_cpu` → `faiss` in the import check list
- [ ] Remove `prophet`, `feast` from the main venv import check (they live in `.venv-feast311`)
- [ ] Add `openai`, `openai_agents` (the actual package names) to the check list

---

### 4. Add `tools/__init__.py`

The sanity-check script expects `advisory-mvp/tools/__init__.py` — this file does not exist. The `tools/` directory works as a package without it in Python 3.12 (implicit namespace packages) but the script's file-existence check fails.

- [ ] Add empty `tools/__init__.py`
- [ ] Add empty `scoring/__init__.py` (same issue)
- [ ] Add empty `orchestrator/__init__.py` (verify it exists)

---

### 5. Harden the FastAPI startup in the sanity-check script

The script starts uvicorn with `--log-level error` and waits 4 seconds — on Render cold start or a slow machine this is not enough. The script has no retry/health-check loop before running API tests.

- [ ] Add a health-check poll loop (retry `/health` up to 10 times with 2s sleep) before running API tests
- [ ] Add `--timeout-keep-alive 30` to uvicorn args to prevent premature connection drops during test

---

### 6. Resolve the `advisory-mvp/` subdirectory path assumption

The sanity-check script assumes files live at `advisory-mvp/<file>` (i.e., it's run from the parent of the repo). The actual repo root IS `advisory-mvp 3/`. Running the script from the wrong directory will cause all file checks to fail.

- [ ] Add a `--repo-root` flag to the script, or add auto-detection logic
- [ ] Document the correct working directory in `MANUAL.md` and the script header

---

### 7. Add advisor review checkpoint to API response

Currently `advisor_review_required` is computed in `agent/orchestrator.py` but is **not returned** in the `/v1/advise` API response payload — the iOS app and Orchestrate agents never see it.

- [ ] Add `advisor_review_required: bool` to the `AdviseResponse` model in `orchestrator/api.py`
- [ ] Surface the flag in the iOS app `ResultCard` — show a prominent warning banner when `true`
- [ ] Add the flag to the watsonx Orchestrate agent instructions so it can tell the user "This report requires advisor review before acting on it"

---

### 8. Advisor notes field on findings

Allow a reviewing advisor to annotate any finding before it reaches the client.

- [ ] Add optional `advisor_note: str | None` field to the `Finding` TypedDict in `scoring/models.py`
- [ ] Add a PATCH endpoint `/v1/advise/{trace_id}/note` that accepts `{metric, note}` and updates the stored trace in Mongo/Postgres
- [ ] Surface advisor notes in the iOS app `ResultCard` below each finding

---

## Notes

- The sanity-check script was generated by IBM Bob as a CI validation tool. It reflects the old `agents/` folder structure from before the openai-agents SDK namespace fix.
- All items above are **non-blocking** for the current production deployment — the live system at `https://advisor-mvp.onrender.com` works correctly.
- Priority order: 2 (tests) → 7 (advisor_review_required in API) → 4 (init files) → 1 (folder layout) → 3 (import checks) → 5 (startup hardening) → 6 (path assumption) → 8 (advisor notes)
