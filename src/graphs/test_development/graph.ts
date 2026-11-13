/**
 * Agentic test-development workflow (model-free analysis + optional LLM
 * synthesis).
 *
 * Behavioral reference: gssc5 test agent + test-closeout-review (one permanent
 * test per in-scope requirement, assert the contract not incidental SW,
 * focused harness, PASS/FAIL with a development plan).
 *
 * Implemented as a Bun/TypeScript LangGraph for this Agent Server — not a
 * Dot Agents `.agents/` scaffold.
 *
 * Invoke via assistant id `test_development`, or `bun run test-dev`.
 * Compiled with MemorySaver (`compileWithMemory`): pass `configurable.thread_id`
 * so `specialistNotes` accumulate across runs on the same thread.
 *
 * Optional synthesis (xAI chat helper) runs after deterministic analysis and
 * skips cleanly when `XAI_API_KEY` is absent.
 */
import { Annotation, StateGraph } from "@langchain/langgraph";
import { compileWithMemory } from "../../checkpoint/index.js";
import {
  formatGssc5Context,
  loadGssc5ContextForRole,
  type Gssc5ContextBundle,
} from "../../gssc5/index.js";
import {
  runAnalysis,
  summarize,
  verdictFrom,
} from "../../test_dev/analyze.js";
import { synthesizeTestDev } from "../../test_dev/synthesize.js";
import type {
  ChangeSet,
  ChangedFile,
  Contract,
  CoverageLink,
  Finding,
  PlanItem,
  ProposedMemoryUpdate,
  SpecialistNote,
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

const SpecialistNotesAnnotation = Annotation<SpecialistNote[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const ProposedMemoryAnnotation = Annotation<ProposedMemoryUpdate[]>({
  reducer: (_left, right) => right ?? [],
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
  /** Durable specialist notes across thread turns (append-only). */
  specialistNotes: SpecialistNotesAnnotation,
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

const loadGssc5Context = async (
  state: typeof TestDevState.State,
  config?: { configurable?: { gssc5Root?: string; gssc5Enabled?: boolean } },
): Promise<typeof TestDevState.Update> => {
  const cs = state.changeSet ?? buildChangeSet(state);
  const pathHints = (cs.files ?? [])
    .map((f) => f.path)
    .slice(0, 20)
    .join(" ");
  const query = [state.label, pathHints, "test closeout"].filter(Boolean).join(" ");
  const bundle = loadGssc5ContextForRole("test", {
    query,
    root: config?.configurable?.gssc5Root,
    enabled: config?.configurable?.gssc5Enabled,
    requireSkills: ["test-closeout-review"],
    maxSkills: 3,
    maxMemories: 2,
  });
  return {
    gssc5Context: bundle,
    gssc5ContextText: formatGssc5Context(bundle),
    gssc5Root: bundle.root,
    steps: ["load_gssc5_context"],
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
  const summary = summarize(verdict, findings, plan);
  const note: SpecialistNote = {
    at: new Date().toISOString(),
    verdict,
    summary,
    label: state.changeSet?.label ?? state.label,
  };
  return {
    verdict,
    summary,
    specialistNotes: [note],
    steps: ["verdict"],
  };
};

const synthesize = async (
  state: typeof TestDevState.State,
  config?: { configurable?: { synthesisEnabled?: boolean } },
): Promise<typeof TestDevState.Update> => {
  const result = await synthesizeTestDev({
    verdict: state.verdict ?? "",
    summary: state.summary ?? "",
    findings: state.findings ?? [],
    plan: state.plan,
    scopeGraphIds: state.scopeGraphIds,
    commands: state.commands,
    gssc5ContextText: state.gssc5ContextText,
    enabled: config?.configurable?.synthesisEnabled,
  });
  return {
    narrativeSummary: result.narrativeSummary,
    proposedMemoryUpdates: result.proposedMemoryUpdates,
    synthesisNote: result.note,
    steps: ["synthesize"],
  };
};

const builder = new StateGraph(TestDevState)
  .addNode("parse_changeset", parseChangeset)
  .addNode("load_gssc5_context", loadGssc5Context)
  .addNode("analyze", analyzeScope)
  .addNode("finalize", finalize)
  .addNode("synthesize", synthesize)
  .addEdge("__start__", "parse_changeset")
  .addEdge("parse_changeset", "load_gssc5_context")
  .addEdge("load_gssc5_context", "analyze")
  .addEdge("analyze", "finalize")
  .addEdge("finalize", "synthesize");

export const graph = compileWithMemory(builder, {
  name: "GSSC Test Development",
});
