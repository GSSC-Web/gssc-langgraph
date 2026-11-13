import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

/** True when a value looks like a git remote URL (not a filesystem path). */
export function looksLikeGitUrl(value: string): boolean {
  const v = value.trim();
  return (
    /^https?:\/\//i.test(v) ||
    /^git@/i.test(v) ||
    /^ssh:\/\//i.test(v) ||
    /^git:\/\//i.test(v) ||
    v.endsWith(".git")
  );
}

/**
 * Resolve an **existing** gssc5 checkout that owns `.agents/` (no clone).
 *
 * Order:
 * 1. Explicit `override` argument (filesystem path — not a URL)
 * 2. `GSSC5_ROOT` env (filesystem path — not a URL)
 * 3. Sibling checkout `../gssc5` relative to cwd
 * 4. `./gssc5` under cwd
 *
 * For clone/fetch into a cache dir, use `ensureGssc5Checkout`.
 * Returns `""` when no usable local root is found.
 */
export function resolveGssc5Root(
  override?: string,
  cwd: string = process.cwd(),
): string {
  const candidates: string[] = [];

  if (override?.trim()) {
    if (looksLikeGitUrl(override)) return "";
    candidates.push(resolve(cwd, override.trim()));
  }

  const env = process.env.GSSC5_ROOT?.trim();
  if (env) {
    if (looksLikeGitUrl(env)) {
      // Path-only env; URLs belong in GSSC5_REPO_URL.
    } else {
      candidates.push(resolve(cwd, env));
    }
  }

  candidates.push(resolve(cwd, "..", "gssc5"));
  candidates.push(resolve(cwd, "gssc5"));

  for (const root of candidates) {
    if (isGssc5Root(root)) return root;
  }
  return "";
}

export function isGssc5Root(root: string): boolean {
  if (!root) return false;
  return (
    existsSync(join(root, ".agents", "skills")) ||
    existsSync(join(root, ".agents", "memories")) ||
    existsSync(join(root, ".agents", "agents.md"))
  );
}

export function agentsDir(root: string): string {
  return join(root, ".agents");
}
