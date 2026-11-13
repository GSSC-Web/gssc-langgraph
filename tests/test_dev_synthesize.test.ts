import { afterEach, describe, expect, test } from "bun:test";
import { synthesizeTestDev } from "../src/test_dev/synthesize.js";

const KEY = "XAI_API_KEY";
let saved: string | undefined;

function stash() {
  saved = process.env[KEY];
}

function restore() {
  if (saved === undefined) delete process.env[KEY];
  else process.env[KEY] = saved;
}

afterEach(() => {
  restore();
});

describe("synthesizeTestDev", () => {
  test("skips without API key and keeps deterministic summary", async () => {
    stash();
    delete process.env[KEY];
    const out = await synthesizeTestDev({
      verdict: "PASS",
      summary: "PASS — 0 findings",
      findings: [],
      scopeGraphIds: ["health"],
      plan: [],
      commands: ["bun test tests/graphs.test.ts"],
    });
    expect(out.note).toBe("skipped: no XAI_API_KEY");
    expect(out.narrativeSummary).toBe("PASS — 0 findings");
    expect(out.proposedMemoryUpdates).toEqual([]);
  });

  test("respects enabled: false", async () => {
    stash();
    process.env[KEY] = "test-key-not-for-production";
    const out = await synthesizeTestDev({
      verdict: "FAIL",
      summary: "FAIL — 1 finding",
      findings: [],
      enabled: false,
    });
    expect(out.note).toBe("skipped: disabled");
    expect(out.narrativeSummary).toBe("FAIL — 1 finding");
  });
});
