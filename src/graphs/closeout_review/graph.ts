/**
 * Agentic closeout review workflow (model-free).
 *
 * Behavioral reference: gssc5 peer closeout skills
 * (requirements-closeout-review + software-closeout-review +
 * test-closeout-review) — scope → peer lanes → PASS/FAIL with proposed fixes,
 * no silent contract rewrites. Implemented here as a Bun/TypeScript LangGraph
 * — not a Dot Agents `.agents/` scaffold, and not a revival of `service_review`.
 *
 * Invoke via Agent Server assistant id `closeout_review`, or `bun run closeout`.
 *
 * Ownership: `closeout_review` / `src/closeout/` only. Peers:
 * `software_dev` (plan + SW closeout), `test_development` (test plan/closeout).
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import {
  CHECK_RUNNERS,
  summarize,
  verdictFrom,
} from "../../closeout/checks.js";
import type {
  ChangeSet,
  ChangedFile,
  CloseoutCheckId,
  CloseoutFinding,
  CloseoutVerdict,
} from "../../closeout/types.js";

const FindingAnnotation = Annotation<CloseoutFinding[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const StepsAnnotation = Annotation<string[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const CloseoutState = Annotation.Root({
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
  checksRun: Annotation<CloseoutCheckId[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
  verdict: Annotation<CloseoutVerdict | "">(),
  summary: Annotation<string>(),
  steps: StepsAnnotation,
});

function buildChangeSet(state: typeof CloseoutState.State): ChangeSet {
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
  state: typeof CloseoutState.State,
): Promise<typeof CloseoutState.Update> => {
  const changeSet = buildChangeSet(state);
  return {
    changeSet,
    steps: ["parse_changeset"],
  };
};

function makeCheckNode(checkId: CloseoutCheckId) {
  return async (
    state: typeof CloseoutState.State,
  ): Promise<typeof CloseoutState.Update> => {
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
  state: typeof CloseoutState.State,
): Promise<typeof CloseoutState.Update> => {
  const findings = state.findings ?? [];
  const verdict = verdictFrom(findings);
  return {
    verdict,
    summary: summarize(verdict, findings),
    steps: ["verdict"],
  };
};

const builder = new StateGraph(CloseoutState)
  .addNode("parse_changeset", parseChangeset)
  .addNode("check_scope", makeCheckNode("scope"))
  .addNode("check_contracts", makeCheckNode("contracts"))
  .addNode("check_software_trace", makeCheckNode("software_trace"))
  .addNode("check_software_match", makeCheckNode("software_match"))
  .addNode("check_software_quality", makeCheckNode("software_quality"))
  .addNode("check_third_party", makeCheckNode("third_party"))
  .addNode("check_test_coverage", makeCheckNode("test_coverage"))
  .addNode("check_test_target", makeCheckNode("test_target"))
  .addNode("check_secrets", makeCheckNode("secrets"))
  .addNode("finalize", finalize)
  .addEdge("__start__", "parse_changeset")
  .addEdge("parse_changeset", "check_scope")
  .addEdge("check_scope", "check_contracts")
  .addEdge("check_contracts", "check_software_trace")
  .addEdge("check_software_trace", "check_software_match")
  .addEdge("check_software_match", "check_software_quality")
  .addEdge("check_software_quality", "check_third_party")
  .addEdge("check_third_party", "check_test_coverage")
  .addEdge("check_test_coverage", "check_test_target")
  .addEdge("check_test_target", "check_secrets")
  .addEdge("check_secrets", "finalize");

export const graph = builder.compile();
graph.name = "GSSC Closeout Review";
