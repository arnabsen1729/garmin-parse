"""Deterministic training statistics on normalized records, with no Garmin access."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, median
from typing import Literal

from garmin_parse.schema import Activity, is_running

UNITS = {"distance_m": "meters", "moving_duration_s": "seconds", "pace_s_km": "seconds/kilometer", "hr_bpm": "beats/minute", "hr_zones_s": "seconds", "frequency_per_week": "activities/7 calendar days"}
WARNINGS = ["Treadmill distance depends on device calibration. HR comparisons require comparable pace, terrain and intensity. These metrics do not diagnose injury or predict injury risk."]


def validate_range(start: date | None, end: date | None):
    if start and end and start > end:
        raise ValueError("start_date must be on or before end_date")


def filter_activities(records, *, start_date=None, end_date=None, activity_type="running", min_distance_m=None, max_distance_m=None, running_subtype=None):
    validate_range(start_date, end_date)
    if min_distance_m is not None and min_distance_m < 0 or max_distance_m is not None and max_distance_m < 0:
        raise ValueError("Distance bounds must be non-negative")
    if min_distance_m is not None and max_distance_m is not None and min_distance_m > max_distance_m:
        raise ValueError("Invalid distance range")
    selected = []
    for r in records:
        if start_date and r.local_date < start_date or end_date and r.local_date > end_date:
            continue
        if activity_type and (not is_running(r.activity_type) if activity_type == "running" else r.activity_type != activity_type):
            continue
        if running_subtype and (not is_running(r.activity_type) or r.activity_type != running_subtype):
            continue
        distance = r.metrics.distance_m
        if min_distance_m is not None and (distance is None or distance < min_distance_m):
            continue
        if max_distance_m is not None and (distance is None or distance > max_distance_m):
            continue
        selected.append(r)
    # Deduplicate deterministically, retaining the most recently fetched copy.
    unique = {}
    for r in sorted(selected, key=lambda a: a.fetched_at):
        unique[r.activity_id] = r
    return sorted(unique.values(), key=lambda r: (r.local_date, r.local_start.isoformat(), r.activity_id))


def _sum(values):
    present = [v for v in values if v is not None]
    return sum(present) if present else None


def summarize(records: list[Activity], *, start_date=None, end_date=None) -> dict:
    validate_range(start_date, end_date)
    records = filter_activities(records, start_date=start_date, end_date=end_date, activity_type=None)
    distances = [r.metrics.distance_m for r in records]
    durations = [r.metrics.moving_duration_s for r in records]
    paired = [(r.metrics.distance_m, r.metrics.moving_duration_s) for r in records if r.metrics.distance_m and r.metrics.moving_duration_s is not None]
    paces = [t * 1000 / d for d, t in paired]
    hrs = [r.metrics.average_hr_bpm for r in records if r.metrics.average_hr_bpm is not None]
    zones = defaultdict(float)
    for r in records:
        for zone, seconds in r.hr_zones_s.items():
            zones[zone] += seconds
    start = start_date or (records[0].local_date if records else None)
    end = end_date or (records[-1].local_date if records else None)
    span = (end - start).days + 1 if start and end else None
    longest = max((r for r in records if r.metrics.distance_m is not None), key=lambda r: r.metrics.distance_m, default=None)
    return {
        "activity_count": len(records), "run_count": sum(is_running(r.activity_type) for r in records),
        "total_distance_m": _sum(distances), "total_moving_duration_s": _sum(durations),
        "average_distance_m": mean([d for d in distances if d is not None]) if any(d is not None for d in distances) else None,
        "longest_activity_id": longest.activity_id if longest else None,
        "longest_distance_m": longest.metrics.distance_m if longest else None,
        "mean_activity_pace_s_km": mean(paces) if paces else None,
        "median_activity_pace_s_km": median(paces) if paces else None,
        "aggregate_pace_s_km": sum(t for d, t in paired) * 1000 / sum(d for d, t in paired) if paired else None,
        "pace_sample_count": len(paired),
        "average_activity_hr_bpm": mean(hrs) if hrs else None,
        "median_activity_hr_bpm": median(hrs) if hrs else None, "hr_sample_count": len(hrs),
        "hr_zones_s": dict(zones), "hr_zone_sample_count": sum(bool(r.hr_zones_s) for r in records),
        "frequency_per_week": len(records) * 7 / span if span else None,
        "calendar_days": span, "incomplete_count": sum(not r.complete for r in records),
        "missing_distance_count": sum(d is None for d in distances),
        "missing_moving_duration_count": sum(t is None for t in durations),
        "units": UNITS,
    }


def trends(records, *, start_date=None, end_date=None, granularity: Literal["weekly", "monthly"] = "weekly"):
    if granularity not in {"weekly", "monthly"}:
        raise ValueError("granularity must be weekly or monthly")
    validate_range(start_date, end_date)
    records = filter_activities(records, start_date=start_date, end_date=end_date, activity_type=None)
    start = start_date or (min((r.local_date for r in records), default=None))
    end = end_date or (max((r.local_date for r in records), default=None))
    if not start or not end:
        return []
    cursor = start - timedelta(days=start.weekday()) if granularity == "weekly" else start.replace(day=1)
    buckets = []
    while cursor <= end:
        if len(buckets) >= 1200:
            raise ValueError("Date range exceeds 1200 trend buckets")
        next_date = cursor + timedelta(days=7) if granularity == "weekly" else (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        a, b = max(start, cursor), min(end, next_date - timedelta(days=1))
        selected = [r for r in records if a <= r.local_date <= b]
        summary = summarize(selected, start_date=a, end_date=b)
        # No records in a bucket means zero observed distance, not a missing measurement.
        distance = summary["total_distance_m"] if selected else 0
        previous = buckets[-1]["distance_m"] if buckets else None
        change = (distance - previous) / previous * 100 if distance is not None and previous else None
        buckets.append({"start_date": a.isoformat(), "end_date": b.isoformat(), "partial_period": a != cursor or b != next_date - timedelta(days=1), "distance_m": distance, "activity_count": len(selected), "change_percent": change, "missing_distance_count": summary["missing_distance_count"]})
        cursor = next_date
    return buckets


def rolling(records, as_of: date):
    records = filter_activities(records, activity_type=None)
    values = {}
    for days in (7, 28):
        selected = [r for r in records if as_of - timedelta(days=days - 1) <= r.local_date <= as_of]
        values[f"missing_distance_{days}d_count"] = sum(r.metrics.distance_m is None for r in selected)
        values[f"activity_{days}d_count"] = len(selected)
        values[f"distance_{days}d_m"] = _sum(r.metrics.distance_m for r in selected) if selected else 0
    current = values["distance_7d_m"]
    previous_records = [r for r in records if as_of - timedelta(days=13) <= r.local_date <= as_of - timedelta(days=7)]
    previous = _sum(r.metrics.distance_m for r in previous_records) if previous_records else 0
    values["previous_7d_distance_m"] = previous
    values["week_over_week_change_percent"] = (current - previous) / previous * 100 if previous and current is not None else None
    values["as_of"] = as_of.isoformat()
    return values


def compare(a, b, *, a_start=None, a_end=None, b_start=None, b_end=None):
    sa = summarize(a, start_date=a_start, end_date=a_end)
    sb = summarize(b, start_date=b_start, end_date=b_end)
    keys = ("activity_count", "total_distance_m", "total_moving_duration_s", "aggregate_pace_s_km", "average_activity_hr_bpm", "frequency_per_week")
    differences = {k: sb[k] - sa[k] if sa[k] is not None and sb[k] is not None else None for k in keys}
    return {"period_a": sa, "period_b": sb, "difference_b_minus_a": differences, "units": UNITS}
