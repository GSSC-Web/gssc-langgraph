/**
 * Process-wide default checkpointer selected by `GSSC_CHECKPOINT_BACKEND`
 * (default: MemorySaver). Initialized once at module load via top-level await
 * so Agent Server graph compiles attach the durable saver when configured.
 */
import type { BaseCheckpointSaver } from "@langchain/langgraph";
import { createCheckpointerFromEnv } from "./create.js";
import { resolveCheckpointConfig } from "./env.js";

/** Resolved backend for the shared instance (handy for tests / diagnostics). */
export const sharedCheckpointConfig = resolveCheckpointConfig();

/**
 * Shared checkpointer used by `compileWithMemory` / `compileGraph({ persist })`
 * unless an explicit `checkpointer` option is passed.
 */
export const sharedCheckpointer: BaseCheckpointSaver =
  await createCheckpointerFromEnv();
