---
id: TASK-8
title: Render type-specific activity sections
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-2
dependencies:
  - TASK-7
type: feature
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Dispatch by activity category (running/cycling/swimming/strength/other) to render extra fields as Markdown tables: cadence/vertical oscillation/stride length (running), power (cycling), stroke/SWOLF/pool length (swimming), sets/reps/exercises (strength).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Running, cycling, swimming, and strength activities each render their extra fields correctly
- [ ] #2 Unrecognized/other activity types still render the generic section without erroring
<!-- AC:END -->
