# garmin-parse

Syncs every Garmin Connect activity to a local Markdown file — one file per
activity — so you can paste the stats straight into any LLM chat for
analysis. There's no visualization/dashboard tooling here; that's explicitly
out of scope for now (see [`roadmap.md`](roadmap.md)).

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
