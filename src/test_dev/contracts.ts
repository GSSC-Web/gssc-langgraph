/**
 * Documented contracts for gssc-langgraph assistants.
 *
 * These stand in for StrictDoc LLRs in gssc5: each entry is a permanent
 * behavior a bun:test should lock. Keep in sync with README “Assumed API
 * contract” / registered graph docs — do not invent behavior from code alone.
 */
import type { ChangeSet, Contract } from "./types.js";

/** Baseline public contracts gssc5 / local smoke rely on. */
export const BASELINE_CONTRACTS: Contract[] = [
  {
    id: "health.status_ok",
    graphId: "health",
    title: "Health returns ok",
    requirement:
      "The health assistant SHALL return status \"ok\" and identify service \"gssc-langgraph\".",
    assertHints: ["status", "ok", "gssc-langgraph"],
    source: "baseline",
  },
  {
    id: "health.checked_at",
    graphId: "health",
    title: "Health timestamps check",
    requirement:
      "The health assistant SHALL include a non-empty checkedAt timestamp.",
    assertHints: ["checkedAt"],
    source: "baseline",
  },
];

const GRAPH_FILE_RE = /^src\/graphs\/([^/]+)\/graph\.tsx?$/;

/** Graphs that are tooling workflows — still need tests, but not gssc5 HTTP baseline. */
export const TOOLING_GRAPH_IDS = new Set([
  "test_development",
  "software_dev",
]);

function textOf(
  cs: ChangeSet,
  path: string,
): string {
  return cs.files.find((f) => f.path === path)?.content ?? "";
}

/**
 * Infer a minimal “compiled + named + invokeable” contract for any graph that
 * lacks a hand-authored baseline entry. Inference is structural only — it does
 * not invent domain behavior from implementation details.
 */
export function inferStructuralContracts(
  cs: ChangeSet,
  graphIds: string[],
): Contract[] {
  const out: Contract[] = [];
  for (const id of graphIds) {
    if (BASELINE_CONTRACTS.some((c) => c.graphId === id)) continue;
    const path = `src/graphs/${id}/graph.ts`;
    const body = textOf(cs, path) || textOf(cs, `src/graphs/${id}/graph.tsx`);
    if (!body) continue;

    out.push({
      id: `${id}.compiled_export`,
      graphId: id,
      title: `${id} exports compiled graph`,
      requirement: `Graph "${id}" SHALL export a compiled \`graph\` with a stable graph.name.`,
      assertHints: ["graph", "name", id.replace(/_/g, " ")],
      source: "inferred",
    });

    // Prefer invoke smoke when the graph looks model-free / locally runnable.
    const usesChatModel =
      /ChatOpenAI|ChatAnthropic|initChatModel|from\s+["']@langchain\/openai["']|from\s+["']@langchain\/anthropic["']/.test(
        body,
      );
    if (!usesChatModel) {
      out.push({
        id: `${id}.invoke_smoke`,
        graphId: id,
        title: `${id} invoke smoke`,
        requirement: `Graph "${id}" SHALL be invokable in bun:test without external API keys (model-free smoke).`,
        assertHints: ["invoke"],
        source: "inferred",
      });
    }
  }
  return out;
}

export function graphIdsFromChangeSet(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "deleted") ids.add(m[1]!);
  }
  // Registry may list graphs even when only tests/langgraph.json changed.
  const lg = textOf(cs, "langgraph.json");
  if (lg) {
    try {
      const parsed = JSON.parse(lg) as { graphs?: Record<string, string> };
      for (const id of Object.keys(parsed.graphs ?? {})) ids.add(id);
    } catch {
      // ignore
    }
  }
  return [...ids].sort();
}

/** Changed (non-unchanged) graph ids — preferred scope for diff reviews. */
export function changedGraphIds(cs: ChangeSet): string[] {
  const ids = new Set<string>();
  for (const f of cs.files) {
    const m = f.path.match(GRAPH_FILE_RE);
    if (m && f.status !== "unchanged" && f.status !== "deleted") {
      ids.add(m[1]!);
    }
  }
  return [...ids].sort();
}

export function resolveContracts(
  cs: ChangeSet,
  scopeGraphIds: string[],
): Contract[] {
  const baseline = BASELINE_CONTRACTS.filter((c) =>
    scopeGraphIds.includes(c.graphId),
  );
  const inferred = inferStructuralContracts(cs, scopeGraphIds);
  return [...baseline, ...inferred];
}
