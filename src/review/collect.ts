import { $ } from "bun";
import { readdir, readFile, stat } from "node:fs/promises";
import { join, relative } from "node:path";
import type { ChangeSet, ChangedFile } from "./types.js";

const SKIP_DIRS = new Set([
  "node_modules",
  ".git",
  "dist",
  ".cursor",
  "coverage",
]);

async function walkFiles(root: string, dir: string): Promise<string[]> {
  const entries = await readdir(dir, { withFileTypes: true });
  const out: string[] = [];
  for (const ent of entries) {
    if (SKIP_DIRS.has(ent.name)) continue;
    const abs = join(dir, ent.name);
    if (ent.isDirectory()) {
      out.push(...(await walkFiles(root, abs)));
    } else if (ent.isFile()) {
      out.push(relative(root, abs).replaceAll("\\", "/"));
    }
  }
  return out;
}

async function readOptional(root: string, path: string): Promise<string | undefined> {
  try {
    return await readFile(join(root, path), "utf8");
  } catch {
    return undefined;
  }
}

/** Full workspace snapshot for structural review. */
export async function collectWorkspace(root: string): Promise<ChangeSet> {
  const paths = await walkFiles(root, root);
  const interesting = paths.filter(
    (p) =>
      p === "langgraph.json" ||
      p === "package.json" ||
      p === "README.md" ||
      p === ".env.example" ||
      p.startsWith("src/") ||
      p.startsWith("tests/") ||
      p.endsWith(".py") ||
      p === "pyproject.toml" ||
      p === "requirements.txt",
  );

  const files: ChangedFile[] = [];
  for (const path of interesting) {
    const content = await readOptional(root, path);
    files.push({
      path,
      content,
      status: "unchanged",
    });
  }

  return { label: "workspace", files };
}

function parseDiffPaths(diff: string): Map<string, { status: ChangedFile["status"]; patch: string }> {
  const map = new Map<string, { status: ChangedFile["status"]; patch: string }>();
  const parts = diff.split(/^diff --git /m).filter(Boolean);
  for (const part of parts) {
    const header = part.split("\n")[0] ?? "";
    const m = header.match(/a\/(.+?)\s+b\/(.+)$/);
    if (!m) continue;
    const aPath = m[1]!;
    const bPath = m[2]!;
    const body = `diff --git ${part}`;
    let status: ChangedFile["status"] = "modified";
    if (/^new file mode/m.test(part) || aPath === "/dev/null") status = "added";
    if (/^deleted file mode/m.test(part) || bPath === "/dev/null") status = "deleted";
    const path = status === "deleted" ? aPath : bPath;
    map.set(path, { status, patch: body });
  }
  return map;
}

/** Build a ChangeSet from a unified diff, enriching with on-disk file contents when present. */
export async function collectFromDiff(
  root: string,
  diff: string,
  label = "diff",
): Promise<ChangeSet> {
  const parsed = parseDiffPaths(diff);
  const files: ChangedFile[] = [];

  for (const [path, meta] of parsed) {
    let content: string | undefined;
    if (meta.status !== "deleted") {
      content = await readOptional(root, path);
    }
    files.push({
      path,
      content,
      patch: meta.patch,
      status: meta.status,
    });
  }

  // Always attach registry/package when present so contract/stack checks can run.
  for (const extra of ["langgraph.json", "package.json", "README.md", ".env.example"]) {
    if (files.some((f) => f.path === extra)) continue;
    const content = await readOptional(root, extra);
    if (content !== undefined) {
      files.push({ path: extra, content, status: "unchanged" });
    }
  }

  // Attach existing test files for coverage heuristics when graphs change.
  const graphChanged = files.some((f) => /^src\/graphs\//.test(f.path));
  if (graphChanged) {
    try {
      const testDir = join(root, "tests");
      const st = await stat(testDir);
      if (st.isDirectory()) {
        const tests = await walkFiles(root, testDir);
        for (const path of tests) {
          if (files.some((f) => f.path === path)) continue;
          const content = await readOptional(root, path);
          files.push({ path, content, status: "unchanged" });
        }
      }
    } catch {
      // no tests dir
    }
  }

  return { label, files, diff };
}

async function collectUntracked(root: string): Promise<ChangedFile[]> {
  const listed =
    await $`git -C ${root} ls-files --others --exclude-standard`.quiet().nothrow();
  if (listed.exitCode !== 0) return [];
  const paths = listed.stdout
    .toString()
    .split("\n")
    .map((p) => p.trim())
    .filter(Boolean)
    .filter(
      (p) =>
        p.startsWith("src/") ||
        p.startsWith("tests/") ||
        p === "langgraph.json" ||
        p === "package.json" ||
        p === "README.md" ||
        p === ".env.example" ||
        p.endsWith(".py") ||
        p === "pyproject.toml" ||
        p === "requirements.txt",
    );
  const files: ChangedFile[] = [];
  for (const path of paths) {
    const content = await readOptional(root, path);
    files.push({ path, content, status: "added" });
  }
  return files;
}

export async function collectGitDiff(
  root: string,
  baseRef: string,
): Promise<ChangeSet> {
  // Prefer merge-base against baseRef when possible.
  let diff = "";
  try {
    const merged =
      await $`git -C ${root} merge-base ${baseRef} HEAD`.quiet().nothrow();
    const mergeBase = merged.exitCode === 0 ? merged.stdout.toString().trim() : baseRef;
    const range = `${mergeBase}...HEAD`;
    const result = await $`git -C ${root} diff --no-ext-diff ${range}`.quiet().nothrow();
    diff = result.stdout.toString();
    const unstaged = await $`git -C ${root} diff --no-ext-diff`.quiet().nothrow();
    const staged = await $`git -C ${root} diff --no-ext-diff --cached`.quiet().nothrow();
    const extra = `${staged.stdout.toString()}${unstaged.stdout.toString()}`;
    if (extra.trim()) {
      diff = diff ? `${diff}\n${extra}` : extra;
    }
  } catch {
    const result = await $`git -C ${root} diff --no-ext-diff ${baseRef}...HEAD`.quiet().nothrow();
    diff = result.stdout.toString();
  }

  const untracked = await collectUntracked(root);

  if (!diff.trim() && untracked.length === 0) {
    // Nothing changed vs base — fall back to workspace structural review.
    const ws = await collectWorkspace(root);
    return { ...ws, label: `workspace (no diff vs ${baseRef})` };
  }

  const cs = diff.trim()
    ? await collectFromDiff(root, diff, `git ${baseRef}...HEAD`)
    : { label: `git ${baseRef}...HEAD`, files: [] as ChangedFile[] };

  for (const f of untracked) {
    if (!cs.files.some((x) => x.path === f.path)) cs.files.push(f);
  }
  // Ensure registry is present when untracked graphs appear.
  if (
    untracked.some((f) => f.path.startsWith("src/graphs/")) &&
    !cs.files.some((f) => f.path === "langgraph.json")
  ) {
    const content = await readOptional(root, "langgraph.json");
    if (content !== undefined) {
      cs.files.push({ path: "langgraph.json", content, status: "unchanged" });
    }
  }
  return cs;
}

export async function collectPaths(
  root: string,
  paths: string[],
): Promise<ChangeSet> {
  const files: ChangedFile[] = [];
  for (const path of paths) {
    const content = await readOptional(root, path);
    files.push({
      path: path.replaceAll("\\", "/"),
      content,
      status: content === undefined ? "deleted" : "modified",
    });
  }
  for (const extra of ["langgraph.json", "package.json", "README.md", ".env.example"]) {
    if (files.some((f) => f.path === extra)) continue;
    const content = await readOptional(root, extra);
    if (content !== undefined) {
      files.push({ path: extra, content, status: "unchanged" });
    }
  }
  return { label: "paths", files };
}
