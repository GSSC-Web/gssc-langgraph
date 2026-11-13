# gssc5 skills / memories in LangGraph

This service **consumes** [GSSC-Web/gssc5](https://github.com/GSSC-Web/gssc5) Dot Agents content as turn context. It does not scaffold a `.agents/` tree here and does not modify gssc5.

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
| 1 | Explicit `root` / `configurable.gssc5Root` (tests, Studio) |
| 2 | `GSSC5_ROOT` environment variable (absolute or cwd-relative) |
| 3 | Sibling checkout `../gssc5` next to this repo |

HTTP / git-submodule fetch is **not** required for local/dev: point `GSSC5_ROOT` at a normal clone. If no root is found, loaders return an empty bundle with a `note` and graphs continue.

```bash
# .env
GSSC5_ROOT=/path/to/gssc5
```

## API

```ts
import {
  loadGssc5Context,
  loadGssc5ContextForRole,
  createLoadGssc5ContextNode,
  resolveGssc5Root,
} from "../gssc5/index.js";
```

- `listSkills` / `listMemories` — catalog from `.agents/`
- `selectAndLoad` — keyword + preference scoring, then read file bodies
- `loadGssc5ContextForRole("software" | "test" | "general")` — role presets
- `createLoadGssc5ContextNode({ role, queryField })` — reusable LangGraph node

### Relevance (practical, Bun/TS)

1. Tokenize the query (goal / requirements / paths).
2. Score each skill/memory: id/name/description/tag overlap, `importance: high`, role `prefer*`, domain heuristics (`closeout`, `backend`, `kaneo`, …).
3. Always include `requireSkills` / `requireMemories` when present in the catalog.
4. Cap defaults: 3 skills, 2 memories.

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

Not wired: `health` (and other one-shot smoke / model-free checkers that do not need Dot Agents text).

## Tests

Fixture checkout: `tests/fixtures/gssc5/.agents/…`  
Suite: `tests/gssc5_context.test.ts` (`bun test`).
