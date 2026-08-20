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

## Out of scope (deferred)
- Visualization / dashboard tool — revisit once there's a real need, likely requires adding structured (JSON) output alongside Markdown.
- Scheduled/automatic sync (cron/launchd) — manual CLI trigger only for now.
