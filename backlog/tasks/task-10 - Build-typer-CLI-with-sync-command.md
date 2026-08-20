---
id: TASK-10
title: Build typer CLI with sync command
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 21:09'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Built src/garmin_parse/cli.py: typer app with a 'sync' command (kept as a named subcommand via an empty @app.callback(), which stops Typer's single-command auto-collapse). sync calls auth.get_client(), then activities.fetch_new_activities(client, activities_dir), flattens each returned bundle via a local _flatten_bundle() helper ({**bundle['summary'], detail/splits/hr_zones: bundle[...]}) and passes it to render.write_activity_file(). Prints 'N new activities saved' or '0 new activities — already up to date'. GarminAuthError from auth and any exception from fetch_new_activities are caught and turned into a clean stderr message + exit code 1 instead of a traceback. Updated pyproject.toml [project.scripts] to garmin_parse.cli:main. Added tests/test_cli.py (4 tests, typer.testing.CliRunner, fully mocked auth/activities/render) covering: bundle flattening + per-bundle write calls + count message, zero-new-activities message, auth failure clean error, mid-sync fetch failure clean error. Full suite: 30 passed. Manually verified 'uv run garmin-parse --help' and 'uv run garmin-parse sync --help'.
<!-- SECTION:NOTES:END -->
