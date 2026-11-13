/**
 * Shared LLM defaults for GSSC LangGraph domain workflows.
 *
 * Provider of choice: xAI (Grok) via `@langchain/xai` `ChatXAI`.
 */
export {
  DEFAULT_LLM_PROVIDER,
  DEFAULT_XAI_MODEL,
  GSSC_XAI_MODEL_ENV,
  XAI_API_KEY_ENV,
  XAI_MODEL_ENV,
} from "./constants.js";
export { resolveLlmConfig, type LlmProvider, type ResolvedLlmConfig } from "./config.js";
export { createChatModel, type CreateChatModelOptions } from "./chat.js";
