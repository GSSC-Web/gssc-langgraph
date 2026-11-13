---
id: kaneo-task-ready
name: kaneo-task-ready
description: >-
  Promote a Kaneo GLG task from Not Ready to Ready to Start when blockers are
  Done and Definition of Ready is met; set DoR Satisfied true. Use when grooming
  or after unblock eligibility.
enabled: true
---

# Kaneo task ready

**When:** A Not Ready (or equivalent) **GLG** task has clear blockers and met DoR, or owner asks to promote Ready to Start.

**Result:** Status `to-do` (Ready to Start) and DoR Satisfied `true`, or a note of remaining gaps.

## Steps

1. Read task DoR, DoR Satisfied, Issue Type, and incoming `blocks`.
2. Confirm every blocking source is Done (or no blockers).
3. Confirm DoR text is met (typical: scope locked for LangGraph/Python eng work; acceptance and PR/link path known; deps named).
4. If met: set DoR Satisfied `true` and status `to-do`. If not: leave Not Ready / Planned; update DoR only when facts changed.
5. Do not promote Planned backlog Defect/Enhancement unless the owner pulls them into the wave.
