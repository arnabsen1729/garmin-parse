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
- GitHub Actions workflow (`workflow_dispatch` plus daily cron) that runs `sync`, commits/pushes new activity files, and self-refreshes its cached-session secret
- README section documenting the one-time setup (fine-grained PAT, seeding secrets) and how to trigger a run from the GitHub mobile app

## Phase 6 — Mobile-friendly viewer redesign
Replace the bare `site/index.html` viewer with a real mobile-first design.
- Initial visual direction drafted via Claude Design (not yet implemented)
- Must keep: chronological activity browsing, per-activity stat view, one-tap "copy raw data" for pasting into an LLM, GitHub source link
- Constraint: stays a static page, no backend, no build step

## Original scope
Scheduled sync was originally deferred; it is now implemented below.

## Automated analytics and MCP — implemented

- Validated versioned JSON sidecars, explicit metric units, privacy allowlist.
- Streaming atomic per-activity persistence, resumable backfill, reconciliation,
  metadata detection, partial-failure reporting, local synchronization lock.
- Daily Actions target 08:00 IST, manual trigger, concurrency control, changed-only
  session refresh, job summary and progress persistence on partial failure.
- Deterministic running summaries, date/subtype/distance filters, weekly/monthly
  trends, rolling windows and arbitrary period comparisons.
- Seven read-only MCP tools with local stdio and authenticated Streamable HTTP.
- External OAuth JWT validation including owner restriction; deployment guidance.
- Offline regression and protocol tests; existing Markdown/viewer compatibility.

## Remaining

- Run an authenticated historical backfill and reconcile against live Garmin data.
- Provision OAuth provider/HTTPS hosting and validate a live ChatGPT connection;
  no provider or deployment has been created automatically.
- Decide privacy policy for public JSON before publishing historical sidecars.
- Optional private snapshot distribution from sync storage to a remote MCP host.
- More real-world fixtures for Garmin variants, unsupported DTO schemas and sport
  metrics; normalized presentation adapter for the existing Markdown renderer.
- Consider checkpointed summary pagination for unusually large histories if API
  cost warrants it; current full scans favor correctness over list-request savings.
- The mobile-friendly viewer work remains independent.


## Extended running measurements — implemented

- Default running sync captures sanitized source DTOs, chart sensor channels,
  all returned lap/split fields, HR/power zones, weather, gear and linked workouts.
- Original FIT recordings decode in memory for sensor records and recorded RR
  intervals, with GPS routes/coordinates and account identity removed.
- Versioned detail sidecars, automatic historical upgrades, checksums and repair.
- Paginated read-only MCP access through `get_activity_data`.
- Synthetic FIT and offline API/protocol/privacy/recovery tests.
- One recent run was smoke-tested read-only: 1,593 chart samples and 1,639 FIT
  messages. Other device variants and full UI parity remain unverified; UI-derived
  or account-level health metrics are not guaranteed by the activity API.
