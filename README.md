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
│   ├── health/graph.ts              # assistant id: health
│   ├── sample_agent/graph.ts        # assistant id: sample_agent
│   ├── service_review/graph.ts      # assistant id: service_review
│   └── test_development/graph.ts    # assistant id: test_development
├── src/review/                 # service review criteria, collectors, CLI
├── src/test_dev/               # test-development contracts, analyzers, CLI
└── tests/
```

Add future GSSC domain graphs as new folders under `src/graphs/<domain>/` and register them in `langgraph.json`.

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

## Test development workflow

Runnable agentic test-development bot (LangGraph graph + CLI). Behavioral reference: [gssc5 test agent](https://github.com/GSSC-Web/gssc5/blob/master/.agents/agents/test/agent.md) and [test-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/test-closeout-review/SKILL.md) (one permanent test per in-scope requirement, assert the contract not incidental SW, focused harness, PASS/FAIL + plan) — implemented here as a **model-free** Bun/TypeScript workflow, not a Dot Agents `.agents/` scaffold.

Without StrictDoc LLRs, **contracts** are documented assistant behaviors (baseline health/sample_agent API + structural contracts for other registered graphs).

### What it does

| Step | Focus |
| --- | --- |
| `scope` | In-scope graphs from diff / workspace |
| `coverage_map` | Each contract has a permanent bun:test locking it |
| `target` | Tests assert the documented contract, not “whatever SW does” |
| `asserts` | Behavior from the contract verb; flag weak/empty expects |
| `timing` | Prefer focused `bun test <file>` commands |

**Output:** `verdict: PASS|FAIL`, `summary`, `findings[]`, `coverage[]`, a development `plan[]` (add/update tests, suggested stubs), and `commands[]` for focused runs.

### Trigger locally

```bash
bun run test-dev                 # git range vs origin/master (+ dirty), else workspace
bun run test-dev --base master
bun run test-dev --workspace     # full contract map
bun run test-dev --diff pr.patch
bun run test-dev --json          # machine-readable report
bun run test-dev --run           # analysis + execute suggested focused bun test
```

Or with mise: `mise run test-dev`.

Exit `0` on PASS, `1` on FAIL.

### Trigger via Agent Server

With `bun run dev`, call assistant `test_development`:

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "test_development",
    "input": {
      "label": "workspace",
      "files": {}
    }
  }'
```

Prefer `bun run test-dev` for git-aware collection; the assistant accepts a pre-built `files` map and optional `diff` string (same shape as `service_review`).

Sibling **software development** bot (separate PR / tree under `src/software_dev/` + `software_development` graph) is intentionally out of scope here.

## Registered graphs

| Assistant id | Purpose |
| --- | --- |
| `health` | Smoke / liveness payload via the same runs API |
| `sample_agent` | Model-free echo workflow for gssc5 integration tests |
| `service_review` | Model-free review workflow (registry, stack, gssc5 contract, …) |
| `test_development` | Model-free test-development workflow (contracts → plan / closeout) |

The Agent Server also exposes HTTP `GET /ok` for process health.

## Run locally (Bun)

Requires [Bun](https://bun.sh) (≥ 1.1 recommended). With [mise](https://mise.jdx.dev/) installed, `mise install` pins Bun from `mise.toml`, and `mise run install|dev|test|typecheck|review|test-dev` wraps the same scripts as below (same style as [gssc5](https://github.com/GSSC-Web/gssc5)).

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
