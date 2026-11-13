/** Shared types for the closeout_review workflow. */

export type CloseoutVerdict = "PASS" | "FAIL";

export type FindingSeverity = "error" | "warning" | "info";

/**
 * Closeout checks mapped from gssc5 peer skills:
 * requirements-closeout-review, software-closeout-review, test-closeout-review.
 */
export type CloseoutCheckId =
  | "scope"
  | "contracts"
  | "software_trace"
  | "software_match"
  | "software_quality"
  | "third_party"
  | "test_coverage"
  | "test_target"
  | "secrets";

export type CloseoutFinding = {
  check: CloseoutCheckId;
  severity: FindingSeverity;
  path?: string;
  /** Optional contract / assistant / requirement id when known. */
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

export type CloseoutReport = {
  verdict: CloseoutVerdict;
  summary: string;
  findings: CloseoutFinding[];
  checksRun: CloseoutCheckId[];
};

/**
 * How the caller scoped this closeout turn (for short-lived Cursor agents).
 * Provide at least one of: Kaneo task id, PR scope, UID list, or files/diff.
 */
export type CloseoutInputScope = {
  /** Kaneo task id when reviewing a tracked defect/task. */
  kaneoTaskId?: string;
  /**
   * PR / git scope hint (e.g. `origin/master...HEAD`, PR URL, or branch name).
   * Informational for synthesis; CLI still collects the change set separately.
   */
  prScope?: string;
  /** Explicit requirement / assistant / contract UIDs in scope. */
  uids?: string[];
};

/** Proposed gssc5 memory update from optional LLM synthesis (advisory only). */
export type ProposedMemoryUpdate = {
  /** Target memory id (e.g. `backend-arch`) or `new:<slug>`. */
  memoryId: string;
  /** Short proposed text / bullet to add or revise. */
  summary: string;
  rationale?: string;
};

export type CloseoutSynthesis = {
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

/** Durable per-thread note appended by finalize when using MemorySaver. */
export type ReviewMemoryNote = {
  at: string;
  verdict: CloseoutVerdict;
  summary: string;
  label?: string;
};
