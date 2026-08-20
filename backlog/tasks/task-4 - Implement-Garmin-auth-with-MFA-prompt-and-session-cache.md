---
id: TASK-4
title: Implement Garmin auth with MFA prompt and session cache
status: To Do
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 19:47'
labels: []
milestone: m-1
dependencies:
  - TASK-1
type: feature
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
auth.py wraps garminconnect.Garmin login, prompts for MFA code on first login, persists session via garth token cache so re-runs skip MFA until expiry.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 First run prompts for email/password and MFA code when required
- [ ] #2 Second run within token lifetime does not re-prompt for MFA
- [ ] #3 No credentials are written into the git repo
<!-- AC:END -->
