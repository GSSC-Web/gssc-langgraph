/**
 * Node-only SQLite durability smoke (better-sqlite3 is unsupported in Bun).
 * Agent Server runs on Node (`langgraph.json` node_version), so this matches prod.
 *
 * Usage: node scripts/verify-sqlite-checkpoint.mjs
 */
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { Annotation, StateGraph } from "@langchain/langgraph";
import { SqliteSaver } from "@langchain/langgraph-checkpoint-sqlite";
import { randomUUID } from "node:crypto";

const dir = mkdtempSync(join(tmpdir(), "gssc-cp-"));
const dbPath = join(dir, "checkpoints.sqlite");

try {
  const State = Annotation.Root({
    notes: Annotation({
      reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
      default: () => [],
    }),
  });

  const makeGraph = () => {
    const checkpointer = SqliteSaver.fromConnString(dbPath);
    const builder = new StateGraph(State)
      .addNode("append", async (state) => ({
        notes: [`n${(state.notes?.length ?? 0) + 1}`],
      }))
      .addEdge("__start__", "append");
    return builder.compile({ checkpointer, name: "sqlite-restart" });
  };

  const config = { configurable: { thread_id: `sqlite-restart-${randomUUID()}` } };

  const firstGraph = makeGraph();
  const first = await firstGraph.invoke({}, config);
  if (JSON.stringify(first.notes) !== JSON.stringify(["n1"])) {
    throw new Error(`expected ["n1"], got ${JSON.stringify(first.notes)}`);
  }

  // New saver instance + same DB file + thread_id ≈ process restart.
  const secondGraph = makeGraph();
  const second = await secondGraph.invoke({}, config);
  if (JSON.stringify(second.notes) !== JSON.stringify(["n1", "n2"])) {
    throw new Error(
      `expected ["n1","n2"] after restart, got ${JSON.stringify(second.notes)}`,
    );
  }

  console.log("ok: sqlite checkpointer preserved notes across saver restart");
} finally {
  rmSync(dir, { recursive: true, force: true });
}
