/**
 * Env helpers for selecting the LangGraph checkpointer backend.
 *
 * Default is in-process MemorySaver (`GSSC_CHECKPOINT_BACKEND` unset or
 * `memory`) so `bun run dev` stays zero-config. Set `sqlite` or `postgres`
 * for durable thread state (including specialist `reviewMemory` /
 * `specialistNotes`) that survives process restarts.
 */
export const CHECKPOINT_BACKEND_ENV = "GSSC_CHECKPOINT_BACKEND";
export const CHECKPOINT_SQLITE_PATH_ENV = "GSSC_CHECKPOINT_SQLITE_PATH";
export const CHECKPOINT_POSTGRES_URL_ENV = "GSSC_CHECKPOINT_POSTGRES_URL";
export const CHECKPOINT_POSTGRES_SCHEMA_ENV = "GSSC_CHECKPOINT_POSTGRES_SCHEMA";

/** Default on-disk SQLite path when backend=sqlite and no path env is set. */
export const DEFAULT_SQLITE_PATH = ".data/langgraph-checkpoints.sqlite";

export type CheckpointBackend = "memory" | "sqlite" | "postgres";

export type CheckpointConfig =
  | { backend: "memory" }
  | { backend: "sqlite"; path: string }
  | { backend: "postgres"; connectionString: string; schema: string };

function normalizeBackend(raw: string): CheckpointBackend | null {
  const v = raw.trim().toLowerCase();
  if (v === "" || v === "memory" || v === "mem" || v === "inmemory") {
    return "memory";
  }
  if (v === "sqlite" || v === "sqlite3") return "sqlite";
  if (v === "postgres" || v === "postgresql" || v === "pg") return "postgres";
  return null;
}

/**
 * Resolve checkpointer settings from env. Throws on unknown backend or
 * missing Postgres URL when `backend=postgres`.
 */
export function resolveCheckpointConfig(
  env: NodeJS.ProcessEnv = process.env,
): CheckpointConfig {
  const backend =
    normalizeBackend(env[CHECKPOINT_BACKEND_ENV] ?? "") ??
    (() => {
      throw new Error(
        `Unsupported ${CHECKPOINT_BACKEND_ENV}=${JSON.stringify(env[CHECKPOINT_BACKEND_ENV])}. ` +
          `Use memory | sqlite | postgres.`,
      );
    })();

  if (backend === "memory") {
    return { backend: "memory" };
  }

  if (backend === "sqlite") {
    const path =
      env[CHECKPOINT_SQLITE_PATH_ENV]?.trim() || DEFAULT_SQLITE_PATH;
    return { backend: "sqlite", path };
  }

  const connectionString = env[CHECKPOINT_POSTGRES_URL_ENV]?.trim();
  if (!connectionString) {
    throw new Error(
      `${CHECKPOINT_BACKEND_ENV}=postgres requires ${CHECKPOINT_POSTGRES_URL_ENV}`,
    );
  }
  const schema =
    env[CHECKPOINT_POSTGRES_SCHEMA_ENV]?.trim() || "public";
  return { backend: "postgres", connectionString, schema };
}
