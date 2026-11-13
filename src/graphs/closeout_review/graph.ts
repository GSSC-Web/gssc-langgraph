/**
 * Agentic closeout review workflow (model-free checks + optional LLM synthesis).
 *
 * Behavioral reference: gssc5 peer closeout skills
 * (requirements-closeout-review + software-closeout-review +
 * test-closeout-review) — scope → peer lanes → PASS/FAIL with proposed fixes,
 * no silent contract rewrites. Implemented here as a Bun/TypeScript LangGraph
 * — not a Dot Agents `.agents/` scaffold, and not a revival of `service_review`.
 *
 * Invoke via Agent Server assistant id `closeout_review`, or `bun run closeout`.
 * Compiled with MemorySaver (`compileWithMemory`): pass `configurable.thread_id`
 * so `reviewMemory` accumulates across runs on the same thread.
 *
 * Ownership: `closeout_review` / `src/closeout/` only. Peers:
 * `software_dev` (plan + SW closeout), `test_development` (test plan/closeout).
 *
 * gssc5: loads reviewer-preset skills/memories via `load_gssc5_context`.
 * Optional synthesis (xAI chat helper) runs after deterministic checks and
 * skips cleanly when `XAI_API_KEY` is absent.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import { compileWithMemory } from "../../checkpoint/index.js";
import {
  ARCH_MEMORY_IDS,
  CLOSEOUT_PEER_SKILL_IDS,
  formatGssc5Context,
  loadGssc5ContextForRole,
  type Gssc5ContextBundle,
} from "../../gssc5/index.js";
import {
  CHECK_RUNNERS,
  summarize,
  verdictFrom,
} from "../../closeout/checks.js";
import { synthesizeCloseout } from "../../closeout/synthesize.js";
import type {
  ChangeSet,
  ChangedFile,
  CloseoutCheckId,
  CloseoutFinding,
  CloseoutVerdict,
  ProposedMemoryUpdate,
  ReviewMemoryNote,
} from "../../closeout/types.js";

const FindingAnnotation = Annotation<CloseoutFinding[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const StepsAnnotation = Annotation<string[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const UidsAnnotation = Annotation<string[]>({
  reducer: (_left, right) => right ?? [],
  default: () => [],
});

const ProposedMemoryAnnotation = Annotation<ProposedMemoryUpdate[]>({
  reducer: (_left, right) => right ?? [],
  default: () => [],
});

const ReviewMemoryAnnotation = Annotation<ReviewMemoryNote[]>({
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

  /** Kaneo task id when reviewing a tracked defect/task. */
  kaneoTaskId: Annotation<string>(),
  /** PR / git scope hint (URL, `base...head`, or branch). */
  prScope: Annotation<string>(),
  /** Explicit requirement / assistant / contract UIDs in scope. */
  uids: UidsAnnotation,

  /** Internal / output */
  changeSet: Annotation<ChangeSet | null>(),
  findings: FindingAnnotation,
  checksRun: Annotation<CloseoutCheckId[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
  verdict: Annotation<CloseoutVerdict | "">(),
  summary: Annotation<string>(),
  /** gssc5 Dot Agents skills/memories pulled in for this turn (optional). */
  gssc5Context: Annotation<Gssc5ContextBundle | null>({
    reducer: (_left, right) => right ?? null,
    default: () => null,
  }),
  gssc5ContextText: Annotation<string>(),
  gssc5Root: Annotation<string>(),
  /** Optional LLM narrative (falls back to deterministic summary when skipped). */
  narrativeSummary: Annotation<string>(),
  proposedMemoryUpdates: ProposedMemoryAnnotation,
  synthesisNote: Annotation<string>(),
  /** Durable review notes across thread turns (append-only). */
  reviewMemory: ReviewMemoryAnnotation,
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

const loadGssc5Context = async (
  state: typeof CloseoutState.State,
  config?: { configurable?: { gssc5Root?: string; gssc5Enabled?: boolean } },
): Promise<typeof CloseoutState.Update> => {
  const cs = state.changeSet ?? buildChangeSet(state);
  const pathHints = (cs.files ?? [])
    .map((f) => f.path)
    .slice(0, 20)
    .join(" ");
  const query = [
    state.label,
    state.kaneoTaskId,
    state.prScope,
    (state.uids ?? []).join(" "),
    pathHints,
    "closeout review requirements software test",
  ]
    .filter(Boolean)
    .join(" ");

  const bundle = loadGssc5ContextForRole("reviewer", {
    query,
    root: config?.configurable?.gssc5Root,
    enabled: config?.configurable?.gssc5Enabled,
    requireSkills: [...CLOSEOUT_PEER_SKILL_IDS],
    requireMemories: [...ARCH_MEMORY_IDS],
    maxSkills: 3,
    maxMemories: 3,
  });

  return {
    gssc5Context: bundle,
    gssc5ContextText: formatGssc5Context(bundle),
    gssc5Root: bundle.root,
    steps: ["load_gssc5_context"],
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
  const summary = summarize(verdict, findings);
  const note: ReviewMemoryNote = {
    at: new Date().toISOString(),
    verdict,
    summary,
    label: state.changeSet?.label ?? state.label,
  };
  return {
    verdict,
    summary,
    reviewMemory: [note],
    steps: ["verdict"],
  };
};

const synthesize = async (
  state: typeof CloseoutState.State,
  config?: { configurable?: { synthesisEnabled?: boolean } },
): Promise<typeof CloseoutState.Update> => {
  const result = await synthesizeCloseout({
    verdict: state.verdict ?? "",
    summary: state.summary ?? "",
    findings: state.findings ?? [],
    gssc5ContextText: state.gssc5ContextText,
    kaneoTaskId: state.kaneoTaskId,
    prScope: state.prScope,
    uids: state.uids,
    enabled: config?.configurable?.synthesisEnabled,
  });
  return {
    narrativeSummary: result.narrativeSummary,
    proposedMemoryUpdates: result.proposedMemoryUpdates,
    synthesisNote: result.note,
    steps: ["synthesize"],
  };
};

const builder = new StateGraph(CloseoutState)
  .addNode("parse_changeset", parseChangeset)
  .addNode("load_gssc5_context", loadGssc5Context)
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
  .addNode("synthesize", synthesize)
  .addEdge("__start__", "parse_changeset")
  .addEdge("parse_changeset", "load_gssc5_context")
  .addEdge("load_gssc5_context", "check_scope")
  .addEdge("check_scope", "check_contracts")
  .addEdge("check_contracts", "check_software_trace")
  .addEdge("check_software_trace", "check_software_match")
  .addEdge("check_software_match", "check_software_quality")
  .addEdge("check_software_quality", "check_third_party")
  .addEdge("check_third_party", "check_test_coverage")
  .addEdge("check_test_coverage", "check_test_target")
  .addEdge("check_test_target", "check_secrets")
  .addEdge("check_secrets", "finalize")
  .addEdge("finalize", "synthesize");

export const graph = compileWithMemory(builder, {
  name: "GSSC Closeout Review",
});
