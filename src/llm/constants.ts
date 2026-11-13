/**
 * Default LLM provider / model for GSSC LangGraph graphs that call a chat model.
 *
 * Prefer xAI (Grok) for this service; override with env when needed.
 * See README "LLM provider (xAI)" and LangSmith model-configuration steps.
 */

/** LangChain / LangSmith provider id for xAI. */
export const DEFAULT_LLM_PROVIDER = "xai" as const;

/**
 * Default Grok chat model id.
 *
 * xAI currently recommends `grok-4.7` for code, chat, and agentic work.
 * Override with `GSSC_XAI_MODEL` (preferred) or `XAI_MODEL`.
 */
export const DEFAULT_XAI_MODEL = "grok-4.7";

/** Env var holding the xAI API key (`ChatXAI` reads this by default). */
export const XAI_API_KEY_ENV = "XAI_API_KEY";

/** Preferred env override for the Grok model id used by this service. */
export const GSSC_XAI_MODEL_ENV = "GSSC_XAI_MODEL";

/** Alternate env override (matches common LangChain / gateway naming). */
export const XAI_MODEL_ENV = "XAI_MODEL";
