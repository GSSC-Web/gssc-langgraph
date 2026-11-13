# closeout_review I/O contract

Contract for short-lived Cursor / Kaneo agents invoking assistant id `closeout_review` (or `bun run closeout --json`).

Deterministic checks are always model-free. gssc5 context loads via the **`reviewer`** preset. Optional LLM synthesis runs only when `XAI_API_KEY` is set.

## Input

Provide **at least one** scope signal. Prefer combining a change set with optional metadata.

| Field | Type | Meaning |
| --- | --- | --- |
| `files` | `Record<string, string>` | Path → file contents (primary change-set form) |
| `fileStatuses` | `Record<string, "added"\|"modified"\|"deleted"\|"unchanged">` | Optional statuses for `files` |
| `diff` | `string` | Optional unified diff (paths merged into the change set) |
| `label` | `string` | Human label for the change set (also used in the gssc5 query) |
| `changeSet` | object | Pre-built `{ label, files[], diff? }` (skips rebuild when present) |
| `kaneoTaskId` | `string` | Kaneo task / defect id |
| `prScope` | `string` | PR URL, `base...head`, or branch hint (informational) |
| `uids` | `string[]` | Explicit requirement / assistant / contract UIDs in scope |

### RunnableConfig overrides

| Key | Meaning |
| --- | --- |
| `configurable.gssc5Root` | Filesystem path to a gssc5 checkout |
| `configurable.gssc5Enabled` | Set `false` to skip gssc5 load |
| `configurable.synthesisEnabled` | Set `false` to skip LLM synthesis even when a key is present |

### Minimal examples

**File map + diff (structural):**

```json
{
  "label": "pr-closeout",
  "files": {
    "langgraph.json": "{\"graphs\":{\"health\":\"./src/graphs/health/graph.ts:graph\"}}",
    "src/graphs/health/graph.ts": "export const graph = {}"
  },
  "diff": ""
}
```

**Kaneo + PR scope + UIDs:**

```json
{
  "kaneoTaskId": "KANEO-42",
  "prScope": "https://github.com/GSSC-Web/gssc-langgraph/pull/12",
  "uids": ["health", "LLR-12"],
  "label": "KANEO-42",
  "files": { "README.md": "# …" }
}
```

CLI equivalent: `bun run closeout --workspace` or `--diff pr.patch` (collects the file map for you).

## Output

| Field | Type | Meaning |
| --- | --- | --- |
| `verdict` | `"PASS" \| "FAIL"` | Deterministic closeout result |
| `summary` | `string` | Short deterministic summary |
| `findings` | `CloseoutFinding[]` | Per-check issues with optional `uid` / `fix` |
| `checksRun` | `string[]` | Checks that executed |
| `steps` | `string[]` | Graph step names (`parse_changeset`, `load_gssc5_context`, `check_*`, `verdict`, `synthesize`, …) |
| `changeSet` | object \| null | Normalized change set |
| `gssc5Context` | object \| null | Structured skills/memories bundle (`skills`, `memories`, `selected`, `note`, `root`) |
| `gssc5ContextText` | `string` | Flattened markdown for prompts |
| `gssc5Root` | `string` | Resolved checkout path (may be `""`) |
| `narrativeSummary` | `string` | LLM NL summary, or deterministic `summary` when synthesis skipped |
| `proposedMemoryUpdates` | `{ memoryId, summary, rationale? }[]` | Advisory only — never auto-applied |
| `synthesisNote` | `string` | `ok` \| `skipped: no XAI_API_KEY` \| `skipped: disabled` \| `error: …` |

### Finding shape

```ts
{
  check: CloseoutCheckId;
  severity: "error" | "warning" | "info";
  path?: string;
  uid?: string;
  message: string;
  fix?: string;
}
```

### Agent consumption tips

1. Treat `verdict` + `findings` as authoritative; ignore LLM text for PASS/FAIL.
2. Use `gssc5ContextText` (or `gssc5Context.skills`) when drafting follow-up fixes.
3. Surface `proposedMemoryUpdates` to a human; do not write them into gssc5 automatically.
4. Missing gssc5 checkout → empty `gssc5Context` + `note`; graph still returns `verdict`.
5. Missing `XAI_API_KEY` → `synthesisNote` starts with `skipped:`; graph still returns `verdict`.

## Required gssc5 skills (reviewer)

When a checkout is available, `load_gssc5_context` hard-requires:

- `requirements-closeout-review`
- `software-closeout-review`
- `test-closeout-review`

And architecture memories: `backend-arch`, `public-arch`, `members-arch`.
