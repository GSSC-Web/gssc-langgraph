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
