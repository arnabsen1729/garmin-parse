# Roadmap

## Phase 1 — Project scaffolding
Set up tooling and repo plumbing so real feature work has a place to land.
- uv-managed Python project (`pyproject.toml`, src layout)
- `.gitignore`
- GitHub repo (private)

## Phase 2 — Garmin Connect sync core
Authenticate against Garmin Connect and get raw activity data flowing.
- Login + MFA-prompt + session cache (`auth.py`)
- Scan `activities/` for already-synced IDs (`existing.py`)
- Fetch activity list + per-activity detail from Garmin Connect (`activities.py`)

## Phase 3 — Markdown rendering
Turn raw activity data into the paste-into-an-LLM output format.
- Generic stats section (date, duration, distance, HR, calories, elevation, training effect)
- Type-specific sections (running / cycling / swimming / strength / other)
- File layout: `activities/YYYY/YYYY-MM-DD_ActivityType_ActivityID.md`

## Phase 4 — CLI + docs
Wire it together into something runnable.
- `typer` CLI, `uv run garmin-parse sync`
- README with setup + usage

## Phase 5 — On-demand cloud automation
Let a sync be triggered from a phone instead of needing a terminal on this Mac.
- Harden `auth.py` for non-interactive environments (clean error instead of hanging/crashing when no TTY is available and cached tokens are invalid)
- GitHub Actions workflow (`workflow_dispatch` only, no cron) that runs `sync`, commits/pushes new activity files, and self-refreshes its cached-session secret
- README section documenting the one-time setup (fine-grained PAT, seeding secrets) and how to trigger a run from the GitHub mobile app

## Out of scope (deferred)
- Further visualization/dashboard work beyond the existing `site/index.html` static viewer.
- Scheduled/cron-based sync — on-demand (`workflow_dispatch`) only for now.
