/**
 * Types for loading gssc5 Dot Agents skills / memories into LangGraph state.
 *
 * Source layout (sibling repo GSSC-Web/gssc5, read-only):
 *   .agents/skills/<id>/SKILL.md
 *   .agents/memories/<id>.md
 */

export type Gssc5DocKind = "skill" | "memory";

export interface Gssc5DocMeta {
  id: string;
  kind: Gssc5DocKind;
  /** Absolute or resolved path under the gssc5 root. */
  path: string;
  /** Relative path from `.agents/` (e.g. `skills/foo/SKILL.md`). */
  relPath: string;
  name?: string;
  title?: string;
  description?: string;
  tags: string[];
  importance?: string;
  enabled: boolean;
}

export interface Gssc5Doc extends Gssc5DocMeta {
  /** Full markdown body including frontmatter. */
  content: string;
  /** Body without YAML frontmatter. */
  body: string;
}

export interface Gssc5ScoredDoc {
  doc: Gssc5Doc;
  score: number;
  reasons: string[];
}

export interface Gssc5ContextBundle {
  /** Resolved gssc5 checkout root, or empty when unavailable. */
  root: string;
  query: string;
  skills: Gssc5Doc[];
  memories: Gssc5Doc[];
  /** Selection diagnostics (ids + scores). */
  selected: Array<{ id: string; kind: Gssc5DocKind; score: number; reasons: string[] }>;
  /** Why nothing loaded (missing root, empty catalog, etc.). */
  note: string;
}

export interface SelectGssc5Options {
  /** Free-text query (goal, message, task brief). */
  query?: string;
  /** Soft boost for these skill ids. */
  preferSkills?: string[];
  /** Soft boost for these memory ids. */
  preferMemories?: string[];
  /** Hard-include these skill ids when present in the catalog. */
  requireSkills?: string[];
  /** Hard-include these memory ids when present in the catalog. */
  requireMemories?: string[];
  maxSkills?: number;
  maxMemories?: number;
  /** Minimum score to keep (after required docs). Default 1. */
  minScore?: number;
}

export interface LoadGssc5ContextOptions extends SelectGssc5Options {
  /** Override root resolution (tests / explicit path). */
  root?: string;
  /** Skip filesystem work when false. Default true. */
  enabled?: boolean;
}

/** Role presets used by domain graphs. */
export type Gssc5RoleHint = "software" | "test" | "general";

export const ROLE_PRESETS: Record<
  Gssc5RoleHint,
  Pick<SelectGssc5Options, "preferSkills" | "preferMemories">
> = {
  software: {
    preferSkills: ["software-closeout-review", "requirements-closeout-review"],
    preferMemories: ["backend-arch", "public-arch", "members-arch"],
  },
  test: {
    preferSkills: ["test-closeout-review", "requirements-closeout-review"],
    preferMemories: ["backend-arch", "public-arch", "members-arch"],
  },
  general: {
    preferSkills: [],
    preferMemories: ["backend-arch", "public-arch", "members-arch"],
  },
};
