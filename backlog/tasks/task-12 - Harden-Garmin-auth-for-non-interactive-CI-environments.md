---
id: TASK-12
title: Harden Garmin auth for non-interactive CI environments
status: To Do
assignee: []
created_date: '2026-08-21 13:51'
labels: []
milestone: m-4
dependencies: []
type: feature
ordinal: 12000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
In auth.py, before falling through to interactive input()/getpass prompts, check sys.stdin.isatty(). If not a TTY, raise GarminAuthError immediately with a clear message instead of hanging/crashing with an unhandled EOFError. This is required for the upcoming GitHub Actions workflow, where a cached token that's invalid/expired must fail cleanly rather than hang.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 When cached token login fails and stdin is not a TTY, get_client raises GarminAuthError with an actionable message, and input()/getpass are never called
- [ ] #2 Existing interactive behavior (TTY present) is unchanged
- [ ] #3 New unit test in tests/test_auth.py covers the non-interactive case; full suite still passes
<!-- AC:END -->
