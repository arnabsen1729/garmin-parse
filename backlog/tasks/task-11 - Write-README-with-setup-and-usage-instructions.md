---
id: TASK-11
title: Write README with setup and usage instructions
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 21:10'
labels: []
milestone: m-3
dependencies:
  - TASK-10
type: docs
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Document prerequisites (uv), first-run auth flow (email/password + MFA), running uv run garmin-parse sync, and where output lands.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A new user can follow the README to get from clone to a synced activities/ folder
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Replaced uv-generated README stub with full setup/usage docs: prerequisites, uv sync setup, first-run auth/MFA flow with token caching, sync usage and output layout, per-file content explanation (stats-page equivalent, no raw time-series, by design for LLM pasting), unofficial-library caveat, and test-running instructions.
<!-- SECTION:NOTES:END -->
