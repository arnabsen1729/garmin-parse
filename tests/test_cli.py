"""CLI integration tests exercise actual synchronization with a fake Garmin client."""
import json
from unittest.mock import MagicMock

from typer.testing import CliRunner

from garmin_parse import cli, auth
from garmin_parse.auth import GarminAuthError

runner = CliRunner()


def client_with(rows):
    client = MagicMock()
    client.get_activities.return_value = rows
    client.get_activity.return_value = {"summaryDTO": {}}
    client.get_activity_splits.return_value = {"lapDTOs": []}
    client.get_activity_hr_in_timezones.return_value = []
    client.get_activity_details.return_value = {"metricDescriptors": [], "activityDetailMetrics": []}
    for endpoint in ("get_activity_typed_splits", "get_activity_split_summaries", "get_activity_power_in_timezones", "get_activity_weather", "get_activity_gear", "get_activity_exercise_sets"):
        getattr(client, endpoint).return_value = {}
    from garminconnect.exceptions import GarminConnectNotFoundError
    client.download_activity.side_effect = GarminConnectNotFoundError("No original recording")
    return client


def test_sync_writes_both_formats(monkeypatch, tmp_path):
    client = client_with([{"activityId": 1, "activityType": {"typeKey": "running"}, "startTimeLocal": "2026-01-01 08:00:00", "distance": 5000}])
    monkeypatch.setattr(auth, "get_client", lambda: client)
    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "New activities: 1" in result.stdout
    assert len(list(tmp_path.glob('*/*.md'))) == 1
    assert json.loads(next(p for p in tmp_path.glob('*/*.json') if not p.name.endswith('.details.json')).read_text())["metrics"]["distance_m"] == 5000


def test_sync_zero_new(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "get_client", lambda: client_with([]))
    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])
    assert result.exit_code == 0
    assert "New activities: 0" in result.stdout


def test_sync_auth_failure(monkeypatch, tmp_path):
    def fail():
        raise GarminAuthError("bad credentials")
    monkeypatch.setattr(auth, "get_client", fail)
    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "bad credentials" in result.output
    assert "Traceback" not in result.output


def test_sync_fetch_failure(monkeypatch, tmp_path):
    client = client_with([])
    client.get_activities.side_effect = RuntimeError("session expired")
    monkeypatch.setattr(auth, "get_client", lambda: client)
    result = runner.invoke(cli.app, ["sync", "--activities-dir", str(tmp_path)])
    assert result.exit_code == 1
    assert "session expired" in result.output


def test_mutually_exclusive_modes():
    result = runner.invoke(cli.app, ["sync", "--backfill", "--reconcile"])
    assert result.exit_code == 2


def test_http_refuses_missing_auth_configuration(monkeypatch, tmp_path):
    monkeypatch.delenv("GARMIN_MCP_ISSUER", raising=False)
    result = runner.invoke(cli.app, ["mcp", "--activities-dir", str(tmp_path), "--transport", "streamable-http"])
    assert result.exit_code == 2
    assert "HTTP requires" in result.output
