# gssc-langgraph agent guidelines

Layout follows the [Dot Agents Protocol](https://dotagentsprotocol.com), matching [gssc5](https://github.com/GSSC-Web/gssc5) conventions. This file is the project source of truth (not a duplicate root `AGENTS.md`).

## Overview

Standalone LangGraph.js Agent Server for GSSC-Web. Sibling [gssc5](https://github.com/GSSC-Web/gssc5) consumes it over HTTP/SDK; this repo does not embed into the gssc5 process.

| Path | Role |
| --- | --- |
| `src/graphs/` | LangGraph assistants (`health`, `sample_agent`, …) |
| `langgraph.json` | Agent Server graph registry + env |
| `tests/` | Bun unit tests for graphs |
| `.agents/` | Agent guidelines, skills, profiles, memories |

## Commands

- Install: `bun install`
- Dev server: `bun run dev` → `http://127.0.0.1:2024`
- Tests: `bun test`
- Typecheck: `bun run typecheck`

## Core rules

- Stack is **TypeScript + Bun** (not Python). Prefer Bun scripts and `@langchain/langgraph` / `@langchain/langgraph-cli`.
- Prefer the official Agent Server over a custom HTTP framework.
- Register every graph in `langgraph.json`; assistant ids are the public contract for gssc5.
- Keep input/output shapes documented and stable for gssc5 (`@langchain/langgraph-sdk` / REST threads+runs).
- Prefer gssc5 **backend → this service** (no browser CORS required for that pattern).
- Never commit secrets. Keep placeholders only in `.agents/mcp.json` and `.env.example`.
- Protocol’s `skill.md` maps to Cursor’s `SKILL.md` here (same as gssc5).

## Skills

Read `.agents/skills/<name>/SKILL.md` when relevant:

| Skill | When |
| --- | --- |
| `langgraph-service-review` | Review PRs / changes to graphs, config, tests, and gssc5 API contracts before merge |

## Agent profiles

Load when acting in that role (short loop; do not restate skill bodies):

- `.agents/agents/reviewer/agent.md` — dedicated LangGraph service reviewer

## Architecture memories

Durable stack facts (not wave status):

- `.agents/memories/langgraph-arch.md`

## Host prompt

Reusable host system prompt: `.agents/system-prompt.md`.

## How to invoke the reviewer

1. Open this repo in Cursor (or any Dot Agents–compatible host).
2. Ask the agent to act as the **reviewer** profile, or to run `langgraph-service-review`.
3. Point it at a PR, diff, or paths under `src/graphs/`, `langgraph.json`, `tests/`, or README contract sections.
4. Expect a **PASS** / **FAIL** verdict with concrete file+fix notes (see the skill).
