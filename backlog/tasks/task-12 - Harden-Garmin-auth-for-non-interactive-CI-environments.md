---
id: TASK-12
title: Harden Garmin auth for non-interactive CI environments
status: Done
assignee: []
created_date: '2026-08-21 13:51'
updated_date: '2026-08-21 13:54'
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Added sys.stdin.isatty() check in get_client(): when cached-token login fails and stdin is not a TTY, raises GarminAuthError with an actionable message instead of falling through to input()/getpass prompts (which would raise EOFError in CI). Existing TTY-present prompting behavior unchanged. Added test_get_client_raises_clear_error_when_noninteractive_and_no_cached_tokens to tests/test_auth.py; patched isatty=True in existing interactive-path tests. Full suite (31 tests) passes.
<!-- SECTION:NOTES:END -->
