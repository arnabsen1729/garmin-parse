---
id: TASK-4
title: Implement Garmin auth with MFA prompt and session cache
status: Done
assignee: []
created_date: '2026-08-20 19:47'
updated_date: '2026-08-20 20:58'
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
- [x] #1 First run prompts for email/password and MFA code when required
- [x] #2 Second run within token lifetime does not re-prompt for MFA
- [x] #3 No credentials are written into the git repo
<!-- AC:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Implement src/garmin_parse/auth.py with get_client(tokenstore='~/.garminconnect'): try Garmin(prompt_mfa=cb).login(tokenstore=path) first (uses cached tokens if present); on GarminConnectAuthenticationError (no creds/cache), prompt email via input() and password via getpass.getpass(), construct new Garmin(email,password,prompt_mfa=cb), retry login(tokenstore=path); wrap final failures in a clear RuntimeError/GarminAuthError.
2. Add pytest as dev dependency via uv add --dev pytest.
3. Write tests/test_auth.py mocking garminconnect.Garmin, input, getpass to verify: cache-hit path skips prompting; cache-miss path prompts email/password and retries; prompt_mfa callable uses input(); password never read via input().
4. Run uv run pytest tests/test_auth.py -q and confirm pass.
5. Update backlog task status to Done with notes.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Implemented src/garmin_parse/auth.py: get_client(tokenstore) first attempts Garmin(prompt_mfa=_prompt_mfa).login(tokenstore=path) with no credentials to resume cached garth tokens (no prompting). On GarminConnectAuthenticationError (no/invalid cache), prompts email via input() and password via getpass.getpass(), constructs a fresh Garmin(email, password, prompt_mfa=_prompt_mfa), and retries login(tokenstore=path); library persists tokens to tokenstore internally. Any residual failure is wrapped in GarminAuthError with an actionable message. No credentials are ever written to disk or logged; only garminconnect's own token cache file is persisted. Added pytest as dev dep (uv add --dev pytest) and tests/test_auth.py mocking garminconnect.Garmin/input/getpass to verify: (1) cache-hit path skips prompting entirely (covers AC2 - no re-prompt while cache valid), (2) cache-miss path prompts for email/password and retries with fresh credentials (AC1), (3) prompt_mfa uses input(), (4) password is only ever read via getpass.getpass, never input() (AC3 - no plaintext credential exposure), (5) final failure raises GarminAuthError. Ran: uv run pytest tests/test_auth.py -q -> 5 passed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Added src/garmin_parse/auth.py exposing get_client(tokenstore='~/.garminconnect') that resumes cached garth/garminconnect tokens silently when valid, otherwise interactively prompts for email/password (getpass for password) and MFA code, then lets garminconnect persist the session to tokenstore. Verified with mocked unit tests (tests/test_auth.py, 5 tests) since no live Garmin credentials are available in this environment; uv run pytest tests/test_auth.py -q passed 5/5.
<!-- SECTION:FINAL_SUMMARY:END -->
