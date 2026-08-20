---
id: TASK-9
title: Write activity files with YYYY/date-type-id layout
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 21:05'
labels: []
milestone: m-2
dependencies:
  - TASK-8
type: feature
ordinal: 9000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Persist rendered Markdown to activities/YYYY/YYYY-MM-DD_ActivityType_ActivityID.md, creating year subfolders as needed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 File path matches activities/YYYY/YYYY-MM-DD_ActivityType_ActivityID.md for a real synced activity
- [ ] #2 Year subfolder is created automatically if missing
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added activity_file_path() (activities_dir/YYYY/YYYY-MM-DD_typeKey_activityId.md, typeKey sanitized to lowercase/underscores) and write_activity_file() which creates the year subfolder if missing and writes the rendered Markdown, returning the path. Covered by tests/test_render.py (path-format and on-disk creation tests).
<!-- SECTION:NOTES:END -->
