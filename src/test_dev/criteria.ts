/**
 * Test-development criteria for gssc-langgraph.
 *
 * Behavioral reference: gssc5 `.agents/agents/test/agent.md` and
 * `.agents/skills/test-closeout-review/SKILL.md` — one permanent test per
 * in-scope requirement, assert the requirement (not incidental SW), prefer
 * focused harness runs, PASS/FAIL closeout with proposed fixes.
 *
 * Adapted here for a Bun/TypeScript LangGraph Agent Server without StrictDoc
 * LLRs or `@relation` markers: contracts come from documented assistant
 * behavior (README + graph docs + baseline assistants).
 */
import type { TestDevCheckId } from "./types.js";

export type Criterion = {
  id: TestDevCheckId;
  title: string;
  description: string;
};

export const CRITERIA: Criterion[] = [
  {
    id: "scope",
    title: "Scope",
    description:
      "Identify in-scope graphs and their documented contracts for this change set or workspace.",
  },
  {
    id: "coverage_map",
    title: "Coverage map",
    description:
      "Exactly one permanent bun:test (or focused describe block) should lock each in-scope contract — no silent gaps.",
  },
  {
    id: "target",
    title: "Target",
    description:
      "Tests validate the documented contract (README / graph docs / baseline API), not “whatever the software currently does.”",
  },
  {
    id: "asserts",
    title: "Asserts",
    description:
      "Assert status/behavior named by the contract; avoid empty or tautological expects; body/contents only when the contract names them.",
  },
  {
    id: "timing",
    title: "Timing",
    description:
      "Prefer focused harness runs (`bun test <file>`); avoid redundant suite weight and slow integration where unit invoke suffices.",
  },
];

/**
 * gssc5 test-agent rule adapted: if the test is wrong, fix the test;
 * if software or documented contract conflict, ask before changing either.
 */
export const CONFLICT_GUIDANCE =
  "If the test is wrong, fix the test. If software and the documented contract conflict, ask the owner before changing either.";
