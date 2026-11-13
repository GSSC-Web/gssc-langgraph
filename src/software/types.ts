/** Shared types for the software_dev workflow. */

export type SoftwareVerdict = "PASS" | "FAIL";

export type FindingSeverity = "error" | "warning" | "info";

/** Software-closeout / development checks. */
export type SoftwareCheckId =
  | "scope"
  | "trace"
  | "match"
  | "quality"
  | "third_party"
  | "discipline";

export type SoftwareFinding = {
  check: SoftwareCheckId;
  severity: FindingSeverity;
  path?: string;
  /** Optional requirement / work-item id when known. */
  uid?: string;
  message: string;
  fix?: string;
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

export type PlanStep = {
  id: string;
  title: string;
  detail: string;
};

export type SoftwareReport = {
  verdict: SoftwareVerdict;
  summary: string;
  goal: string;
  plan: PlanStep[];
  findings: SoftwareFinding[];
  checksRun: SoftwareCheckId[];
};

/** Durable per-thread note appended by finalize when using MemorySaver. */
export type SpecialistNote = {
  at: string;
  verdict: SoftwareVerdict;
  summary: string;
  label?: string;
  goal?: string;
};

/** Proposed gssc5 memory update from optional LLM synthesis (advisory only). */
export type ProposedMemoryUpdate = {
  /** Target memory id (e.g. `backend-arch`) or `new:<slug>`. */
  memoryId: string;
  /** Short proposed text / bullet to add or revise. */
  summary: string;
  rationale?: string;
};

export type SoftwareSynthesis = {
  /** Short natural-language summary for humans / Cursor agents. */
  narrativeSummary: string;
  /** Suggested memory edits — never applied automatically. */
  proposedMemoryUpdates: ProposedMemoryUpdate[];
  /**
   * Why synthesis ran or was skipped
   * (`ok`, `skipped: no XAI_API_KEY`, `skipped: disabled`, `error: …`).
   */
  note: string;
};
