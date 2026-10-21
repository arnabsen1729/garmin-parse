# garmin-parse

Syncs Garmin Connect activities to backward-compatible Markdown and validated
JSON sidecars. Deterministic running analytics are available through a read-only
MCP server, so compatible clients can query training history without manual exports. A minimal static [web viewer](#web-viewer) is included for
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
uv sync --locked
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
activities/<YYYY>/<YYYY-MM-DD>_<activity-type>_<activityId>.json
activities/<YYYY>/<YYYY-MM-DD>_<activity-type>_<activityId>.details.json  # running activities
```

Every run prints scanned, new, updated, incomplete, skipped and failed counts.
The default sync scans all summary pages to detect new and older missed imports,
and updates records whose listing metadata changed. Complete unchanged JSON
records avoid detail requests. Missing JSON (including existing Markdown-only
history), incomplete records and interrupted Markdown/JSON writes are repaired.
Progress is saved per activity; rerunning is idempotent and resumable.

```sh
# Populate historical JSON and repair incomplete records, scanning all history
uv run garmin-parse sync --backfill

# Refetch all details, including edits invisible in listing metadata
uv run garmin-parse sync --reconcile
```

Backfill is an explicit historical coverage operation; it uses the same efficient
skip rules as incremental sync. Reconciliation intentionally makes more API calls.
The two flags are mutually exclusive. Existing Markdown is never used to invent
missing measurements. Original API records must be available for full backfill.
Existing activity filenames stay stable if Garmin changes date/type; JSON contains
the current metadata. Source deletions do not delete local records.

Exit codes: **0** successful (including no activity changes), **1** authentication,
API or persistence failure, **2** partial sync or invalid CLI options. Partial
imports are saved with missing-resource markers and retried on later runs.
A full-history success timestamp is not advanced by a partial run.

By default it reads/writes the `activities/` directory in the current
working directory. Use `--activities-dir` to point elsewhere:

```sh
uv run garmin-parse sync --activities-dir /path/to/activities
```

## Running on-demand via GitHub Actions

`.github/workflows/sync.yml` lets you trigger a sync from your phone (or any
browser) without a terminal, using a manually-triggered GitHub Actions
workflow. It also runs daily at **02:30 UTC / 08:00 IST**. This needs a one-time
setup by the repo owner. GitHub can delay or skip scheduled events; this is a
target time, not a delivery guarantee. Use the manual trigger after a missed run.

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
also re-seeds the `GARMIN_TOKENSTORE` secret **only when the cached file changed**.
The runner restricts file permissions; token contents are never printed or staged.
Runs are serialized and cannot cancel an in-progress sync. Changed Markdown/JSON
and sync state are committed, including completed work from partial runs; empty
commits are skipped. Counters appear in logs and the GitHub job summary.
Run timestamps can produce a metadata-only commit even when no activities change. Any
significant failure produces a failed workflow. Branch protection may require
explicit permission for the bot to commit directly to main.

The one exception is if Garmin invalidates the session entirely (e.g. it
forces a fresh login or an MFA challenge). When that happens the workflow
run fails with a clear error. The fix is the same as the initial setup: run
`garmin-parse sync` locally once more to re-authenticate, then re-seed the
`GARMIN_TOKENSTORE` secret as in step 2 above.

### Trade-off

This setup stores a live Garmin session as a GitHub secret so you can
trigger syncs from your phone. That's a real trade-off, not a free lunch:
someone able to edit or run a privileged workflow can potentially exfiltrate
its injected secrets. GitHub does not provide plaintext secret reads through
the secrets API. The PAT remains necessary because the normal `GITHUB_TOKEN`
does not grant repository-secret updates. Keep its scope limited to this
repository and Secrets read/write, set an expiry, and rotate it. A GitHub App
could replace the PAT but adds installation/key management; it is not configured
automatically. Garmin invalidation and PAT expiry still require manual recovery.

## What's in each file

Each Markdown file contains everything shown on Garmin's activity stats
page for that activity's type: generic stats (date, duration, distance,
average/max HR, HR zones, elevation, calories, training effect) plus a
type-specific section for running, cycling, swimming, or strength
activities (other types get the generic section only). Missing fields are
simply omitted, never rendered as blank or "N/A".

Markdown stays a compact summary. Running activities also get a separate
`.details.json` export with sanitized source fields and sensor time series,
including recorded heart-rate/cadence/power samples and FIT RR intervals when
available. GPS coordinates and route geometry are excluded. See extended
capture below for resource coverage and limitations.

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

## Structured data and analytics

JSON schema v2 (with v1 reader compatibility) is defined and validated in `src/garmin_parse/schema.py`; see
[ARCHITECTURE.md](ARCHITECTURE.md) for field units, coverage and numerical semantics.
Normalized records contain allowlisted metrics, dates, type/name, laps and
HR-zone totals. Running detail sidecars retain additional source fields after
privacy filtering. Unsanitized API payloads, owner/profile data, GPS traces and
credentials are excluded.
Missing measurements are null, never silently zero. JSON is canonical for all
computations; Markdown remains the human-readable compatibility output.

The Python analytics module supports inclusive local-date/type/distance/subtype
filters, total/weekly/monthly distance, run counts, duration, longest run,
mean/median activity pace, distance-weighted aggregate pace, HR summaries and
zones, normalized weekly frequency, rolling 7/28-day mileage and week-over-week
change. Duplicate IDs are deduplicated. Zero-distance activities count as runs
but do not contribute to pace. Sample/missing counts identify incomplete coverage.
Overall pace is calculated from paired moving time and distance, never by
averaging paces. HR means are **unweighted activity averages**, not time averages.

```python
from datetime import date
from pathlib import Path
from garmin_parse.query import QueryService

queries = QueryService(Path("activities"))
summary = queries.get_training_summary(
    start_date=date(2026, 9, 1), end_date=date(2026, 9, 30)
)
comparison = queries.compare_training_periods(
    date(2026, 8, 1), date(2026, 8, 31), date(2026, 9, 1), date(2026, 9, 30)
)
```

For distance/subtype filters or first-10 versus last-10 comparisons, use
`analytics.filter_activities` on `storage.load_records(...)[0].values()`, then
`analytics.compare(runs[:10], runs[-10:])`. Sort/filter helpers order runs oldest
first. The MCP list tool orders results newest first. Rolling windows end on
the requested end date (today if omitted), including relevant preceding history.
Training metrics are observations, not diagnoses or validated injury predictions.
Terrain, pace, workout intensity and treadmill calibration affect comparisons.

## Local read-only MCP

```sh
uv run garmin-parse mcp --activities-dir /absolute/path/to/activities
```

This starts **stdio**, for local MCP clients that launch a subprocess. Configure
such a client with executable `uv`, arguments
`["--directory", "/absolute/path/to/garmin-parse", "run", "garmin-parse", "mcp",
"--activities-dir", "/absolute/path/to/activities"]`.
Use an absolute `uv` executable path if your client does not inherit PATH.
No Garmin login is performed. The process only needs read access to this data
directory, not `~/.garminconnect`, GitHub secrets or an OpenAI API key.

| Tool | Inputs | Result |
|---|---|---|
| `list_activities` | optional `start_date`, `end_date`, `activity_type`, `limit` (1–100), `offset` | metadata, metric summaries, total, next offset |
| `get_activity` | numeric-string `activity_id` | normalized record and extended capture status |
| `get_activity_data` | `activity_id`, `resource`, optional `offset`, `limit` (1–1,000), `field`, `message_type` | paginated sanitized source details or sensor samples |
| `get_training_summary` | optional dates and `activity_type` (default `running`) | deterministic aggregates, rolling windows |
| `compare_training_periods` | `period_a_start`, `period_a_end`, `period_b_start`, `period_b_end` | running summaries and B minus A differences |
| `get_running_trends` | optional dates, `granularity` (`weekly` or `monthly`) | distance buckets and period changes |
| `get_data_freshness` | none | timestamps, date coverage, activity/incomplete counts, warnings |

Dates use `YYYY-MM-DD`, inclusive and activity-local. Type `running` includes
recognized subtypes; exact subtype strings filter that subtype. List without a
type includes all sports. Activity metrics include units in key names; aggregate
responses include a units dictionary. Invalid ranges return tool errors. Queries
are limited to 2 MB responses and 1,200 trend buckets; narrow date ranges for
large histories. Freshness warns about Markdown-only history, malformed JSON,
duplicates, interrupted/partial syncs and a last success older than 48 hours. No tools write files or accept paths.

## Remote MCP and ChatGPT

A hosted ChatGPT interface cannot reach this stdio subprocess. It needs a
reachable remote transport and appropriate account/workspace access to custom
apps/plugins. The implementation supports **Streamable HTTP** at `/mcp`, with
mandatory OAuth bearer verification. Deployment and identity-provider provisioning
are deliberately manual; nothing has been exposed publicly.

Use an existing OAuth 2.1 provider supporting authorization code + PKCE (`S256`),
discovery metadata and an appropriate ChatGPT client-registration method (CIMD,
DCR or a predefined client). Configure an API resource/audience matching your
canonical HTTPS MCP URL, consent for `activities:read`, and RS256 JWT access
tokens. Configure redirect URIs from the current ChatGPT connection UI/provider
guidance. Restrict the provider to your account, and set the owner subject below.
Do not use client-credentials grants or a static API key as a substitute for
ChatGPT's user authorization flow.

```sh
export GARMIN_MCP_ISSUER=https://your-identity-provider.example/
export GARMIN_MCP_RESOURCE_URL=https://your-mcp.example/mcp
export GARMIN_MCP_JWKS_URL=https://your-identity-provider.example/.well-known/jwks.json
export GARMIN_MCP_OWNER_SUBJECT=your-provider-user-subject
uv run garmin-parse mcp --transport streamable-http \
  --activities-dir /srv/garmin/activities --host 127.0.0.1 --port 8000
```

Issuer and resource values must match token claims **exactly**, including trailing
slashes. The resource is also the audience. The server validates signature,
issuer, audience, expiry, required claims, scope and owner subject. Another valid
user's token is rejected. Opaque tokens, non-RS256 algorithms and multiple owners
are not supported. The SDK exposes OAuth protected-resource metadata at
`/.well-known/oauth-protected-resource/mcp` for the example resource above,
and advertises discovery in unauthenticated 401 challenges. Your provider must
publish authorization-server/OIDC metadata and support the `resource` parameter.

Put an HTTPS reverse proxy in front of the loopback service. Forward the canonical
Host and Authorization headers and the discovery routes, configure request/rate
limits, and avoid logging tokens or tool payloads. HTTP startup refuses missing
configuration or non-HTTPS issuer/resource/JWKS URLs. DNS rebinding protection
remains enabled. Bind to other interfaces only in a protected deployment network.
Mount only a private, read-only copy of the normalized data. Never mount the
Garmin token directory or inject sync secrets into this service. Update the
snapshot after successful syncs using your existing deployment mechanism; the
MCP process reads files afresh per query. Snapshot distribution is not automated.

In ChatGPT, use the custom MCP app/plugin connection flow available to your
account (developer mode/admin approval may be required), enter the HTTPS `/mcp`
URL, choose OAuth, and complete account linking. Discover the seven read-only tools,
then test freshness and a small date range. A successful connection still requires
a compatible configured OAuth provider; this project is the resource server,
not an authorization server. This has not been deployed or verified in a live
ChatGPT account.

Current primary references (checked 2026-10-21):

- [OpenAI: authentication and OAuth requirements](https://developers.openai.com/plugins/build/auth)
- [OpenAI: connecting a custom MCP server](https://developers.openai.com/api/docs/guides/custom-mcp-server)
- [Official Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk)

## Privacy and operational limits

**Files committed to a public repository are public**, including JSON, heart
rate, activity names and timestamps. MCP authentication cannot make that upstream
copy private. Names may themselves mention locations; inspect them before a
historical backfill/push. For private analytics, use a private repository or
separate private storage directory. The existing public static viewer cannot
protect private data and remains unchanged.

There are no raw GPS traces in normalized JSON, but timestamps and fitness data
are still sensitive. Do not commit `.env`, cached tokens, passwords, raw API dumps
or OAuth access tokens. Keep GitHub secrets only in the sync runner. The workflow
persists only Markdown/JSON activity outputs and the non-secret sync state.

Garmin's unofficial API can invalidate sessions, change fields or throttle calls.
Recover authentication with a local interactive sync and re-seed the GitHub secret
as documented above. Backfill/reconciliation require valid Garmin credentials;
legacy Markdown alone is not complete analytical history. The first upgraded sync
may refetch the entire Markdown-only archive. Summary pagination is not a stable
snapshot; reconcile periodically or after suspected edits/imports. No remote
deployment, automatic OAuth provisioning, raw trace collection, database, or
physiological coaching engine is included.


## Extended running capture: everything available except GPS routes

The default sync now requests the available activity-specific data from Garmin
and preserves it in `<activity>.details.json`. No extra flag is required. Old
normalized records without extended capture are refetched automatically. Use:

```sh
uv run garmin-parse sync --backfill
```

Captured resources:

- `summary` and `detail`: source summary/DTO fields beyond the normalized metric
  allowlist, including stamina, respiration, temperature, performance condition,
  recovery/training-related fields and other named measurements **when supplied**.
- `splits`, `typed_splits`, `split_summaries`: all sanitized returned lap/interval
  fields, including workout structure and additional split measurements.
- `hr_zones`, `power_zones`: zone durations and boundaries returned by Garmin.
- `time_series`: named chart channels, unit descriptors and samples, covering
  recorded HR, cadence, speed/pace, power, running dynamics and other channels.
- `weather`, `gear`, `exercise_sets`: available activity context without location,
  account identity or serial-number fields.
- `workout`: linked workout definition/steps when the activity contains a workout
  ID. This is a definition, which Garmin may subsequently edit, not a guaranteed
  immutable copy of the plan at the time of the run.
- `fit`: decoded original recording messages and field units, including sensor
  samples, lap/session/event records and RR intervals (`hrv`) if the device saved
  them. FIT cadence retains its native source convention; it is not silently
  doubled or merged with normalized steps/minute.

All available named non-location fields are retained rather than silently dropped
because the analytics schema does not yet recognize them. Source values keep
Garmin/FIT field names and units, which may differ from normalized SI metrics.
Use normalized JSON for existing deterministic training aggregates. New source
fields are available for inspection, not automatically added to aggregate formulas.

The original FIT/ZIP is downloaded and decoded **in memory**. Raw files, GPX/TCX,
route geometry, positional chart arrays and GPS coordinates are never persisted.
Chart arrays are decoded using their descriptors before coordinate columns are
removed. Original FIT messages retain the recording's sample cadence; they cannot
reconstruct measurements the device did not record. Unknown/unnamed FIT fields,
device/account identity, weather-station locations, route links and opaque binary
fields are excluded for privacy. This does not redact arbitrary location text in
activity names or workout notes; inspect free text before public publication.

Garmin's chart endpoint may downsample, even with a high requested sample limit.
FIT is the original-sample source when available; manual/imported activities may
not have a FIT export or recorded RR intervals. This is **not** a claim that Garmin
exposes every Connect UI-derived value or daily account health metric through
these activity APIs. Daily HRV status, sleep and training readiness are separate
account-level datasets and are not collected by this activity sync.

The normalized record holds a capture manifest, per-resource statuses and a digest
for the sidecar. `available`/`empty` describe successful responses; `not_found`
means an explicit HTTP 404; `not_linked` means no workout ID was supplied; `failed`
means the request or parsing failed and needs retry. Failed resources make the
sync partial and retain previous good data where possible. Resource warnings
accompany MCP results. Missing/damaged sidecars are repaired by the next sync.
The compact JSON export has a 64 MB safety limit; exceeding it fails that record
rather than silently truncating data. The expanded first backfill makes more API
requests, so large histories may require several resumable runs under rate limits.

Examples of read-only MCP calls:

```json
{"activity_id":"24340755231","resource":"time_series","offset":0,"limit":100}
{"activity_id":"24340755231","resource":"fit","message_type":"hrv","limit":100}
{"activity_id":"24340755231","resource":"detail","field":"summaryDTO"}
{"activity_id":"24340755231","resource":"power_zones"}
```

`get_activity_data` accepts only the named resources above. Lists are paginated;
for dictionary resources, top-level arrays are paginated and their original counts
are returned. `field` selects one dictionary field; `message_type` filters FIT
message names. Time-series pages retain descriptors as context. Responses remain
bounded to 2 MB; reduce the page limit for large records. Neither tool arguments
nor stored manifests can select arbitrary filesystem paths.

Normalized schema v1 remains readable; new writes use v2. The static viewer and
Markdown format remain unchanged. Detail sidecars are picked up by the existing
JSON commit workflow. Because this repository is public, publishing these files
would also publish the expanded sensor data; use private storage when needed.


Validation note: on 2026-10-21 a read-only smoke test against one recent running
activity retrieved 1,593 chart samples and 1,639 FIT messages. All applicable
requested resources succeeded; gear was empty and no workout was linked.
No activity exports were written by that check. Other device variants, historical
coverage and every derived Connect UI field have not been verified live.
