---
id: assistants-arch
title: Assistant / graph architecture
importance: high
tags: [graphs, assistants, checkpointer, synthesis, closeout]
---

# Assistants

Registered in `langgraph.json` (assistant id → `graph` export):

| id | Checkpointer (API export) | Model | Role |
| --- | --- | --- | --- |
| `health` | none (Agent Server) | model-free | Smoke: `status=ok`, `service=gssc-langgraph`, `checkedAt` ISO |
| `conversation` | none (Agent Server) | model-free | Echo + `steps` append; thread via Agent Server `thread_id` |
| `closeout_review` | none (Agent Server) | checks model-free; optional synthesize | Peer closeout (requirements/software/test lanes) |
| `software_dev` | none (Agent Server) | checks model-free; optional synthesize | Plan + software closeout |
| `test_development` | none (Agent Server) | checks model-free; optional synthesize | Test contracts/plan/closeout |

## Checkpointer

- **Agent Server exports** (`langgraph.json` `graph` objects): compile with `builder.compile(name=…)` only — no custom checkpointer. Platform persistence; set `POSTGRES_URI` for durable DB.
- **Tests / direct invoke**: `compile_with_memory(builder, …)` may attach env-selected `MemorySaver` / Sqlite / Postgres (`GSSC_CHECKPOINT_*`). Never use that on API entrypoints (GraphLoadError).
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
