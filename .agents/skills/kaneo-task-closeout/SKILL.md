---
id: kaneo-task-closeout
name: kaneo-task-closeout
description: >-
  After master merge: set Kaneo GLG status Done, Fix Version to the landing
  release, DoD Satisfied true; then run kaneo-unblock-reeval. Use when the
  landing PR merges to master.
enabled: true
---

# Kaneo task closeout

**When:** PR for the Kaneo **GLG** task has merged to **master** (final landing). Not for integration-only land.

**Result:** Task Done with release Fix Version and DoD Satisfied; unblock reevaluation run.

## Steps

1. Confirm merge target is **master** and tip is on master.
2. Set status `done`, Fix Version to the landing release (e.g. `v26.11.3` — use the version that ships this change; keep **Future** only if the release tag is not yet chosen and owner directs otherwise), DoD Satisfied `true`. Leave Implementation as the concise PR/line already recorded.
3. Run `.agents/skills/kaneo-unblock-reeval/SKILL.md`.
4. Comment tip SHA + PR URL on the Kaneo task if not already noted.
