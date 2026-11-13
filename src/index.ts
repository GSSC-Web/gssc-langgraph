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
 *
 * gssc5 Dot Agents skills/memories loaders live under `./gssc5`.
 */
export { graph as healthGraph } from "./graphs/health/graph.js";
export { graph as conversationGraph } from "./graphs/conversation/graph.js";
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
export {
  createLoadGssc5ContextNode,
  loadGssc5Context,
  loadGssc5ContextForRole,
  resolveGssc5Root,
  ensureGssc5Checkout,
  formatGssc5Context,
} from "./gssc5/index.js";
