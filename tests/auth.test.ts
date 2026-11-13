import { describe, expect, test } from "bun:test";
import { HTTPException } from "@langchain/langgraph-sdk/auth";
import {
  API_KEY_ENV,
  AUTH_BYPASS_ENV,
  apiKeyMatches,
  authenticateRequest,
  configuredApiKeys,
  extractApiKey,
  isAuthBypassEnabled,
} from "../src/auth/index.js";

function req(
  path: string,
  headers?: Record<string, string>,
): Request {
  return new Request(`http://127.0.0.1:2024${path}`, { headers });
}

describe("configuredApiKeys", () => {
  test("returns empty when unset", () => {
    expect(configuredApiKeys({})).toEqual([]);
    expect(configuredApiKeys({ [API_KEY_ENV]: "" })).toEqual([]);
    expect(configuredApiKeys({ [API_KEY_ENV]: "  " })).toEqual([]);
  });

  test("parses single and comma-separated keys", () => {
    expect(configuredApiKeys({ [API_KEY_ENV]: "solo-key" })).toEqual([
      "solo-key",
    ]);
    expect(
      configuredApiKeys({ [API_KEY_ENV]: " alpha , beta,gamma " }),
    ).toEqual(["alpha", "beta", "gamma"]);
  });
});

describe("isAuthBypassEnabled", () => {
  test("bypasses when no key is configured", () => {
    expect(isAuthBypassEnabled({})).toBe(true);
  });

  test("does not bypass when a key is set", () => {
    expect(isAuthBypassEnabled({ [API_KEY_ENV]: "secret" })).toBe(false);
  });

  test("explicit bypass wins even when a key is set", () => {
    expect(
      isAuthBypassEnabled({
        [API_KEY_ENV]: "secret",
        [AUTH_BYPASS_ENV]: "true",
      }),
    ).toBe(true);
  });
});

describe("extractApiKey", () => {
  test("reads Bearer token", () => {
    expect(
      extractApiKey(req("/runs/stream", { Authorization: "Bearer tok-1" })),
    ).toBe("tok-1");
  });

  test("reads x-api-key", () => {
    expect(extractApiKey(req("/ok", { "x-api-key": "tok-2" }))).toBe("tok-2");
  });

  test("returns null when missing", () => {
    expect(extractApiKey(req("/runs/stream"))).toBeNull();
  });
});

describe("apiKeyMatches", () => {
  test("matches configured key", () => {
    expect(apiKeyMatches("abc", ["abc"])).toBe(true);
    expect(apiKeyMatches("abc", ["zzz", "abc"])).toBe(true);
    expect(apiKeyMatches("nope", ["abc"])).toBe(false);
  });
});

describe("authenticateRequest", () => {
  test("local bypass allows unauthenticated API calls when key unset", () => {
    const user = authenticateRequest(req("/runs/stream"), {});
    expect(user.identity).toBe("local-bypass");
    expect(user.permissions).toEqual([]);
  });

  test("rejects unauthenticated requests when key is configured", () => {
    const env = { [API_KEY_ENV]: "test-secret-key" };
    expect(() => authenticateRequest(req("/runs/stream"), env)).toThrow(
      HTTPException,
    );
    try {
      authenticateRequest(req("/assistants"), env);
      throw new Error("expected HTTPException");
    } catch (err) {
      expect(err).toBeInstanceOf(HTTPException);
      expect((err as HTTPException).status).toBe(401);
    }
  });

  test("rejects wrong Bearer token", () => {
    const env = { [API_KEY_ENV]: "test-secret-key" };
    try {
      authenticateRequest(
        req("/runs/stream", { Authorization: "Bearer wrong" }),
        env,
      );
      throw new Error("expected HTTPException");
    } catch (err) {
      expect(err).toBeInstanceOf(HTTPException);
      expect((err as HTTPException).status).toBe(401);
    }
  });

  test("accepts matching Bearer token", () => {
    const env = { [API_KEY_ENV]: "test-secret-key" };
    const user = authenticateRequest(
      req("/runs/stream", { Authorization: "Bearer test-secret-key" }),
      env,
    );
    expect(user.identity).toBe("api-key");
  });

  test("accepts matching x-api-key", () => {
    const env = { [API_KEY_ENV]: "test-secret-key" };
    const user = authenticateRequest(
      req("/threads", { "x-api-key": "test-secret-key" }),
      env,
    );
    expect(user.identity).toBe("api-key");
  });

  test("GET /ok is allowed without credentials when auth is on", () => {
    const env = { [API_KEY_ENV]: "test-secret-key" };
    const user = authenticateRequest(req("/ok"), env);
    expect(user.identity).toBe("healthcheck");
  });

  test("explicit AUTH_BYPASS allows unauthenticated calls with key set", () => {
    const env = {
      [API_KEY_ENV]: "test-secret-key",
      [AUTH_BYPASS_ENV]: "1",
    };
    const user = authenticateRequest(req("/runs/stream"), env);
    expect(user.identity).toBe("local-bypass");
  });
});
