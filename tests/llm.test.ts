import { afterEach, describe, expect, test } from "bun:test";
import {
  createChatModel,
  DEFAULT_LLM_PROVIDER,
  DEFAULT_XAI_MODEL,
  resolveLlmConfig,
} from "../src/llm/index.js";

const TRACKED = ["XAI_API_KEY", "GSSC_XAI_MODEL", "XAI_MODEL"] as const;
const saved: Partial<Record<(typeof TRACKED)[number], string | undefined>> = {};

function stashEnv() {
  for (const key of TRACKED) {
    saved[key] = process.env[key];
  }
}

function restoreEnv() {
  for (const key of TRACKED) {
    const value = saved[key];
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
}

afterEach(() => {
  restoreEnv();
});

describe("resolveLlmConfig", () => {
  test("defaults to xai / grok-4.7 without keys", () => {
    stashEnv();
    delete process.env.XAI_API_KEY;
    delete process.env.GSSC_XAI_MODEL;
    delete process.env.XAI_MODEL;

    const cfg = resolveLlmConfig();
    expect(cfg.provider).toBe(DEFAULT_LLM_PROVIDER);
    expect(cfg.provider).toBe("xai");
    expect(cfg.model).toBe(DEFAULT_XAI_MODEL);
    expect(cfg.model).toBe("grok-4.7");
    expect(cfg.hasApiKey).toBe(false);
  });

  test("GSSC_XAI_MODEL wins over XAI_MODEL", () => {
    stashEnv();
    process.env.XAI_MODEL = "grok-4.3";
    process.env.GSSC_XAI_MODEL = "grok-4.6";

    expect(resolveLlmConfig().model).toBe("grok-4.6");
  });

  test("explicit override wins over env", () => {
    stashEnv();
    process.env.GSSC_XAI_MODEL = "grok-4.6";
    expect(resolveLlmConfig({ model: "grok-4.5" }).model).toBe("grok-4.5");
  });

  test("hasApiKey reflects XAI_API_KEY", () => {
    stashEnv();
    // Avoid `xai-…` shaped literals so secrets review does not false-positive.
    process.env.XAI_API_KEY = "test-key-not-for-production";
    expect(resolveLlmConfig().hasApiKey).toBe(true);
  });
});

describe("createChatModel", () => {
  test("throws a clear error when XAI_API_KEY is missing", () => {
    stashEnv();
    delete process.env.XAI_API_KEY;
    expect(() => createChatModel()).toThrow(/XAI_API_KEY/);
  });

  test("constructs ChatXAI with resolved model when key is set", () => {
    stashEnv();
    process.env.XAI_API_KEY = "test-key-not-for-production";
    process.env.GSSC_XAI_MODEL = "grok-4.7";

    const model = createChatModel({ temperature: 0 });
    expect(model).toBeDefined();
    // ChatXAI exposes the selected model name for LangSmith / debugging.
    expect((model as { model?: string }).model ?? (model as { modelName?: string }).modelName).toBe(
      "grok-4.7",
    );
  });
});
