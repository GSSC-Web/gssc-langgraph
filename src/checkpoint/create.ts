/**
 * Build a LangGraph checkpointer from env (MemorySaver / SqliteSaver /
 * PostgresSaver).
 *
 * Memory is the default. SQLite and Postgres use the official
 * `@langchain/langgraph-checkpoint-*` packages so thread state — including
 * specialist `reviewMemory` / `specialistNotes` — survives Agent Server
 * restarts when the same `thread_id` is reused.
 */
import {
  MemorySaver,
  type BaseCheckpointSaver,
} from "@langchain/langgraph";
import {
  resolveCheckpointConfig,
  type CheckpointConfig,
} from "./env.js";

/**
 * Create (and for Postgres, `setup()`) a checkpointer for the given config.
 * Prefer {@link createCheckpointerFromEnv} at process start.
 */
export async function createCheckpointer(
  config: CheckpointConfig,
): Promise<BaseCheckpointSaver> {
  if (config.backend === "memory") {
    return new MemorySaver();
  }

  if (config.backend === "sqlite") {
    try {
      const { SqliteSaver } = await import(
        "@langchain/langgraph-checkpoint-sqlite"
      );
      return SqliteSaver.fromConnString(config.path);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes("better-sqlite3") || message.includes("Bun")) {
        throw new Error(
          `GSSC_CHECKPOINT_BACKEND=sqlite requires Node (better-sqlite3). ` +
            `The LangGraph Agent Server uses Node — set this in .env for ` +
            `\`bun run dev\` / production images. Under the Bun runtime use ` +
            `memory (default) or postgres instead. Underlying error: ${message}`,
          { cause: err },
        );
      }
      throw err;
    }
  }

  const { PostgresSaver } = await import(
    "@langchain/langgraph-checkpoint-postgres"
  );
  const saver = PostgresSaver.fromConnString(config.connectionString, {
    schema: config.schema,
  });
  await saver.setup();
  return saver;
}

/** Resolve env → create the process checkpointer (calls Postgres `setup()`). */
export async function createCheckpointerFromEnv(
  env: NodeJS.ProcessEnv = process.env,
): Promise<BaseCheckpointSaver> {
  return createCheckpointer(resolveCheckpointConfig(env));
}
