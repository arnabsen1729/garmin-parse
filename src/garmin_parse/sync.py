"""Streaming synchronization: persist progress before requesting the next activity."""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from requests.exceptions import ConnectionError, Timeout

from garminconnect.exceptions import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError

from garmin_parse.activities import _fetch_activity_bundle
from garmin_parse.existing import existing_activity_ids
from garmin_parse.render import activity_file_path, render_activity_markdown
from garmin_parse.schema import CaptureManifest, fingerprint, is_running, normalize
from garmin_parse.activity_data import CAPTURE_VERSION, MAX_CAPTURE_BYTES, capture_activity
from garmin_parse.storage import atomic_write, load_capture, load_records, sync_lock, write_json

logger = logging.getLogger(__name__)


@dataclass
class SyncStats:
    scanned: int = 0
    new: int = 0
    updated: int = 0
    incomplete: int = 0
    skipped: int = 0
    failed: int = 0
    history_scanned: bool = False
    storage_warnings: int = 0

    @property
    def successful(self):
        return self.failed == 0 and self.incomplete == 0 and self.history_scanned and self.storage_warnings == 0


def retry(fn):
    for attempt in range(3):
        try:
            return fn()
        except (GarminConnectAuthenticationError, GarminConnectTooManyRequestsError):
            raise
        except (ConnectionError, Timeout, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def run_sync(client, directory: Path, *, mode: str = "incremental", page_size: int = 100) -> SyncStats:
    if mode not in {"incremental", "backfill", "reconcile"} or page_size < 1:
        raise ValueError("Invalid sync mode or page size")
    with sync_lock(directory):
        return _run_sync(client, directory, mode=mode, page_size=page_size)


def sync_with_auth(client_factory, directory: Path, *, mode: str = "incremental") -> SyncStats:
    """Lock token access as well as activity writes; track login failures in freshness."""
    with sync_lock(directory):
        state_path = directory / ".sync-state.json"
        try:
            state = json.loads(state_path.read_text())
            if not isinstance(state, dict):
                state = {}
        except (OSError, ValueError):
            state = {}
        state.update(last_attempt_at=datetime.now(timezone.utc).isoformat(), status="authenticating", mode=mode)
        write_json(state_path, state)
        try:
            client = client_factory()
        except BaseException:
            state.update(status="failed", failure_phase="authentication")
            write_json(state_path, state)
            raise
        return _run_sync(client, directory, mode=mode, page_size=100)


def _run_sync(client, directory, *, mode, page_size):
    records, warnings = load_records(directory)
    for warning in warnings:
        logger.warning(warning)
    known = existing_activity_ids(directory) | records.keys()
    stats = SyncStats()
    seen = set()
    state_path = directory / ".sync-state.json"
    try:
        previous = json.loads(state_path.read_text())
        if not isinstance(previous, dict):
            previous = {}
    except (OSError, ValueError):
        previous = {}
    # Mark the attempt before any network operations; interrupted scans are observable.
    previous.pop("failure_phase", None)
    state = {**previous, "last_attempt_at": datetime.now(timezone.utc).isoformat(), "status": "running", "mode": mode}
    write_json(state_path, state)
    try:
        start = 0
        repeated_pages = 0
        while True:
            page = retry(lambda: client.get_activities(start=start, limit=page_size))
            if not isinstance(page, list):
                raise ValueError("Invalid Garmin activity listing")
            if not page:
                stats.history_scanned = True
                break
            seen_before = len(seen)
            for summary in page:
                activity_id = str(summary.get("activityId", ""))
                if activity_id in seen:
                    continue
                seen.add(activity_id)
                stats.scanned += 1
                try:
                    if not activity_id.isdigit():
                        raise ValueError("Missing or invalid activity ID")
                    old = records.get(activity_id)
                    md_paths = sorted(directory.glob(f"*/*_{activity_id}.md"))
                    md_valid = bool(old and md_paths and old.markdown_sha256 == hashlib.sha256(md_paths[0].read_bytes()).hexdigest())
                    old_capture = None
                    needs_capture = is_running((summary.get("activityType") or {}).get("typeKey", ""))
                    capture_valid = not needs_capture
                    if needs_capture and old and old.capture and old.capture.capture_version == CAPTURE_VERSION:
                        try:
                            old_capture = load_capture(directory, old)
                            capture_valid = True
                        except (ValueError, OSError):
                            capture_valid = False
                    if old and old.complete and md_valid and capture_valid and mode != "reconcile" and old.summary_fingerprint == fingerprint(summary):
                        stats.skipped += 1
                        continue
                    bundle = _fetch_activity_bundle(client, summary, activity_id)
                    record = normalize(bundle)
                    extended = capture_activity(client, bundle, activity_id) if needs_capture else None
                    if extended:
                        for resource, status in extended.statuses.items():
                            if status == "failed":
                                logger.warning("Activity %s: extended resource %s failed; retry on next sync", activity_id, resource)
                        if old_capture:
                            for resource, status in extended.statuses.items():
                                if status == "failed" and old_capture.resources.get(resource) is not None:
                                    extended.resources[resource] = old_capture.resources[resource]
                        # An unsuccessful extended fetch must not advance full-success metadata.
                        if "failed" in extended.statuses.values():
                            record.last_successful_fetch_at = old.last_successful_fetch_at if old else None
                    # Preserve previously fetched subresources when a refresh temporarily fails.
                    if old and record.missing_resources:
                        record.last_successful_fetch_at = old.last_successful_fetch_at
                        if "hr_zones" in record.missing_resources:
                            record.hr_zones_s = old.hr_zones_s
                        if "splits" in record.missing_resources:
                            record.laps = old.laps
                        for key in type(record.metrics).model_fields:
                            if getattr(record.metrics, key) is None:
                                setattr(record.metrics, key, getattr(old.metrics, key))
                    flat = {**summary, **{k: bundle[k] for k in ("detail", "splits", "hr_zones")}}
                    markdown = md_paths[0].read_text() if old and record.missing_resources and md_paths else render_activity_markdown(flat)
                    record.markdown_sha256 = hashlib.sha256(markdown.encode()).hexdigest()
                    # Keep the existing path stable after Garmin renames/re-dates an activity.
                    path = md_paths[0] if md_paths else activity_file_path(flat, directory)
                    if extended:
                        data = json.dumps(extended.model_dump(mode="json"), separators=(",", ":"), sort_keys=True, allow_nan=False) + "\n"
                        if len(data.encode()) > MAX_CAPTURE_BYTES:
                            raise ValueError("Extended activity exceeds storage limit; no truncation performed")
                        atomic_write(path.with_suffix(".details.json"), data)
                        record.capture = CaptureManifest(capture_version=CAPTURE_VERSION, sha256=hashlib.sha256(data.encode()).hexdigest(),
                                                         statuses=extended.statuses, warnings=extended.warnings)
                    atomic_write(path, markdown)
                    write_json(path.with_suffix(".json"), record.model_dump(mode="json"))
                    if activity_id in known:
                        stats.updated += 1
                    else:
                        stats.new += 1
                    records[activity_id] = record
                except (GarminConnectAuthenticationError, GarminConnectTooManyRequestsError):
                    raise
                except OSError:
                    # Persistence failures are fatal: further writes cannot be trusted.
                    raise
                except (ValueError, TypeError, KeyError) as exc:
                    stats.failed += 1
                    logger.error("Parsing activity %s failed: %s", activity_id, exc)
            if len(page) < page_size:
                stats.history_scanned = True
                break
            repeated_pages = repeated_pages + 1 if len(seen) == seen_before else 0
            if repeated_pages >= 3:
                raise ValueError("Garmin pagination repeatedly returned only previously scanned IDs")
            start += page_size
    except BaseException:
        stats.incomplete = sum(not record.complete for record in records.values()) + len(existing_activity_ids(directory) - records.keys())
        state.update(status="failed", stats=asdict(stats))
        write_json(state_path, state)
        raise
    _, final_warnings = load_records(directory)
    stats.storage_warnings = len(final_warnings)
    for warning in final_warnings:
        logger.warning(warning)
    remaining_legacy = existing_activity_ids(directory) - records.keys()
    stats.incomplete = sum(not record.complete for record in records.values()) + len(remaining_legacy)
    if remaining_legacy:
        logger.warning("%d Markdown activities still lack JSON; history coverage is incomplete", len(remaining_legacy))
    state.update(status="success" if stats.successful else "partial", stats=asdict(stats))
    if stats.successful:
        state["last_successful_sync_at"] = datetime.now(timezone.utc).isoformat()
        if mode in {"backfill", "reconcile"}:
            state["last_complete_history_scan_at"] = state["last_successful_sync_at"]
    write_json(state_path, state)
    return stats
