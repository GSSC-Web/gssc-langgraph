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
├── src/checkpoint/             # MemorySaver + compileWithMemory / threadConfig
├── src/gssc5/                  # load/select gssc5 `.agents` skills + memories
├── src/graphs/
│   ├── health/graph.ts              # assistant id: health
│   ├── conversation/graph.ts        # assistant id: conversation (MemorySaver)
│   ├── closeout_review/graph.ts     # assistant id: closeout_review
│   ├── test_development/graph.ts    # assistant id: test_development
│   └── software_dev/graph.ts        # assistant id: software_dev
├── src/review/                 # shared change-set collectors for tooling CLIs
├── src/closeout/               # closeout_review criteria, checks, CLI
├── src/test_dev/               # test-development contracts, analyzers, CLI
├── src/software/               # software_dev plan + closeout criteria, CLI
└── tests/
```

Add future GSSC domain graphs as new folders under `src/graphs/<domain>/` and register them in `langgraph.json`. Prefer `createChatModel()` from `src/llm` when a graph needs an LLM (xAI by default). Conversational / LLM graphs should `compileWithMemory` from `src/checkpoint` so clients can continue via `thread_id`.

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

Smoke/tooling assistants (`health`, `conversation`, `closeout_review`, `software_dev`, `test_development`) remain **model-free** so `bun run dev` / CI work without provider keys.

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

## Software development bot

Runnable agentic software workflow (LangGraph graph + CLI). Behavioral reference: [gssc5 software agent](https://github.com/GSSC-Web/gssc5/blob/master/.agents/agents/software/agent.md) and [software-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/software-closeout-review/SKILL.md) (scope → implement → third-party-first → PASS/FAIL, no silent contract rewrites) — implemented here as a **model-free** Bun/TypeScript workflow, not a Dot Agents `.agents/` scaffold.

The sibling **test** development bot is a separate assistant (`test_development` / `src/test_dev/`); this bot owns `software_dev` / `src/software/` only.

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
        "langgraph.json": "{\"graphs\":{\"health\":\"./src/graphs/health/graph.ts:graph\"}}",
        "src/graphs/membership/graph.ts": "export const graph = {}"
      }
    }
  }'
```

## Closeout review workflow

Runnable agentic **closeout reviewer** (LangGraph graph + CLI). Behavioral reference: gssc5 peer closeout skills — [requirements-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/requirements-closeout-review/SKILL.md), [software-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/software-closeout-review/SKILL.md), [test-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/test-closeout-review/SKILL.md) (scope → peer lanes → PASS/FAIL with proposed fixes; no silent contract rewrites) — implemented here as a **model-free** Bun/TypeScript workflow, not a Dot Agents `.agents/` scaffold.

This is a **new** assistant (`closeout_review` / `src/closeout/`), not a revival of `service_review`. Peers: `software_dev` (plan + SW closeout) and `test_development` (test plan/closeout). Baseline contract required here is **`health` only**.

### What it checks

| Check | gssc5 peer | Focus |
| --- | --- | --- |
| `scope` | all | Reviewable change set / workspace present |
| `contracts` | requirements | Baseline `health` stays registered; no silent README/contract drops |
| `software_trace` | software | `langgraph.json` ↔ `src/graphs/<id>/graph.ts` (+ README for new ids) |
| `software_match` | software | Real StateGraph + `export const graph` / `compileWithMemory` (not a hollow stub) |
| `software_quality` | software | Fail-fast, size, `graph.name`, model-free smoke/tooling |
| `third_party` | software | LangGraph.js / Bun / langgraph-cli over reinvented HTTP or Python |
| `test_coverage` | test | Changed / workspace graphs have bun:test coverage |
| `test_target` | test | Intentional expects; no deleting covering tests to “fix” SW |
| `secrets` | ops | No committed secrets / real-looking keys |

**Output:** `verdict: PASS|FAIL`, `summary`, and `findings[]` with `check`, `severity`, `path`, `uid?`, `message`, `fix`.

### Trigger locally

```bash
bun run closeout                 # git range vs origin/master (+ dirty), else workspace
bun run closeout --base master
bun run closeout --workspace     # full structural closeout
bun run closeout --diff pr.patch
bun run closeout --json          # machine-readable report
# or: mise run closeout
```

Exit `0` on PASS, `1` on FAIL.

### Trigger via Agent Server

With `bun run dev`, call assistant `closeout_review`:

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "closeout_review",
    "input": {
      "label": "api",
      "files": {
        "langgraph.json": "{\"graphs\":{\"health\":\"./src/graphs/health/graph.ts:graph\"}}",
        "src/graphs/orphan/graph.ts": "export const graph = {}"
      }
    }
  }'
```

Prefer `bun run closeout` for git-aware PR/diff collection; the assistant accepts a pre-built `files` map and optional `diff` string.

## Test development workflow

Runnable agentic test-development bot (LangGraph graph + CLI). Behavioral reference: [gssc5 test agent](https://github.com/GSSC-Web/gssc5/blob/master/.agents/agents/test/agent.md) and [test-closeout-review](https://github.com/GSSC-Web/gssc5/blob/master/.agents/skills/test-closeout-review/SKILL.md) (one permanent test per in-scope requirement, assert the contract not incidental SW, focused harness, PASS/FAIL + plan) — implemented here as a **model-free** Bun/TypeScript workflow, not a Dot Agents `.agents/` scaffold.

Without StrictDoc LLRs, **contracts** are documented assistant behaviors (baseline health API + structural contracts for other registered graphs).

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

Prefer `bun run test-dev` for git-aware collection; the assistant accepts a pre-built `files` map and optional `diff` string (same shape as `closeout_review`).

Sibling **software development** bot lives under `software_dev` / `src/software/` (separate ownership); this workflow does not implement software closeout. Pre-merge **closeout review** is `closeout_review` / `src/closeout/`.

## gssc5 skills / memories context

Domain graphs can pull relevant [gssc5 Dot Agents](https://github.com/GSSC-Web/gssc5/tree/master/.agents) skills and architecture memories into LangGraph state as **read-only context** (this service does not copy or own those files).

| Concern | Default |
| --- | --- |
| Locator | `GSSC5_ROOT` (filesystem path) → sibling `../gssc5` → auto-clone into `GSSC5_CACHE_DIR` |
| Remote | `GSSC5_REPO_URL` (default `https://github.com/GSSC-Web/gssc5.git`), ref `GSSC5_REF=master` |
| Layout | `.agents/skills/<id>/SKILL.md`, `.agents/memories/<id>.md` |
| Relevance | Keyword/tag scoring + role presets (`software` / `test`) + optional `requireSkills` |
| Wired graphs | `software_dev`, `test_development` (not `health`) |
| Missing / failed checkout | Empty `gssc5Context` + `note`; graph continues |

Helpers live under `src/gssc5/` (`loadGssc5Context`, `createLoadGssc5ContextNode`). Per-invoke overrides: `configurable.gssc5Root`, `gssc5Enabled`, `preferSkills`, `requireSkills`, ….

See [docs/gssc5-skills-memories.md](docs/gssc5-skills-memories.md).

## Registered graphs

| Assistant id | Purpose | Checkpointer |
| --- | --- | --- |
| `health` | Smoke / liveness payload via the same runs API (baseline contract) | none (one-shot) |
| `conversation` | Model-free multi-turn echo demo (thread persistence) | **MemorySaver** |
| `closeout_review` | Model-free closeout review (gssc5 peer closeout skills) | none (one-shot) |
| `test_development` | Model-free test-development workflow (contracts → plan / closeout) | none (one-shot) |
| `software_dev` | Model-free software plan + closeout (gssc5 software-agent spirit) | none (one-shot) |

The Agent Server also exposes HTTP `GET /ok` for process health.

## Threads + MemorySaver (short-term memory)

Conversational assistants persist graph state **per thread** when compiled with a checkpointer. This service uses LangGraph’s in-process [`MemorySaver`](https://docs.langchain.com/oss/javascript/langgraph/add-memory) for local/dev:

```ts
import { compileWithMemory, threadConfig } from "./checkpoint/index.js";
// or: import { compileWithMemory, threadConfig } from "./index.js";

export const graph = compileWithMemory(builder, { name: "My Agent" });

// Direct invoke (unit tests / scripts):
await graph.invoke({ message: "hi" }, threadConfig("conversation-1"));
await graph.invoke({ message: "again" }, threadConfig("conversation-1"));
```

| Concern | Detail |
| --- | --- |
| Which graphs | `conversation` today; new conversational / LLM graphs should opt in via `compileWithMemory` |
| One-shot bots | `health`, closeout-style workflows stay on `builder.compile()` (no durable turn memory) |
| Persistence scope | **In-process** — lost on Agent Server restart. Fine for local `bun run dev` |
| Production follow-up | Swap to a durable saver (e.g. Postgres / SQLite checkpointer) when multi-replica or restart-safe memory is required — not blocking this setup |
| Agent Server threads | Create a thread, then stream runs with that `thread_id` (SDK or REST below) |

### Invoke with a thread (SDK)

```ts
import { Client } from "@langchain/langgraph-sdk";

const client = new Client({
  apiUrl: process.env.GSSC_LANGGRAPH_BASE_URL ?? "http://127.0.0.1:2024",
});

const thread = await client.threads.create();
await client.runs.wait(thread.thread_id, "conversation", {
  input: { message: "hello" },
});
// Same thread_id → prior checkpointed state is loaded for the next turn
await client.runs.wait(thread.thread_id, "conversation", {
  input: { message: "follow-up" },
});
```

### Invoke with a thread (Agent Server REST)

```bash
THREAD_ID=$(curl -s -X POST http://127.0.0.1:2024/threads \
  -H 'Content-Type: application/json' -d '{}' | jq -r .thread_id)

curl -s -N -X POST "http://127.0.0.1:2024/threads/${THREAD_ID}/runs/stream" \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "conversation",
    "input": { "message": "hello from gssc5" }
  }'
```

Pass the same `THREAD_ID` on later runs to continue the conversation. Omit the thread (threadless `POST /runs/stream`) for one-shot invokes such as `health`.

## Run locally (Bun)

Requires [Bun](https://bun.sh) (≥ 1.1 recommended). With [mise](https://mise.jdx.dev/) installed, `mise install` pins Bun from `mise.toml`, and `mise run install|dev|test|typecheck|closeout|test-dev|software` wraps the same scripts as below (same style as [gssc5](https://github.com/GSSC-Web/gssc5)).

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

// Conversation assistant with a thread (MemorySaver persists state for this thread_id)
const thread = await client.threads.create();
const runStream = client.runs.stream(thread.thread_id, "conversation", {
  input: { message: "hello from gssc5" },
});
// Reuse thread.thread_id on later runs to continue the conversation.
```

### Option B — REST (threads + runs)

Create a thread:

```bash
curl -s -X POST http://127.0.0.1:2024/threads \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Stream a run (threadless) — health assistant:

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
| Assistant selection | `assistant_id` = graph key from `langgraph.json` (`health`, `conversation`, …) |
| Stateless | `POST /runs/stream` with `thread_id` omitted / SDK `null` |
| Stateful | `POST /threads` then `threads/{id}/runs/stream` (or SDK `runs.stream(thread_id, …)`); graphs compiled with `compileWithMemory` load prior checkpoints |
| Input shape | Per-graph; health accepts `{}`; `conversation` expects `{ "message": string }` |
| Checkpointer (local) | In-process `MemorySaver` on `conversation` (and future conversational graphs via `compileWithMemory`) |
| Auth (local) | None |
| Auth (prod) | TBD — LangSmith API key and/or custom auth handler |

Official references:

- [Local server (JS)](https://docs.langchain.com/oss/javascript/langgraph/local-server)
- [Application structure](https://docs.langchain.com/langsmith/setup-javascript)
- [LangGraph CLI](https://docs.langchain.com/langsmith/cli)
- [ChatXAI (xAI / Grok)](https://docs.langchain.com/oss/javascript/integrations/chat/xai)
- [LangSmith model configurations](https://docs.langchain.com/langsmith/model-configurations)
- [xAI models](https://docs.x.ai/docs/models)
