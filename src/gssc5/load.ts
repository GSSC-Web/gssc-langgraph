import { ensureGssc5Checkout } from "./checkout.js";
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
 *
 * Resolves an existing local checkout first; otherwise clones/updates
 * GSSC-Web/gssc5 into a cache directory (see `ensureGssc5Checkout`).
 */
export function loadGssc5Context(
  options: LoadGssc5ContextOptions = {},
): Gssc5ContextBundle {
  const query = (options.query ?? "").trim();
  if (options.enabled === false) {
    return emptyGssc5Context("disabled", query);
  }

  const checkout = ensureGssc5Checkout({
    root: options.root,
    autoCheckout: options.autoCheckout,
    cacheDir: options.cacheDir,
    repoUrl: options.repoUrl,
    ref: options.ref,
  });

  if (!checkout.root) {
    return emptyGssc5Context(checkout.note, query);
  }

  const { skills, memories, selected } = selectAndLoad(checkout.root, options);
  const note =
    skills.length + memories.length === 0
      ? `no skills/memories met the relevance threshold (${checkout.note})`
      : `loaded ${skills.length} skill(s), ${memories.length} memor${
          memories.length === 1 ? "y" : "ies"
        } from ${checkout.root} (${checkout.source})`;

  return {
    root: checkout.root,
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
