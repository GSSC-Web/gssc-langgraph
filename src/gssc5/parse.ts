/**
 * Minimal YAML frontmatter parser for gssc5 skill/memory markdown.
 * Handles the subset used in Dot Agents files (scalars, simple lists).
 */

export interface ParsedFrontmatter {
  meta: Record<string, unknown>;
  body: string;
  raw: string;
}

const FM_RE = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/;

export function parseFrontmatter(raw: string): ParsedFrontmatter {
  const m = FM_RE.exec(raw);
  if (!m) {
    return { meta: {}, body: raw, raw };
  }
  return {
    meta: parseSimpleYaml(m[1] ?? ""),
    body: (m[2] ?? "").trimStart(),
    raw,
  };
}

function parseSimpleYaml(block: string): Record<string, unknown> {
  const meta: Record<string, unknown> = {};
  const lines = block.split(/\r?\n/);
  let i = 0;
  while (i < lines.length) {
    const line = lines[i]!;
    i += 1;
    if (!line.trim() || line.trimStart().startsWith("#")) continue;

    const folded = line.match(/^([A-Za-z0-9_-]+):\s*>-\s*$/);
    if (folded) {
      const key = folded[1]!;
      const parts: string[] = [];
      while (i < lines.length) {
        const next = lines[i]!;
        if (/^\S/.test(next) && next.includes(":")) break;
        if (!next.trim()) {
          i += 1;
          break;
        }
        parts.push(next.trim());
        i += 1;
      }
      meta[key] = parts.join(" ").trim();
      continue;
    }

    const kv = line.match(/^([A-Za-z0-9_-]+):\s*(.*)$/);
    if (!kv) continue;
    const key = kv[1]!;
    const rest = (kv[2] ?? "").trim();

    if (rest.startsWith("[") && rest.endsWith("]")) {
      meta[key] = rest
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean);
      continue;
    }

    if (rest === "" || rest === "|" || rest === ">" || rest === ">-") {
      const parts: string[] = [];
      while (i < lines.length) {
        const next = lines[i]!;
        if (/^\S/.test(next) && next.includes(":")) break;
        parts.push(next.trim());
        i += 1;
      }
      const joinWithSpace = rest === ">" || rest === ">-";
      meta[key] = parts.join(joinWithSpace ? " " : "\n").trim();
      continue;
    }

    if (rest === "true" || rest === "false") {
      meta[key] = rest === "true";
      continue;
    }

    meta[key] = rest.replace(/^["']|["']$/g, "");
  }
  return meta;
}

export function asString(value: unknown): string | undefined {
  if (typeof value === "string" && value.trim()) return value.trim();
  return undefined;
}

export function asStringList(value: unknown): string[] {
  if (Array.isArray(value)) {
    return value
      .map((v) => (typeof v === "string" ? v.trim() : String(v)))
      .filter(Boolean);
  }
  if (typeof value === "string" && value.trim()) {
    return value
      .split(/[,\s]+/)
      .map((s) => s.trim())
      .filter(Boolean);
  }
  return [];
}

export function asBool(value: unknown, fallback = true): boolean {
  if (typeof value === "boolean") return value;
  if (typeof value === "string") {
    const v = value.trim().toLowerCase();
    if (v === "true") return true;
    if (v === "false") return false;
  }
  return fallback;
}
