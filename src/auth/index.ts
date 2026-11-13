/**
 * Agent Server API-key / Bearer auth for the LangGraph CLI server.
 *
 * Wired via `langgraph.json` → `auth.path` = `./src/auth/index.ts:auth`.
 *
 * Behaviour:
 * - If `GSSC_LANGGRAPH_API_KEY` is unset/empty (or `GSSC_LANGGRAPH_AUTH_BYPASS`
 *   is truthy), requests are allowed (local/dev bypass).
 * - Otherwise require `Authorization: Bearer <key>` (or `x-api-key`) matching
 *   the configured key (comma-separated keys supported for rotation).
 * - `GET /ok` stays reachable without credentials for process probes.
 *
 * Cloudflare Access (edge SSO / service tokens) is separate: it may sit in
 * front of a deployment but does not replace this app-level API key.
 */
import { timingSafeEqual } from "node:crypto";
import { Auth, HTTPException } from "@langchain/langgraph-sdk/auth";

export const API_KEY_ENV = "GSSC_LANGGRAPH_API_KEY";
export const AUTH_BYPASS_ENV = "GSSC_LANGGRAPH_AUTH_BYPASS";

const UNAUTH_HEADERS = { "WWW-Authenticate": "Bearer" } as const;

function truthyEnv(value: string | undefined): boolean {
  if (!value) return false;
  const v = value.trim().toLowerCase();
  return v === "1" || v === "true" || v === "yes" || v === "on";
}

/** Configured API keys from env (empty → local bypass when bypass not forced). */
export function configuredApiKeys(
  env: NodeJS.ProcessEnv = process.env,
): string[] {
  const raw = env[API_KEY_ENV]?.trim();
  if (!raw) return [];
  return raw
    .split(",")
    .map((part) => part.trim())
    .filter((part) => part.length > 0);
}

/** True when auth should allow requests without a matching API key. */
export function isAuthBypassEnabled(
  env: NodeJS.ProcessEnv = process.env,
): boolean {
  if (truthyEnv(env[AUTH_BYPASS_ENV])) return true;
  return configuredApiKeys(env).length === 0;
}

export function extractApiKey(request: Request): string | null {
  const authorization = request.headers.get("authorization");
  if (authorization) {
    const match = /^Bearer\s+(\S+)$/i.exec(authorization.trim());
    if (match?.[1]) return match[1];
  }
  const xApiKey = request.headers.get("x-api-key")?.trim();
  return xApiKey && xApiKey.length > 0 ? xApiKey : null;
}

function safeEqualString(provided: string, expected: string): boolean {
  const a = Buffer.from(provided, "utf8");
  const b = Buffer.from(expected, "utf8");
  if (a.length !== b.length) return false;
  return timingSafeEqual(a, b);
}

export function apiKeyMatches(
  provided: string,
  keys: readonly string[],
): boolean {
  return keys.some((key) => safeEqualString(provided, key));
}

function requestPathname(request: Request): string | null {
  try {
    return new URL(request.url).pathname;
  } catch {
    return null;
  }
}

export type AuthIdentity = {
  identity: string;
  permissions: string[];
  is_authenticated: boolean;
  display_name: string;
};

/**
 * Pure authenticate helper (unit-testable). Throws {@link HTTPException} on
 * missing/invalid credentials when auth is enforced.
 */
export function authenticateRequest(
  request: Request,
  env: NodeJS.ProcessEnv = process.env,
): AuthIdentity {
  // Process liveness — keep probeable without a key even when auth is on.
  if (requestPathname(request) === "/ok") {
    return {
      identity: "healthcheck",
      permissions: [],
      is_authenticated: true,
      display_name: "healthcheck",
    };
  }

  if (isAuthBypassEnabled(env)) {
    return {
      identity: "local-bypass",
      permissions: [],
      is_authenticated: true,
      display_name: "local-bypass",
    };
  }

  const token = extractApiKey(request);
  if (!token) {
    throw new HTTPException(401, {
      message: "Missing Authorization Bearer token (or x-api-key)",
      headers: { ...UNAUTH_HEADERS },
    });
  }

  const keys = configuredApiKeys(env);
  if (!apiKeyMatches(token, keys)) {
    throw new HTTPException(401, {
      message: "Invalid API key",
      headers: { ...UNAUTH_HEADERS },
    });
  }

  return {
    identity: "api-key",
    permissions: [],
    is_authenticated: true,
    display_name: "api-key",
  };
}

/** LangGraph Agent Server auth instance (registered in `langgraph.json`). */
export const auth = new Auth().authenticate(async (request) =>
  authenticateRequest(request),
);
