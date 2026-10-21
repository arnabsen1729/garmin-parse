"""Read-only query service shared by transports; configured root never comes from tools."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from garmin_parse.analytics import WARNINGS, compare, filter_activities, rolling, summarize, trends
from garmin_parse.existing import existing_activity_ids
from garmin_parse.storage import load_capture, load_records
from garmin_parse.activity_data import RESOURCE_NAMES
from garmin_parse.schema import is_running


class QueryService:
    def __init__(self, directory: Path):
        self.directory = directory.resolve()

    def _read(self):
        records, warnings = load_records(self.directory)
        legacy = existing_activity_ids(self.directory) - records.keys()
        if legacy:
            warnings.append(f"{len(legacy)} Markdown activities lack valid JSON; run sync --backfill")
        try:
            state = json.loads((self.directory / ".sync-state.json").read_text())
            if not isinstance(state, dict):
                raise ValueError("Invalid sync state")
        except (ValueError, OSError):
            state = {}
        if state.get("status") != "success":
            warnings.append("Latest sync is absent, interrupted, failed or partial; totals may omit activities")
        if len(warnings) > 50:
            warnings = warnings[:50] + [f"{len(warnings) - 50} additional storage warnings omitted"]
        return list(records.values()), warnings

    def list_activities(self, *, start_date=None, end_date=None, activity_type=None, limit=50, offset=0):
        if not 1 <= limit <= 100 or not 0 <= offset <= 1_000_000:
            raise ValueError("limit must be 1..100 and offset 0..1000000")
        records, warnings = self._read()
        selected = filter_activities(records, start_date=start_date, end_date=end_date, activity_type=activity_type)
        items = [{"activity_id": r.activity_id, "activity_type": r.activity_type, "activity_name": r.activity_name, "local_date": r.local_date.isoformat(), "metrics": r.metrics.model_dump(), "complete": r.complete} for r in reversed(selected)]
        return {"activities": items[offset:offset + limit], "total": len(items), "next_offset": offset + limit if offset + limit < len(items) else None, "summary": summarize(selected, start_date=start_date, end_date=end_date), "warnings": warnings}

    def get_activity(self, activity_id: str):
        if not activity_id.isdigit() or len(activity_id) > 32:
            raise ValueError("activity_id must contain at most 32 digits")
        records, warnings = self._read()
        record = next((r for r in records if r.activity_id == activity_id), None)
        if record is None:
            raise ValueError("Activity not found; it may need backfill")
        return {"activity": record.model_dump(mode="json"), "warnings": warnings}

    def get_activity_data(self, activity_id: str, *, resource="detail", offset=0, limit=100, field=None, message_type=None):
        """Read a sanitized source resource, paging samples/arrays without returning paths."""
        if resource not in RESOURCE_NAMES:
            raise ValueError("Unknown activity resource")
        if not 1 <= limit <= 1000 or not 0 <= offset <= 10_000_000:
            raise ValueError("limit must be 1..1000 and offset 0..10000000")
        record = self.get_activity(activity_id)["activity"]
        from garmin_parse.schema import Activity
        capture = load_capture(self.directory, Activity.model_validate(record))
        value = capture.resources.get(resource)
        if field is not None:
            if not isinstance(value, dict) or field not in value:
                raise ValueError("Resource field not found")
            value = value[field]
        if message_type is not None:
            if resource != "fit" or not isinstance(value, list):
                raise ValueError("message_type is supported only for FIT messages")
            value = [item for item in value if item.get("message") == message_type]
        metadata = {}
        if resource == "time_series" and field is None and isinstance(value, dict):
            metadata = {k: v for k, v in value.items() if k != "samples"}
            value = value["samples"]
        counts = {}
        total = None
        if isinstance(value, list):
            total = len(value)
            value = value[offset:offset + limit]
        elif isinstance(value, dict):
            counts = {key: len(items) for key, items in value.items() if isinstance(items, list)}
            total = max(counts.values(), default=None)
            value = {key: items[offset:offset + limit] if isinstance(items, list) else items for key, items in value.items()}
        return {"activity_id": activity_id, "resource": resource, "status": capture.statuses[resource],
                "data": value, "metadata": metadata, "total": total, "collection_counts": counts,
                "next_offset": offset + limit if total is not None and offset + limit < total else None,
                "units": "Garmin source fields retain source units; chart descriptors and FIT fields include units where supplied. Use normalized metrics for aggregates.",
                "warnings": capture.warnings}

    def get_training_summary(self, *, start_date=None, end_date=None, activity_type="running"):
        records, warnings = self._read()
        selected = filter_activities(records, start_date=start_date, end_date=end_date, activity_type=activity_type)
        # Rolling windows include preceding history even when the displayed range is short.
        all_type = filter_activities(records, activity_type=activity_type)
        as_of = end_date or date.today()
        return {"summary": summarize(selected, start_date=start_date, end_date=end_date), "rolling": rolling(all_type, as_of), "warnings": warnings + WARNINGS}

    def compare_training_periods(self, a_start, a_end, b_start, b_end):
        records, warnings = self._read()
        a = filter_activities(records, start_date=a_start, end_date=a_end)
        b = filter_activities(records, start_date=b_start, end_date=b_end)
        return {**compare(a, b, a_start=a_start, a_end=a_end, b_start=b_start, b_end=b_end), "warnings": warnings + WARNINGS}

    def get_running_trends(self, *, start_date=None, end_date=None, granularity="weekly"):
        records, warnings = self._read()
        selected = filter_activities(records, start_date=start_date, end_date=end_date)
        return {"periods": trends(selected, start_date=start_date, end_date=end_date, granularity=granularity), "distance_unit": "meters", "warnings": warnings}

    def get_data_freshness(self):
        records, warnings = self._read()
        try:
            state = json.loads((self.directory / ".sync-state.json").read_text())
            if not isinstance(state, dict):
                raise ValueError("Invalid sync state")
        except (OSError, ValueError):
            state = {}
            warnings.append("No synchronization state available")
        if state.get("status") != "success":
            warnings.append("Latest sync is absent, interrupted, failed or partial")
        last_success = state.get("last_successful_sync_at")
        if last_success:
            try:
                timestamp = datetime.fromisoformat(last_success)
                if timestamp.tzinfo is None:
                    raise ValueError("Missing timezone")
                if datetime.now(timezone.utc) - timestamp > timedelta(hours=48):
                    warnings.append("Last successful synchronization is more than 48 hours old")
            except (ValueError, TypeError):
                warnings.append("Invalid last successful synchronization timestamp")
        extended_missing = sum(is_running(r.activity_type) and r.capture is None for r in records)
        if extended_missing:
            warnings.append(f"{extended_missing} running activities need extended-data backfill")
        dates = sorted(r.local_date for r in records)
        timestamps = [r.start_timestamp.astimezone(timezone.utc).isoformat() for r in records if r.start_timestamp]
        return {"activity_count": len(records), "most_recent_activity_timestamp": max(timestamps, default=None), "available_start_date": dates[0].isoformat() if dates else None, "available_end_date": dates[-1].isoformat() if dates else None, "last_successful_sync_at": state.get("last_successful_sync_at"), "last_complete_history_scan_at": state.get("last_complete_history_scan_at"), "last_attempt_status": state.get("status"), "extended_capture_missing_count": extended_missing, "incomplete_record_count": sum(not r.complete for r in records), "warnings": warnings}
