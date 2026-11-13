import { afterEach, describe, expect, test } from "bun:test";
import {
  CHECKPOINT_BACKEND_ENV,
  CHECKPOINT_POSTGRES_URL_ENV,
  CHECKPOINT_SQLITE_PATH_ENV,
  resolveCheckpointConfig,
} from "../src/checkpoint/index.js";

const ORIGINAL_ENV = {
  backend: process.env[CHECKPOINT_BACKEND_ENV],
  sqlite: process.env[CHECKPOINT_SQLITE_PATH_ENV],
  postgres: process.env[CHECKPOINT_POSTGRES_URL_ENV],
};

afterEach(() => {
  if (ORIGINAL_ENV.backend === undefined) {
    delete process.env[CHECKPOINT_BACKEND_ENV];
  } else {
    process.env[CHECKPOINT_BACKEND_ENV] = ORIGINAL_ENV.backend;
  }
  if (ORIGINAL_ENV.sqlite === undefined) {
    delete process.env[CHECKPOINT_SQLITE_PATH_ENV];
  } else {
    process.env[CHECKPOINT_SQLITE_PATH_ENV] = ORIGINAL_ENV.sqlite;
  }
  if (ORIGINAL_ENV.postgres === undefined) {
    delete process.env[CHECKPOINT_POSTGRES_URL_ENV];
  } else {
    process.env[CHECKPOINT_POSTGRES_URL_ENV] = ORIGINAL_ENV.postgres;
  }
});

describe("resolveCheckpointConfig", () => {
  test("defaults to memory when unset", () => {
    delete process.env[CHECKPOINT_BACKEND_ENV];
    expect(resolveCheckpointConfig({})).toEqual({ backend: "memory" });
  });

  test("accepts sqlite aliases and default path", () => {
    expect(
      resolveCheckpointConfig({ [CHECKPOINT_BACKEND_ENV]: "sqlite" }),
    ).toEqual({
      backend: "sqlite",
      path: ".data/langgraph-checkpoints.sqlite",
    });
    expect(
      resolveCheckpointConfig({
        [CHECKPOINT_BACKEND_ENV]: "SQLITE3",
        [CHECKPOINT_SQLITE_PATH_ENV]: "/tmp/cp.sqlite",
      }),
    ).toEqual({ backend: "sqlite", path: "/tmp/cp.sqlite" });
  });

  test("requires postgres URL", () => {
    expect(() =>
      resolveCheckpointConfig({ [CHECKPOINT_BACKEND_ENV]: "postgres" }),
    ).toThrow(/GSSC_CHECKPOINT_POSTGRES_URL/);
  });

  test("rejects unknown backends", () => {
    expect(() =>
      resolveCheckpointConfig({ [CHECKPOINT_BACKEND_ENV]: "redis" }),
    ).toThrow(/Unsupported/);
  });
});

describe("sqlite durable checkpointer (Node)", () => {
  test("preserves reducer state across saver instances (restart)", async () => {
    // better-sqlite3 is unsupported in the Bun runtime; Agent Server uses Node.
    const proc = Bun.spawn({
      cmd: ["node", "scripts/verify-sqlite-checkpoint.mjs"],
      cwd: import.meta.dir + "/..",
      stdout: "pipe",
      stderr: "pipe",
    });
    const exitCode = await proc.exited;
    const stdout = await new Response(proc.stdout).text();
    const stderr = await new Response(proc.stderr).text();
    expect(exitCode, `stderr=${stderr}\nstdout=${stdout}`).toBe(0);
    expect(stdout).toContain("ok: sqlite checkpointer");
  });
});
