import { ChatXAI } from "@langchain/xai";
import type { ChatXAIInput } from "@langchain/xai";
import { resolveLlmConfig } from "./config.js";
import { XAI_API_KEY_ENV } from "./constants.js";

export type CreateChatModelOptions = Omit<ChatXAIInput, "model"> & {
  /** Override default / env model id (e.g. `grok-4.7`). */
  model?: string;
};

/**
 * Create the default chat model for domain graphs: xAI `ChatXAI` (Grok).
 *
 * Requires `XAI_API_KEY` in the environment (or `apiKey` in options).
 * Model id defaults to `grok-4.7`, overridable via `GSSC_XAI_MODEL` / `XAI_MODEL`
 * or the `model` option.
 *
 * The smoke assistant (`health`) stays model-free and should not call this
 * helper.
 */
export function createChatModel(options: CreateChatModelOptions = {}): ChatXAI {
  const { model: modelOverride, apiKey, ...rest } = options;
  const resolved = resolveLlmConfig({ model: modelOverride });

  const key = apiKey ?? process.env[XAI_API_KEY_ENV];
  if (!key || !String(key).trim()) {
    throw new Error(
      `Missing ${XAI_API_KEY_ENV}. Set it in .env (see .env.example) before calling createChatModel().`,
    );
  }

  return new ChatXAI({
    ...rest,
    apiKey: String(key).trim(),
    model: resolved.model,
  });
}
