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
