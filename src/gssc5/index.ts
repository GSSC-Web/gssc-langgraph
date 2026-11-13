/**
 * gssc5 skills/memories loader for LangGraph graphs.
 *
 * Reads Dot Agents content from a local gssc5 checkout (see `resolveGssc5Root`).
 * Does not modify gssc5; this service only consumes `.agents/` as context.
 */
export { resolveGssc5Root, isGssc5Root, agentsDir } from "./root.js";
export { parseFrontmatter } from "./parse.js";
export { listSkills, listMemories, loadDoc, loadDocs } from "./catalog.js";
export { scoreDoc, selectAndLoad, tokenize } from "./select.js";
export {
  loadGssc5Context,
  loadGssc5ContextForRole,
  formatGssc5Context,
  emptyGssc5Context,
} from "./load.js";
export { createLoadGssc5ContextNode } from "./node.js";
export type {
  Gssc5Doc,
  Gssc5DocMeta,
  Gssc5DocKind,
  Gssc5ScoredDoc,
  Gssc5ContextBundle,
  Gssc5RoleHint,
  SelectGssc5Options,
  LoadGssc5ContextOptions,
} from "./types.js";
export { ROLE_PRESETS } from "./types.js";
export type {
  Gssc5ContextNodeConfig,
  Gssc5ContextNodeState,
} from "./node.js";
