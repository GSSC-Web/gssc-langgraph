/**
 * In-process LangGraph checkpointer (MemorySaver) for thread-scoped short-term
 * memory. Suitable for local `bun run dev` / unit tests.
 *
 * Production durable stores (Postgres / SQLite savers) are a follow-up — swap
 * the saver passed to `compileWithMemory` / `compileGraph` when needed.
 */
import {
  MemorySaver,
  type BaseCheckpointSaver,
} from "@langchain/langgraph";
import type { RunnableConfig } from "@langchain/core/runnables";

/** Shared process-local checkpointer instance. */
export const memorySaver: BaseCheckpointSaver = new MemorySaver();

/** Build a RunnableConfig that keys checkpoints to a thread. */
export function threadConfig(
  threadId: string,
  extra?: Omit<RunnableConfig, "configurable"> & {
    configurable?: Record<string, unknown>;
  },
): RunnableConfig {
  return {
    ...extra,
    configurable: {
      ...(extra?.configurable ?? {}),
      thread_id: threadId,
    },
  };
}

export type CompileGraphOptions = {
  /**
   * When true (default for `compileWithMemory`), attach a checkpointer so
   * clients can persist state across turns via `configurable.thread_id`.
   * Set false for one-shot graphs that do not need memory.
   */
  persist?: boolean;
  /** Override the default shared MemorySaver (or pass `false` to disable). */
  checkpointer?: BaseCheckpointSaver | boolean;
  /** Optional Studio / ops display name (`compile({ name })`). */
  name?: string;
  description?: string;
};

type CompileOpts = {
  checkpointer?: BaseCheckpointSaver | boolean;
  name?: string;
  description?: string;
};

/**
 * Compile a StateGraph builder, optionally with a checkpointer.
 *
 * New conversational / LLM graphs should prefer `compileWithMemory`.
 * One-shot review/dev bots can keep `builder.compile()` or call
 * `compileGraph(builder, { persist: false, name: "…" })`.
 */
export function compileGraph<TCompiled>(
  builder: { compile: (options?: CompileOpts) => TCompiled },
  options: CompileGraphOptions = {},
): TCompiled {
  const {
    persist = false,
    checkpointer = persist ? memorySaver : undefined,
    name,
    description,
  } = options;

  return builder.compile({
    ...(checkpointer !== undefined ? { checkpointer } : {}),
    ...(name !== undefined ? { name } : {}),
    ...(description !== undefined ? { description } : {}),
  });
}

/**
 * Compile with the shared MemorySaver so thread_id-based persistence works.
 * Opt-in helper for conversational / LLM graphs that need thread memory.
 *
 * Direct `graph.invoke` / `stream` calls must pass `configurable.thread_id`
 * (see `threadConfig`). Agent Server / SDK runs use the thread created via
 * `POST /threads` / `client.threads.create()`.
 */
export function compileWithMemory<TCompiled>(
  builder: { compile: (options?: CompileOpts) => TCompiled },
  options: Omit<CompileGraphOptions, "persist"> = {},
): TCompiled {
  return compileGraph(builder, { ...options, persist: true });
}
