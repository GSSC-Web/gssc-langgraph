---
id: langgraph-arch
title: gssc-langgraph service architecture
importance: high
tags: [langgraph, bun, typescript, gssc5, agent-server]
---

# LangGraph service

- Repo: standalone Agent Server for GSSC-Web; consumed by gssc5 (not in-process).
- Runtime: TypeScript + Bun (`packageManager: bun@…`); `bun run dev` → `@langchain/langgraph-cli` on `http://127.0.0.1:2024`.
- Config: `langgraph.json` registers graphs; `env: .env`; Wolfi image distro for CLI builds.
- Graphs live under `src/graphs/<id>/graph.ts` exporting compiled `graph`.
- Current assistants:
  - `health` — model-free smoke payload (`status`/`service`/`checkedAt`); same runs API as real workflows. Process liveness also via `GET /ok`.
  - `sample_agent` — model-free echo; input `{ message: string }`; output `reply` + `steps` reducer.
- gssc5 contract (assumed until wired):
  - Env: `GSSC_LANGGRAPH_BASE_URL=http://127.0.0.1:2024`
  - Prefer gssc5 backend → this service (avoid browser CORS).
  - SDK: `@langchain/langgraph-sdk` Client (`threads` / `runs.stream`); REST alternatives in README.
  - Auth local: none; production auth TBD (LangSmith / custom `auth` in `langgraph.json`).
- Tests: `tests/*.test.ts` with `bun:test`; invoke compiled graphs directly (no server required).
- Packaging: prefer `bunx @langchain/langgraph-cli build`; root `Dockerfile` packages graph code with Bun only.
