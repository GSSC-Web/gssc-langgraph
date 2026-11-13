import { listMemories, listSkills, loadDoc } from "./catalog.js";
import type {
  Gssc5Doc,
  Gssc5DocMeta,
  Gssc5ScoredDoc,
  SelectGssc5Options,
} from "./types.js";

const STOP = new Set([
  "a",
  "an",
  "the",
  "and",
  "or",
  "to",
  "of",
  "for",
  "in",
  "on",
  "with",
  "by",
  "is",
  "are",
  "be",
  "as",
  "at",
  "from",
  "this",
  "that",
  "it",
  "its",
  "into",
  "via",
  "use",
  "using",
  "when",
  "before",
  "after",
  "each",
  "per",
  "not",
  "no",
  "vs",
]);

/** Tokenize a query for keyword overlap scoring. */
export function tokenize(text: string): string[] {
  return text
    .toLowerCase()
    .split(/[^a-z0-9_@.-]+/)
    .map((t) => t.trim())
    .filter((t) => t.length >= 2 && !STOP.has(t));
}

function haystack(meta: Gssc5DocMeta): string {
  return [
    meta.id,
    meta.name,
    meta.title,
    meta.description,
    meta.tags.join(" "),
    meta.importance,
    meta.relPath,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function scoreDoc(
  meta: Gssc5DocMeta,
  tokens: string[],
  preferIds: Set<string>,
): Gssc5ScoredDoc {
  const reasons: string[] = [];
  let score = 0;
  const hay = haystack(meta);

  if (preferIds.has(meta.id)) {
    score += 10;
    reasons.push(`prefer:${meta.id}`);
  }

  if (meta.importance === "high") {
    score += 1;
    reasons.push("importance:high");
  }

  for (const token of tokens) {
    if (meta.id === token || meta.id.includes(token)) {
      score += 5;
      reasons.push(`id:${token}`);
      continue;
    }
    if (meta.tags.some((t) => t.toLowerCase() === token || t.toLowerCase().includes(token))) {
      score += 4;
      reasons.push(`tag:${token}`);
      continue;
    }
    if (hay.includes(token)) {
      score += 2;
      reasons.push(`text:${token}`);
    }
  }

  // Lightweight domain heuristics for common gssc5 terms.
  if (tokens.includes("closeout") && meta.id.includes("closeout")) {
    score += 3;
    reasons.push("heuristic:closeout");
  }
  if (
    (tokens.includes("backend") || tokens.includes("elysia") || tokens.includes("prisma")) &&
    meta.id === "backend-arch"
  ) {
    score += 4;
    reasons.push("heuristic:backend");
  }
  if (
    (tokens.includes("public") || tokens.includes("angular") || tokens.includes("frontend")) &&
    (meta.id === "public-arch" || meta.id === "members-arch")
  ) {
    score += 3;
    reasons.push("heuristic:frontend");
  }
  if (
    (tokens.includes("kaneo") || tokens.includes("ticket") || tokens.includes("defect")) &&
    meta.id.startsWith("kaneo-")
  ) {
    score += 4;
    reasons.push("heuristic:kaneo");
  }

  return {
    doc: {
      ...meta,
      content: "",
      body: "",
    },
    score,
    reasons: [...new Set(reasons)],
  };
}

function pick(
  scored: Gssc5ScoredDoc[],
  requiredIds: string[],
  max: number,
  minScore: number,
  catalog: Map<string, Gssc5DocMeta>,
): Gssc5ScoredDoc[] {
  const chosen = new Map<string, Gssc5ScoredDoc>();

  for (const id of requiredIds) {
    const meta = catalog.get(id);
    if (!meta || !meta.enabled) continue;
    const existing = scored.find((s) => s.doc.id === id);
    chosen.set(id, existing ?? { doc: { ...meta, content: "", body: "" }, score: 100, reasons: [`require:${id}`] });
  }

  const ranked = [...scored]
    .filter((s) => s.doc.enabled && s.score >= minScore)
    .sort((a, b) => b.score - a.score || a.doc.id.localeCompare(b.doc.id));

  for (const s of ranked) {
    if (chosen.size >= max) break;
    if (!chosen.has(s.doc.id)) chosen.set(s.doc.id, s);
  }

  return [...chosen.values()].sort(
    (a, b) => b.score - a.score || a.doc.id.localeCompare(b.doc.id),
  );
}

/**
 * Select and load relevant skills + memories for a turn/task.
 * Practical keyword + preference scoring (no embedding model required).
 */
export function selectAndLoad(
  root: string,
  options: SelectGssc5Options = {},
): {
  skills: Gssc5Doc[];
  memories: Gssc5Doc[];
  selected: Array<{
    id: string;
    kind: "skill" | "memory";
    score: number;
    reasons: string[];
  }>;
} {
  const tokens = tokenize(options.query ?? "");
  const maxSkills = options.maxSkills ?? 3;
  const maxMemories = options.maxMemories ?? 2;
  const minScore = options.minScore ?? 1;

  const skillMetas = listSkills(root).filter((m) => m.enabled);
  const memoryMetas = listMemories(root).filter((m) => m.enabled);

  const preferSkills = new Set(options.preferSkills ?? []);
  const preferMemories = new Set(options.preferMemories ?? []);

  const scoredSkills = skillMetas.map((m) => scoreDoc(m, tokens, preferSkills));
  const scoredMemories = memoryMetas.map((m) =>
    scoreDoc(m, tokens, preferMemories),
  );

  const skillCatalog = new Map(skillMetas.map((m) => [m.id, m]));
  const memoryCatalog = new Map(memoryMetas.map((m) => [m.id, m]));

  const pickedSkills = pick(
    scoredSkills,
    options.requireSkills ?? [],
    maxSkills,
    minScore,
    skillCatalog,
  );
  const pickedMemories = pick(
    scoredMemories,
    options.requireMemories ?? [],
    maxMemories,
    minScore,
    memoryCatalog,
  );

  const skills = pickedSkills.map((s) => loadDoc(skillCatalog.get(s.doc.id)!));
  const memories = pickedMemories.map((s) =>
    loadDoc(memoryCatalog.get(s.doc.id)!),
  );

  return {
    skills,
    memories,
    selected: [
      ...pickedSkills.map((s) => ({
        id: s.doc.id,
        kind: "skill" as const,
        score: s.score,
        reasons: s.reasons,
      })),
      ...pickedMemories.map((s) => ({
        id: s.doc.id,
        kind: "memory" as const,
        score: s.score,
        reasons: s.reasons,
      })),
    ],
  };
}
