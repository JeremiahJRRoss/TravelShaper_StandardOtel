# Documentation Reconciliation Report

**Date:** April 6, 2026  
**Scope:** All documentation in README.md, RUNNING.md, and src/docs/

---

## Summary of Changes Made

### README.md
- **Fixed graph topology diagram** — was missing `route_and_inject` node. Now shows `START → route_and_inject → llm_call → ...`
- **Added `route_and_inject` to Design Decisions** — new bullet explaining voice routing as a dedicated graph node
- **No other substantive changes** — query count (11), test count (14), tool list, and endpoint docs were already correct

### docs/ARCHITECTURE.md (major rewrite of affected sections)
- **Section 4.2** — graph topology corrected from `START → llm_call` to `START → route_and_inject → llm_call`; added `route_and_inject` to node descriptions
- **Section 5.1** — request lifecycle now starts with `route_and_inject` step before first `llm_call`
- **Section 7.3** — trace structure now includes `route_and_inject` span
- **Section 7.4** — added answer completeness as third metric
- **Section 9.2** — corrected: `get_system_prompt()` is called by `route_and_inject`, NOT by `llm_call`
- **Section 13** — fixed numbering (was incorrectly labeled 11.1/11.2)
- **Version bumped** to 2.1 (v0.1.5)

### docs/system-prompt-spec.md
- **Corrected routing description** — `get_system_prompt()` is called by `route_and_inject` node once at graph entry, not by `llm_call` on every invocation
- **Added design note** explaining why a dedicated node vs. inline routing
- **Version bumped** to 2.1 (v0.1.5)

### docs/trace-queries.md
- **Added Query 11** — past-date error handling test (Boston → Paris with dates 30 days in the past). This existed in `run_traces.sh` but was undocumented.
- **Updated title** from "10 Queries" to "11 Queries"
- **Updated coverage matrix** — added row 11
- **Added note** about dynamic date computation in `run_traces.sh`

### docs/PRD.md
- **Fixed duplicate section 6 numbering** — was two "Section 6"s; renumbered all sections
- **Section 7.1 (Scope)** — added place validation, preference validation, and answer completeness to in-scope table
- **Section 8.4 (API contract)** — POST /chat now documents all four fields (`message`, `departure`, `destination`, `preferences`) and error response shape
- **Section 9.1** — graph structure corrected to include `route_and_inject`
- **Section 10** — added answer completeness evaluation; updated trace count to 11
- **Section 11** — updated test count to 14 with breakdown
- **Version bumped** to 1.2

### docs/presentation-outline.md
- **Slide 4** — graph diagram corrected to include `route_and_inject`
- **Slide 9** — added answer completeness as third evaluation metric
- **Preparation checklist** — updated trace count to 11

### docs/docker-spec.md
- **Version bumped** to 2.1 (v0.1.5)

### docs/test-specification.md
- **Test 5** — assertion list now includes `route_and_inject` (matches actual test code)
- **Version bumped** to 2.1 (v0.1.5)

### RUNNING.md
- **Section 4** — updated from "10 trace queries" to "11 trace queries"
- **Section 7** — project structure updated to include `evaluations/metrics/answer_completeness.py`, `scripts/` directory, `setup.sh`; test counts corrected (4 + 2 + 8 = 14)
- **Removed outdated clone path** (`se-interview-main`)

---

## Items Requiring Human Decision

### 1. Version mismatch: CHANGELOG 0.1.5 vs code 0.1.4

**The problem:** `CHANGELOG.md` has a `[0.1.5]` entry dated 2026-04-06 describing the tracing consolidation work. However, `api.py` still has `version="0.1.4"` and `pyproject.toml` has `version = "0.1.4"`. The documentation updates above reference v0.1.5 to match the CHANGELOG.

**Options:**
- **Option A (recommended):** Bump `api.py` version string and `pyproject.toml` version to `"0.1.5"` to match the CHANGELOG. This is a two-line change.
- **Option B:** Mark the CHANGELOG 0.1.5 entry as `[Unreleased]` and keep code at 0.1.4.

**Files to change for Option A:**
- `api.py` line: `version="0.1.4"` → `version="0.1.5"`
- `pyproject.toml` line: `version = "0.1.4"` → `version = "0.1.5"`
- `static/index.html` line: `V0.1.4` → `V0.1.5`

### 2. Query 7 preferences text mismatch

**The problem:** `docs/trace-queries.md` (original) had Query 7 preferences as `"I need AC that actually works and a bathroom I am not scared of."` but `run_traces.sh` has `"I would like a safe, clean, trip that focuses on learning about the religious history in the region"`. The corrected trace-queries.md uses the `run_traces.sh` version since that's what actually executes.

**Action needed:** Confirm the `run_traces.sh` version is the intended text, or update the script to match the original doc.

### 3. docs/evaluation-prompts.md `run_evals.py` example code

**The problem:** The example code at the bottom of `evaluation-prompts.md` shows a simplified version of `run_evals.py` that doesn't match the actual implementation (missing answer completeness metric, missing defensive column discovery, missing `_select_request_spans`). This is a reference/pedagogical example, not copy-paste code.

**Options:**
- **Option A:** Add a note clarifying the example is simplified and the actual implementation in `evaluations/run_evals.py` is the source of truth.
- **Option B:** Update the example to match the actual code (would make the doc much longer).

---

## Files NOT Changed (confirmed accurate)

- `CHANGELOG.md` — accurate (pending version decision above)
- `docs/implementation-plan.md` — historical document, not a living reference
- `docs/evaluation-prompts.md` — prompt text is accurate; only the example code at bottom is simplified (see item 3 above)
- All Python source files — no code changes, documentation only
