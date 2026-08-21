---
id: TASK-14
title: Document GitHub Actions setup in README
status: To Do
assignee: []
created_date: '2026-08-21 13:51'
labels: []
milestone: m-4
dependencies:
  - TASK-13
type: docs
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Add a 'Running on-demand via GitHub Actions' section to README.md: how to create a fine-grained PAT scoped to just this repo with 'Secrets: Read and write' permission and nothing else, how to store it as the SECRETS_PAT secret via 'gh secret set SECRETS_PAT' (typed directly by the user, never pasted in chat), and that a sync is triggered from the GitHub mobile app's Actions tab (Run workflow) once secrets are set up.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 README explains the PAT scope precisely (repo-limited, Secrets permission only)
- [ ] #2 README explains how to trigger a run from the GitHub mobile app
<!-- AC:END -->
