# Garmin analytics architecture

## Data flow

```text
Garmin Connect (credentials only in sync process)
  → paginated summaries → detail / lap / HR-zone resources
  → schema.normalize: explicit field allowlist, validated Activity v2
  → atomic Markdown + normalized JSON + sanitized extended running sidecars in activities/YYYY/
  → read-only QueryService → deterministic analytics → MCP → client
```

No database, unsanitized responses, GPS traces, or new external persistence
service is required. Pydantic validates records both at ingestion and query time. Query
modules import neither Garmin authentication nor the Garmin SDK. MCP gets one
administrator-configured data directory; tools accept no paths, SQL or writes.

## Audit findings and decisions

The original fetcher pages newest-first in batches of 100, stops after 20 known
Markdown IDs, accumulates bundles in memory, then writes Markdown. Detail,
splits and HR failures become `None` and only log warnings. Existing IDs never
refresh, including incomplete records; old imports beyond the stopping point
can be missed. Raw bundles were discarded. Historical backfill worked only
for entirely absent Markdown IDs. Writes were not atomic and persistence errors
escaped the clean CLI error handler. Authentication caches and refreshes tokens
through the installed garminconnect SDK; invalid cached login cannot prompt in
CI. The SDK persists refreshed sessions to its configured token directory.

The active sync now scans **all summary pages** in every mode. This intentionally
trades list requests for detection of older missed activities and summary edits.
Complete unchanged records make no detail calls. The original public
`fetch_new_activities` function is retained for compatibility and its existing
tests; the CLI uses the new streaming synchronizer. Reconciliation refetches
all details, because not every detail change has a reliable listing revision.

Markdown rendering retains its existing DTO adapter and byte-level format;
JSON is normalized from the same fetched bundle. This compatibility boundary
avoids rewriting the cycling/swimming/strength renderer and prevents pretending
legacy Markdown contains the full analytical schema. All computations use JSON,
never rendered text or an LLM. Future renderer migration can use a normalized
presentation adapter without changing the analytical contract.

The static viewer reads the GitHub tree and filters `.md` files. Sidecars and
root-level sync state require no viewer change. Existing user activity files
are not migrated or deleted automatically by development work.

## Schema version 2 (v1 remains readable)

`schema.Activity` is the authoritative validated normalized schema; generate its JSON Schema:

```sh
uv run python -c 'import json; from garmin_parse.schema import Activity; print(json.dumps(Activity.model_json_schema(), indent=2))'
```

Identity uses a numeric-string Garmin ID, type, optional name, original local
start/date, optional UTC start and timezone name. Metrics use unit-bearing keys:
meters, seconds, meters/second, seconds/km, kcal, bpm, steps/minute, milliseconds,
centimeters for vertical oscillation and percentages where named. Garmin stride
length in centimeters converts to meters. Garmin `movingDuration` is kept
separate from `elapsedDuration` (falling back to `duration` only for elapsed
duration). Moving duration is never inferred from elapsed duration. Metrics
missing from the source stay null; negative/non-finite measurements fail parsing.
Unknown source fields are ignored. HR zones map zone numbers to seconds;
`lapDTOs` become ordered normalized laps with metric objects. No GPS or owner DTO
is retained. A fingerprint detects listing changes without storing the raw DTO.

`last_successful_fetch_at` records the latest complete successful resource fetch
(or null if none); a partial refresh preserves the previous success timestamp.
`missing_resources` records failed detail/splits/zones calls; empty successful
responses mean the endpoint supplied no measurements, not that physiological
data exists. `fetched_at` records the resource fetch attempt time: when resources
are missing it is **not** a claim of a complete successful fetch. Old known
metrics/laps/zones survive transient refresh failures. `markdown_sha256` detects
missing/changed Markdown and incomplete pair writes. A schema version bump
requires an explicit reader/migration change; versions other than v1/v2 are rejected.

## Persistence, recovery and failures

Each record is persisted before fetching the next. Temp files in the destination
directory are flushed/fsynced and replaced atomically; JSON is committed last.
Two files are not one filesystem transaction: a crash between replacements is
repaired by checking the stored Markdown digest or the absent JSON. Complete
unchanged records remain resumable checkpoints. Existing file paths remain stable
when Garmin changes type/date, avoiding duplicate historical files; current
identity/date live in JSON and Markdown content. No automatic deletions are made.

A process-level advisory file lock serializes local sync on macOS/Linux. Actions
also serializes runs and checks out main at execution time. Listing/network,
authentication and persistence failures abort; per-record parsing failures and
missing resources produce a partial result and nonzero CLI exit. Network timeouts
and connection errors retry at most twice with 1s/2s backoff; authentication and
rate limits do not retry. Other endpoint failures leave a repairable incomplete
record for the next invocation rather than retrying aggressively. The unofficial
SDK sometimes wraps HTTP errors, so not every transient failure is retried.

`activities/.sync-state.json` tracks attempt status, mode, counters, last successful
sync and last successful explicit backfill/reconciliation scan. An interrupted
process can leave status `running`, which freshness warns about. A partial run
never advances the success timestamp. Markdown-only records absent from the
Garmin listing still count as incomplete coverage. Successfully fetched progress
is retained on API, parsing or interruption failures. The system cannot guarantee
that Garmin's paginated listing is a stable snapshot while activities are added;
subsequent scans and reconciliation recover omissions. API deletion is not a
request to delete local history.

## Analytics semantics

Date boundaries are inclusive **activity-local** dates; an overnight run belongs
to its starting local date. Weeks begin Monday, months begin on day 1; trend
buckets mark partial periods and include empty buckets as zero observed mileage.
Missing measurement totals are null if no measurement exists; otherwise totals
are sums of known values and missing/sample counts report coverage. Zero-distance
runs count for frequency but never contribute to pace. Duplicate IDs retain the
latest fetched record. Running variants include treadmill, trail, track and
virtual running; other sports are excluded from running queries.

Aggregate pace = sum(moving seconds) / sum(distance meters) × 1000 over records
with **both** metrics and positive distance. Mean/median activity paces are
separate unweighted statistics over the same valid pairs. HR means/medians are
unweighted activity-average statistics, not time-weighted physiological metrics.
HR zone totals contain observed values only. Frequency = count × 7 / inclusive
calendar days, so partial-week frequency is explicitly normalized. Rolling 7/28
days end on the requested end date (today when omitted) and include preceding
history outside the displayed date range. Week-over-week rolling change compares
the last 7 days with the preceding 7; zero denominators return null. The first
trend bucket has no prior-period comparison. Mileage means distance, returned in
meters; no implicit miles conversion. Treadmill accuracy and missing measurements
limit interpretation; no coaching, diagnosis or injury predictor is generated.

## Read-only server and remote security

The maintained official Python MCP SDK provides stdio and Streamable HTTP. Seven
tools use validated typed inputs, structured output, limit ≤100, bounded offsets,
≤1200 trend buckets and ≤2MB serialized responses. Errors ask clients to narrow
queries. Invalid JSON and duplicates generate warnings; freshness also reports
Markdown without JSON. The query loader rejects symlink records and symlink year
directories. Activity names are untrusted data, never instructions.

HTTP requires an externally managed OAuth authorization server. The SDK provides
protected-resource discovery and bearer middleware. Our verifier checks RS256
signature against configured cached JWKS, exact issuer and audience, expiration,
issued-at/not-before where supplied, required `activities:read` scope, and an
explicit owner subject. A valid token for another user cannot access this single
owner dataset. JWKS fetches run outside the async event loop. Opaque-token
introspection and multi-user datasets are not implemented. Bearer tokens are not
persisted or forwarded to Garmin. Plain local HTTP binds loopback by default;
production requires an HTTPS reverse proxy and private read-only data mount.
Keep DNS rebinding/Host protection enabled. No public deployment is performed.

See README for OAuth provider, ChatGPT, secrets and privacy setup.


## Extended running capture

`activity_data.py` adds a separate capture policy version and privacy-filtered
source layer. Normalized schema v2 adds `capture` (statuses, warnings and digest);
existing v1 records stay readable and running records upgrade on next sync.
`load_records` ignores `.details.json` files so analytical reads remain small.

The synchronizer fetches summary/detail/splits/HR zones as before, plus chart
samples (`maxPolylineSize=0`), typed splits, split summaries, power zones, weather,
gear, exercise sets, a linked workout when identified, and the original FIT export.
Responses retain named non-location fields after recursive filtering. Chart
positional arrays are resolved into descriptor-named samples; both coordinate
channels and their values are removed. Undescribed columns are omitted, malformed
or ambiguous descriptors fail parsing. Units stay in chart descriptors/FIT fields;
raw source values are not implicitly used as normalized numerical aggregates.

FIT/ZIP is parsed in memory using fitdecode with strict CRC/error checking.
No raw recording is saved or extracted to disk, even for ZIP members containing
traversal paths. Non-FIT members are ignored. GPS/route fields and semicircle
coordinates are removed; account/device identity, unnamed fields and opaque binary
values are excluded. RR intervals are retained only if present in the original
recording; daily/account HRV is a different dataset. Free-text names/notes can
still reveal locations and must be reviewed before publication.

The sidecar is atomically replaced before Markdown and the normalized commit
marker. Its SHA256 in the marker detects an interrupted/mismatched pair. Missing
or invalid sidecars trigger refetch; failed individual resources preserve old
values but keep `failed` status and do not advance full-success timestamps.
Explicit 404s are recorded as `not_found` instead of retrying permanently absent
resources on every daily run. Other fetch/parse failures yield partial sync.
An absent linked-workout reference is `not_linked`. A later reconciliation rechecks
all resources. A chart response may be downsampled; FIT supplies original samples
when available. A missing FIT export is a coverage limitation, not invented data.

Detail files use compact JSON with a 64 MB safety bound. Oversize exports fail
without truncation. `get_activity_data` pages chart samples, FIT messages or
source arrays, with optional source-field/FIT-message selection. Its resource
names are a fixed enumeration; paths are derived from the validated activity ID
inside the configured root. Reads verify the manifest checksum and reject symlinks.
The main MCP/analytics record stays below its existing 2 MB limit; source queries
also retain the 2 MB response bound. This extension does not add account-level
health, GPS collection, cloud services or any Garmin write operations.


Validation: the extended pipeline was also smoke-tested read-only against one
recent running activity on 2026-10-21. All requested applicable resources returned
success (gear empty, no linked workout), with 1,593 chart samples and 1,639 decoded
FIT messages. No activity exports were written. This checks one device/activity,
not exhaustive UI parity, historical backfill or other device/sport variants.
