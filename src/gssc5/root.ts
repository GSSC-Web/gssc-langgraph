import { existsSync } from "node:fs";
import { join, resolve } from "node:path";

/**
 * Resolve the gssc5 checkout that owns `.agents/`.
 *
 * Order:
 * 1. Explicit `override` argument
 * 2. `GSSC5_ROOT` env (absolute or cwd-relative)
 * 3. Sibling checkout `../gssc5` relative to this package root
 *
 * Returns `""` when no usable root is found (graphs no-op gracefully).
 */
export function resolveGssc5Root(
  override?: string,
  cwd: string = process.cwd(),
): string {
  const candidates: string[] = [];

  if (override?.trim()) {
    candidates.push(resolve(cwd, override.trim()));
  }

  const env = process.env.GSSC5_ROOT?.trim();
  if (env) {
    candidates.push(resolve(cwd, env));
  }

  // Package root when tests/CLI run from repo; also try cwd itself as langgraph root.
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
