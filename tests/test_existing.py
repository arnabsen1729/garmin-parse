"""Unit tests for garmin_parse.existing."""

from __future__ import annotations

from pathlib import Path

from garmin_parse.existing import existing_activity_ids


def test_populated_tree_returns_correct_id_set(tmp_path: Path) -> None:
    year_2025 = tmp_path / "2025"
    year_2026 = tmp_path / "2026"
    year_2025.mkdir()
    year_2026.mkdir()

    (year_2025 / "2025-12-31_running_18111111111.md").write_text("x")
    (year_2026 / "2026-08-20_cycling_18234567890.md").write_text("x")
    (year_2026 / "2026-08-21_running_18234567891.md").write_text("x")

    assert existing_activity_ids(tmp_path) == {
        "18111111111",
        "18234567890",
        "18234567891",
    }


def test_missing_activities_dir_returns_empty_set(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"

    assert existing_activity_ids(missing) == set()


def test_non_matching_filename_is_skipped(tmp_path: Path) -> None:
    year_dir = tmp_path / "2026"
    year_dir.mkdir()

    (year_dir / "README.md").write_text("not an activity")
    (year_dir / "2026-08-20_running_18234567890.md").write_text("x")

    assert existing_activity_ids(tmp_path) == {"18234567890"}


def test_accepts_str_path(tmp_path: Path) -> None:
    year_dir = tmp_path / "2026"
    year_dir.mkdir()
    (year_dir / "2026-08-20_running_18234567890.md").write_text("x")

    assert existing_activity_ids(str(tmp_path)) == {"18234567890"}
