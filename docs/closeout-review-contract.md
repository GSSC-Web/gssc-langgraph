# closeout_review I/O contract

Contract for short-lived Cursor / Kaneo agents invoking assistant id `closeout_review` (or `uv run closeout --json`).

**v2 envelope:** every run emits `response` with `schemaVersion: "2"`. Branch on `response.verdict` (`PASS`|`FAIL`|`ERROR`). Prose-only `diff` → `ERROR` / `changeset.required`. Lean changeSet: `files[{path,status}]` + `diff --git` (full `content` discouraged). See [graph-response-v2.md](graph-response-v2.md).

Deterministic checks are always model-free. gssc5 context loads via the **`reviewer`** preset. Optional LLM synthesis runs only when `XAI_API_KEY` is set.

## Agent Server auth

When calling the Agent Server (not the local CLI), if `GSSC_LANGGRAPH_API_KEY` is set on the server, every request except `GET /ok` must include credentials:

| Header | Example |
| --- | --- |
| `Authorization: Bearer <key>` | `Authorization: Bearer $GSSC_LANGGRAPH_API_KEY` |
| `x-api-key: <key>` | `x-api-key: $GSSC_LANGGRAPH_API_KEY` |

Local `uv run langgraph dev` with an empty key (or `GSSC_LANGGRAPH_AUTH_BYPASS=true`) does not require these headers. See README [Agent Server auth](../README.md#agent-server-auth).

```bash
curl -s -N -X POST http://127.0.0.1:2024/runs/stream \
  -H "Authorization: Bearer $GSSC_LANGGRAPH_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{
    "assistant_id": "closeout_review",
    "input": {
      "label": "pr-closeout",
      "files": { "README.md": "# …" }
    }
  }'
```

```ts
import { Client } from "@langchain/langgraph-sdk";

const apiKey = process.env.GSSC_LANGGRAPH_API_KEY;
const client = new Client({
  apiUrl: process.env.GSSC_LANGGRAPH_BASE_URL ?? "http://127.0.0.1:2024",
  ...(apiKey
    ? { defaultHeaders: { Authorization: `Bearer ${apiKey}` } }
    : {}),
});

const thread = await client.threads.create();
await client.runs.wait(thread.thread_id, "closeout_review", {
  input: { label: "pr-closeout", files: { "README.md": "# …" } },
});
// Reuse thread.thread_id so reviewMemory accumulates (Agent Server persistence;
// set POSTGRES_URI for a durable store).
```

## Input

Provide **at least one** file-scoped signal. Prefer combining a change set with optional metadata.

**Required for a useful first pass:** populated `files` / `changeSet.files`, **or** a real unified diff whose body contains `diff --git` headers. A prose or summary string in `diff` alone does **not** scope file checks — the graph returns a soft **warning** (not FAIL) and asks you to retry with a structured change set.

| Field | Type | Meaning |
| --- | --- | --- |
| `files` | `Record<string, string>` | Path → file contents (**primary** change-set form; preferred) |
| `fileStatuses` | `Record<string, "added"\|"modified"\|"deleted"\|"unchanged">` | Optional statuses for `files` |
| `diff` | `string` | Optional **unified** diff (`diff --git a/… b/…`); paths merge into the change set. Prose/summary text is ignored for path extraction |
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
    "langgraph.json": "{\"graphs\":{\"health\":\"./src/gssc_langgraph/graphs/health/graph.py:graph\"}}",
    "src/gssc_langgraph/graphs/health/graph.py": "from langgraph.graph import StateGraph\ngraph = StateGraph(...).compile()"
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

CLI equivalent: `uv run closeout --workspace` or `--diff pr.patch` (collects the file map for you).

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
| `gssc5ContextText` | `string` | Flattened markdown for prompts (empty unless `includeContextBodies`) |
| `response` | object | Canonical v2 GraphResponse — **branch here** |
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

1. Treat `response.verdict` + `response.findings` as authoritative; ignore LLM text for PASS/FAIL.
2. If scope findings mention prose/`diff --git`, retry immediately with `files` or a real patch — do not treat that warning pass as a completed closeout.
3. Use `response.contextRef` by default; set `includeContextBodies: true` only when you need fat `gssc5ContextText` / skill bodies for drafting.
4. Surface `proposedMemoryUpdates` to a human; do not write them into gssc5 automatically.
5. Missing gssc5 checkout → empty `gssc5Context` + `note`; graph still returns `verdict`.
6. Missing `XAI_API_KEY` → `synthesisNote` starts with `skipped:`; graph still returns `verdict`.

## Required gssc5 skills (reviewer)

When a checkout is available, `load_gssc5_context` hard-requires:

- `requirements-closeout-review`
- `software-closeout-review`
- `test-closeout-review`

And architecture memories: `backend-arch`, `public-arch`, `members-arch`.
