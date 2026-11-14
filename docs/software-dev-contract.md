# software_dev I/O contract

Contract for short-lived Cursor / Kaneo agents invoking assistant id `software_dev` (or `uv run software --json`).

Deterministic plan + software closeout checks are always model-free. gssc5 context loads via the **`software`** preset (`software-closeout-review`). Optional LLM synthesis runs only when `XAI_API_KEY` is set.

**Work-surface specialization:** planners detect **gssc5 FE**, **gssc5 BE**, **mixed** (dual-domain BE Bun + FE ng — not winner-take-all), vs **langgraph service**. Backend-only must not FE-default; mixed must keep both. Synthesis must not invent markers/tests absent from `changeSet` paths.

## Input

Provide a **goal** and/or a change set. Prefer combining a goal with files/diff when closing out concrete work.

| Field | Type | Meaning |
| --- | --- | --- |
| `goal` | `string` | Free-text development goal / task brief (recommended) |
| `requirements` | `string` | Optional LLR / requirements excerpt (feeds the plan) |
| `files` | `Record<string, string>` | Path → file contents (primary change-set form) |
| `fileStatuses` | `Record<string, "added"\|"modified"\|"deleted"\|"unchanged">` | Optional statuses for `files` |
| `diff` | `string` | Optional unified diff (paths merged into the change set) |
| `label` | `string` | Human label for the change set |
| `changeSet` | object | Pre-built `{ label, files[], diff? }` (skips rebuild when present) |

### RunnableConfig overrides

| Key | Meaning |
| --- | --- |
| `configurable.gssc5Root` | Filesystem path to a gssc5 checkout |
| `configurable.gssc5Enabled` | Set `false` to skip gssc5 load |
| `configurable.synthesisEnabled` | Set `false` to skip LLM synthesis even when a key is present |

### Minimal examples

**Goal only (plan):**

```json
{
  "goal": "Add a membership lookup graph with Elysia-style handlers"
}
```

**Goal + file map + diff (plan + closeout):**

```json
{
  "goal": "Register membership graph and cover it with pytest",
  "label": "pr-software",
  "files": {
    "langgraph.json": "{\"graphs\":{\"health\":\"./src/gssc_langgraph/graphs/health/graph.py:graph\"}}",
    "src/gssc_langgraph/graphs/membership/graph.py": "from langgraph.graph import StateGraph\ngraph = StateGraph(...).compile()"
  },
  "diff": ""
}
```

CLI equivalent: `uv run software --goal "…" --workspace` or `--diff pr.patch` (collects the file map for you). Use `--plan-only` to skip change-set collection.

## Output

| Field | Type | Meaning |
| --- | --- | --- |
| `verdict` | `"PASS" \| "FAIL"` | Deterministic software closeout result |
| `summary` | `string` | Short deterministic summary |
| `plan` | `PlanStep[]` | Ordered implementation steps (`id`, `title`, `detail`) |
| `findings` | `SoftwareFinding[]` | Per-check issues with optional `uid` / `fix` |
| `checksRun` | `string[]` | Checks that executed (`scope`, `trace`, `match`, …) |
| `steps` | `string[]` | Graph step names (`parse_input`, `load_gssc5_context`, `plan_work`, `check_*`, `verdict`, `synthesize`, …) |
| `changeSet` | object \| null | Normalized change set (null for plan-only) |
| `gssc5Context` | object \| null | Structured skills/memories bundle |
| `gssc5ContextText` | `string` | Flattened markdown for prompts |
| `gssc5Root` | `string` | Resolved checkout path (may be `""`) |
| `narrativeSummary` | `string` | LLM NL summary, or deterministic `summary` when synthesis skipped |
| `proposedMemoryUpdates` | `{ memoryId, summary, rationale? }[]` | Advisory only — never auto-applied |
| `synthesisNote` | `string` | `ok` \| `skipped: no XAI_API_KEY` \| `skipped: disabled` \| `error: …` |
| `specialistNotes` | object[] | Durable per-thread notes via Agent Server threads (or `compile_with_memory` in tests) |

### Finding shape

```ts
{
  check: SoftwareCheckId;
  severity: "error" | "warning" | "info";
  path?: string;
  uid?: string;
  message: string;
  fix?: string;
}
```

### Agent consumption tips

1. Treat `verdict` + `findings` as authoritative; ignore LLM text for PASS/FAIL.
2. Follow `plan` for implementation order; peer with `test_development` for test closeout.
3. Use `gssc5ContextText` when drafting follow-up fixes.
4. Surface `proposedMemoryUpdates` to a human; do not write them into gssc5 automatically.
5. Missing `XAI_API_KEY` → `synthesisNote` starts with `skipped:`; graph still returns `verdict` + `plan`.

## Required gssc5 skill (software)

When a checkout is available, `load_gssc5_context` hard-requires:

- `software-closeout-review`
