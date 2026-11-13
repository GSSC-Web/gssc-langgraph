import {
  DEFAULT_LLM_PROVIDER,
  DEFAULT_XAI_MODEL,
  GSSC_XAI_MODEL_ENV,
  XAI_API_KEY_ENV,
  XAI_MODEL_ENV,
} from "./constants.js";

export type LlmProvider = typeof DEFAULT_LLM_PROVIDER;

export type ResolvedLlmConfig = {
  provider: LlmProvider;
  /** Chat model id passed to `ChatXAI` (e.g. `grok-4.7`). */
  model: string;
  /** True when `XAI_API_KEY` is present (non-empty). */
  hasApiKey: boolean;
};

function env(name: string): string | undefined {
  const value = process.env[name];
  if (value == null) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/**
 * Resolve the service-wide LLM defaults from the environment.
 *
 * Does not construct a client or require a key — safe for tests and smoke graphs.
 */
export function resolveLlmConfig(
  overrides?: Partial<{ model: string }>,
): ResolvedLlmConfig {
  const model =
    overrides?.model?.trim() ||
    env(GSSC_XAI_MODEL_ENV) ||
    env(XAI_MODEL_ENV) ||
    DEFAULT_XAI_MODEL;

  return {
    provider: DEFAULT_LLM_PROVIDER,
    model,
    hasApiKey: Boolean(env(XAI_API_KEY_ENV)),
  };
}
