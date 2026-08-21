# garmin-parse

Syncs every Garmin Connect activity to a local Markdown file — one file per
activity — so you can paste the stats straight into any LLM chat for
analysis. A minimal static [web viewer](#web-viewer) is included for
browsing activities from a browser, and a sync can be triggered
[on demand from your phone](#running-on-demand-via-github-actions) via
GitHub Actions — see [`roadmap.md`](roadmap.md) for what's still deferred
(a richer, mobile-friendly redesign of the viewer is in progress).

## Prerequisites

- [`uv`](https://docs.astral.sh/uv/) installed
- Python 3.14+ (pinned in `.python-version`; `uv` will fetch it if needed)
- A Garmin Connect account

## Setup

```sh
uv sync
```

Installs dependencies from the lockfile into a local virtualenv.

## First run (authentication)

The first time you run `uv run garmin-parse sync`, you'll be prompted
interactively in the terminal:

```
Garmin Connect email: you@example.com
Garmin Connect password:
```

The password is read with `getpass`, so it's never echoed to the screen and
never logged. If your account has MFA enabled, you'll also be prompted for
the MFA code Garmin sends you.

On a successful login, a session token is cached to disk (`~/.garminconnect`
by default). Every subsequent run reuses that cached session, so you won't
see the email/password/MFA prompts again until the token expires.

## Usage

```sh
uv run garmin-parse sync
```

This fetches any activities that haven't already been synced and writes
each one as:

```
activities/<YYYY>/<YYYY-MM-DD>_<activity-type>_<activityId>.md
```

It prints how many new activities were saved (e.g. `12 new activities
saved`, or `0 new activities — already up to date`).

Re-running is safe and cheap: it's incremental, and stops paging through
your history as soon as it hits activities it's already synced, so it
doesn't re-walk your entire history every time.

By default it reads/writes the `activities/` directory in the current
working directory. Use `--activities-dir` to point elsewhere:

```sh
uv run garmin-parse sync --activities-dir /path/to/activities
```

## Running on-demand via GitHub Actions

`.github/workflows/sync.yml` lets you trigger a sync from your phone (or any
browser) without a terminal, using a manually-triggered GitHub Actions
workflow. This needs a one-time setup by the repo owner.

### One-time setup

1. Run `uv run garmin-parse sync` locally at least once so an authenticated
   session is cached at `~/.garminconnect/garmin_tokens.json` (see
   [First run (authentication)](#first-run-authentication) above).

2. Seed the `GARMIN_TOKENSTORE` secret from that cached session:

   ```sh
   gh secret set GARMIN_TOKENSTORE --repo <owner>/<repo> < ~/.garminconnect/garmin_tokens.json
   ```

3. Create a fine-grained GitHub Personal Access Token scoped to **only this
   repository**. There's no CLI/API way to create one, so this has to be
   done in GitHub's web UI:

   **Settings → Developer settings → Personal access tokens → Fine-grained
   tokens → Generate new token.** Set "Repository access" to this repository
   only, and under "Repository permissions" set **Secrets** to
   **"Read and write"**. Leave every other permission (including Contents)
   unset.

4. Store that token as the `SECRETS_PAT` secret:

   ```sh
   gh secret set SECRETS_PAT --repo <owner>/<repo>
   ```

   Paste the token when prompted by the terminal, not as a chat message to
   an AI assistant or anywhere else it could get logged or committed.

### Triggering a sync

Once the secrets are set up, no terminal is needed: open the repo in the
GitHub mobile app or web UI, go to the **Actions** tab, select the
**"Sync Garmin activities"** workflow, and click **"Run workflow"**.

### What happens automatically

The workflow restores the cached Garmin session from `GARMIN_TOKENSTORE`,
runs `garmin-parse sync`, and pushes any new activity files straight to the
repo. If Garmin refreshes the session token during the run, the workflow
also re-seeds the `GARMIN_TOKENSTORE` secret with the updated token — so
this should keep working indefinitely without repeating the local setup.

The one exception is if Garmin invalidates the session entirely (e.g. it
forces a fresh login or an MFA challenge). When that happens the workflow
run fails with a clear error. The fix is the same as the initial setup: run
`garmin-parse sync` locally once more to re-authenticate, then re-seed the
`GARMIN_TOKENSTORE` secret as in step 2 above.

### Trade-off

This setup stores a live Garmin session as a GitHub secret so you can
trigger syncs from your phone. That's a real trade-off, not a free lunch:
anyone with write access to repo secrets (or the `SECRETS_PAT` token) can
read out `GARMIN_TOKENSTORE` and use it to act as your Garmin session.
Only set this up if you're comfortable with that.

## What's in each file

Each Markdown file contains everything shown on Garmin's activity stats
page for that activity's type: generic stats (date, duration, distance,
average/max HR, HR zones, elevation, calories, training effect) plus a
type-specific section for running, cycling, swimming, or strength
activities (other types get the generic section only). Missing fields are
simply omitted, never rendered as blank or "N/A".

Raw per-second time-series data (e.g. second-by-second GPS/HR samples) is
intentionally left out — the goal is a compact, human-and-LLM-readable
summary you can paste into a chat without hitting context/size limits, not
a full data export.

## A note on reliability

This tool uses the unofficial [`garminconnect`](https://pypi.org/project/garminconnect/)
PyPI library to talk to Garmin Connect's web API — there is no official,
supported Garmin API for this. Garmin can change their web endpoints at any
time without notice, which could break syncing until the library (or this
tool) is updated.

## Running tests

```sh
uv run pytest
```

## Web viewer

`site/index.html` is a minimal, self-contained static page for browsing and
copying an activity's raw Markdown from a browser — useful when you want to
share a specific activity with someone without walking them through GitHub.
It has no build step and no server: it fetches the file list and raw content
straight from GitHub at page load, then renders the selected activity with a
"Copy raw data" button.

Because the page fetches from GitHub client-side with no authentication,
**the repository must be public** for it to work.

To deploy on [Vercel](https://vercel.com):

1. Import this repository as a new Vercel project.
2. Set **Root Directory** to `site`.
3. Set the framework preset to "Other" (no build command, no output
   directory override needed) — Vercel will serve `index.html` as a static
   site.

You can also just open `site/index.html` directly in a browser, or serve it
locally with `python3 -m http.server` from inside `site/`.
