import { afterEach, describe, expect, test } from "bun:test";
import { synthesizeCloseout } from "../src/closeout/synthesize.js";

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

describe("synthesizeCloseout", () => {
  test("skips without API key and keeps deterministic summary", async () => {
    stash();
    delete process.env[KEY];
    const out = await synthesizeCloseout({
      verdict: "PASS",
      summary: "PASS — 0 findings",
      findings: [],
    });
    expect(out.note).toBe("skipped: no XAI_API_KEY");
    expect(out.narrativeSummary).toBe("PASS — 0 findings");
    expect(out.proposedMemoryUpdates).toEqual([]);
  });

  test("respects enabled: false", async () => {
    stash();
    process.env[KEY] = "test-key-not-for-production";
    const out = await synthesizeCloseout({
      verdict: "FAIL",
      summary: "FAIL — 1 finding",
      findings: [],
      enabled: false,
    });
    expect(out.note).toBe("skipped: disabled");
    expect(out.narrativeSummary).toBe("FAIL — 1 finding");
  });
});
