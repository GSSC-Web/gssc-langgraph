/**
 * Software development / closeout criteria for gssc-langgraph.
 *
 * Behavioral reference: gssc5 `.agents/agents/software/agent.md` and
 * `.agents/skills/software-closeout-review/SKILL.md` (scope → implement →
 * third-party-first → focused checks → PASS/FAIL, no silent requirement
 * rewrites). Adapted for this Bun/TypeScript LangGraph Agent Server — not
 * StrictDoc `@relation` audits, and not a Dot Agents `.agents/` scaffold.
 */
import type { SoftwareCheckId } from "./types.js";

export type Criterion = {
  id: SoftwareCheckId;
  title: string;
  description: string;
};

export const CRITERIA: Criterion[] = [
  {
    id: "scope",
    title: "Scope",
    description:
      "A clear development goal (or reviewable change set) is present; work stays on LangGraph service concerns.",
  },
  {
    id: "trace",
    title: "Trace / wiring",
    description:
      "New or changed assistants are registered in langgraph.json and discoverable (export `graph`, documented assistant id).",
  },
  {
    id: "match",
    title: "Match intent",
    description:
      "Software realizes the stated goal / LangGraph assistant contract (Annotation + StateGraph + compile), not a hollow stub.",
  },
  {
    id: "quality",
    title: "Quality",
    description:
      "Logic and error paths are sound; fail-fast; no oversized god modules; smoke assistants stay model-free when intended.",
  },
  {
    id: "third_party",
    title: "Third parties",
    description:
      "Prefer LangGraph.js, langgraph-cli Agent Server, Bun/mise, Zod — flag reinvented HTTP servers or Python stack drift.",
  },
  {
    id: "discipline",
    title: "Dev discipline",
    description:
      "Do not silently rewrite contracts or delete baseline assistants; do not “fix” software by deleting covering tests in the same change.",
  },
];

/** Assistant ids treated as the public gssc5 contract baseline (do not drop). */
export const BASELINE_ASSISTANT_IDS = ["health", "sample_agent"] as const;

/** Prefer these adopted libraries over custom reinvention. */
export const PREFERRED_STACK = [
  "@langchain/langgraph",
  "@langchain/langgraph-cli",
  "@langchain/core",
  "bun",
  "zod",
] as const;

/** Paths / imports that imply reinventing the Agent Server. */
export const REINVENTED_SERVER_HINTS = [
  /from\s+["']elysia["']/,
  /from\s+["']express["']/,
  /from\s+["']hono["']/,
  /from\s+["']fastify["']/,
  /from\s+["']koa["']/,
  /createServer\s*\(/,
];

/** Soft size guard for graph modules (lines). */
export const GRAPH_GOD_FILE_LINES = 400;
