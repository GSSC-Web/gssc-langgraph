/**
 * Thread-scoped checkpointer helpers. Default saver is the process-shared
 * instance from env (`MemorySaver` unless `GSSC_CHECKPOINT_BACKEND=sqlite|postgres`).
 *
 * Suitable for local `bun run dev` (memory) and production durable stores.
 */
import type { BaseCheckpointSaver } from "@langchain/langgraph";
import type { RunnableConfig } from "@langchain/core/runnables";
import { sharedCheckpointer } from "./shared.js";

/** Alias for {@link sharedCheckpointer} (historical name used by callers/tests). */
export const memorySaver: BaseCheckpointSaver = sharedCheckpointer;

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
  /**
   * Override the shared checkpointer (or pass `false` to disable). Defaults to
   * the env-selected saver (`MemorySaver` / SqliteSaver / PostgresSaver).
   */
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
 * Prefer `compileWithMemory` for conversational / LLM graphs and for
 * specialists that accumulate durable notes. Pure one-shot smoke graphs
 * (e.g. `health`) can keep `builder.compile()` or call
 * `compileGraph(builder, { persist: false, name: "…" })`.
 */
export function compileGraph<TCompiled>(
  builder: { compile: (options?: CompileOpts) => TCompiled },
  options: CompileGraphOptions = {},
): TCompiled {
  const {
    persist = false,
    checkpointer = persist ? sharedCheckpointer : undefined,
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
 * Compile with the shared checkpointer so thread_id-based persistence works.
 * Used by `conversation` and specialist bots (`closeout_review`,
 * `software_dev`, `test_development`); prefer this for new conversational /
 * LLM graphs as well.
 *
 * Direct `graph.invoke` / `stream` calls must pass `configurable.thread_id`
 * (see `threadConfig`). Agent Server / SDK runs use the thread created via
 * `POST /threads` / `client.threads.create()`. Specialists append durable
 * notes (`reviewMemory` / `specialistNotes`) in finalize when the thread is
 * reused. With `GSSC_CHECKPOINT_BACKEND=sqlite|postgres`, those notes survive
 * process restarts.
 */
export function compileWithMemory<TCompiled>(
  builder: { compile: (options?: CompileOpts) => TCompiled },
  options: Omit<CompileGraphOptions, "persist"> = {},
): TCompiled {
  return compileGraph(builder, { ...options, persist: true });
}
