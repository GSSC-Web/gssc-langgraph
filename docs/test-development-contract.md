# test_development I/O contract

Contract for short-lived Cursor / Kaneo agents invoking assistant id `test_development` (or `uv run test-dev --json`).

Deterministic contract → coverage analysis is always model-free. gssc5 context loads via the **`test`** preset (`test-closeout-review`). Optional LLM synthesis runs only when `XAI_API_KEY` is set.

**Work-surface specialization:** gssc5 FE → Angular `*.test.ts` / `bunx ng test`; gssc5 BE (`apps/backend`) → Bun `*.test.ts` / `bun test` / `mise run //backend:test` (not `ng test`); langgraph service → pytest / `graph.invoke`. Backend-only change sets must not FE-default.

## Input

Provide **at least one** change-set signal (files and/or diff). Workspace / git collection via the CLI is the usual path.

| Field | Type | Meaning |
| --- | --- | --- |
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

**File map (structural):**

```json
{
  "label": "pr-test-dev",
  "files": {
    "langgraph.json": "{\"graphs\":{\"health\":\"./src/gssc_langgraph/graphs/health/graph.py:graph\"}}",
    "src/gssc_langgraph/graphs/health/graph.py": "from langgraph.graph import StateGraph\ngraph = StateGraph(...).compile()",
    "tests/test_graphs.py": "import pytest\n\ndef test_health():\n    assert True"
  },
  "diff": ""
}
```

CLI equivalent: `uv run test-dev --workspace` or `--diff pr.patch` (collects the file map for you). Pass `--run` to execute suggested focused `pytest` commands after analysis.

## Output

| Field | Type | Meaning |
| --- | --- | --- |
| `verdict` | `"PASS" \| "FAIL"` | Deterministic test closeout result |
| `summary` | `string` | Short deterministic summary |
| `scopeGraphIds` | `string[]` | Graph / assistant ids in scope |
| `contracts` | `Contract[]` | Behaviors permanent tests should lock |
| `coverage` | `CoverageLink[]` | Contract → test path / covered flag |
| `plan` | `PlanItem[]` | Test plan (`add_test`, `update_test`, `add_assert`, …) |
| `commands` | `string[]` | Suggested focused `pytest …` commands |
| `findings` | `Finding[]` | Per-check issues with optional `contractId` / `fix` |
| `checksRun` | `string[]` | Checks that executed (`scope`, `coverage_map`, …) |
| `steps` | `string[]` | Graph step names (`parse_changeset`, `load_gssc5_context`, `analyze`, `verdict`, `synthesize`, …) |
| `changeSet` | object \| null | Normalized change set |
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
  check: TestDevCheckId;
  severity: "error" | "warning" | "info";
  path?: string;
  graphId?: string;
  contractId?: string;
  message: string;
  fix?: string;
}
```

### Agent consumption tips

1. Treat `verdict` + `findings` as authoritative; ignore LLM text for PASS/FAIL.
2. Use `plan` + `commands` to add/update permanent pytest coverage; assert contracts, not incidental SW.
3. Use `gssc5ContextText` when drafting follow-up test stubs.
4. Surface `proposedMemoryUpdates` to a human; do not write them into gssc5 automatically.
5. Missing `XAI_API_KEY` → `synthesisNote` starts with `skipped:`; graph still returns `verdict` + `plan`.

## Required gssc5 skill (test)

When a checkout is available, `load_gssc5_context` hard-requires:

- `test-closeout-review`
