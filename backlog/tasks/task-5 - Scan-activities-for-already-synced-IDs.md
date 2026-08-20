---
id: TASK-5
title: Scan activities/ for already-synced IDs
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-1
dependencies:
  - TASK-1
type: feature
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
existing.py walks activities/*/*.md, extracts trailing _<ActivityID>.md, returns set of known IDs.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Returns correct ID set on a populated activities/ tree
- [ ] #2 Returns empty set when activities/ does not exist yet
<!-- AC:END -->
