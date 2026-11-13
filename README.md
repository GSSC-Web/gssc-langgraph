# gssc-langgraph

Standalone [LangGraph.js](https://docs.langchain.com/oss/javascript/langgraph/overview) service for GSSC-Web. The sibling app [gssc5](https://github.com/GSSC-Web/gssc5) is expected to call this service over the LangGraph Agent Server HTTP/SDK API — this repo does **not** embed into the gssc5 process.

## Assumptions (confirm with Bonyfish if needed)

| Choice | Decision |
| --- | --- |
| Runtime | **TypeScript + Bun** (`packageManager: bun`), LangGraph.js — not Python |
| Serving | Official **Agent Server** via `@langchain/langgraph-cli` (`bun run dev`) — no custom HTTP framework |
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
├── src/graphs/
│   ├── health/graph.ts         # assistant id: health
│   ├── sample_agent/graph.ts   # assistant id: sample_agent
│   ├── service_review/graph.ts # assistant id: service_review
│   └── software_dev/graph.ts   # assistant id: software_dev
├── src/review/                 # service review criteria, collectors, CLI
├── src/software/               # software_dev plan + closeout criteria, CLI
└── tests/
```

Add future GSSC domain graphs as new folders under `src/graphs/<domain>/` and register them in `langgraph.json`.

## Software development bot

Runnable agentic software workflow (LangGraph graph + CLI). Behavioral reference: [gssc5 software agent](https://github.com/GSSC-Web/gssc5/blob/master/.agents/agents/software/agent.md) and [software-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/software-closeout-review/SKILL.md) (scope → implement → third-party-first → PASS/FAIL, no silent contract rewrites) — implemented here as a **model-free** Bun/TypeScript workflow, not a Dot Agents `.agents/` scaffold.

The sibling **test** development bot is a separate assistant (`test_dev`); this bot owns `software_dev` / `src/software/` only.

### What it does

1. Emits a deterministic **implementation plan** from `--goal` (and optional change set).
2. Runs software closeout checks:

| Check | Focus |
| --- | --- |
| `scope` | Goal and/or reviewable change set present |
| `trace` | New assistants registered in `langgraph.json` + README mention |
| `match` | Real StateGraph + `export const graph` (not a hollow stub) |
| `quality` | Fail-fast, size, `graph.name`, model-free smoke assistants |
| `third_party` | LangGraph.js / Bun / langgraph-cli over reinvented HTTP or Python |
| `discipline` | No silent baseline/contract drops; no deleting covering tests to “fix” SW |

**Output:** `verdict: PASS|FAIL`, `summary`, `plan[]`, and `findings[]`.

### Trigger locally

```bash
bun run software --goal "Add foo assistant that …"
bun run software --goal "…" --workspace
bun run software --workspace          # closeout scan of the tree
bun run software --diff pr.patch
bun run software --plan-only --goal "Fix health checkedAt skew"
bun run software --json
# or: mise run software -- --goal "…"
```

Default git base is `origin/master`. Exit `0` on PASS, `1` on FAIL.

### Trigger via Agent Server

With `bun run dev`, call assistant `software_dev`:

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "software_dev",
    "input": {
      "goal": "Add a domain graph for membership lookups",
      "label": "api",
      "files": {
        "langgraph.json": "{\"graphs\":{\"health\":\"./src/graphs/health/graph.ts:graph\",\"sample_agent\":\"./src/graphs/sample_agent/graph.ts:graph\"}}",
        "src/graphs/membership/graph.ts": "export const graph = {}"
      }
    }
  }'
```

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
| `software_dev` | Model-free software plan + closeout (gssc5 software-agent spirit) |

The Agent Server also exposes HTTP `GET /ok` for process health.

## Run locally (Bun)

Requires [Bun](https://bun.sh) (≥ 1.1 recommended). With [mise](https://mise.jdx.dev/) installed, `mise install` pins Bun from `mise.toml`, and `mise run install|dev|test|typecheck|review|software` wraps the same scripts as below (same style as [gssc5](https://github.com/GSSC-Web/gssc5)).

```bash
bun install          # or: mise run install
cp .env.example .env
# optional: set LANGSMITH_API_KEY for tracing / Studio

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
