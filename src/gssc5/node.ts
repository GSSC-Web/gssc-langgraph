import type { RunnableConfig } from "@langchain/core/runnables";
import { formatGssc5Context, loadGssc5ContextForRole } from "./load.js";
import type {
  Gssc5ContextBundle,
  Gssc5RoleHint,
  LoadGssc5ContextOptions,
} from "./types.js";

export interface Gssc5ContextNodeConfig {
  /** Default role preset when not overridden per-invoke. */
  role?: Gssc5RoleHint;
  /** State field used as the relevance query. */
  queryField?: string;
  /** Extra static prefer/require options. */
  loadOptions?: LoadGssc5ContextOptions;
  /** Step name recorded in `steps` when the host graph tracks them. */
  stepName?: string;
}

export interface Gssc5ContextNodeState {
  gssc5Context?: Gssc5ContextBundle | null;
  gssc5ContextText?: string;
  gssc5Root?: string;
  steps?: string[];
  [key: string]: unknown;
}

type NodeConfig = RunnableConfig<{
  gssc5Root?: string;
  gssc5Role?: Gssc5RoleHint;
  gssc5Enabled?: boolean;
  preferSkills?: string[];
  preferMemories?: string[];
  requireSkills?: string[];
  requireMemories?: string[];
}>;

/**
 * Factory for a LangGraph node that selects + loads gssc5 skills/memories.
 *
 * Writes:
 * - `gssc5Context` — structured bundle
 * - `gssc5ContextText` — flattened markdown for prompts
 * - `gssc5Root` — resolved checkout path (may be empty)
 * - `steps` — appends step name when the host uses a steps reducer
 */
export function createLoadGssc5ContextNode(
  defaults: Gssc5ContextNodeConfig = {},
) {
  const roleDefault = defaults.role ?? "general";
  const queryField = defaults.queryField ?? "message";
  const stepName = defaults.stepName ?? "load_gssc5_context";

  return async (
    state: Gssc5ContextNodeState,
    config?: NodeConfig,
  ): Promise<Partial<Gssc5ContextNodeState>> => {
    const configurable = config?.configurable ?? {};
    const role = configurable.gssc5Role ?? roleDefault;
    const rawQuery = state[queryField];
    const query =
      typeof rawQuery === "string"
        ? rawQuery
        : typeof state.goal === "string"
          ? state.goal
          : typeof state.message === "string"
            ? state.message
            : "";

    const bundle = loadGssc5ContextForRole(role, {
      ...defaults.loadOptions,
      query,
      root: configurable.gssc5Root ?? defaults.loadOptions?.root,
      enabled: configurable.gssc5Enabled ?? defaults.loadOptions?.enabled,
      preferSkills: [
        ...(defaults.loadOptions?.preferSkills ?? []),
        ...(configurable.preferSkills ?? []),
      ],
      preferMemories: [
        ...(defaults.loadOptions?.preferMemories ?? []),
        ...(configurable.preferMemories ?? []),
      ],
      requireSkills: [
        ...(defaults.loadOptions?.requireSkills ?? []),
        ...(configurable.requireSkills ?? []),
      ],
      requireMemories: [
        ...(defaults.loadOptions?.requireMemories ?? []),
        ...(configurable.requireMemories ?? []),
      ],
    });

    return {
      gssc5Context: bundle,
      gssc5ContextText: formatGssc5Context(bundle),
      gssc5Root: bundle.root,
      steps: [stepName],
    };
  };
}
