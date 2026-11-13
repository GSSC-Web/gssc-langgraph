# gssc5 skills / memories in LangGraph

This service **consumes** [GSSC-Web/gssc5](https://github.com/GSSC-Web/gssc5) Dot Agents content as turn context. It does not scaffold a `.agents/` tree here and does not modify upstream gssc5.

## Source layout (gssc5)

```text
gssc5/
└── .agents/
    ├── agents.md
    ├── system-prompt.md
    ├── agents/<role>/agent.md      # profiles (software, test, …)
    ├── skills/<id>/SKILL.md        # closeout + Kaneo skills
    └── memories/<id>.md            # durable arch notes (tags + importance)
```

Agents load by **path**: guidelines first, then role profile, then skills/memories when relevant. This package mirrors that selection for graphs that benefit from the text (plan/closeout context), without embedding Dot Agents as the product.

## How this service locates gssc5

| Priority | Mechanism |
| --- | --- |
| 1 | Explicit `root` / `configurable.gssc5Root` — **filesystem path only** |
| 2 | `GSSC5_ROOT` — **filesystem path only** (not a URL) |
| 3 | Sibling checkout `../gssc5` (or `./gssc5`) next to cwd |
| 4 | Auto-checkout: shallow `git clone` / `git fetch` of `GSSC5_REPO_URL` into `GSSC5_CACHE_DIR` |

`GSSC5_ROOT` is never treated as a remote. For a custom clone URL use `GSSC5_REPO_URL`.

```bash
# Prefer an existing local clone (path, not URL):
GSSC5_ROOT=/path/to/gssc5

# Or let the service clone/update into a cache dir:
# GSSC5_CACHE_DIR=~/.cache/gssc-langgraph/gssc5-repo
# GSSC5_REPO_URL=https://github.com/GSSC-Web/gssc5.git
# GSSC5_REF=master
# GSSC5_AUTO_CHECKOUT=true   # default; set false to disable network
```

Default cache: `$XDG_CACHE_HOME/gssc-langgraph/gssc5-repo` (else `~/.cache/gssc-langgraph/gssc5-repo`). Checkout lands at `<cache>/gssc5`.

If checkout fails (no git, offline, bad URL), loaders return an empty bundle with a `note` and graphs continue.

## API

```ts
import {
  loadGssc5Context,
  loadGssc5ContextForRole,
  createLoadGssc5ContextNode,
  ensureGssc5Checkout,
  resolveGssc5Root,
} from "../gssc5/index.js";
```

- `ensureGssc5Checkout` — local path first, else clone/fetch into cache
- `listSkills` / `listMemories` — catalog from `.agents/`
- `selectAndLoad` — keyword + preference scoring, then read file bodies
- `loadGssc5ContextForRole("software" | "test" | "general" | "reviewer")` — role presets
- `createLoadGssc5ContextNode({ role, queryField })` — reusable LangGraph node

### Role presets

| Role | Prefer skills | Prefer memories |
| --- | --- | --- |
| `software` | software + requirements closeout | `backend-arch`, `public-arch`, `members-arch` |
| `test` | test + requirements closeout | same arch trio |
| `general` | (none) | same arch trio |
| `reviewer` | all three peer closeout skills | same arch trio |

`CLOSEOUT_PEER_SKILL_IDS` = `requirements-closeout-review`, `software-closeout-review`, `test-closeout-review`.  
`ARCH_MEMORY_IDS` = `backend-arch`, `public-arch`, `members-arch`.

### Relevance (practical, Bun/TS)

1. Tokenize the query (goal / requirements / paths).
2. Score each skill/memory: id/name/description/tag overlap, `importance: high`, role `prefer*`, domain heuristics (`closeout`, `backend`, `kaneo`, …).
3. Always include `requireSkills` / `requireMemories` when present in the catalog.
4. Cap defaults: 3 skills, 2 memories (closeout_review uses 3 / 3 with hard-requires).

### State fields written

| Field | Meaning |
| --- | --- |
| `gssc5Context` | Structured bundle (`skills`, `memories`, `selected`, `note`, `root`) |
| `gssc5ContextText` | Flattened markdown for prompts |
| `gssc5Root` | Resolved checkout path (may be `""`) |
| `steps` | Includes `load_gssc5_context` |

## Wired graphs

| Graph | Role preset | Notes |
| --- | --- | --- |
| `software_dev` | `software` | After `parse_input`; requires `software-closeout-review` when available |
| `test_development` | `test` | After `parse_changeset`; requires `test-closeout-review`; query from label + paths |
| `closeout_review` | `reviewer` | After `parse_changeset`; `requireSkills` = all three peer closeout skills; `requireMemories` = arch trio every run |

Not wired: `health` / `conversation` (smoke assistants that do not need Dot Agents text).

## Tests

Fixture checkout: `tests/fixtures/gssc5/.agents/…`  
Suite: `tests/gssc5_context.test.ts` (`bun test`) — auto-checkout covered with a mock `git` runner (no network). Closeout graph wiring also covered in `tests/closeout_review.test.ts`.
