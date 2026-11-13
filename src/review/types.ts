/** Shared change-set types for tooling CLIs (collect + software / test_dev). */

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
