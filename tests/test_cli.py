"""Tests for garmin_parse.cli's ``sync`` command.

All Garmin/network/filesystem interaction is mocked: ``auth.get_client``,
``activities.fetch_new_activities``, and ``render.write_activity_file`` are
monkeypatched so nothing here hits the network or writes real files beyond
``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from garmin_parse import cli
from garmin_parse.auth import GarminAuthError

runner = CliRunner()


def _bundle(activity_id: int, **extra_summary_fields):
    summary = {"activityId": activity_id, "activityType": {"typeKey": "running"}}
    summary.update(extra_summary_fields)
    return {
        "summary": summary,
        "detail": {"summaryDTO": {}},
        "splits": {"some": "splits"},
        "hr_zones": [{"zoneNumber": 1, "secsInZone": 60}],
    }


def test_sync_flattens_bundles_and_writes_each(monkeypatch, tmp_path):
    bundles = [_bundle(1), _bundle(2), _bundle(3)]

    written: list[dict] = []

    def fake_get_client(*args, **kwargs):
        return object()

    def fake_fetch_new_activities(client, activities_dir):
        return bundles

    def fake_write_activity_file(activity, activities_dir):
        written.append(activity)
        return Path(activities_dir) / "fake.md"

    monkeypatch.setattr(cli.auth_module, "get_client", fake_get_client)
    monkeypatch.setattr(
        cli.activities_module, "fetch_new_activities", fake_fetch_new_activities
    )
    monkeypatch.setattr(cli.render_module, "write_activity_file", fake_write_activity_file)

    result = runner.invoke(
        cli.app, ["sync", "--activities-dir", str(tmp_path)]
    )

    assert result.exit_code == 0
    assert "3 new activities saved" in result.stdout
    assert len(written) == 3

    for i, activity in enumerate(written, start=1):
        # Flattened: summary fields merged to top level.
        assert activity["activityId"] == i
        assert activity["activityType"] == {"typeKey": "running"}
        # Plus the three extra keys from the bundle, alongside summary fields.
        assert activity["detail"] == {"summaryDTO": {}}
        assert activity["splits"] == {"some": "splits"}
        assert activity["hr_zones"] == [{"zoneNumber": 1, "secsInZone": 60}]
        # No leftover "summary" key -- it was flattened, not nested.
        assert "summary" not in activity


def test_sync_zero_new_activities_prints_up_to_date(monkeypatch, tmp_path):
    def fake_get_client(*args, **kwargs):
        return object()

    def fake_fetch_new_activities(client, activities_dir):
        return []

    write_calls = []

    def fake_write_activity_file(activity, activities_dir):
        write_calls.append(activity)
        return Path(activities_dir) / "fake.md"

    monkeypatch.setattr(cli.auth_module, "get_client", fake_get_client)
    monkeypatch.setattr(
        cli.activities_module, "fetch_new_activities", fake_fetch_new_activities
    )
    monkeypatch.setattr(cli.render_module, "write_activity_file", fake_write_activity_file)

    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])

    assert result.exit_code == 0
    assert "0 new activities" in result.stdout
    assert "up to date" in result.stdout
    assert write_calls == []


def test_sync_auth_failure_produces_clean_error(monkeypatch, tmp_path):
    def fake_get_client(*args, **kwargs):
        raise GarminAuthError("Garmin login failed: bad credentials")

    monkeypatch.setattr(cli.auth_module, "get_client", fake_get_client)

    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])

    assert result.exit_code != 0
    # A clean error message, not a raw traceback dumped to the console.
    assert "Garmin login failed" in result.output
    assert "Traceback" not in result.output


def test_sync_fetch_failure_produces_clean_error(monkeypatch, tmp_path):
    def fake_get_client(*args, **kwargs):
        return object()

    def fake_fetch_new_activities(client, activities_dir):
        raise RuntimeError("session expired")

    monkeypatch.setattr(cli.auth_module, "get_client", fake_get_client)
    monkeypatch.setattr(
        cli.activities_module, "fetch_new_activities", fake_fetch_new_activities
    )

    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])

    assert result.exit_code != 0
    assert "session expired" in result.output
    assert "Traceback" not in result.output
