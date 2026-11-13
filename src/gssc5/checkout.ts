import { existsSync, mkdirSync, rmSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { spawnSync } from "node:child_process";
import { isGssc5Root, looksLikeGitUrl, resolveGssc5Root } from "./root.js";

export const DEFAULT_GSSC5_REPO_URL =
  "https://github.com/GSSC-Web/gssc5.git";
export const DEFAULT_GSSC5_REF = "master";

export type GitRunner = (
  args: string[],
  options?: { cwd?: string },
) => { status: number; stdout: string; stderr: string };

export interface EnsureGssc5CheckoutOptions {
  /** Explicit filesystem root (same as GSSC5_ROOT). Not a URL. */
  root?: string;
  /** Working directory for relative path resolution. */
  cwd?: string;
  /** Clone/update cache directory (contains a `gssc5` checkout). */
  cacheDir?: string;
  /** Git remote URL. Default: GSSC-Web/gssc5. */
  repoUrl?: string;
  /** Branch/tag/ref to check out. Default: master. */
  ref?: string;
  /**
   * When true (default), clone/fetch into the cache if no local root exists.
   * Set false for offline unit tests that only use fixtures.
   */
  autoCheckout?: boolean;
  /** Injectable git runner (tests). */
  git?: GitRunner;
}

export interface Gssc5CheckoutResult {
  root: string;
  /** How the root was obtained. */
  source: "override" | "env" | "sibling" | "cache" | "none";
  note: string;
}

export function defaultGssc5CacheDir(cwd: string = process.cwd()): string {
  const env = process.env.GSSC5_CACHE_DIR?.trim();
  if (env) return resolve(cwd, env);
  // Prefer XDG cache when available; fall back to tmp + home.
  const xdg = process.env.XDG_CACHE_HOME?.trim();
  if (xdg) return join(xdg, "gssc-langgraph", "gssc5-repo");
  const home = homedir();
  if (home) return join(home, ".cache", "gssc-langgraph", "gssc5-repo");
  return join(tmpdir(), "gssc-langgraph", "gssc5-repo");
}

export function resolveGssc5RepoUrl(override?: string): string {
  return (
    override?.trim() ||
    process.env.GSSC5_REPO_URL?.trim() ||
    DEFAULT_GSSC5_REPO_URL
  );
}

export function resolveGssc5Ref(override?: string): string {
  return (
    override?.trim() ||
    process.env.GSSC5_REF?.trim() ||
    DEFAULT_GSSC5_REF
  );
}

function autoCheckoutEnabled(override?: boolean): boolean {
  if (typeof override === "boolean") return override;
  const env = process.env.GSSC5_AUTO_CHECKOUT?.trim().toLowerCase();
  if (env === "0" || env === "false" || env === "no" || env === "off") {
    return false;
  }
  return true;
}

export const defaultGitRunner: GitRunner = (args, options) => {
  const result = spawnSync("git", args, {
    cwd: options?.cwd,
    encoding: "utf8",
    env: process.env,
  });
  return {
    status: result.status ?? 1,
    stdout: result.stdout?.toString() ?? "",
    stderr: result.stderr?.toString() ?? "",
  };
};

function isGitRepo(dir: string, git: GitRunner): boolean {
  if (!existsSync(join(dir, ".git"))) return false;
  const r = git(["rev-parse", "--is-inside-work-tree"], { cwd: dir });
  return r.status === 0 && r.stdout.trim() === "true";
}

/**
 * Clone or update gssc5 into the cache directory.
 * Returns the checkout path when `.agents/` is present.
 */
export function checkoutGssc5ToCache(
  options: EnsureGssc5CheckoutOptions = {},
): Gssc5CheckoutResult {
  const cwd = options.cwd ?? process.cwd();
  const cacheDir = resolve(
    cwd,
    options.cacheDir?.trim() || defaultGssc5CacheDir(cwd),
  );
  const target = join(cacheDir, "gssc5");
  const repoUrl = resolveGssc5RepoUrl(options.repoUrl);
  const ref = resolveGssc5Ref(options.ref);
  const git = options.git ?? defaultGitRunner;

  mkdirSync(cacheDir, { recursive: true });

  try {
    if (isGitRepo(target, git) && isGssc5Root(target)) {
      // Best-effort update; keep existing tree if fetch fails (offline).
      const fetch = git(
        ["fetch", "--depth", "1", "origin", ref],
        { cwd: target },
      );
      if (fetch.status === 0) {
        const co = git(["checkout", "-f", "FETCH_HEAD"], { cwd: target });
        if (co.status !== 0) {
          git(["checkout", "-f", ref], { cwd: target });
        }
      }
      if (isGssc5Root(target)) {
        return {
          root: target,
          source: "cache",
          note: `using cached gssc5 at ${target} (ref ${ref})`,
        };
      }
    }

    if (existsSync(target)) {
      rmSync(target, { recursive: true, force: true });
    }

    const clone = git(
      [
        "clone",
        "--depth",
        "1",
        "--branch",
        ref,
        "--single-branch",
        repoUrl,
        target,
      ],
      { cwd: cacheDir },
    );
    if (clone.status !== 0) {
      return {
        root: "",
        source: "none",
        note: `git clone failed (${repoUrl}@${ref}): ${
          clone.stderr.trim() || clone.stdout.trim() || `exit ${clone.status}`
        }`,
      };
    }

    if (!isGssc5Root(target)) {
      return {
        root: "",
        source: "none",
        note: `cloned ${repoUrl} but .agents/ not found under ${target}`,
      };
    }

    return {
      root: target,
      source: "cache",
      note: `cloned gssc5 into ${target} (ref ${ref})`,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    return {
      root: "",
      source: "none",
      note: `gssc5 checkout error: ${message}`,
    };
  }
}

/**
 * Resolve a usable gssc5 root: existing local path first, else clone/update cache.
 *
 * `GSSC5_ROOT` / `root` must be a **filesystem path**, not a git URL.
 * Use `GSSC5_REPO_URL` for a custom remote.
 */
export function ensureGssc5Checkout(
  options: EnsureGssc5CheckoutOptions = {},
): Gssc5CheckoutResult {
  const cwd = options.cwd ?? process.cwd();
  const override = options.root?.trim();

  if (override && looksLikeGitUrl(override)) {
    return {
      root: "",
      source: "none",
      note:
        "GSSC5_ROOT/root must be a filesystem path, not a URL — set GSSC5_REPO_URL for a custom remote",
    };
  }

  const envRoot = process.env.GSSC5_ROOT?.trim();
  if (envRoot && looksLikeGitUrl(envRoot) && !override) {
    return {
      root: "",
      source: "none",
      note:
        "GSSC5_ROOT must be a filesystem path, not a URL — set GSSC5_REPO_URL for a custom remote",
    };
  }

  // Prefer explicit override / env / sibling without cloning.
  if (override) {
    const resolved = resolve(cwd, override);
    if (isGssc5Root(resolved)) {
      return {
        root: resolved,
        source: "override",
        note: `using override root ${resolved}`,
      };
    }
    // Explicit root that does not exist: do not fall through to clone unless
    // caller omitted root and wants auto-checkout. Treat as hard miss.
    return {
      root: "",
      source: "none",
      note: `gssc5 root not found at override path ${resolved}`,
    };
  }

  if (envRoot) {
    const resolved = resolve(cwd, envRoot);
    if (isGssc5Root(resolved)) {
      return {
        root: resolved,
        source: "env",
        note: `using GSSC5_ROOT ${resolved}`,
      };
    }
  }

  const sibling = resolveGssc5Root(undefined, cwd);
  if (sibling) {
    const source: Gssc5CheckoutResult["source"] =
      envRoot && resolve(cwd, envRoot) === sibling ? "env" : "sibling";
    return {
      root: sibling,
      source,
      note: `using local gssc5 at ${sibling}`,
    };
  }

  if (!autoCheckoutEnabled(options.autoCheckout)) {
    return {
      root: "",
      source: "none",
      note:
        "gssc5 root not found (set GSSC5_ROOT, place sibling ../gssc5, or enable auto-checkout)",
    };
  }

  return checkoutGssc5ToCache(options);
}
