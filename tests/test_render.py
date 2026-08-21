"""Unit tests for garmin_parse.render.

Activities are plain dicts shaped like a flattened Garmin activity summary
(top-level ``activityId``, ``activityType``, ``startTimeLocal``, and the
usual summary metrics) plus ``detail``/``splits``/``hr_zones`` keys, any of
which may be ``None``.
"""

from __future__ import annotations

from pathlib import Path

from garmin_parse.render import (
    activity_file_path,
    render_activity_markdown,
    write_activity_file,
)


def _base_activity(**overrides):
    activity = {
        "activityId": 18234567890,
        "activityType": {"typeKey": "running"},
        "startTimeLocal": "2026-08-20 06:30:00",
        "duration": 1800.0,
        "distance": 5000.0,
        "averageSpeed": 2.78,
        "maxSpeed": 3.5,
        "averageHR": 150,
        "maxHR": 172,
        "elevationGain": 45.0,
        "elevationLoss": 40.0,
        "calories": 350,
        "aerobicTrainingEffect": 3.2,
        "anaerobicTrainingEffect": 1.1,
        "trainingEffectLabel": "tempo",
        "detail": None,
        "splits": None,
        "hr_zones": None,
    }
    activity.update(overrides)
    return activity


def test_generic_section_renders_expected_fields_for_running_activity():
    activity = _base_activity(
        hr_zones=[
            {"zoneNumber": 1, "secsInZone": 60},
            {"zoneNumber": 2, "secsInZone": 300},
            {"zoneNumber": 3, "secsInZone": 900},
        ]
    )

    markdown = render_activity_markdown(activity)

    assert "Running" in markdown
    assert "2026-08-20 06:30" in markdown
    assert "30:00" in markdown  # duration
    assert "5.00 km" in markdown  # distance
    assert "10.01 km/h" in markdown  # average speed 2.78 m/s
    assert "12.60 km/h" in markdown  # max speed 3.5 m/s
    assert "150 bpm" in markdown
    assert "172 bpm" in markdown
    assert "45 m" in markdown
    assert "40 m" in markdown
    assert "350 kcal" in markdown
    assert "3.2" in markdown
    assert "1.1" in markdown
    assert "Tempo" in markdown
    assert "Heart Rate Zones" in markdown
    assert "| 1 | 1:00 |" in markdown
    assert "| 2 | 5:00 |" in markdown
    assert "| 3 | 15:00 |" in markdown


def test_running_specific_fields_included_when_present():
    activity = _base_activity(
        averageRunningCadenceInStepsPerMinute=170.0,
        maxRunningCadenceInStepsPerMinute=190.0,
        detail={
            "summaryDTO": {
                "avgVerticalOscillation": 8.5,
                "avgStrideLength": 115.0,
                "avgGroundContactTime": 240.0,
            }
        },
    )

    markdown = render_activity_markdown(activity)

    assert "## Running" in markdown
    assert "Average Cadence:** 170" in markdown
    assert "Max Cadence:** 190" in markdown
    assert "Vertical Oscillation" in markdown
    assert "8.5" in markdown
    assert "Stride Length" in markdown
    assert "1.15 m" in markdown
    assert "Ground Contact Time" in markdown
    assert "240" in markdown


def test_cycling_activity_renders_power_fields():
    activity = _base_activity(
        activityType={"typeKey": "road_biking"},
        avgPower=210.0,
        maxPower=450.0,
        normPower=225.0,
    )

    markdown = render_activity_markdown(activity)

    assert "## Cycling" in markdown
    assert "Average Power:** 210 W" in markdown
    assert "Max Power:** 450 W" in markdown
    assert "Normalized Power:** 225 W" in markdown
    # Running-only fields must not leak in.
    assert "Cadence" not in markdown


def test_swimming_activity_renders_stroke_and_swolf():
    activity = _base_activity(
        activityType={"typeKey": "lap_swimming"},
        detail={
            "summaryDTO": {
                "strokeType": "freestyle",
                "avgSwolf": 38.0,
                "poolLength": 25.0,
                "activeLengths": 40,
            }
        },
    )

    markdown = render_activity_markdown(activity)

    assert "## Swimming" in markdown
    assert "Stroke Type:** Freestyle" in markdown
    assert "SWOLF:** 38" in markdown
    assert "Pool Length:** 25 m" in markdown
    assert "Lengths:** 40" in markdown


def test_strength_activity_renders_sets_and_reps():
    activity = _base_activity(
        activityType={"typeKey": "strength_training"},
        totalSets=5,
        totalReps=60,
        detail={
            "exerciseSets": [
                {"exercises": [{"name": "SQUAT"}], "reps": 10},
                {"exercises": [{"name": "BENCH_PRESS"}], "reps": 8},
            ]
        },
    )

    markdown = render_activity_markdown(activity)

    assert "## Strength Training" in markdown
    assert "Total Sets:** 5" in markdown
    assert "Total Reps:** 60" in markdown
    assert "| SQUAT | 10 |" in markdown
    assert "| BENCH_PRESS | 8 |" in markdown


def test_unrecognized_activity_type_renders_generic_section_without_error():
    activity = _base_activity(activityType={"typeKey": "paddling"})

    markdown = render_activity_markdown(activity)

    assert "Paddling" in markdown
    assert "Duration" in markdown
    # No type-specific heading should be added for an unknown category.
    assert "## Cycling" not in markdown
    assert "## Running" not in markdown
    assert "## Swimming" not in markdown
    assert "## Strength Training" not in markdown


def test_missing_field_is_omitted_not_rendered_blank():
    activity = _base_activity(maxHR=None, elevationLoss=None)
    # also drop the keys entirely to simulate "missing", not just None
    del activity["maxHR"]
    del activity["elevationLoss"]

    markdown = render_activity_markdown(activity)

    assert "Max HR" not in markdown
    assert "Elevation Loss" not in markdown
    # Sanity: fields that *are* present still show up.
    assert "Average HR" in markdown


def test_activity_file_path_matches_expected_format(tmp_path: Path):
    activity = _base_activity()

    path = activity_file_path(activity, tmp_path)

    assert path == tmp_path / "2026" / "2026-08-20_running_18234567890.md"


def test_write_activity_file_creates_year_subfolder_and_file(tmp_path: Path):
    activity = _base_activity()

    written_path = write_activity_file(activity, tmp_path)

    assert written_path == tmp_path / "2026" / "2026-08-20_running_18234567890.md"
    assert written_path.exists()
    content = written_path.read_text()
    assert "Running" in content
    assert "5.00 km" in content
