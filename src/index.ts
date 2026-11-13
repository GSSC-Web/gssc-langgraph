/**
 * Package entry — domain graphs live under `./graphs/*` and are registered
 * in `langgraph.json`. Add new workflows as sibling folders and wire them
 * into `langgraph.json`.
 *
 * LLM defaults (xAI / Grok) live under `./llm` — use `createChatModel()` in
 * domain graphs; keep smoke assistants model-free.
 *
 * Thread persistence helpers live under `./checkpoint` — conversational /
 * LLM graphs should `compileWithMemory` and pass `configurable.thread_id`.
 */
export { graph as healthGraph } from "./graphs/health/graph.js";
export {
  createChatModel,
  resolveLlmConfig,
  DEFAULT_LLM_PROVIDER,
  DEFAULT_XAI_MODEL,
} from "./llm/index.js";
export {
  memorySaver,
  threadConfig,
  compileGraph,
  compileWithMemory,
} from "./checkpoint/index.js";
