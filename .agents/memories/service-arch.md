---
id: service-arch
title: gssc-langgraph service architecture
importance: high
tags: [langgraph, python, uv, agent-server, mcp]
---

# Service architecture

- **Role:** Standalone LangGraph Agent Server for GSSC-Web. gssc5 (and other clients) call it over HTTP/SDK; this repo does **not** embed into the gssc5 process.
- **Runtime:** Python ≥3.12, packaged with **uv** (`pyproject.toml` / `uv.lock`). Tooling via `mise.toml` (`mise run install|dev|test|closeout|test-dev|software`).
- **Serving:** Official Agent Server via `langgraph` CLI (`uv run langgraph dev`, default `http://127.0.0.1:2024`). Prefer `langgraph.json` + CLI over custom FastAPI/Flask/Starlette servers.
- **MCP:** Agent Server exposes Streamable HTTP MCP at **`/mcp`** (primary reason for the Python stack). Each registered graph is an MCP tool; tool name = graph id. Disable only via `http.disable_mcp` if ever required.
- **Package root:** `src/gssc_langgraph/` — graphs under `graphs/<assistant_id>/graph.py`, shared `auth/`, `checkpoint/`, `llm/`, `gssc5/`, domain modules `closeout/`, `software/`, `test_dev/`, `review/`.
- **Registry:** `langgraph.json` lists assistants + `auth.path` + `env: .env` + `python_version: 3.12`.
- **LLM default:** xAI / Grok via `create_chat_model()` (`langchain_xai.ChatXAI`). Default model `grok-4.7`; override with `GSSC_XAI_MODEL` or `XAI_MODEL`. Key: `XAI_API_KEY`.
- **Tracing:** LangSmith via `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT` (see `.env.example`).
- **gssc5 context:** Optional checkout of sibling gssc5 `.agents` skills/memories (`GSSC5_ROOT` / auto-clone cache). Used by specialist graphs; empty-on-fail.
- **Tests:** `pytest` under `tests/`; fixtures for gssc5 under `tests/fixtures/gssc5/`.
- **Non-goals:** No `service_review`, no `sample_agent`, not a StrictDoc requirements tree, not Kaneo product code.
