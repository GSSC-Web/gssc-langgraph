# gssc-langgraph agent guidelines

Layout follows the [Dot Agents Protocol](https://dotagentsprotocol.com). This file is the project source of truth (not a duplicate root `AGENTS.md`).

## Overview

**gssc-langgraph** is the standalone [LangGraph](https://docs.langchain.com/oss/python/langgraph/overview) Agent Server for GSSC-Web. The sibling app [gssc5](https://github.com/GSSC-Web/gssc5) calls this service over the Agent Server HTTP/SDK API (and MCP at `/mcp`). This repo is **Python + uv**, not a Dot Agents product scaffold for gssc5’s StrictDoc/web apps.

| Path | Role |
| --- | --- |
| `src/gssc_langgraph/` | Python package: graphs, auth, checkpoint, llm, gssc5 loaders, domain bots |
| `langgraph.json` | Agent Server registry (assistants + auth + env) |
| `docs/` | I/O contracts for specialist assistants |
| `.agents/` | Agent guidelines, skills, tasks, memories, Kaneo MCP wiring |

This project does **not** ship role agent profiles under `.agents/agents/` (no requirements/software/test agent types). Prefer skills + memories + Kaneo for process.

## Commands

- Install tools: `mise install`
- Install deps: `mise run install` (or `uv sync --all-extras`)
- Dev Agent Server: `mise run dev` → `http://127.0.0.1:2024` (MCP: `/mcp`)
- Tests: `mise run test` (or `uv run pytest`)
- Specialist CLIs: `mise run closeout` | `test-dev` | `software`

## Core rules

- Kaneo ALM (project **GLG**) owns task scope, board columns, and Fix Version.
- Prefer the official LangGraph Agent Server (`langgraph` / `langgraph-cli`) over reinvented HTTP servers.
- Prefer adopted third parties (LangGraph, LangSmith, xAI/Grok, uv/mise, pytest) over custom reinvention.
- Do **not** reintroduce `service_review` or `sample_agent`.
- Baseline assistant contract is **`health`** only; keep it registered and model-free.
- Smoke assistants (`health`, `conversation`) stay model-free; specialists may use optional xAI synthesis when `XAI_API_KEY` is set.
- Never commit secrets. Keep tokens out of git / `mcp.json`. Protocol’s `skill.md` maps to Cursor’s `SKILL.md` here.
- Default git branch is **`master`** (not `main`).

## Kaneo board (project GLG)

- Workspace: **GSSC Web**. Project slug: **GLG** (GSSC LangGraph). Sister product board: GSSC5 — do not file gssc-langgraph work there.
- Open PR → status **Ready for Review** (`in-review`) when that column exists; otherwise leave a PR comment on the Kaneo task.
- **Done** only on merge to **master** with Fix Version set to the landing release (use **Future** until then).
- DoR Satisfied only when Definition of Ready is met; DoD Satisfied only when Done.
- Integration-only land ≠ Done.
- Wire MCP via `.agents/mcp.json` (placeholders only). Discover workspace/project via Kaneo MCP — do not hardcode opaque ids in skill steps.

Custom fields (as used on GLG): Issue Type, Reported Version, Fix Version, Definition of Ready / DoR Satisfied, Definition of Done / DoD Satisfied, Defects Discovered.

## Skills

Read `.agents/skills/<name>/SKILL.md` when relevant:

| Skill | When |
| --- | --- |
| `backlog-grooming` | ALM refinement / wave prep |
| `kaneo-create-task` | Create Defect / Enhancement / Planned tasks |
| `kaneo-task-ready` | Promote Not Ready → Ready to Start |
| `kaneo-task-closeout` | Master merge closeout fields + unblock |
| `kaneo-unblock-reeval` | After Done: promote unblock-eligible targets |

Specialist **graph** closeout (deterministic checks in-repo) is separate: assistants `closeout_review`, `software_dev`, `test_development` — see `docs/*-contract.md`. Those are LangGraph workflows, not Dot Agents role profiles.

## Architecture memories

Durable stack facts (not wave status):

- `.agents/memories/service-arch.md` — package layout, Agent Server, MCP
- `.agents/memories/assistants-arch.md` — graph ids, checkpointers, synthesis
- `.agents/memories/ops-arch.md` — auth, env knobs, CI, Kaneo linkage

## Weekly tasks

Repeat every 7 days; Kaneo **Defect** tasks only — no auto-fixes. Create only when no equivalent open Defect/optimization ticket exists; otherwise refine that ticket. Cross-scanner findings that are the same issue share one ticket. New Defects always go to **Planned backlog** (`planned`), regardless of priority. See `kaneo-create-task`.

- `.agents/tasks/weekly-defect-analysis/task.md`
- `.agents/tasks/weekly-third-party-optimize/task.md`

## Host prompt

Reusable host system prompt: `.agents/system-prompt.md`.
