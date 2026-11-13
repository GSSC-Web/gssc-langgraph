/**
 * Agentic software development workflow (model-free plan/checks + optional LLM
 * synthesis).
 *
 * Behavioral reference: gssc5 software agent + software-closeout-review
 * (scope → implement → third-party-first → PASS/FAIL). Implemented here as a
 * Bun/TypeScript LangGraph — not a Dot Agents `.agents/` scaffold.
 *
 * Invoke via Agent Server assistant id `software_dev`, or `bun run software`.
 * Compiled with MemorySaver (`compileWithMemory`): pass `configurable.thread_id`
 * so `specialistNotes` accumulate across runs on the same thread.
 *
 * Naming note: sibling `test_dev` owns test-bot paths; this graph stays under
 * `software_dev` / `src/software/`.
 *
 * Optional synthesis (xAI chat helper) runs after deterministic checks and
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
  CHECK_RUNNERS,
  summarize,
  verdictFrom,
} from "../../software/checks.js";
import { buildPlan } from "../../software/plan.js";
import { synthesizeSoftware } from "../../software/synthesize.js";
import type {
  ChangeSet,
  ChangedFile,
  PlanStep,
  ProposedMemoryUpdate,
  SoftwareCheckId,
  SoftwareFinding,
  SoftwareVerdict,
  SpecialistNote,
} from "../../software/types.js";

const FindingAnnotation = Annotation<SoftwareFinding[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const StepsAnnotation = Annotation<string[]>({
  reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
  default: () => [],
});

const PlanAnnotation = Annotation<PlanStep[]>({
  reducer: (_left, right) => right ?? [],
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

const SoftwareState = Annotation.Root({
  /** Free-text development goal / task brief. */
  goal: Annotation<string>(),
  /** Optional requirements / LLR excerpt (informational for plan). */
  requirements: Annotation<string>(),
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
  plan: PlanAnnotation,
  findings: FindingAnnotation,
  checksRun: Annotation<SoftwareCheckId[]>({
    reducer: (left, right) => [...(left ?? []), ...(right ?? [])],
    default: () => [],
  }),
  verdict: Annotation<SoftwareVerdict | "">(),
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

function buildChangeSet(state: typeof SoftwareState.State): ChangeSet | null {
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

  if (files.length === 0 && !state.diff?.trim()) return null;

  return {
    label: state.label?.trim() || (state.diff ? "diff" : "files"),
    files,
    diff: state.diff,
  };
}

const parseInput = async (
  state: typeof SoftwareState.State,
): Promise<typeof SoftwareState.Update> => {
  const changeSet = buildChangeSet(state);
  return {
    changeSet,
    goal: state.goal ?? "",
    steps: ["parse_input"],
  };
};

const loadGssc5Context = async (
  state: typeof SoftwareState.State,
  config?: { configurable?: { gssc5Root?: string; gssc5Enabled?: boolean } },
): Promise<typeof SoftwareState.Update> => {
  const query = [state.goal, state.requirements].filter(Boolean).join("\n");
  const bundle = loadGssc5ContextForRole("software", {
    query,
    root: config?.configurable?.gssc5Root,
    enabled: config?.configurable?.gssc5Enabled,
    requireSkills: ["software-closeout-review"],
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

const planWork = async (
  state: typeof SoftwareState.State,
): Promise<typeof SoftwareState.Update> => {
  const goal = (state.goal ?? "").trim();
  const req = (state.requirements ?? "").trim();
  const combined = [goal, req].filter(Boolean).join("\n");
  const plan = buildPlan(combined || goal, state.changeSet ?? null);
  return {
    plan,
    steps: ["plan_work"],
  };
};

function makeCheckNode(checkId: SoftwareCheckId) {
  return async (
    state: typeof SoftwareState.State,
  ): Promise<typeof SoftwareState.Update> => {
    const findings = CHECK_RUNNERS[checkId](
      state.goal ?? "",
      state.changeSet ?? null,
    );
    return {
      findings,
      checksRun: [checkId],
      steps: [`check_${checkId}`],
    };
  };
}

const finalize = async (
  state: typeof SoftwareState.State,
): Promise<typeof SoftwareState.Update> => {
  const findings = state.findings ?? [];
  const plan = state.plan ?? [];
  const verdict = verdictFrom(findings);
  const summary = summarize(verdict, findings, plan.length);
  const note: SpecialistNote = {
    at: new Date().toISOString(),
    verdict,
    summary,
    label: state.changeSet?.label ?? state.label,
    goal: (state.goal ?? "").trim() || undefined,
  };
  return {
    verdict,
    summary,
    specialistNotes: [note],
    steps: ["verdict"],
  };
};

const synthesize = async (
  state: typeof SoftwareState.State,
  config?: { configurable?: { synthesisEnabled?: boolean } },
): Promise<typeof SoftwareState.Update> => {
  const result = await synthesizeSoftware({
    verdict: state.verdict ?? "",
    summary: state.summary ?? "",
    goal: state.goal,
    plan: state.plan,
    findings: state.findings ?? [],
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

const builder = new StateGraph(SoftwareState)
  .addNode("parse_input", parseInput)
  .addNode("load_gssc5_context", loadGssc5Context)
  .addNode("plan_work", planWork)
  .addNode("check_scope", makeCheckNode("scope"))
  .addNode("check_trace", makeCheckNode("trace"))
  .addNode("check_match", makeCheckNode("match"))
  .addNode("check_quality", makeCheckNode("quality"))
  .addNode("check_third_party", makeCheckNode("third_party"))
  .addNode("check_discipline", makeCheckNode("discipline"))
  .addNode("finalize", finalize)
  .addNode("synthesize", synthesize)
  .addEdge("__start__", "parse_input")
  .addEdge("parse_input", "load_gssc5_context")
  .addEdge("load_gssc5_context", "plan_work")
  .addEdge("plan_work", "check_scope")
  .addEdge("check_scope", "check_trace")
  .addEdge("check_trace", "check_match")
  .addEdge("check_match", "check_quality")
  .addEdge("check_quality", "check_third_party")
  .addEdge("check_third_party", "check_discipline")
  .addEdge("check_discipline", "finalize")
  .addEdge("finalize", "synthesize");

export const graph = compileWithMemory(builder, {
  name: "GSSC Software Dev",
});
