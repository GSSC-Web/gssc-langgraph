---
id: assistants-arch
title: Assistant / graph architecture
importance: high
tags: [graphs, assistants, checkpointer, synthesis, closeout]
---

# Assistants

Registered in `langgraph.json` (assistant id → `graph` export):

| id | Checkpointer | Model | Role |
| --- | --- | --- | --- |
| `health` | none | model-free | Smoke: `status=ok`, `service=gssc-langgraph`, `checkedAt` ISO |
| `conversation` | `compile_with_memory` | model-free | Echo + `steps` append; thread via `thread_id` |
| `closeout_review` | `compile_with_memory` | checks model-free; optional synthesize | Peer closeout (requirements/software/test lanes) |
| `software_dev` | `compile_with_memory` | checks model-free; optional synthesize | Plan + software closeout |
| `test_development` | `compile_with_memory` | checks model-free; optional synthesize | Test contracts/plan/closeout |

## Checkpointer

- Default: in-process `MemorySaver` (`GSSC_CHECKPOINT_BACKEND` unset or `memory`).
- Durable: `sqlite` (`GSSC_CHECKPOINT_SQLITE_PATH`) or `postgres` (`GSSC_CHECKPOINT_POSTGRES_URL`).
- Clients pass Agent Server / SDK `thread_id`. Specialists append durable notes (`reviewMemory` / `specialistNotes`) on reuse.

## Synthesis

- After deterministic verdict, optional `synthesize` may call xAI for `narrativeSummary` + advisory `proposedMemoryUpdates`.
- Skip cleanly when `XAI_API_KEY` unset (`synthesisNote: skipped: no XAI_API_KEY`) or `configurable.synthesisEnabled=false`.
- Never auto-apply proposed memory updates. Authoritative PASS/FAIL is always from model-free checks.

## Baseline / stack policy

- Baseline assistant required in registry: **`health` only**.
- Prefer Python + uv + LangGraph Agent Server; flag reinvented HTTP frameworks; do not treat `.py` / `pyproject.toml` as out-of-stack.
- Graph modules: `src/gssc_langgraph/graphs/<id>/graph.py` exporting compiled `graph`.

## CLIs

- `closeout` → closeout_review checks (exit 0 PASS / 1 FAIL / 2 error)
- `software` → software_dev plan + checks
- `test-dev` → test_development analysis
