# GraphResponse v2 consumer contract

Shared envelope for `GSSC_Software_Dev`, `GSSC_Test_Development`,
`GSSC_Closeout_Review`, `GSSC_Health`, and (thinly) `GSSC_Conversation`.

Coordinators and short-lived workers **branch on `response.verdict` only** —
do not parse `narrativeSummary` / synthesis prose for PASS/FAIL/ERROR.

## Envelope

```json
{
  "schemaVersion": "2",
  "tool": "GSSC_Closeout_Review",
  "label": "GSSC5-65",
  "verdict": "PASS|FAIL|ERROR",
  "summary": "≤240 chars",
  "findings": [{ "code": "changeset.required", "severity": "error", "message": "…" }],
  "nextActions": [{ "action": "retry_with_fixed_input", "owner": "worker" }],
  "digest": { "chatOneLiner": "…", "prBodyMarkdown": "…" },
  "friction": { "fileOnKaneo": false, "notes": "" },
  "domains": ["backend"],
  "contextRef": { "root": "…", "cacheKey": "…", "skillIds": [], "memoryIds": [] },
  "payload": {}
}
```

LangGraph state also keeps legacy top-level fields (`verdict`, `summary`, …)
and nests the canonical object at **`response`**.

## Verdict semantics (GLG-36)

| Verdict | Meaning |
| --- | --- |
| `PASS` | Inputs valid; no blocking findings |
| `FAIL` | Inputs valid; review/plan found blocking issues — fix the work |
| `ERROR` | Bad/missing inputs, schema violation, oversized content, unparseable changeSet — fix inputs and retry |

Prose-only Closeout `diff` (no `changeSet.files`, no `diff --git`) → **`ERROR`**
with `findings[].code = "changeset.required"`.

## Lean changeSet (GLG-39)

Canonical request:

- `changeSet.files[{ path, status }]` + unified `diff` (`diff --git` headers)
- `ChangedFile.content` is **optional and discouraged**
- Guidance: keep request bodies ≤32KB; a single file `content` >16KB → `ERROR` (`input.content_too_large`)

## DomainPin (GLG-38)

`domains` is always present on SoftDev/TestDev (and Closeout when paths allow):

`backend` | `public-fe` | `members-fe` | `admin-fe` | `langgraph` | `unknown`

Optional request field `domainHint` is honored. Mixed changeSets emit **multiple**
domains and dual-domain plan/commands (not winner-take-all). Never default
gssc5 app tickets to Python/`src/gssc_langgraph`.

## SoftDev `payload.plan[]` (GLG-42)

```json
{ "id": "tests", "title": "…", "domain": "backend", "kind": "test",
  "paths": ["…"], "commands": ["bun test"] }
```

## TestDev gates (GLG-40)

`payload.testCases[]` and `payload.gaps[]`. Blocking gaps → **FAIL** (not soft PASS).

## Slim context (GLG-41)

Default responses omit skill/memory `content`/`body`. Use `contextRef` plus
optional `includeContextBodies: true` for debug only.

## Size budgets (GLG-43)

- Target ≤24KB typical `response` JSON; hard cap ~48KB with `truncated: true`
- Drop optional narrative before verdict / findings / nextActions
- `digest.chatOneLiner` ≤120 chars

## Kaneo friction (GLG-37)

`digest.chatOneLiner`, `digest.prBodyMarkdown`, and `friction` are always present
(empty friction when none).
