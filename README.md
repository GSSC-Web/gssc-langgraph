# gssc-langgraph

Standalone [LangGraph (Python)](https://docs.langchain.com/oss/python/langgraph/overview) Agent Server for GSSC-Web. The sibling app [gssc5](https://github.com/GSSC-Web/gssc5) calls this service over the LangGraph Agent Server HTTP/SDK API — and over **MCP at `/mcp`**. This repo does **not** embed into the gssc5 process.

> **Stack note:** Previously TypeScript/Bun. Rewritten to Python because the Bun/JS Agent Server path did not support the MCP endpoint we need.

## Assumptions

| Choice | Decision |
| --- | --- |
| Runtime | **Python ≥3.12 + uv** (`pyproject.toml` / `uv.lock`) — LangGraph Python |
| Serving | Official **Agent Server** via `langgraph` CLI (`mise run dev` / `uv run langgraph dev`) |
| MCP | Enabled by default at **`/mcp`** (Streamable HTTP); each graph is an MCP tool |
| LLM (domain graphs) | **xAI / Grok** via `langchain_xai.ChatXAI` (`create_chat_model()`) — default `grok-4.7` |
| Auth | **API key / Bearer** via `gssc_langgraph.auth` + `langgraph.json` (`GSSC_LANGGRAPH_API_KEY`). Empty key = local bypass |
| Default URL | `http://127.0.0.1:2024` |
| Dot Agents | This repo has `.agents/` for Kaneo/GLG process; graphs may also load **gssc5** `.agents` skills/memories as read-only context |

## Project layout

```text
.
├── langgraph.json                 # Agent Server config (graphs + env + auth)
├── mise.toml                      # Python + uv pins and task aliases
├── pyproject.toml / uv.lock
├── .agents/                       # Dot Agents guidelines, Kaneo MCP, skills, tasks
├── .env.example
├── Dockerfile
├── src/gssc_langgraph/
│   ├── auth/                      # Agent Server API-key / Bearer auth
│   ├── llm/                       # xAI / Grok defaults
│   ├── checkpoint/                # compile_with_memory for tests/helpers only
│   ├── gssc5/                     # load/select gssc5 `.agents` skills + memories
│   ├── graphs/
│   │   ├── health/graph.py
│   │   ├── conversation/graph.py
│   │   ├── closeout_review/graph.py
│   │   ├── test_development/graph.py
│   │   └── software_dev/graph.py
│   ├── review/                    # change-set collectors for CLIs
│   ├── closeout/                  # closeout_review criteria, checks, CLI
│   ├── test_dev/                  # test-development contracts, analyzers, CLI
│   └── software/                  # software_dev plan + closeout, CLI
├── docs/                          # I/O contracts
└── tests/                         # pytest
```

## Quick start

```bash
mise install          # or: install uv + Python 3.12
mise run install      # uv sync --all-extras
cp .env.example .env  # optional keys
mise run dev          # Agent Server on :2024 — MCP at /mcp
```

Without mise:

```bash
uv sync --all-extras
uv run langgraph dev --port 2024
uv run pytest
```

## MCP endpoint

With the Agent Server running, graphs are exposed as MCP tools over Streamable HTTP:

| Item | Value |
| --- | --- |
| URL | `http://127.0.0.1:2024/mcp` (or your deployed Agent Server `/mcp`) |
| Transport | Streamable HTTP |
| Tool names | Assistant ids (`health`, `conversation`, `closeout_review`, `software_dev`, `test_development`) |
| Auth | Same as Agent Server — Bearer / `x-api-key` when `GSSC_LANGGRAPH_API_KEY` is set |

Disable only if needed via `langgraph.json` → `http.disable_mcp: true` (not recommended for this service).

## LLM provider (xAI)

```python
from gssc_langgraph.llm import create_chat_model

llm = create_chat_model(temperature=0)
# optional: create_chat_model(model="grok-4.6")
```

| Concern | Default |
| --- | --- |
| Provider | xAI (`ChatXAI`) |
| Model id | `grok-4.7` |
| API key | `XAI_API_KEY` |
| Model override | `GSSC_XAI_MODEL` (preferred) or `XAI_MODEL` |

Smoke assistants (`health`, `conversation`) are **model-free**. Specialists keep deterministic checks model-free and skip optional synthesis when `XAI_API_KEY` is unset.

### LangSmith

1. Workspace secret `XAI_API_KEY` (provider: xAI).
2. Model configuration with Provider **xAI**, model **`grok-4.7`**.
3. Local traces: `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, `LANGSMITH_PROJECT` in `.env`.

## Registered graphs

| Assistant id | Purpose | Checkpointer (API export) |
| --- | --- | --- |
| `health` | Smoke / liveness (`status` / `service` / `checkedAt`) | none (Agent Server) |
| `conversation` | Model-free multi-turn echo | none (Agent Server) |
| `closeout_review` | Closeout review + optional synthesis | none — `reviewMemory` via threads |
| `test_development` | Test plan / closeout + optional synthesis | none — `specialistNotes` via threads |
| `software_dev` | Software plan / closeout + optional synthesis | none — `specialistNotes` via threads |

Also: HTTP `GET /ok` for process probes.

I/O contracts: [docs/closeout-review-contract.md](docs/closeout-review-contract.md), [docs/software-dev-contract.md](docs/software-dev-contract.md), [docs/test-development-contract.md](docs/test-development-contract.md).

## Agent Server auth

| Mode | Behavior |
| --- | --- |
| `GSSC_LANGGRAPH_API_KEY` empty | Local bypass (`identity: local-bypass`) |
| Key set | Require `Authorization: Bearer <key>` or `x-api-key` |
| `GSSC_LANGGRAPH_AUTH_BYPASS=true` | Force bypass (never in prod) |
| `GET /ok` | Always allowed |

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H "Authorization: Bearer $GSSC_LANGGRAPH_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"assistant_id":"health","input":{}}'
```

## Threads + checkpointer

`langgraph.json` graph exports compile **without** a custom checkpointer.
Agent Server owns thread persistence — set `POSTGRES_URI` for a durable store.
Do not attach `InMemorySaver` / `MemorySaver` to API-exported graphs
(`langgraph_api` raises `GraphLoadError`).

`compile_with_memory` + `GSSC_CHECKPOINT_*` are for pytest / direct-invoke
helpers only:

| `GSSC_CHECKPOINT_BACKEND` | Saver | Survives restart? |
| --- | --- | --- |
| unset / `memory` | In-process MemorySaver | No |
| `sqlite` | SqliteSaver via `GSSC_CHECKPOINT_SQLITE_PATH` | Yes (single node) |
| `postgres` | PostgresSaver via `GSSC_CHECKPOINT_POSTGRES_URL` | Yes (shared DB) |

```python
from gssc_langgraph.checkpoint import compile_with_memory, thread_config

# Tests / offline scripts only — not langgraph.json exports:
graph = compile_with_memory(builder, {"name": "My Agent"})
await graph.ainvoke({"message": "hi"}, thread_config("conversation-1"))
```

Specialists append durable notes on the same Agent Server / SDK `thread_id`
(`reviewMemory` / `specialistNotes`). CLI one-shots mint a fresh id per run.

### SDK / REST threads

```python
from langgraph_sdk import get_client
import os

api_key = os.environ.get("GSSC_LANGGRAPH_API_KEY")
client = get_client(
    url=os.environ.get("GSSC_LANGGRAPH_BASE_URL", "http://127.0.0.1:2024"),
    api_key=api_key or None,
    headers={"Authorization": f"Bearer {api_key}"} if api_key else None,
)
```

```bash
AUTH_HEADER=(-H "Authorization: Bearer $GSSC_LANGGRAPH_API_KEY")
THREAD_ID=$(curl -s -X POST http://127.0.0.1:2024/threads \
  "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' -d '{}' | jq -r .thread_id)

curl -s -N -X POST "http://127.0.0.1:2024/threads/${THREAD_ID}/runs/stream" \
  "${AUTH_HEADER[@]}" -H 'Content-Type: application/json' \
  -d '{"assistant_id":"conversation","input":{"message":"hello from gssc5"}}'
```

## Specialist CLIs

```bash
mise run closeout -- --workspace
mise run software -- --goal "Add membership lookup assistant"
mise run test-dev -- --workspace
# or: uv run closeout | software | test-dev
```

Exit `0` PASS / `1` FAIL / `2` usage-runtime error.

## gssc5 skills / memories (upstream context)

Specialists can pull [gssc5](https://github.com/GSSC-Web/gssc5) Dot Agents skills/memories as read-only context (`GSSC5_ROOT` → sibling `../gssc5` → auto-clone cache). See [docs/gssc5-skills-memories.md](docs/gssc5-skills-memories.md).

This repo’s **own** Dot Agents process (Kaneo **GLG**, backlog/Kaneo skills, weekly tasks) lives under [`.agents/`](.agents/agents.md).

## Tests / CI

```bash
uv run pytest
uv run python scripts/verify_sqlite_checkpoint.py
```

PR CI on `master` is path-filtered (`unit` + `sqlite` + aggregate `CI` gate). See `.github/workflows/test.yml`.

## Docker

Prefer `uv run langgraph build` for a full Agent Server image. The repo `Dockerfile` is a minimal uv-based packaging hint.

## Non-goals

- Do not reintroduce `service_review` or `sample_agent`
- Not a StrictDoc requirements product; specialist bots are LangGraph workflows
- Kaneo product work is separate; ALM process for this repo is `.agents/` → project **GLG**
