---
id: weekly-defect-analysis
name: Weekly defect analysis
description: >-
  Scan gssc-langgraph for defects vs contracts, orphaned SW, security, or
  consistency holes; file or refine Kaneo GLG Defect tasks (no auto-fixes;
  no duplicate tickets).
enabled: true
intervalMinutes: 10080
runOnStartup: false
---

# Weekly defect analysis

## Purpose

Scan for defects: missing/wrong/extra behavior vs documented contracts and assistant I/O, away-from-architecture (orphaned SW), security issues, or reasoning/consistency holes in this Python LangGraph service.

## Rules

- Use Kaneo MCP on project **GLG**; create only via `.agents/skills/kaneo-create-task/SKILL.md` with **Issue Type = Defect**, and only after the dedupe check below.
- One Defect per distinct issue; link related assistant ids / doc paths when known.
- Label **Backend** (or as fits).
- Do **not** mark DoR Satisfied; do **not** auto-implement fixes in this run.
- Prefer architecture memories + `docs/*-contract.md` to classify findings only.
- **Cross-scanner:** If `weekly-third-party-optimize` already has (or would have) the same issue, share one ticket — refine it; do not file twice.

## Dedupe before create

Use the **GLG** Kaneo project via MCP (list/discover projects; do not embed opaque project ids in repo docs).

1. Before creating, search Kaneo for **open** Defects/optimization tickets matching the same locus / symptom / optimization (title keywords, description paths, assistant ids).
2. **Match** = same primary code path, same contract/assistant gap, or clearly the same optimization opportunity — **not** merely the same label.
3. **If match:** refine that task (description, Implementation note, locus/scope); add a comment with week date + what changed. Do **not** create a new number. Do **not** change column unless owner policy applies (e.g. demote a medium/low/no-priority Defect still on Not Ready → `planned`).
4. **If no match:** create via `kaneo-create-task` (Issue Type Defect, DoR Satisfied false, Fix Version Future, no auto-fix). New Defects always go to **Planned backlog** (`status: planned`), regardless of priority.
5. **If match and nothing material changed:** leave the task unchanged; count as unchanged-skipped.

## Steps

1. Sample `docs/*-contract.md`, `langgraph.json`, and recent SW/tests for mismatches and orphans (missing registry entries, hollow graphs, broken auth/checkpoint/MCP assumptions).
2. Note security/consistency holes without exploiting them; describe locus and expected behavior (secrets, auth bypass misuse, durable checkpointer misconfig).
3. For each distinct finding, run **Dedupe before create**; create or refine accordingly.
4. Report counts: **created** vs **refined** vs **unchanged-skipped** (or none).
