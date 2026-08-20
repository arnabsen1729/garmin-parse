---
id: TASK-6
title: Fetch activity list and per-activity detail from Garmin Connect
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 21:01'
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
- [x] #1 Lists full account activity history newest-first
- [x] #2 Skips detail fetch for IDs already present locally
- [x] #3 Fetches splits/HR-zone detail needed for the stats-page render
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built src/garmin_parse/activities.py with fetch_new_activities(client, activities_dir, page_size=100, stop_after_consecutive_known=20). Pages client.get_activities newest-first, skips IDs already in existing_activity_ids(), fetches get_activity/get_activity_splits/get_activity_hr_in_timezones per new activity with each sub-call wrapped individually (failure -> None + warning, activity still returned). Pagination stops once a run of consecutive already-known IDs (default 20) is seen or a short/empty page is returned; get_activities itself is not caught so auth/API failures propagate. Added tests/test_activities.py with a FakeClient stub covering: skip-known/no-detail-calls, full-detail-fetch-for-new, isolated sub-call failure (one endpoint down doesn't drop the activity or its other fields), pagination stop on consecutive-known threshold and on short page, empty account, and propagation of get_activities failures. uv run pytest tests/test_activities.py -q: 8 passed; full suite uv run pytest -q: 17 passed, no regressions.
<!-- SECTION:NOTES:END -->
