---
id: weekly-third-party-optimize
name: Weekly third-party optimization scan
description: >-
  Scan gssc-langgraph for suboptimal or reinvented use of the adopted stack and
  file or refine Kaneo GLG Defect tasks (no auto-fixes; no duplicate tickets).
enabled: true
intervalMinutes: 10080
runOnStartup: false
---

# Weekly third-party optimization

## Purpose

Compare workspace code to adopted-stack practice (LangGraph / Agent Server / langgraph-cli, LangSmith, xAI, uv/mise, pytest, official checkpointers) and find suboptimal or reinvented usage.

## Rules

- Use Kaneo MCP on project **GLG**; create only via `.agents/skills/kaneo-create-task/SKILL.md` with **Issue Type = Defect**, and only after the dedupe check below.
- One Defect per distinct opportunity (or one grouped Defect with a checklist if findings are tiny).
- Cite docs/URL + code locus; label **Backend** (or as fits).
- Do **not** mark DoR Satisfied; do **not** auto-implement fixes in this run.
- Prefer architecture memories only to judge findings — not to ship fixes here.
- **Cross-scanner:** If `weekly-defect-analysis` already has (or would have) the same issue, share one ticket — refine it; do not file twice.

## Dedupe before create

Use the **GLG** Kaneo project via MCP (list/discover projects; do not embed opaque project ids in repo docs).

1. Before creating, search Kaneo for **open** Defects/optimization tickets matching the same locus / symptom / optimization (title keywords, description paths, assistant ids).
2. **Match** = same primary code path, same contract gap, or clearly the same optimization opportunity — **not** merely the same label.
3. **If match:** refine that task (description, Implementation note, locus/scope); add a comment with week date + what changed. Do **not** create a new number. Do **not** change column unless owner policy applies (e.g. demote a medium/low/no-priority Defect still on Not Ready → `planned`).
4. **If no match:** create via `kaneo-create-task` (Issue Type Defect, DoR Satisfied false, Fix Version Future, no auto-fix). New Defects always go to **Planned backlog** (`status: planned`), regardless of priority.
5. **If match and nothing material changed:** leave the task unchanged; count as unchanged-skipped.

## Steps

1. Skim recent changes and known hotspots vs `.agents/memories/service-arch.md`, `assistants-arch.md`, `ops-arch.md`, and README.
2. Flag reinvented HTTP servers (FastAPI/Flask/Starlette/Express/etc.) where Agent Server fits; hand-rolled clients where LangGraph SDK fits; leftover Bun/TS primary-stack packaging; custom checkpoint stores when official sqlite/postgres savers fit; non-xAI defaults when policy is xAI.
3. For each distinct finding, run **Dedupe before create**; create or refine accordingly.
4. Report counts: **created** vs **refined** vs **unchanged-skipped** (or none).
