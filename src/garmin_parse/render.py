"""Render a Garmin activity dict into a Markdown "stats page" document.

Design notes
------------
An ``activity`` dict, as consumed here, is expected to carry the Garmin
activity-summary fields at the top level (``activityId``, ``activityType``
(a dict with ``typeKey``), ``startTimeLocal``, ``distance``, ``duration``,
``calories``, ``averageHR``, ``maxHR``, ``elevationGain``, etc. -- the same
field names ``garminconnect.Garmin.get_activities`` returns), plus three
extra keys added by the sync pipeline:

* ``detail``   -- result of ``client.get_activity(activity_id)``, or ``None``
* ``splits``   -- result of ``client.get_activity_splits(activity_id)``, or ``None``
* ``hr_zones`` -- result of ``client.get_activity_hr_in_timezones(activity_id)``, or ``None``

Any of ``detail``/``splits``/``hr_zones`` may be missing or ``None`` (a
sub-fetch failure is tolerated upstream), and any individual field within
them may be absent. This module's guiding rule, per product decision: a
missing/``None`` field is *omitted* from the rendered Markdown -- never
rendered as a blank line or "N/A" placeholder.

The generic section (date, activity type, duration, distance, avg/max
speed, avg/max HR + HR-zone breakdown, elevation, calories, training
effect) is common to every activity. A type-specific section is appended
on top, dispatched by a coarse category bucketed from ``activityType.typeKey``:
running, cycling, swimming, strength, or "other" (generic-only, no error).
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Field lookup helpers
# ---------------------------------------------------------------------------


def _detail_dict(activity: dict[str, Any]) -> dict[str, Any]:
    detail = activity.get("detail")
    return detail if isinstance(detail, dict) else {}


def _summary_dto(activity: dict[str, Any]) -> dict[str, Any]:
    detail = _detail_dict(activity)
    summary_dto = detail.get("summaryDTO")
    return summary_dto if isinstance(summary_dto, dict) else {}


def _lookup(activity: dict[str, Any], *keys: str) -> Any:
    """Return the first non-``None`` value for any of ``keys``.

    Searches, per key, the top-level activity dict, then ``detail``, then
    ``detail["summaryDTO"]`` -- extra per-activity detail (e.g. running
    dynamics, swim metrics) commonly lives one of those places depending on
    which Garmin Connect endpoint surfaced it.
    """
    sources = (activity, _detail_dict(activity), _summary_dto(activity))
    for key in keys:
        for source in sources:
            value = source.get(key)
            if value is not None:
                return value
    return None


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _line(label: str, value: Any, unit: str = "") -> str | None:
    """Return a Markdown bullet line, or ``None`` if ``value`` is missing."""
    if value is None:
        return None
    return f"- **{label}:** {value}{unit}"


def _format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _format_distance_km(meters: float) -> str:
    return f"{meters / 1000:.2f} km"


def _format_speed_kmh(meters_per_second: float) -> str:
    return f"{meters_per_second * 3.6:.2f} km/h"


def _format_date(start_time_local: str) -> str:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(start_time_local, fmt).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            continue
    return start_time_local


# ---------------------------------------------------------------------------
# Activity category
# ---------------------------------------------------------------------------


def activity_category(activity: dict[str, Any]) -> str:
    """Bucket ``activity``'s ``activityType.typeKey`` into a coarse category.

    Returns one of ``"running"``, ``"cycling"``, ``"swimming"``,
    ``"strength"``, or ``"other"`` (unrecognized types render the generic
    section only, without error).
    """
    type_key = ((activity.get("activityType") or {}).get("typeKey") or "").lower()
    if "running" in type_key:
        return "running"
    if "cycling" in type_key or "biking" in type_key:
        return "cycling"
    if "swimming" in type_key:
        return "swimming"
    if "strength" in type_key:
        return "strength"
    return "other"


# ---------------------------------------------------------------------------
# Generic section
# ---------------------------------------------------------------------------


def _render_generic_section(activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    activity_type = activity.get("activityType") or {}
    type_key = activity_type.get("typeKey")
    if type_key:
        lines.append(_line("Activity Type", type_key.replace("_", " ").title()))

    start_time_local = activity.get("startTimeLocal")
    if start_time_local:
        lines.append(_line("Date", _format_date(start_time_local)))

    duration = activity.get("duration")
    if duration is not None:
        lines.append(_line("Duration", _format_duration(duration)))

    distance = activity.get("distance")
    if distance is not None:
        lines.append(_line("Distance", _format_distance_km(distance)))

    average_speed = activity.get("averageSpeed")
    if average_speed is not None:
        lines.append(_line("Average Speed", _format_speed_kmh(average_speed)))

    max_speed = activity.get("maxSpeed")
    if max_speed is not None:
        lines.append(_line("Max Speed", _format_speed_kmh(max_speed)))

    average_hr = activity.get("averageHR")
    if average_hr is not None:
        lines.append(_line("Average HR", int(average_hr), " bpm"))

    max_hr = activity.get("maxHR")
    if max_hr is not None:
        lines.append(_line("Max HR", int(max_hr), " bpm"))

    elevation_gain = activity.get("elevationGain")
    if elevation_gain is not None:
        lines.append(_line("Elevation Gain", f"{elevation_gain:.0f}", " m"))

    elevation_loss = activity.get("elevationLoss")
    if elevation_loss is not None:
        lines.append(_line("Elevation Loss", f"{elevation_loss:.0f}", " m"))

    calories = activity.get("calories")
    if calories is not None:
        lines.append(_line("Calories", int(calories), " kcal"))

    aerobic_te = activity.get("aerobicTrainingEffect")
    if aerobic_te is not None:
        lines.append(_line("Aerobic Training Effect", f"{aerobic_te:.1f}"))

    anaerobic_te = activity.get("anaerobicTrainingEffect")
    if anaerobic_te is not None:
        lines.append(_line("Anaerobic Training Effect", f"{anaerobic_te:.1f}"))

    training_effect_label = activity.get("trainingEffectLabel")
    if training_effect_label is not None:
        lines.append(
            _line("Training Effect", training_effect_label.replace("_", " ").title())
        )

    lines = [line for line in lines if line is not None]

    hr_zone_table = _render_hr_zone_table(activity.get("hr_zones"))
    if hr_zone_table:
        lines.append("")
        lines.append("### Heart Rate Zones")
        lines.append("")
        lines.extend(hr_zone_table)

    return lines


def _render_hr_zone_table(hr_zones: Any) -> list[str]:
    if not hr_zones:
        return []

    rows: list[str] = []
    for zone in hr_zones:
        if not isinstance(zone, dict):
            continue
        zone_number = zone.get("zoneNumber") or zone.get("zone")
        secs_in_zone = zone.get("secsInZone")
        if secs_in_zone is None:
            secs_in_zone = zone.get("secondsInZone")
        if zone_number is None or secs_in_zone is None:
            continue
        rows.append(f"| {zone_number} | {_format_duration(secs_in_zone)} |")

    if not rows:
        return []

    return ["| Zone | Time |", "| --- | --- |", *rows]


# ---------------------------------------------------------------------------
# Type-specific sections
# ---------------------------------------------------------------------------


def _render_running_section(activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    cadence = _lookup(
        activity, "averageRunningCadenceInStepsPerMinute", "averageRunningCadence"
    )
    if cadence is not None:
        lines.append(_line("Average Cadence", f"{cadence:.0f}", " spm"))

    max_cadence = _lookup(
        activity, "maxRunningCadenceInStepsPerMinute", "maxRunningCadence"
    )
    if max_cadence is not None:
        lines.append(_line("Max Cadence", f"{max_cadence:.0f}", " spm"))

    vertical_oscillation = _lookup(activity, "avgVerticalOscillation")
    if vertical_oscillation is not None:
        lines.append(_line("Vertical Oscillation", f"{vertical_oscillation:.1f}", " cm"))

    stride_length = _lookup(activity, "avgStrideLength")
    if stride_length is not None:
        lines.append(_line("Stride Length", f"{stride_length:.2f}", " m"))

    ground_contact_time = _lookup(activity, "avgGroundContactTime")
    if ground_contact_time is not None:
        lines.append(_line("Ground Contact Time", f"{ground_contact_time:.0f}", " ms"))

    return [line for line in lines if line is not None]


def _render_cycling_section(activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    average_power = _lookup(activity, "avgPower")
    if average_power is not None:
        lines.append(_line("Average Power", f"{average_power:.0f}", " W"))

    max_power = _lookup(activity, "maxPower")
    if max_power is not None:
        lines.append(_line("Max Power", f"{max_power:.0f}", " W"))

    normalized_power = _lookup(activity, "normPower", "normalizedPower")
    if normalized_power is not None:
        lines.append(_line("Normalized Power", f"{normalized_power:.0f}", " W"))

    return [line for line in lines if line is not None]


def _render_swimming_section(activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    stroke_type = _lookup(activity, "strokeType", "swimStroke", "activityStrokeType")
    if stroke_type is not None:
        lines.append(_line("Stroke Type", str(stroke_type).replace("_", " ").title()))

    swolf = _lookup(activity, "avgSwolf", "averageSwolf")
    if swolf is not None:
        lines.append(_line("SWOLF", f"{swolf:.0f}"))

    pool_length = _lookup(activity, "poolLength")
    if pool_length is not None:
        lines.append(_line("Pool Length", f"{pool_length:.0f}", " m"))

    lengths = _lookup(activity, "activeLengths", "lengths")
    if lengths is not None:
        lines.append(_line("Lengths", int(lengths)))

    return [line for line in lines if line is not None]


def _render_strength_section(activity: dict[str, Any]) -> list[str]:
    lines: list[str] = []

    total_sets = _lookup(activity, "totalSets")
    if total_sets is not None:
        lines.append(_line("Total Sets", int(total_sets)))

    total_reps = _lookup(activity, "totalReps")
    if total_reps is not None:
        lines.append(_line("Total Reps", int(total_reps)))

    lines = [line for line in lines if line is not None]

    exercise_sets = _detail_dict(activity).get("exerciseSets")
    exercise_rows: list[str] = []
    if isinstance(exercise_sets, list):
        for exercise_set in exercise_sets:
            if not isinstance(exercise_set, dict):
                continue
            exercises = exercise_set.get("exercises") or []
            names = ", ".join(
                str(exercise.get("name"))
                for exercise in exercises
                if isinstance(exercise, dict) and exercise.get("name")
            )
            reps = exercise_set.get("reps")
            if not names:
                continue
            reps_display = reps if reps is not None else "-"
            exercise_rows.append(f"| {names} | {reps_display} |")

    if exercise_rows:
        lines.append("")
        lines.append("| Exercise | Reps |")
        lines.append("| --- | --- |")
        lines.extend(exercise_rows)

    return lines


_CATEGORY_RENDERERS = {
    "running": ("Running", _render_running_section),
    "cycling": ("Cycling", _render_cycling_section),
    "swimming": ("Swimming", _render_swimming_section),
    "strength": ("Strength Training", _render_strength_section),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def render_activity_markdown(activity: dict[str, Any]) -> str:
    """Render ``activity`` into a full Markdown document.

    The document has a generic section (fields common to all activities)
    followed by a type-specific section, chosen via
    :func:`activity_category`. Fields missing/``None`` on ``activity`` are
    omitted entirely rather than rendered blank. Unrecognized activity
    types get the generic section only, with no error.
    """
    activity_type = activity.get("activityType") or {}
    type_key = activity_type.get("typeKey") or "Activity"
    title = type_key.replace("_", " ").title()

    lines = [f"# {title}", ""]
    lines.extend(_render_generic_section(activity))

    category = activity_category(activity)
    renderer_entry = _CATEGORY_RENDERERS.get(category)
    if renderer_entry is not None:
        heading, renderer = renderer_entry
        section_lines = renderer(activity)
        if section_lines:
            lines.append("")
            lines.append(f"## {heading}")
            lines.append("")
            lines.extend(section_lines)

    return "\n".join(lines) + "\n"


_FILENAME_SAFE_RE = re.compile(r"[^a-z0-9]+")


def _sanitize_type_key(type_key: str) -> str:
    sanitized = _FILENAME_SAFE_RE.sub("_", type_key.lower()).strip("_")
    return sanitized or "activity"


def activity_file_path(activity: dict[str, Any], activities_dir: Path) -> Path:
    """Return the on-disk path for ``activity``'s rendered Markdown file.

    Format: ``activities_dir/<YYYY>/<YYYY-MM-DD>_<typeKey>_<activityId>.md``,
    where the year/date come from ``startTimeLocal`` and ``typeKey`` is
    sanitized to be filesystem-safe (lowercased, non-alphanumerics collapsed
    to underscores).
    """
    start_time_local = activity["startTimeLocal"]
    date_part = start_time_local.split("T")[0].split(" ")[0]
    year = date_part.split("-")[0]

    activity_type = activity.get("activityType") or {}
    type_key = _sanitize_type_key(activity_type.get("typeKey") or "activity")

    activity_id = activity["activityId"]

    filename = f"{date_part}_{type_key}_{activity_id}.md"
    return Path(activities_dir) / year / filename


def write_activity_file(activity: dict[str, Any], activities_dir: Path) -> Path:
    """Render ``activity`` and write it to its computed path.

    Creates the destination year subfolder if it doesn't already exist.
    Returns the path written.
    """
    path = activity_file_path(activity, Path(activities_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_activity_markdown(activity))
    return path
