---
id: TASK-13
title: Add GitHub Actions workflow_dispatch sync workflow
status: Done
assignee: []
created_date: '2026-08-21 13:51'
updated_date: '2026-08-21 14:02'
labels: []
milestone: m-4
dependencies:
  - TASK-12
type: feature
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add .github/workflows/sync.yml: workflow_dispatch trigger only (no cron), permissions: contents: write. Steps: checkout, set up uv, restore secrets.GARMIN_TOKENSTORE to ~/.garminconnect/garmin_tokens.json, run 'uv run garmin-parse sync' (continue-on-error so later steps still run on failure), commit+push any new activities/ files (skip cleanly if no diff), refresh the GARMIN_TOKENSTORE secret via 'gh secret set' using a separate secrets.SECRETS_PAT (a fine-grained PAT scoped to just this repo's Secrets: write permission), then fail the job if the sync step failed.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Workflow only has a workflow_dispatch trigger, no schedule
- [ ] #2 A manual run with a valid cached token in GARMIN_TOKENSTORE completes without any interactive prompt
- [ ] #3 New activity files, if any, are committed and pushed to the branch/PR; a run with nothing new makes no empty commit
- [ ] #4 The GARMIN_TOKENSTORE secret is rewritten via gh secret set after the run regardless of whether the sync step succeeded
- [ ] #5 The job is reported as failed if the sync step failed, even though commit/secret-refresh still ran
<!-- AC:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added .github/workflows/sync.yml: workflow_dispatch-only trigger (no cron), contents:write permission. Steps: checkout, install uv (astral-sh/setup-uv pinned by SHA to v10.0.1 -- no python-version-file input exists on that action, so relies on uv sync natively reading the repo's .python-version=3.14), uv sync --locked, restore GARMIN_TOKENSTORE secret to ~/.garminconnect/garmin_tokens.json without ever echoing it, run 'garmin-parse sync' with continue-on-error/id=sync, commit+push activities/ only if git diff --cached is non-empty (if: always()), refresh GARMIN_TOKENSTORE via gh secret set authenticated with SECRETS_PAT (if: always(), tolerates missing token file), and a final step that exit 1s if steps.sync.outcome == 'failure'. Validated by parsing the YAML with pyyaml (uv run --with pyyaml) -- parses cleanly. Verified astral-sh/setup-uv input names and current pinned SHA/tag via a research subagent reading the action's actual action.yml/README rather than guessing. NOT live-tested end-to-end: no real GARMIN_TOKENSTORE/SECRETS_PAT secrets exist in this environment and none were created, so an actual workflow_dispatch run against Garmin/GitHub has not been exercised -- that verification is pending once real secrets are seeded.
<!-- SECTION:NOTES:END -->
