---
id: langgraph-service-review
name: langgraph-service-review
description: >-
  Closeout review of LangGraph.js graphs, langgraph.json registry, Bun/TS
  quality, tests, and gssc5 HTTP/SDK contracts. Use before merge or when the
  owner asks for a LangGraph service review.
enabled: true
---

# LangGraph service review

**When:** End of a gssc-langgraph task before merge, or owner asks for a service / graph / contract review.

**Result:** **PASS** or **FAIL** with path + proposed fix. No silent contract rewrites to match SW.

## Steps

1. **Scope** — Review in-scope paths for this PR tip: `src/graphs/**`, `langgraph.json`, `package.json`, `tsconfig.json`, `tests/**`, README contract sections, `.env.example`, Docker/CLI packaging. Exclude drive-bys unless owner named them.
2. **Registry** — Every exported graph is registered in `langgraph.json` under a stable `assistant_id`. Keys match folder/export intent. No orphan registrations or unregistered graphs intended for gssc5.
3. **Graph quality** — Prefer `Annotation` + `StateGraph`, clear node names, compiled `export const graph`, sensible `graph.name`. Reducers/defaults sound. Fail-fast on bad input when the contract requires it. Avoid model-keyed graphs for smoke paths that must run without API keys (keep `health` / sample-style graphs model-free unless intentionally otherwise).
4. **gssc5 contract** — Assistant ids, input shapes, and threadless vs threaded usage stay compatible with README + `@langchain/langgraph-sdk` Client usage. Prefer server-side gssc5 backend → this service. Flag breaking input/output or id renames; require explicit owner acknowledgment.
5. **Stack** — TypeScript + Bun only. Prefer `@langchain/langgraph`, `@langchain/langgraph-cli`, Zod where schemas help. No Python LangGraph, no custom HTTP server replacing the Agent Server without owner ask.
6. **Tests & checks** — Bun tests cover new/changed graph behavior. `bun test` and `bun run typecheck` are expected to pass for the tip. Tests assert documented contract behavior, not accidental implementation quirks.
7. **Safety / ops** — No secrets in git. `.env.example` lists needed vars without values. Docker/CLI notes remain accurate.
8. **Verdict** — PASS / FAIL. Allowed without waiting: missing test for a trivial rename, docs typos, registry comment clarity. Not silent: assistant id renames, input shape breaks, auth/CORS assumption flips, stack changes.

## Orchestration

Load `.agents/agents/reviewer/agent.md` when acting as the dedicated reviewer. Cite `.agents/memories/langgraph-arch.md` for durable facts.
