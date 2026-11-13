/** Shared types for the service_review workflow. */

export type ReviewVerdict = "PASS" | "FAIL";

export type FindingSeverity = "error" | "warning" | "info";

export type ReviewCheckId =
  | "registry"
  | "graph_quality"
  | "stack"
  | "gssc5_contract"
  | "tests"
  | "secrets";

export type Finding = {
  check: ReviewCheckId;
  severity: FindingSeverity;
  path?: string;
  message: string;
  fix?: string;
};

export type ChangedFile = {
  path: string;
  /** Full file contents when available (workspace / collected files). */
  content?: string;
  /** Unified-diff hunks for this path when reviewing a diff. */
  patch?: string;
  status: "added" | "modified" | "deleted" | "unchanged";
};

export type ChangeSet = {
  /** Human label: e.g. git base ref or "workspace". */
  label: string;
  files: ChangedFile[];
  /** Raw unified diff when present. */
  diff?: string;
};

export type ReviewReport = {
  verdict: ReviewVerdict;
  summary: string;
  findings: Finding[];
  checksRun: ReviewCheckId[];
};
