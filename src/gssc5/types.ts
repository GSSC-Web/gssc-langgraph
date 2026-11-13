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
  /**
   * Explicit filesystem path to a gssc5 checkout (not a git URL).
   * For a custom remote, set `repoUrl` / `GSSC5_REPO_URL` instead.
   */
  root?: string;
  /** Skip filesystem work when false. Default true. */
  enabled?: boolean;
  /**
   * Clone/fetch gssc5 into a cache dir when no local root exists.
   * Default true (disable with `GSSC5_AUTO_CHECKOUT=false`).
   */
  autoCheckout?: boolean;
  /** Cache directory for auto-checkout (default: XDG/home `.cache/gssc-langgraph/gssc5-repo`). */
  cacheDir?: string;
  /** Git remote URL (default `https://github.com/GSSC-Web/gssc5.git`). */
  repoUrl?: string;
  /** Branch/tag/ref for auto-checkout (default `master`). */
  ref?: string;
}

/** Role presets used by domain graphs. */
export type Gssc5RoleHint = "software" | "test" | "general" | "reviewer";

/** Architecture memories preferred (and often required) by domain graphs. */
export const ARCH_MEMORY_IDS = [
  "backend-arch",
  "public-arch",
  "members-arch",
] as const;

/** Peer closeout-review skills consumed by the closeout_review graph. */
export const CLOSEOUT_PEER_SKILL_IDS = [
  "requirements-closeout-review",
  "software-closeout-review",
  "test-closeout-review",
] as const;

export const ROLE_PRESETS: Record<
  Gssc5RoleHint,
  Pick<SelectGssc5Options, "preferSkills" | "preferMemories">
> = {
  software: {
    preferSkills: ["software-closeout-review", "requirements-closeout-review"],
    preferMemories: [...ARCH_MEMORY_IDS],
  },
  test: {
    preferSkills: ["test-closeout-review", "requirements-closeout-review"],
    preferMemories: [...ARCH_MEMORY_IDS],
  },
  general: {
    preferSkills: [],
    preferMemories: [...ARCH_MEMORY_IDS],
  },
  /** Peer closeout reviewer — all three closeout skills + arch memories. */
  reviewer: {
    preferSkills: [...CLOSEOUT_PEER_SKILL_IDS],
    preferMemories: [...ARCH_MEMORY_IDS],
  },
};
