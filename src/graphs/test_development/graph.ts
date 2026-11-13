/**
 * Agentic test-development workflow (model-free).
 *
 * Behavioral reference: gssc5 test agent + test-closeout-review (one permanent
 * test per in-scope requirement, assert the contract not incidental SW,
 * focused harness, PASS/FAIL with a development plan).
 *
 * Implemented as a Bun/TypeScript LangGraph for this Agent Server — not a
 * Dot Agents `.agents/` scaffold.
 *
 * Invoke via assistant id `test_development`, or `bun run test-dev`.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import {
  runAnalysis,
  summarize,
  verdictFrom,
} from "../../test_dev/analyze.js";
import type {
  ChangeSet,
  ChangedFile,
  Contract,
  CoverageLink,
  Finding,
  PlanItem,
  TestDevCheckId,
  TestDevVerdict,
} from "../../test_dev/types.js";

const FindingAnnotation = Annotation<Finding[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const StepsAnnotation = Annotation<string[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const TestDevState = Annotation.Root({
  /** Optional unified diff. */
  diff: Annotation<string>(),
  /** Optional file map (path → contents). */
  files: Annotation<Record<string, string>>(),
  /** Optional change-set label. */
  label: Annotation<string>(),
  /** Optional explicit file statuses when providing `files`. */
  fileStatuses: Annotation<Record<string, ChangedFile["status"]>>(),

  /** Internal / output */
  changeSet: Annotation<ChangeSet | null>(),
  scopeGraphIds: Annotation<string[]>({
    reducer: (_left, right) => right ?? [],
    default: () => [],
  }),
  contracts: Annotation<Contract[]>({
    reducer: (_left, right) => right ?? [],
    default: () => [],
  }),
  coverage: Annotation<CoverageLink[]>({
    reducer: (_left, right) => right ?? [],
    default: () => [],
  }),
  findings: FindingAnnotation,
  checksRun: Annotation<TestDevCheckId[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
  plan: Annotation<PlanItem[]>({
    reducer: (_left, right) => right ?? [],
    default: () => [],
  }),
  commands: Annotation<string[]>({
    reducer: (_left, right) => right ?? [],
    default: () => [],
  }),
  verdict: Annotation<TestDevVerdict | "">(),
  summary: Annotation<string>(),
  steps: StepsAnnotation,
});

function buildChangeSet(state: typeof TestDevState.State): ChangeSet {
  if (state.changeSet) return state.changeSet;

  const files: ChangedFile[] = [];
  const map = state.files ?? {};
  const statuses = state.fileStatuses ?? {};
  for (const [path, content] of Object.entries(map)) {
    files.push({
      path,
      content,
      status: statuses[path] ?? "modified",
    });
  }

  if (state.diff?.trim()) {
    const pathRe = /^diff --git a\/(.+?) b\/(.+)$/gm;
    let m: RegExpExecArray | null;
    while ((m = pathRe.exec(state.diff)) !== null) {
      const path = m[2]!;
      if (!files.some((f) => f.path === path)) {
        files.push({
          path,
          status: "modified",
        });
      }
    }
  }

  return {
    label: state.label?.trim() || (state.diff ? "diff" : "files"),
    files,
    diff: state.diff,
  };
}

const parseChangeset = async (
  state: typeof TestDevState.State,
): Promise<typeof TestDevState.Update> => {
  return {
    changeSet: buildChangeSet(state),
    steps: ["parse_changeset"],
  };
};

const analyzeScope = async (
  state: typeof TestDevState.State,
): Promise<typeof TestDevState.Update> => {
  const cs = state.changeSet ?? buildChangeSet(state);
  const result = runAnalysis(cs);
  return {
    changeSet: cs,
    scopeGraphIds: result.scopeGraphIds,
    contracts: result.contracts,
    coverage: result.coverage,
    findings: result.findings,
    checksRun: result.checksRun,
    plan: result.plan,
    commands: result.commands,
    steps: ["analyze"],
  };
};

const finalize = async (
  state: typeof TestDevState.State,
): Promise<typeof TestDevState.Update> => {
  const findings = state.findings ?? [];
  const plan = state.plan ?? [];
  const verdict = verdictFrom(findings);
  return {
    verdict,
    summary: summarize(verdict, findings, plan),
    steps: ["verdict"],
  };
};

const builder = new StateGraph(TestDevState)
  .addNode("parse_changeset", parseChangeset)
  .addNode("analyze", analyzeScope)
  .addNode("finalize", finalize)
  .addEdge("__start__", "parse_changeset")
  .addEdge("parse_changeset", "analyze")
  .addEdge("analyze", "finalize");

export const graph = builder.compile();
graph.name = "GSSC Test Development";
