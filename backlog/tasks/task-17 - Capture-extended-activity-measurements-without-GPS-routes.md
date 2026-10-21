---
id: TASK-17
title: Capture extended activity measurements without GPS routes
status: Done
assignee:
  - '@codex'
created_date: '2026-10-21 05:39'
updated_date: '2026-10-21 05:52'
labels: []
dependencies: []
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Preserve available Garmin activity details and recorded measurements beyond normalized analytics while removing route coordinates and account credentials.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 Extended endpoints and sanitized FIT measurements persist without coordinates or route geometry
- [x] #2 Existing records upgrade resumably and missing resources remain observable
- [x] #3 Read-only paginated MCP detail access, documentation and offline tests pass
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Inspect installed SDK and source endpoint formats. 2. Add privacy filtering and versioned detail sidecars including FIT decoding. 3. Wire default running capture, resumable upgrades and bounded MCP access. 4. Test location filtering, malformed responses, failure recovery and compatibility; document limitations.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented schema v2 capture manifests with v1 compatibility, sanitized source sidecars, full installed activity endpoint coverage, linked workouts, in-memory strict FIT decoding, resumable upgrades and paginated read-only MCP. Validation: uv sync --locked; 119 pytest tests passed; compileall and git diff --check passed. A read-only live smoke test against one recent run returned 1593 chart samples and 1639 FIT messages; no activity exports written. Other devices/UI parity and full historical backfill remain unverified. No commit, push or deployment performed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Expanded default running capture to retain available source fields and original recorded sensor/RR measurements while filtering GPS routes/coordinates and account identity. Added checksummed detail sidecars, automatic upgrades/repair and get_activity_data MCP pagination. Verified by 119 passing tests and a successful read-only live smoke test.
<!-- SECTION:FINAL_SUMMARY:END -->
