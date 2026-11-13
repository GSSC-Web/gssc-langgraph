/**
 * Deterministic implementation plan for the software_dev workflow.
 *
 * Mirrors the gssc5 software agent operation loop (scope → implement →
 * third-party-first → focused tests → closeout) adapted for this service.
 */
import type { ChangeSet, PlanStep } from "./types.js";

const GRAPH_FILE_RE = /^src\/graphs\/([^/]+)\/graph\.tsx?$/;

function changedGraphIds(cs: ChangeSet | null): string[] {
  if (!cs) return [];
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "unchanged" && f.status !== "deleted") {
      ids.add(m[1]!);
    }
  }
  return [...ids].sort();
}

function goalMentions(
  goal: string,
  ...needles: string[]
): boolean {
  const g = goal.toLowerCase();
  return needles.some((n) => g.includes(n));
}

/**
 * Build ordered plan steps from a goal string and optional change set.
 * Model-free: keyword + changeset heuristics only.
 */
export function buildPlan(goal: string, changeSet: ChangeSet | null): PlanStep[] {
  const steps: PlanStep[] = [];
  const trimmed = goal.trim();
  const graphs = changedGraphIds(changeSet);
  const gLower = trimmed.toLowerCase();
  const addingGraph =
    goalMentions(
      trimmed,
      "add graph",
      "new graph",
      "domain graph",
      "new assistant",
      "add assistant",
    ) ||
    (/\b(add|new|create|scaffold)\b/.test(gLower) &&
      /\b(graph|assistant|workflow)\b/.test(gLower)) ||
    graphs.some((id) =>
      changeSet?.files.some(
        (f) =>
          f.path === `src/graphs/${id}/graph.ts` && f.status === "added",
      ),
    );
  const fixing =
    goalMentions(trimmed, "fix", "bug", "repair", "regress");

  steps.push({
    id: "scope",
    title: "Scope the work",
    detail: trimmed
      ? `Confirm in-scope goal: “${trimmed.slice(0, 200)}${trimmed.length > 200 ? "…" : ""}”. Do not rewrite requirements/contracts to match buggy code.`
      : "No free-text goal — treat the change set as the software closeout scope (same spirit as gssc5 software-closeout-review).",
  });

  if (addingGraph) {
    steps.push({
      id: "scaffold_graph",
      title: "Scaffold the LangGraph assistant",
      detail:
        "Add `src/graphs/<id>/graph.ts` with Annotation.Root + StateGraph, `export const graph = builder.compile()`, and `graph.name`. Keep smoke assistants model-free.",
    });
    steps.push({
      id: "register",
      title: "Register the assistant",
      detail:
        'Wire `"<id>": "./src/graphs/<id>/graph.ts:graph"` in langgraph.json and document the assistant id + input shape in README.',
    });
  } else if (graphs.length > 0) {
    steps.push({
      id: "implement_graphs",
      title: "Implement graph changes",
      detail: `Touch only the in-scope assistants (${graphs.join(", ")}); preserve baseline gssc5 contract ids (health, sample_agent).`,
    });
  } else if (fixing) {
    steps.push({
      id: "reproduce_fix",
      title: "Reproduce then fix",
      detail:
        "Add or run a focused bun:test that fails for the bug, then fix software to satisfy the intended contract — do not weaken asserts to match broken SW.",
    });
  } else {
    steps.push({
      id: "implement",
      title: "Implement behavior",
      detail:
        "Change the smallest set of Bun/TypeScript modules under src/. Prefer @langchain/langgraph + langgraph-cli over a custom HTTP server.",
    });
  }

  steps.push({
    id: "third_party",
    title: "Stay third-party-first",
    detail:
      "Use LangGraph.js, @langchain/langgraph-cli Agent Server, Bun/mise, and Zod. Flag reinvented Express/Hono/Elysia servers or Python LangGraph drift.",
  });

  steps.push({
    id: "tests",
    title: "Run focused tests",
    detail:
      "Add/update bun:test coverage for touched graphs. Prefer `bun test` / `mise run test` on the focused files; do not fix failing tests by watering down asserts when software is wrong.",
  });

  steps.push({
    id: "closeout",
    title: "Software closeout",
    detail:
      "Run `bun run software` (this workflow) and `bun run review` before merge. Peer with the separate test_dev bot when test closeout is required — do not own test-bot files.",
  });

  return steps;
}
