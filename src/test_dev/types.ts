/** Shared types for the test_development workflow. */

export type TestDevVerdict = "PASS" | "FAIL";

export type FindingSeverity = "error" | "warning" | "info";

export type TestDevCheckId =
  | "scope"
  | "coverage_map"
  | "target"
  | "asserts"
  | "timing";

export type Finding = {
  check: TestDevCheckId;
  severity: FindingSeverity;
  path?: string;
  graphId?: string;
  contractId?: string;
  message: string;
  fix?: string;
};

/** Documented behavior a permanent test should lock (LLR analogue for this service). */
export type Contract = {
  id: string;
  graphId: string;
  title: string;
  /** What the requirement/contract says must hold. */
  requirement: string;
  /** Substrings / patterns a covering test should assert. */
  assertHints: string[];
  /** Source of the contract (readme, graph docs, baseline). */
  source: "baseline" | "readme" | "graph_docs" | "inferred";
};

export type CoverageLink = {
  contractId: string;
  graphId: string;
  testPath?: string;
  covered: boolean;
  notes?: string;
};

export type PlanAction =
  | "add_test"
  | "update_test"
  | "add_assert"
  | "run_focused"
  | "ask_owner";

export type PlanItem = {
  action: PlanAction;
  graphId?: string;
  contractId?: string;
  path?: string;
  description: string;
  /** Optional bun:test stub the developer can paste. */
  suggestedTest?: string;
};

export type ChangedFile = {
  path: string;
  content?: string;
  patch?: string;
  status: "added" | "modified" | "deleted" | "unchanged";
};

export type ChangeSet = {
  label: string;
  files: ChangedFile[];
  diff?: string;
};

export type TestDevReport = {
  verdict: TestDevVerdict;
  summary: string;
  findings: Finding[];
  checksRun: TestDevCheckId[];
  scopeGraphIds: string[];
  contracts: Contract[];
  coverage: CoverageLink[];
  plan: PlanItem[];
  commands: string[];
};
