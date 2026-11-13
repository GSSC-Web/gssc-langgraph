/**
 * Test-development analyzers (model-free).
 *
 * Mirrors gssc5 test-closeout-review steps: scope → map → target → asserts →
 * timing → verdict — without StrictDoc `@relation` markers.
 */
import {
  CONFLICT_GUIDANCE,
} from "./criteria.js";
import {
  BASELINE_CONTRACTS,
  changedGraphIds,
  graphIdsFromChangeSet,
  resolveContracts,
  TOOLING_GRAPH_IDS,
} from "./contracts.js";
import type {
  ChangeSet,
  Contract,
  CoverageLink,
  Finding,
  PlanItem,
  TestDevCheckId,
} from "./types.js";

const TEST_FILE_RE = /^tests\/.+\.test\.tsx?$/;

function textOf(cs: ChangeSet, path: string): string {
  return cs.files.find((f) => f.path === path)?.content ?? "";
}

function testFiles(cs: ChangeSet): Array<{ path: string; body: string }> {
  return cs.files
    .filter((f) => TEST_FILE_RE.test(f.path) && f.status !== "deleted")
    .map((f) => ({ path: f.path, body: f.content ?? "" }));
}

function mentionsGraph(body: string, graphId: string): boolean {
  const spaced = graphId.replace(/_/g, " ");
  return (
    body.includes(`src/graphs/${graphId}/`) ||
    body.includes(`graphs/${graphId}/`) ||
    body.includes(`"${graphId}"`) ||
    body.includes(`'${graphId}'`) ||
    body.toLowerCase().includes(spaced.toLowerCase())
  );
}

function hintsCovered(body: string, hints: string[]): number {
  let n = 0;
  for (const h of hints) {
    if (body.toLowerCase().includes(h.toLowerCase())) n++;
  }
  return n;
}

/** Decide which graphs are in scope for this run. */
export function resolveScope(cs: ChangeSet): {
  graphIds: string[];
  findings: Finding[];
} {
  const findings: Finding[] = [];
  const changed = changedGraphIds(cs);
  const all = graphIdsFromChangeSet(cs);

  let graphIds: string[];
  if (cs.label === "workspace" || cs.label.startsWith("workspace")) {
    graphIds = all;
  } else if (changed.length > 0) {
    graphIds = changed;
  } else {
    // Diff touching only tests / registry: scope to graphs mentioned in changed tests,
    // else baseline + tooling present in the change set.
    const touchedTests = testFiles(cs).filter((t) => {
      const f = cs.files.find((x) => x.path === t.path);
      return f && f.status !== "unchanged";
    });
    const mentioned = new Set<string>();
    for (const t of touchedTests) {
      for (const id of all) {
        if (mentionsGraph(t.body, id)) mentioned.add(id);
      }
    }
    if (mentioned.size > 0) {
      graphIds = [...mentioned].sort();
    } else {
      graphIds = all.filter(
        (id) =>
          BASELINE_CONTRACTS.some((c) => c.graphId === id) ||
          TOOLING_GRAPH_IDS.has(id),
      );
      if (graphIds.length === 0) graphIds = all;
    }
  }

  if (graphIds.length === 0) {
    findings.push({
      check: "scope",
      severity: "warning",
      message: "No graphs in scope for test development",
      fix: "Pass --workspace, a diff that touches graphs, or explicit paths.",
    });
  }

  return { graphIds, findings };
}

export function mapCoverage(
  cs: ChangeSet,
  contracts: Contract[],
): { coverage: CoverageLink[]; findings: Finding[] } {
  const findings: Finding[] = [];
  const tests = testFiles(cs);
  const coverage: CoverageLink[] = [];

  for (const c of contracts) {
    const candidates = tests.filter((t) => mentionsGraph(t.body, c.graphId));
    let best: { path: string; score: number } | undefined;
    for (const t of candidates) {
      const score = hintsCovered(t.body, c.assertHints);
      if (!best || score > best.score) best = { path: t.path, score };
    }

    const covered = Boolean(best && best.score > 0);
    coverage.push({
      contractId: c.id,
      graphId: c.graphId,
      testPath: best?.path,
      covered,
      notes: covered
        ? `Matched ${best!.score}/${c.assertHints.length} assert hints in ${best!.path}`
        : candidates.length
          ? `Tests mention graph "${c.graphId}" but miss contract assert hints`
          : `No test file references graph "${c.graphId}"`,
    });

    if (!covered) {
      findings.push({
        check: "coverage_map",
        severity: "error",
        path: best?.path ?? `src/graphs/${c.graphId}/graph.ts`,
        graphId: c.graphId,
        contractId: c.id,
        message: `Contract "${c.id}" has no permanent test locking it`,
        fix: `Add a bun:test that asserts: ${c.requirement}`,
      });
    }
  }

  return { coverage, findings };
}

/**
 * Flag tests that appear to chase implementation quirks rather than contracts
 * (heuristic: expects on private/internal names without matching a contract hint).
 */
export function checkTarget(
  cs: ChangeSet,
  contracts: Contract[],
  coverage: CoverageLink[],
): Finding[] {
  const findings: Finding[] = [];
  const tests = testFiles(cs);

  for (const t of tests) {
    // Only scrutinize tests that claim to cover an in-scope graph.
    const related = contracts.filter((c) => mentionsGraph(t.body, c.graphId));
    if (related.length === 0) continue;

    // Soft flag: test file with only toBeDefined / truthy checks and no contract hints.
    const hasContractAssert = related.some(
      (c) => hintsCovered(t.body, c.assertHints) > 0,
    );
    const onlySmoke =
      /toBeDefined\s*\(/.test(t.body) &&
      !hasContractAssert &&
      related.some((c) => c.source === "baseline");

    if (onlySmoke) {
      findings.push({
        check: "target",
        severity: "warning",
        path: t.path,
        message:
          "Test looks like compile-only smoke without asserting documented contract behavior",
        fix: `Assert the requirement (e.g. ${related[0]!.requirement}). ${CONFLICT_GUIDANCE}`,
      });
    }

    // Flag comments that explicitly snap to current SW.
    if (
      /whatever (the )?software|match(es)? current (impl|behavior)|snapshot of sw/i.test(
        t.body,
      )
    ) {
      findings.push({
        check: "target",
        severity: "error",
        path: t.path,
        message:
          "Test comments suggest asserting current software instead of the documented contract",
        fix: CONFLICT_GUIDANCE,
      });
    }
  }

  // Covered baseline contracts should live under tests/ and reference invoke or field asserts.
  for (const link of coverage) {
    if (!link.covered || !link.testPath) continue;
    const c = contracts.find((x) => x.id === link.contractId);
    if (!c || c.source !== "baseline") continue;
    const body = textOf(cs, link.testPath);
    if (body && !/\.invoke\s*\(/.test(body) && !/expect\s*\(/.test(body)) {
      findings.push({
        check: "target",
        severity: "error",
        path: link.testPath,
        graphId: c.graphId,
        contractId: c.id,
        message: `Covering file for "${c.id}" does not invoke the graph or assert outcomes`,
        fix: "Use graph.invoke(...) and expect(...) against the contract.",
      });
    }
  }

  return findings;
}

export function checkAsserts(
  cs: ChangeSet,
  contracts: Contract[],
  coverage: CoverageLink[],
): Finding[] {
  const findings: Finding[] = [];

  for (const link of coverage) {
    if (!link.covered || !link.testPath) continue;
    const c = contracts.find((x) => x.id === link.contractId);
    if (!c) continue;
    const body = textOf(cs, link.testPath);
    if (!body) continue;

    const hit = hintsCovered(body, c.assertHints);
    const needed = Math.min(2, c.assertHints.length);
    if (hit < needed && c.source === "baseline") {
      findings.push({
        check: "asserts",
        severity: "error",
        path: link.testPath,
        graphId: c.graphId,
        contractId: c.id,
        message: `Baseline contract "${c.id}" is weakly asserted (${hit}/${c.assertHints.length} hints)`,
        fix: `Assert behavior from the contract verb: ${c.requirement}`,
      });
    }

    // Empty expect() or expect(true)
    if (/expect\s*\(\s*true\s*\)/.test(body) || /expect\s*\(\s*\)/.test(body)) {
      findings.push({
        check: "asserts",
        severity: "error",
        path: link.testPath,
        message: "Tautological or empty expect() found",
        fix: "Replace with asserts derived from the contract.",
      });
    }
  }

  return findings;
}

export function checkTiming(cs: ChangeSet, scopeGraphIds: string[]): {
  findings: Finding[];
  commands: string[];
} {
  const findings: Finding[] = [];
  const commands: string[] = [];
  const tests = testFiles(cs);

  const focusedFiles = new Set<string>();
  for (const id of scopeGraphIds) {
    for (const t of tests) {
      if (mentionsGraph(t.body, id)) focusedFiles.add(t.path);
    }
  }

  if (focusedFiles.size === 0) {
    // Suggest creating a dedicated test file per scoped graph.
    for (const id of scopeGraphIds) {
      commands.push(`bun test tests/${id}.test.ts`);
    }
  } else {
    for (const path of [...focusedFiles].sort()) {
      commands.push(`bun test ${path}`);
    }
  }

  // Always offer the focused set as the preferred harness; warn if tests pull in heavy deps.
  for (const t of tests) {
    if (
      /playwright|puppeteer|selenium|cypress/i.test(t.body) &&
      scopeGraphIds.some((id) => mentionsGraph(t.body, id))
    ) {
      findings.push({
        check: "timing",
        severity: "warning",
        path: t.path,
        message:
          "Browser/E2E harness detected for a LangGraph unit contract — prefer graph.invoke in bun:test",
        fix: "Keep permanent contract tests unit-level; reserve E2E for explicit integration tasks.",
      });
    }
  }

  if (commands.length > 1) {
    // Also provide a single combined focused run.
    const files = [...focusedFiles].sort();
    if (files.length > 1) {
      commands.unshift(`bun test ${files.join(" ")}`);
    }
  }

  return { findings, commands };
}

export function buildPlan(
  contracts: Contract[],
  coverage: CoverageLink[],
  findings: Finding[],
  commands: string[],
): PlanItem[] {
  const plan: PlanItem[] = [];

  for (const link of coverage) {
    if (link.covered) continue;
    const c = contracts.find((x) => x.id === link.contractId);
    if (!c) continue;
    const testPath = `tests/${c.graphId}.test.ts`;
    plan.push({
      action: "add_test",
      graphId: c.graphId,
      contractId: c.id,
      path: testPath,
      description: `Add permanent test for ${c.id}: ${c.requirement}`,
      suggestedTest: suggestTestStub(c),
    });
  }

  for (const f of findings) {
    if (f.check === "asserts" && f.contractId && f.path) {
      plan.push({
        action: "add_assert",
        graphId: f.graphId,
        contractId: f.contractId,
        path: f.path,
        description: f.message,
      });
    }
    if (f.check === "target" && f.severity === "error") {
      plan.push({
        action: "ask_owner",
        graphId: f.graphId,
        contractId: f.contractId,
        path: f.path,
        description: f.message,
      });
    }
  }

  for (const cmd of commands.slice(0, 3)) {
    plan.push({
      action: "run_focused",
      description: `Prefer focused harness: ${cmd}`,
    });
  }

  return plan;
}

function suggestTestStub(c: Contract): string {
  const importPath = `../src/graphs/${c.graphId}/graph.js`;
  const hints = c.assertHints.map((h) => `    // assert: ${h}`).join("\n");
  return `import { describe, expect, test } from "bun:test";
import { graph } from "${importPath}";

describe("${c.graphId} — ${c.id}", () => {
  test("${c.title}", async () => {
    // Contract: ${c.requirement}
    const result = await graph.invoke({} as never);
${hints}
    expect(result).toBeDefined();
  });
});
`;
}

export function runAnalysis(cs: ChangeSet): {
  scopeGraphIds: string[];
  contracts: Contract[];
  coverage: CoverageLink[];
  findings: Finding[];
  checksRun: TestDevCheckId[];
  plan: PlanItem[];
  commands: string[];
} {
  const checksRun: TestDevCheckId[] = [];
  const findings: Finding[] = [];

  const scope = resolveScope(cs);
  checksRun.push("scope");
  findings.push(...scope.findings);

  const contracts = resolveContracts(cs, scope.graphIds);

  const mapped = mapCoverage(cs, contracts);
  checksRun.push("coverage_map");
  findings.push(...mapped.findings);

  const targetFindings = checkTarget(cs, contracts, mapped.coverage);
  checksRun.push("target");
  findings.push(...targetFindings);

  const assertFindings = checkAsserts(cs, contracts, mapped.coverage);
  checksRun.push("asserts");
  findings.push(...assertFindings);

  const timing = checkTiming(cs, scope.graphIds);
  checksRun.push("timing");
  findings.push(...timing.findings);

  const plan = buildPlan(
    contracts,
    mapped.coverage,
    findings,
    timing.commands,
  );

  return {
    scopeGraphIds: scope.graphIds,
    contracts,
    coverage: mapped.coverage,
    findings,
    checksRun,
    plan,
    commands: timing.commands,
  };
}

export function verdictFrom(findings: Finding[]): "PASS" | "FAIL" {
  return findings.some((f) => f.severity === "error") ? "FAIL" : "PASS";
}

export function summarize(
  verdict: "PASS" | "FAIL",
  findings: Finding[],
  plan: PlanItem[],
): string {
  const errors = findings.filter((f) => f.severity === "error").length;
  const warnings = findings.filter((f) => f.severity === "warning").length;
  const adds = plan.filter((p) => p.action === "add_test").length;
  if (verdict === "PASS" && warnings === 0 && adds === 0) {
    return "PASS — in-scope contracts have permanent tests.";
  }
  if (verdict === "PASS") {
    return `PASS with ${warnings} warning(s); ${adds} optional plan item(s).`;
  }
  return `FAIL — ${errors} error(s), ${warnings} warning(s); ${adds} test(s) to add.`;
}
