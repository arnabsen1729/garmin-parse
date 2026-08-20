---
id: TASK-1
title: Scaffold uv-managed Python project
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
labels: []
milestone: m-0
dependencies: []
type: chore
ordinal: 1000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Initialize pyproject.toml + src/garmin_parse layout via uv; add garminconnect and typer dependencies.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 uv init produces a working pyproject.toml + src layout
- [ ] #2 garminconnect and typer added via uv add and present in pyproject.toml/uv.lock
- [ ] #3 uv run python -c 'import garmin_parse' succeeds
<!-- AC:END -->
