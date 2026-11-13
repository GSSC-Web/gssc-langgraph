---
id: kaneo-unblock-reeval
name: kaneo-unblock-reeval
description: >-
  After a Kaneo GLG task is Done on master, reevaluate outgoing blocks targets:
  promote to Ready to Start when all blockers Done and DoR met. Use at every
  Done closeout or when owner asks unblock reevaluation.
enabled: true
---

# Kaneo unblock reevaluation

**When:** End of every Kaneo/GLG task that reaches **Done** (master land + Fix Version set), or owner asks to reevaluate Ready to Start.

**Result:** Eligible targets → Ready to Start (`to-do`) with DoR Satisfied true; others stay Not Ready / Planned with notes.

## Steps

1. On the closed task, `get_task_relations` → collect outgoing `blocks` (`sourceTaskId` = this task).
2. For each target, list incoming `blocks`; eligible when every source is Done.
3. Read target DoR / DoR Satisfied. If DoR met and blockers clear: DoR Satisfied `true`, status `to-do`. Else leave Not Ready / Planned; update DoR text only when facts changed.
4. Do not promote Planned / backlog enhancement or defect tickets unless the owner includes them.
5. Report Ready vs still-blocked (by which ticket) vs DoR gaps.

## Notes

- Prefer Kaneo `blocks` over prose deps.
- Integration-only merges do not count as Done for unblock.
- Stay on project **GLG**; do not move GSSC5 tickets from this skill.
