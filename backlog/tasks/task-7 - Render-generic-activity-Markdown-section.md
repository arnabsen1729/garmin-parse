---
id: TASK-7
title: Render generic activity Markdown section
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-2
dependencies:
  - TASK-6
type: feature
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
render.py builds the common header/section: type, date, duration, distance, pace/speed, HR avg/max + zone table, elevation, calories, training effect. Missing fields omitted, not blank.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Generated section matches Garmin Connect stats-page fields for a running activity
- [ ] #2 Fields absent on a given activity are omitted rather than rendered blank
<!-- AC:END -->
