import { resolveGssc5Root } from "./root.js";
import { selectAndLoad } from "./select.js";
import {
  ROLE_PRESETS,
  type Gssc5ContextBundle,
  type Gssc5RoleHint,
  type LoadGssc5ContextOptions,
} from "./types.js";

export function emptyGssc5Context(
  note: string,
  query = "",
): Gssc5ContextBundle {
  return {
    root: "",
    query,
    skills: [],
    memories: [],
    selected: [],
    note,
  };
}

/**
 * Load a relevance-filtered bundle of gssc5 skills + memories.
 * Safe when gssc5 is missing: returns an empty bundle with a note.
 */
export function loadGssc5Context(
  options: LoadGssc5ContextOptions = {},
): Gssc5ContextBundle {
  const query = (options.query ?? "").trim();
  if (options.enabled === false) {
    return emptyGssc5Context("disabled", query);
  }

  const root = resolveGssc5Root(options.root);
  if (!root) {
    return emptyGssc5Context(
      "gssc5 root not found (set GSSC5_ROOT or place a sibling ../gssc5 checkout)",
      query,
    );
  }

  const { skills, memories, selected } = selectAndLoad(root, options);
  const note =
    skills.length + memories.length === 0
      ? "no skills/memories met the relevance threshold"
      : `loaded ${skills.length} skill(s), ${memories.length} memor${memories.length === 1 ? "y" : "ies"} from ${root}`;

  return {
    root,
    query,
    skills,
    memories,
    selected,
    note,
  };
}

export function loadGssc5ContextForRole(
  role: Gssc5RoleHint,
  options: LoadGssc5ContextOptions = {},
): Gssc5ContextBundle {
  const preset = ROLE_PRESETS[role];
  return loadGssc5Context({
    ...options,
    preferSkills: [
      ...(preset.preferSkills ?? []),
      ...(options.preferSkills ?? []),
    ],
    preferMemories: [
      ...(preset.preferMemories ?? []),
      ...(options.preferMemories ?? []),
    ],
  });
}

/** Flatten selected docs into a single prompt-friendly string. */
export function formatGssc5Context(bundle: Gssc5ContextBundle): string {
  if (!bundle.skills.length && !bundle.memories.length) {
    return bundle.note || "(no gssc5 context)";
  }
  const parts: string[] = [];
  for (const skill of bundle.skills) {
    parts.push(`## Skill: ${skill.id}\n\n${skill.body.trim()}`);
  }
  for (const memory of bundle.memories) {
    parts.push(`## Memory: ${memory.id}\n\n${memory.body.trim()}`);
  }
  return parts.join("\n\n---\n\n");
}
