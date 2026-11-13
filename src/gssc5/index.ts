/**
 * gssc5 skills/memories loader for LangGraph graphs.
 *
 * Reads Dot Agents content from a local gssc5 checkout, or clones/updates
 * GSSC-Web/gssc5 into a cache dir (see `ensureGssc5Checkout`).
 * Does not modify upstream gssc5 content; this service only consumes `.agents/`.
 */
export {
  resolveGssc5Root,
  isGssc5Root,
  agentsDir,
  looksLikeGitUrl,
} from "./root.js";
export {
  ensureGssc5Checkout,
  checkoutGssc5ToCache,
  defaultGssc5CacheDir,
  resolveGssc5RepoUrl,
  resolveGssc5Ref,
  DEFAULT_GSSC5_REPO_URL,
  DEFAULT_GSSC5_REF,
} from "./checkout.js";
export type {
  EnsureGssc5CheckoutOptions,
  Gssc5CheckoutResult,
  GitRunner,
} from "./checkout.js";
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
