---
id: ops-arch
title: Ops, auth, env, and Kaneo linkage
importance: high
tags: [auth, env, ci, kaneo, ops]
---

# Ops

## Agent Server auth

- Env: `GSSC_LANGGRAPH_API_KEY` (comma-separated for rotation). Empty → local bypass.
- Force bypass: `GSSC_LANGGRAPH_AUTH_BYPASS=true` (never in prod).
- Clients: `Authorization: Bearer <key>` or `x-api-key: <key>`.
- `GET /ok` always allowed for probes.
- Handler: `src/gssc_langgraph/auth` wired from `langgraph.json` `auth.path`.

## Important env (see `.env.example`)

| Area | Vars |
| --- | --- |
| LangSmith | `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` |
| xAI | `XAI_API_KEY`, `GSSC_XAI_MODEL` / `XAI_MODEL` |
| Base URL | `GSSC_LANGGRAPH_BASE_URL` (default `http://127.0.0.1:2024`) |
| Auth | `GSSC_LANGGRAPH_API_KEY`, `GSSC_LANGGRAPH_AUTH_BYPASS` |
| Checkpoint | `GSSC_CHECKPOINT_BACKEND`, `GSSC_CHECKPOINT_SQLITE_PATH`, `GSSC_CHECKPOINT_POSTGRES_URL`, `GSSC_CHECKPOINT_POSTGRES_SCHEMA` |
| gssc5 checkout | `GSSC5_ROOT`, `GSSC5_CACHE_DIR`, `GSSC5_REPO_URL`, `GSSC5_REF`, `GSSC5_AUTO_CHECKOUT` |

## CI

- GitHub Actions workflow `.github/workflows/test.yml` on PRs to `master`.
- Path-filtered **unit** (pytest) and **sqlite** smoke; aggregate **CI** gate allows skipped jobs on docs-only PRs.

## Kaneo (ALM)

- Workspace **GSSC Web**; project **GSSC LangGraph** / slug **GLG**.
- Sister **GSSC5** is a template/peer product board — file this repo’s work on **GLG**.
- Labels: typically workspace **Backend** for eng work.
- Custom fields: Issue Type, Reported Version, Fix Version, DoR/DoD (+ Satisfied), Defects Discovered.
- MCP placeholders: `.agents/mcp.json` (`KANEO_MCP_URL`, `KANEO_API_TOKEN`, optional workspace/project ids).
- Done = merge to **master** + Fix Version set; open PR → Ready for Review when available.
