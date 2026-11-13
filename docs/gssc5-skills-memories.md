# gssc5 skills / memories in LangGraph

This service **consumes** [GSSC-Web/gssc5](https://github.com/GSSC-Web/gssc5) Dot Agents content as turn context for specialist graphs. It does not modify upstream gssc5.

Separately, **this repo** has its own Dot Agents tree under [`.agents/`](../.agents/agents.md) (Kaneo **GLG** process, backlog/Kaneo skills, weekly tasks). That local tree is not a substitute for upstream gssc5 closeout skills.

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

## How this service locates gssc5

| Priority | Mechanism |
| --- | --- |
| 1 | Explicit `root` / `configurable.gssc5Root` — **filesystem path only** |
| 2 | `GSSC5_ROOT` — **filesystem path only** (not a URL) |
| 3 | Sibling checkout `../gssc5` (or `./gssc5`) next to cwd |
| 4 | Auto-checkout: shallow `git clone` / `git fetch` of `GSSC5_REPO_URL` into `GSSC5_CACHE_DIR` |

```bash
GSSC5_ROOT=/path/to/gssc5
# Or let the service clone/update into a cache dir:
# GSSC5_CACHE_DIR=~/.cache/gssc-langgraph/gssc5-repo
# GSSC5_REPO_URL=https://github.com/GSSC-Web/gssc5.git
# GSSC5_REF=master
# GSSC5_AUTO_CHECKOUT=true
```

Default cache: `$XDG_CACHE_HOME/gssc-langgraph/gssc5-repo` (else `~/.cache/gssc-langgraph/gssc5-repo`). Checkout lands at `<cache>/gssc5`.

If checkout fails, loaders return an empty bundle with a `note` and graphs continue.

## API

```python
from gssc_langgraph.gssc5 import (
    load_gssc5_context,
    load_gssc5_context_for_role,
    create_load_gssc5_context_node,
    ensure_gssc5_checkout,
    resolve_gssc5_root,
)
```

- `ensure_gssc5_checkout` — local path first, else clone/fetch into cache
- `list_skills` / `list_memories` — catalog from `.agents/`
- `select_and_load` — keyword + preference scoring, then read file bodies
- `load_gssc5_context_for_role("software" | "test" | "general" | "reviewer")` — role presets
- `create_load_gssc5_context_node({ role, query_field })` — reusable LangGraph node

### Role presets

| Role | Prefer skills | Prefer memories |
| --- | --- | --- |
| `software` | software + requirements closeout | `backend-arch`, `public-arch`, `members-arch` |
| `test` | test + requirements closeout | same arch trio |
| `general` | (none) | same arch trio |
| `reviewer` | all three peer closeout skills | same arch trio |

`CLOSEOUT_PEER_SKILL_IDS` = `requirements-closeout-review`, `software-closeout-review`, `test-closeout-review`.  
`ARCH_MEMORY_IDS` = `backend-arch`, `public-arch`, `members-arch`.

### Relevance

1. Tokenize the query (goal / requirements / paths).
2. Score each skill/memory: id/name/description/tag overlap, `importance: high`, role `prefer*`, domain heuristics.
3. Always include `require_skills` / `require_memories` when present in the catalog.
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
| `software_dev` | `software` | After `parse_input`; requires `software-closeout-review` when available; append-only `specialistNotes` (Agent Server threads) |
| `test_development` | `test` | After `parse_changeset`; requires `test-closeout-review`; query from label + paths; append-only `specialistNotes` (Agent Server threads) |
| `closeout_review` | `reviewer` | After `parse_changeset`; `requireSkills` = all three peer closeout skills; `requireMemories` = arch trio every run; append-only `reviewMemory` (Agent Server threads) |

These specialists can run with Agent Server / SDK threads so prior `specialistNotes` / `reviewMemory` persist for the `thread_id`. Pass `configurable.thread_id` (or create a thread) — CLI one-shots mint a fresh id per run. API-exported graphs do **not** attach a custom checkpointer; Agent Server handles persistence (set `POSTGRES_URI` for a durable DB). Use `compile_with_memory` only in tests / direct invoke helpers.

Not wired for gssc5 context: `health` / `conversation` (smoke assistants that do not need Dot Agents text).

## Tests

Fixture checkout: `tests/fixtures/gssc5/.agents/…`  
Suite: `tests/test_gssc5_context.py` (`pytest`).
