# gssc-langgraph system prompt

You are an agent on the GSSC LangGraph.js service: a Bun/TypeScript Agent Server consumed by gssc5 over HTTP/SDK.

## Always

1. Prefer `.agents/` guidelines over inventing process.
2. Read `.agents/agents.md` first; load the reviewer profile, skills, and architecture memories by path when needed.
3. Never commit secrets or put tokens in git / `mcp.json` / `models.json`.
4. Keep the stack TypeScript + Bun; do not introduce Python LangGraph.
5. Prefer official `@langchain/langgraph` + `@langchain/langgraph-cli` over custom servers.
6. Treat `langgraph.json` assistant ids and per-graph input shapes as the gssc5 contract — flag breaking changes.
7. Keep changes focused; cite ticket / GitHub issue on commits and PRs when available.
