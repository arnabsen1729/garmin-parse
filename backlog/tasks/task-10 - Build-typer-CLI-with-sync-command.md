---
id: TASK-10
title: Build typer CLI with sync command
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-3
dependencies:
  - TASK-9
type: feature
ordinal: 10000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
cli.py exposes a single 'sync' command: authenticate, list activities, diff against existing IDs, fetch+render new ones, print summary count.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 uv run garmin-parse sync performs an end-to-end sync against a real Garmin account
- [ ] #2 Re-running sync immediately reports 0 new activities and makes no redundant API calls
<!-- AC:END -->
