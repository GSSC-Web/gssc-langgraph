/**
 * Closeout review criteria for gssc-langgraph.
 *
 * Behavioral reference: gssc5 peer closeout skills —
 * `.agents/skills/requirements-closeout-review/SKILL.md`,
 * `.agents/skills/software-closeout-review/SKILL.md`,
 * `.agents/skills/test-closeout-review/SKILL.md`
 * (scope → peer lanes → PASS/FAIL with proposed fix; no silent contract
 * rewrites). Adapted for this Bun/TypeScript LangGraph Agent Server — not
 * StrictDoc `@relation` audits, and not a Dot Agents `.agents/` scaffold.
 *
 * Distinct from the removed `service_review` assistant and from the
 * development bots (`software_dev`, `test_development`).
 */
import type { CloseoutCheckId } from "./types.js";

export type Criterion = {
  id: CloseoutCheckId;
  title: string;
  /** Which gssc5 closeout skill this lane mirrors. */
  peer: "requirements" | "software" | "test" | "ops";
  description: string;
};

export const CRITERIA: Criterion[] = [
  {
    id: "scope",
    title: "Scope",
    peer: "requirements",
    description:
      "Identify an in-scope change set (or explicit workspace scan) for closeout — same spirit as gssc5 Scope across the three peer skills.",
  },
  {
    id: "contracts",
    title: "Contracts",
    peer: "requirements",
    description:
      "Documented / baseline assistant contracts stay intact (requirements-closeout analogue): no silent baseline drops or README contract deletion.",
  },
  {
    id: "software_trace",
    title: "Software trace",
    peer: "software",
    description:
      "Each shipped graph is registered in langgraph.json (software-closeout Trace analogue without StrictDoc Implementation @relation).",
  },
  {
    id: "software_match",
    title: "Software match",
    peer: "software",
    description:
      "Software realizes the LangGraph assistant contract (Annotation + StateGraph + export graph), not a hollow stub.",
  },
  {
    id: "software_quality",
    title: "Software quality",
    peer: "software",
    description:
      "Logic and error paths sound; fail-fast; no oversized god modules; smoke assistants stay model-free when intended.",
  },
  {
    id: "third_party",
    title: "Third parties",
    peer: "software",
    description:
      "Prefer LangGraph.js, langgraph-cli Agent Server, Bun/mise, Zod — flag reinvented HTTP servers or Python stack drift.",
  },
  {
    id: "test_coverage",
    title: "Test coverage",
    peer: "test",
    description:
      "Changed / registered graphs have permanent bun:test coverage (test-closeout Trace analogue without Test @relation).",
  },
  {
    id: "test_target",
    title: "Test target",
    peer: "test",
    description:
      "Tests assert documented contracts / invoke smoke — not empty expects; do not “fix” by deleting covering tests with SW edits.",
  },
  {
    id: "secrets",
    title: "Secrets / ops",
    peer: "ops",
    description:
      "Never commit secrets; .env.example stays placeholder-only (gssc5 agents.md core rule).",
  },
];

/**
 * Assistant ids treated as the public gssc5 contract baseline (do not drop).
 * Note: `sample_agent` is being removed in a parallel PR — do not require it.
 */
export const BASELINE_ASSISTANT_IDS = ["health"] as const;

/** Smoke / tooling assistants that must remain model-free when present. */
export const MODEL_FREE_ASSISTANT_IDS = [
  "health",
  "closeout_review",
  "software_dev",
  "test_development",
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

/** Rough secret patterns in diffs / files. */
export const SECRET_PATTERNS: Array<{ name: string; re: RegExp }> = [
  { name: "openai-key", re: /sk-[A-Za-z0-9]{20,}/ },
  { name: "anthropic-key", re: /sk-ant-[A-Za-z0-9_-]{20,}/ },
  { name: "xai-key", re: /xai-[A-Za-z0-9_-]{20,}/ },
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
