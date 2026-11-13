/**
 * Review criteria for gssc-langgraph.
 *
 * Inspired by gssc5 closeout-review skills (PASS/FAIL, scoped checks, no silent
 * contract rewrites) but adapted for a Bun/TypeScript LangGraph Agent Server
 * that gssc5 consumes over HTTP/SDK — not StrictDoc/@relation audits.
 */
import type { ReviewCheckId } from "./types.js";

export type Criterion = {
  id: ReviewCheckId;
  title: string;
  description: string;
};

export const CRITERIA: Criterion[] = [
  {
    id: "registry",
    title: "Graph registry",
    description:
      "Every shipped graph under src/graphs/ is registered in langgraph.json with a stable assistant_id; no orphan registry entries.",
  },
  {
    id: "graph_quality",
    title: "Graph quality",
    description:
      "Graphs use Annotation + StateGraph, export compiled `graph`, set graph.name, and keep smoke assistants model-free when intended.",
  },
  {
    id: "stack",
    title: "Stack",
    description:
      "TypeScript + Bun + @langchain/langgraph / langgraph-cli — not Python LangGraph or a custom HTTP server replacing the Agent Server.",
  },
  {
    id: "gssc5_contract",
    title: "gssc5 contract",
    description:
      "Assistant ids and documented input shapes stay compatible with gssc5 SDK/REST usage; flag breaking renames or auth/CORS flips.",
  },
  {
    id: "tests",
    title: "Tests",
    description:
      "Changed or added graphs have covering bun:test coverage asserting documented behavior.",
  },
  {
    id: "secrets",
    title: "Secrets / ops",
    description:
      "No committed secrets; .env.example stays placeholder-only.",
  },
];

/** Assistant ids treated as the public gssc5 contract baseline. */
export const BASELINE_ASSISTANT_IDS = ["health", "sample_agent"] as const;

/** Paths that imply a custom HTTP server replacing langgraph-cli (flag). */
export const CUSTOM_SERVER_HINTS = [
  /from\s+["']elysia["']/,
  /from\s+["']express["']/,
  /from\s+["']hono["']/,
  /from\s+["']fastify["']/,
  /createServer\s*\(/,
];

/** Rough secret patterns in diffs / files. */
export const SECRET_PATTERNS: Array<{ name: string; re: RegExp }> = [
  { name: "openai-key", re: /sk-[A-Za-z0-9]{20,}/ },
  { name: "anthropic-key", re: /sk-ant-[A-Za-z0-9_-]{20,}/ },
  { name: "aws-key", re: /AKIA[0-9A-Z]{16}/ },
  {
    name: "private-key-block",
    re: /-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/,
  },
  {
    name: "bearer-literal",
    re: /Authorization["']?\s*:\s*["']Bearer\s+[A-Za-z0-9._-]{20,}/,
  },
];
