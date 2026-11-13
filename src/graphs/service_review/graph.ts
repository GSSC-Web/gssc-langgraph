/**
 * Agentic service review workflow (model-free).
 *
 * Runs deterministic closeout-style checks inspired by gssc5's review skills,
 * adapted for this Bun/TypeScript LangGraph Agent Server and its gssc5 contract.
 *
 * Invoke via Agent Server assistant id `service_review`, or `bun run review`.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import {
  CHECK_RUNNERS,
  summarize,
  verdictFrom,
} from "../../review/checks.js";
import type {
  ChangeSet,
  ChangedFile,
  Finding,
  ReviewCheckId,
  ReviewVerdict,
} from "../../review/types.js";

const FindingAnnotation = Annotation<Finding[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const StepsAnnotation = Annotation<string[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const ReviewState = Annotation.Root({
  /** Optional unified diff. */
  diff: Annotation<string>(),
  /** Optional file map (path → contents). */
  files: Annotation<Record<string, string>>(),
  /** Optional pre-built change set label. */
  label: Annotation<string>(),
  /** Optional explicit file statuses when providing `files`. */
  fileStatuses: Annotation<Record<string, ChangedFile["status"]>>(),

  /** Internal / output */
  changeSet: Annotation<ChangeSet | null>(),
  findings: FindingAnnotation,
  checksRun: Annotation<ReviewCheckId[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
  verdict: Annotation<ReviewVerdict | "">(),
  summary: Annotation<string>(),
  steps: StepsAnnotation,
});

function buildChangeSet(state: typeof ReviewState.State): ChangeSet {
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
    // Lightweight path extraction when only a diff string is provided via API.
    const pathRe = /^diff --git a\/(.+?) b\/(.+)$/gm;
    let m: RegExpExecArray | null;
    while ((m = pathRe.exec(state.diff)) !== null) {
      const path = m[2]!;
      if (!files.some((f) => f.path === path)) {
        files.push({
          path,
          patch: undefined,
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
  state: typeof ReviewState.State,
): Promise<typeof ReviewState.Update> => {
  const changeSet = buildChangeSet(state);
  return {
    changeSet,
    steps: ["parse_changeset"],
  };
};

function makeCheckNode(checkId: ReviewCheckId) {
  return async (
    state: typeof ReviewState.State,
  ): Promise<typeof ReviewState.Update> => {
    const cs = state.changeSet ?? buildChangeSet(state);
    const findings = CHECK_RUNNERS[checkId](cs);
    return {
      changeSet: cs,
      findings,
      checksRun: [checkId],
      steps: [`check_${checkId}`],
    };
  };
}

const finalize = async (
  state: typeof ReviewState.State,
): Promise<typeof ReviewState.Update> => {
  const findings = state.findings ?? [];
  const verdict = verdictFrom(findings);
  return {
    verdict,
    summary: summarize(verdict, findings),
    steps: ["verdict"],
  };
};

const builder = new StateGraph(ReviewState)
  .addNode("parse_changeset", parseChangeset)
  .addNode("check_registry", makeCheckNode("registry"))
  .addNode("check_graph_quality", makeCheckNode("graph_quality"))
  .addNode("check_stack", makeCheckNode("stack"))
  .addNode("check_gssc5_contract", makeCheckNode("gssc5_contract"))
  .addNode("check_tests", makeCheckNode("tests"))
  .addNode("check_secrets", makeCheckNode("secrets"))
  .addNode("finalize", finalize)
  .addEdge("__start__", "parse_changeset")
  .addEdge("parse_changeset", "check_registry")
  .addEdge("check_registry", "check_graph_quality")
  .addEdge("check_graph_quality", "check_stack")
  .addEdge("check_stack", "check_gssc5_contract")
  .addEdge("check_gssc5_contract", "check_tests")
  .addEdge("check_tests", "check_secrets")
  .addEdge("check_secrets", "finalize");

export const graph = builder.compile();
graph.name = "GSSC Service Review";
