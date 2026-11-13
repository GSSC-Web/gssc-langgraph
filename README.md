# gssc-langgraph

Standalone [LangGraph.js](https://docs.langchain.com/oss/javascript/langgraph/overview) service for GSSC-Web. The sibling app [gssc5](https://github.com/GSSC-Web/gssc5) is expected to call this service over the LangGraph Agent Server HTTP/SDK API — this repo does **not** embed into the gssc5 process.

## Assumptions (confirm with Bonyfish if needed)

| Choice | Decision |
| --- | --- |
| Runtime | **TypeScript + Bun** (`packageManager: bun`), LangGraph.js — not Python |
| Serving | Official **Agent Server** via `@langchain/langgraph-cli` (`bun run dev`) — no custom HTTP framework |
| LLM (domain graphs) | **xAI / Grok** via `@langchain/xai` `ChatXAI` (`createChatModel()` in `src/llm`) — default model `grok-4.7` |
| Auth (local) | **None** for local CLI serve (loopback). Production: LangSmith / custom `langgraph.json` `auth` later |
| CORS | Prefer **gssc5 backend → this service** (server-side). Browser CORS not required for that pattern |
| Default URL | `http://127.0.0.1:2024` (`langgraph-cli dev` default) |
| gssc5 port | gssc5 backend defaults to `PORT=3000` — keep this service on **2024** to avoid collisions |

## Project layout

```text
.
├── langgraph.json              # Agent Server config (graphs + env)
├── mise.toml                   # mise-en-place: Bun pin + task aliases
├── package.json                # Bun package manager
├── tsconfig.json
├── .env.example
├── Dockerfile                  # code package only; prefer langgraph-cli build for server images
├── src/llm/                    # xAI / Grok defaults (`createChatModel`)
├── src/graphs/
│   ├── health/graph.ts         # assistant id: health
│   ├── sample_agent/graph.ts   # assistant id: sample_agent
│   └── service_review/graph.ts # assistant id: service_review
├── src/review/                 # review criteria, collectors, CLI
└── tests/
```

Add future GSSC domain graphs as new folders under `src/graphs/<domain>/` and register them in `langgraph.json`. Prefer `createChatModel()` from `src/llm` when a graph needs an LLM (xAI by default).

## LLM provider (xAI)

Domain graphs that call a chat model should use the shared helper:

```ts
import { createChatModel } from "../llm/index.js";
// or: import { createChatModel } from "../../index.js";

const llm = createChatModel({ temperature: 0 });
// optional: createChatModel({ model: "grok-4.6" })
```

| Concern | Default |
| --- | --- |
| Provider | xAI (`ChatXAI` from `@langchain/xai`) |
| Model id | `grok-4.7` (xAI’s current general / agentic recommendation) |
| API key env | `XAI_API_KEY` |
| Model override env | `GSSC_XAI_MODEL` (preferred) or `XAI_MODEL` |

Smoke assistants (`health`, `sample_agent`, `service_review`) remain **model-free** so `bun run dev` / CI work without provider keys.

### Breaking / migration notes

- No change to existing assistant ids or smoke-graph I/O.
- New dependency: `@langchain/xai`.
- Domain graphs that previously would have used OpenAI/Anthropic should call `createChatModel()` (or pass an explicit provider) instead of hard-coding `ChatOpenAI` / `ChatAnthropic`.
- Set `XAI_API_KEY` before invoking any graph that uses the helper.

### LangSmith tracing + “model of choice” (manual UI)

In-repo defaults cover **code** (`ChatXAI` + env). LangSmith’s workspace **Default Model** for Playground / Evaluators / Chat / Insights is configured in the dashboard and cannot live in this repo:

1. Add a workspace secret named `XAI_API_KEY` under **Settings → Integrations → Provider secrets** (provider: xAI).
2. Open **Settings → Model configurations**, create a configuration with **Provider: xAI**, model **`grok-4.7`** (or your override), API key name `XAI_API_KEY`.
3. In the **Feature Access** table, enable **xAI** for the features you use and set **Default Model** to that configuration.
4. For local/Agent Server traces: set `LANGSMITH_API_KEY`, `LANGSMITH_TRACING=true`, and `LANGSMITH_PROJECT` in `.env` (see `.env.example`). Traces from `ChatXAI` report `ls_provider=xai` and the selected model id.

## Service review workflow

Runnable agentic review (LangGraph graph + CLI), inspired by [gssc5 closeout-review skills](https://github.com/GSSC-Web/gssc5/tree/master/.agents/skills) (PASS/FAIL, scoped checks, no silent contract rewrites) but implemented here as a **model-free** Bun/TypeScript workflow for this Agent Server.

### What it checks

| Check | Focus |
| --- | --- |
| `registry` | `langgraph.json` ↔ `src/graphs/<id>/graph.ts` |
| `graph_quality` | Annotation/StateGraph/export/`graph.name`; smoke graphs stay model-free |
| `stack` | TypeScript + Bun + LangGraph.js (flag Python / custom HTTP servers) |
| `gssc5_contract` | Baseline assistant ids (`health`, `sample_agent`) + sample input shape |
| `tests` | Changed graphs have bun:test coverage |
| `secrets` | No committed secrets / real-looking keys |

**Output:** `verdict: PASS|FAIL`, `summary`, and `findings[]` with `check`, `severity`, `path`, `message`, `fix`.

### Trigger locally

```bash
bun run review                 # git range vs origin/main (+ dirty tree), else workspace
bun run review --base main
bun run review --workspace     # full structural scan
bun run review --diff pr.patch
bun run review --json          # machine-readable report
```

Exit `0` on PASS, `1` on FAIL.

### Trigger via Agent Server

With `bun run dev`, call assistant `service_review`:

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "service_review",
    "input": {
      "label": "api",
      "files": {
        "langgraph.json": "{\"graphs\":{}}",
        "src/graphs/orphan/graph.ts": "export const graph = {}"
      }
    }
  }'
```

Prefer `bun run review` for git-aware PR/diff collection; the assistant accepts a pre-built `files` map and optional `diff` string.

## Registered graphs

| Assistant id | Purpose |
| --- | --- |
| `health` | Smoke / liveness payload via the same runs API |
| `sample_agent` | Model-free echo workflow for gssc5 integration tests |
| `service_review` | Model-free review workflow (registry, stack, gssc5 contract, …) |

The Agent Server also exposes HTTP `GET /ok` for process health.

## Run locally (Bun)

Requires [Bun](https://bun.sh) (≥ 1.1 recommended). With [mise](https://mise.jdx.dev/) installed, `mise install` pins Bun from `mise.toml`, and `mise run install|dev|test|typecheck|review` wraps the same scripts as below (same style as [gssc5](https://github.com/GSSC-Web/gssc5)).

```bash
bun install          # or: mise run install
cp .env.example .env
# optional: LANGSMITH_API_KEY (+ LANGSMITH_TRACING=true) for tracing / Studio
# for domain LLM graphs: set XAI_API_KEY (smoke graphs do not need it)

bun run dev          # or: mise run dev
```

This starts `@langchain/langgraph-cli` in in-memory / local mode.

Expected endpoints:

- API: `http://127.0.0.1:2024`
- OpenAPI docs: `http://127.0.0.1:2024/docs`
- Studio: URL printed by the CLI (`baseUrl=http://127.0.0.1:2024`)

Unit tests (no server required):

```bash
bun test             # or: mise run test
```

Typecheck:

```bash
bun run typecheck    # or: mise run typecheck
```

### Docker / platform image

For a full Agent Server image, use the CLI (recommended):

```bash
bunx @langchain/langgraph-cli build -t gssc-langgraph:local
```

The root `Dockerfile` only packages graph code with Bun; day-to-day local work should use `bun run dev`.

## How gssc5 should call this service

**Base URL env (suggested for gssc5):**

```bash
GSSC_LANGGRAPH_BASE_URL=http://127.0.0.1:2024
```

### Option A — JS/TS SDK (recommended from gssc5 backend)

```bash
bun add @langchain/langgraph-sdk
# or: npm install @langchain/langgraph-sdk
```

```ts
import { Client } from "@langchain/langgraph-sdk";

const client = new Client({
  apiUrl: process.env.GSSC_LANGGRAPH_BASE_URL ?? "http://127.0.0.1:2024",
});

// Threadless health check via the health assistant
const healthStream = client.runs.stream(null, "health", { input: {} });

// Sample agent with a durable thread
const thread = await client.threads.create();
const runStream = client.runs.stream(thread.thread_id, "sample_agent", {
  input: { message: "hello from gssc5" },
});
```

### Option B — REST (threads + runs)

Create a thread:

```bash
curl -s -X POST http://127.0.0.1:2024/threads \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Stream a run (threadless):

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "sample_agent",
    "input": { "message": "hello from gssc5" }
  }'
```

Health assistant:

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{ "assistant_id": "health", "input": {} }'
```

Process liveness:

```bash
curl -s http://127.0.0.1:2024/ok
```

### Assumed API contract for gssc5

| Concern | Contract |
| --- | --- |
| Transport | HTTP to Agent Server (`GSSC_LANGGRAPH_BASE_URL`) |
| Assistant selection | `assistant_id` = graph key from `langgraph.json` (`health`, `sample_agent`, …) |
| Stateless | `POST /runs/stream` with `thread_id` omitted / SDK `null` |
| Stateful | `POST /threads` then threads/runs stream (or SDK equivalents) |
| Input shape | Per-graph; sample agent expects `{ "message": string }` |
| Auth (local) | None |
| Auth (prod) | TBD — LangSmith API key and/or custom auth handler |

Official references:

- [Local server (JS)](https://docs.langchain.com/oss/javascript/langgraph/local-server)
- [Application structure](https://docs.langchain.com/langsmith/setup-javascript)
- [LangGraph CLI](https://docs.langchain.com/langsmith/cli)
- [ChatXAI (xAI / Grok)](https://docs.langchain.com/oss/javascript/integrations/chat/xai)
- [LangSmith model configurations](https://docs.langchain.com/langsmith/model-configurations)
- [xAI models](https://docs.x.ai/docs/models)
