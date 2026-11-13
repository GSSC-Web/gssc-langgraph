---
id: backlog-grooming
name: backlog-grooming
description: >-
  Kaneo/GLG backlog grooming and ALM refinement: capture owner answers,
  task matrix (scope/DoR/DoD/deps/modify|create), Kaneo fields and block
  relations, board columns from DoR, optional cluster fan-out, parent Work
  Type unions. Use for ALM refinement, wave planning, or pre-code prep.
enabled: true
---

# Backlog grooming

**When:** Owner asks for backlog grooming, ALM refinement, wave planning, or preparing Kaneo tickets before implementation on **gssc-langgraph** (project GLG).

**Result:** Written matrix; Kaneo leaves/parents consistent; columns match DoR; short Ready / Not Ready / Planned / deferred report.

## Principles

- Ask when segment/order/DoR templates are open.
- No code in a grooming-only pass.
- Parallelism OK without functional deps; name deps in DoR and Kaneo `blocks`.
- Prefer LangGraph Agent Server / MCP / existing assistants over inventing new process tools.

## Steps

1. **Capture answers** — segment/order; scope per cluster; DoR/DoD templates; labels (usually Backend); ALM hygiene (branch `cursor/<name>-####`, GitHub PR, Fix Version Future→landing release, PR→Ready for Review, Done on **master** only).
2. **Matrix** — task → modify|create, wave, column, DoR Satisfied, depends, one-line scope.
3. **Kaneo prep** — description, Issue Type, DoR/DoD + Satisfied flags, Fix Version **Future**, Implementation empty until PR, labels; prefer `blocks` relations. Discover GLG via Kaneo MCP (do not embed opaque project ids).
4. **Fan-out (optional)** — lead owns parents/graph; cluster writers expand leaves only.
5. **Verify** — re-read touched tickets; fix column vs DoR, inverted `blocks`, duplicate ownership.

## Related skills

- After Done on master: `kaneo-unblock-reeval`
- Promote ready: `kaneo-task-ready`
- Create gaps: `kaneo-create-task`
