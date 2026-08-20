"""Unit tests for garmin_parse.activities.

No real Garmin credentials are available in this environment, so the
``client`` is a stub (a small fake object, not a live ``garminconnect``
instance) whose ``get_activities``/``get_activity``/etc. return canned
data configured per test.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from garmin_parse.activities import fetch_new_activities


def _summary(activity_id: int) -> dict[str, Any]:
    return {"activityId": activity_id, "activityType": {"typeKey": "running"}}


class FakeClient:
    """Minimal stand-in for garminconnect.Garmin used across these tests."""

    def __init__(self, pages: list[list[dict[str, Any]]]) -> None:
        self._pages = pages
        self.get_activities_calls: list[tuple[int, int]] = []
        self.detail_calls: list[str] = []
        self.splits_calls: list[str] = []
        self.hr_zone_calls: list[str] = []
        self.fail_ids: set[str] = set()

    def get_activities(self, start: int = 0, limit: int = 20, activitytype=None):
        self.get_activities_calls.append((start, limit))
        page_index = start // limit
        if page_index >= len(self._pages):
            return []
        return self._pages[page_index]

    def get_activity(self, activity_id: str):
        self.detail_calls.append(activity_id)
        if activity_id in self.fail_ids:
            raise RuntimeError(f"boom: detail {activity_id}")
        return {"activityId": activity_id, "detail": True}

    def get_activity_splits(self, activity_id: str):
        self.splits_calls.append(activity_id)
        if activity_id in self.fail_ids:
            raise RuntimeError(f"boom: splits {activity_id}")
        return {"activityId": activity_id, "splits": True}

    def get_activity_hr_in_timezones(self, activity_id: str):
        self.hr_zone_calls.append(activity_id)
        if activity_id in self.fail_ids:
            raise RuntimeError(f"boom: hr_zones {activity_id}")
        return {"activityId": activity_id, "hr_zones": True}


def _write_known_activity(activities_dir: Path, activity_id: str, year: str = "2026") -> None:
    year_dir = activities_dir / year
    year_dir.mkdir(parents=True, exist_ok=True)
    (year_dir / f"2026-01-01_running_{activity_id}.md").write_text("x")


def test_all_new_activities_fetch_full_detail(tmp_path: Path) -> None:
    client = FakeClient(pages=[[_summary(1), _summary(2)]])

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert len(result) == 2
    ids = {a["summary"]["activityId"] for a in result}
    assert ids == {1, 2}
    for activity in result:
        assert activity["detail"]["detail"] is True
        assert activity["splits"]["splits"] is True
        assert activity["hr_zones"]["hr_zones"] is True
    assert set(client.detail_calls) == {"1", "2"}
    assert set(client.splits_calls) == {"1", "2"}
    assert set(client.hr_zone_calls) == {"1", "2"}


def test_known_activities_are_skipped_with_no_detail_calls(tmp_path: Path) -> None:
    _write_known_activity(tmp_path, "1")
    client = FakeClient(pages=[[_summary(1), _summary(2)]])

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert len(result) == 1
    assert result[0]["summary"]["activityId"] == 2
    assert client.detail_calls == ["2"]
    assert client.splits_calls == ["2"]
    assert client.hr_zone_calls == ["2"]


def test_failing_sub_call_does_not_drop_the_activity(tmp_path: Path) -> None:
    client = FakeClient(pages=[[_summary(1)]])
    client.fail_ids = {"1"}

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert len(result) == 1
    activity = result[0]
    assert activity["summary"]["activityId"] == 1
    assert activity["detail"] is None
    assert activity["splits"] is None
    assert activity["hr_zones"] is None


def test_partial_failure_only_affects_the_failing_sub_call(tmp_path: Path) -> None:
    client = FakeClient(pages=[[_summary(1)]])

    # Only splits fails for this activity; simulate by monkeypatching just that method.
    original_splits = client.get_activity_splits

    def flaky_splits(activity_id: str):
        raise RuntimeError("splits endpoint down")

    client.get_activity_splits = flaky_splits  # type: ignore[assignment]

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert len(result) == 1
    activity = result[0]
    assert activity["detail"] is not None
    assert activity["splits"] is None
    assert activity["hr_zones"] is not None


def test_pagination_stops_after_enough_consecutive_known_ids(tmp_path: Path) -> None:
    # Newest-first: activity 5 is new, activities 4..1 are already known.
    for known_id in ("1", "2", "3", "4"):
        _write_known_activity(tmp_path, known_id)

    page_1 = [_summary(5), _summary(4), _summary(3)]
    page_2 = [_summary(2), _summary(1)]
    # A third page would represent over-fetching past the point we should stop.
    page_3 = [_summary(0)]
    client = FakeClient(pages=[page_1, page_2, page_3])

    result = fetch_new_activities(
        client, tmp_path, page_size=3, stop_after_consecutive_known=4
    )

    assert len(result) == 1
    assert result[0]["summary"]["activityId"] == 5
    # Never had to page far enough to reach page_3.
    assert (6, 3) not in client.get_activities_calls
    assert len(client.get_activities_calls) <= 2


def test_pagination_stops_on_short_page(tmp_path: Path) -> None:
    client = FakeClient(pages=[[_summary(1), _summary(2)]])  # shorter than page_size

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert len(result) == 2
    assert len(client.get_activities_calls) == 1


def test_empty_account_returns_empty_list(tmp_path: Path) -> None:
    client = FakeClient(pages=[[]])

    result = fetch_new_activities(client, tmp_path, page_size=100)

    assert result == []


def test_get_activities_failure_propagates(tmp_path: Path) -> None:
    class ExplodingClient(FakeClient):
        def get_activities(self, start: int = 0, limit: int = 20, activitytype=None):
            raise RuntimeError("auth expired")

    client = ExplodingClient(pages=[])

    with pytest.raises(RuntimeError, match="auth expired"):
        fetch_new_activities(client, tmp_path, page_size=100)
