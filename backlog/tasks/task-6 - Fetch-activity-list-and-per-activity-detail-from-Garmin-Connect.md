---
id: TASK-6
title: Fetch activity list and per-activity detail from Garmin Connect
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-1
dependencies:
  - TASK-4
  - TASK-5
type: feature
ordinal: 6000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
activities.py pages through Garmin.get_activities, fetches full detail only for IDs not already on disk (per existing.py).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Lists full account activity history newest-first
- [ ] #2 Skips detail fetch for IDs already present locally
- [ ] #3 Fetches splits/HR-zone detail needed for the stats-page render
<!-- AC:END -->
