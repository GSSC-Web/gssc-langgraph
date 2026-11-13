import { readdirSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { agentsDir } from "./root.js";
import {
  asBool,
  asString,
  asStringList,
  parseFrontmatter,
} from "./parse.js";
import type { Gssc5Doc, Gssc5DocMeta } from "./types.js";

export function listSkills(root: string): Gssc5DocMeta[] {
  const skillsRoot = join(agentsDir(root), "skills");
  if (!existsSync(skillsRoot)) return [];

  const out: Gssc5DocMeta[] = [];
  for (const entry of readdirSync(skillsRoot, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue;
    const skillPath = join(skillsRoot, entry.name, "SKILL.md");
    if (!existsSync(skillPath)) continue;
    const raw = readFileSync(skillPath, "utf8");
    const { meta } = parseFrontmatter(raw);
    const id = asString(meta.id) ?? entry.name;
    out.push({
      id,
      kind: "skill",
      path: skillPath,
      relPath: `skills/${entry.name}/SKILL.md`,
      name: asString(meta.name) ?? id,
      description: asString(meta.description),
      tags: asStringList(meta.tags),
      enabled: asBool(meta.enabled, true),
    });
  }
  return out.sort((a, b) => a.id.localeCompare(b.id));
}

export function listMemories(root: string): Gssc5DocMeta[] {
  const memoriesRoot = join(agentsDir(root), "memories");
  if (!existsSync(memoriesRoot)) return [];

  const out: Gssc5DocMeta[] = [];
  for (const entry of readdirSync(memoriesRoot, { withFileTypes: true })) {
    if (!entry.isFile() || !entry.name.endsWith(".md")) continue;
    const memPath = join(memoriesRoot, entry.name);
    const raw = readFileSync(memPath, "utf8");
    const { meta } = parseFrontmatter(raw);
    const stem = entry.name.replace(/\.md$/i, "");
    const id = asString(meta.id) ?? stem;
    out.push({
      id,
      kind: "memory",
      path: memPath,
      relPath: `memories/${entry.name}`,
      title: asString(meta.title) ?? id,
      name: asString(meta.title) ?? id,
      tags: asStringList(meta.tags),
      importance: asString(meta.importance),
      enabled: asBool(meta.enabled, true),
    });
  }
  return out.sort((a, b) => a.id.localeCompare(b.id));
}

export function loadDoc(meta: Gssc5DocMeta): Gssc5Doc {
  const raw = readFileSync(meta.path, "utf8");
  const { body } = parseFrontmatter(raw);
  return {
    ...meta,
    content: raw,
    body,
  };
}

export function loadDocs(metas: Gssc5DocMeta[]): Gssc5Doc[] {
  return metas.map(loadDoc);
}
