---
id: TASK-5
title: Scan activities/ for already-synced IDs
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 20:59'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added src/garmin_parse/existing.py with existing_activity_ids(activities_dir) walking */*.md, extracting trailing _<digits>.md as activity ID via regex, returning empty set for missing dirs and skipping non-matching filenames. Added tests/test_existing.py (4 tests, all passing) covering populated multi-year tree, missing dir, non-matching filename, and str path input.
<!-- SECTION:NOTES:END -->
