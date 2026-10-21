import json
from unittest.mock import MagicMock

import pytest
from garminconnect.exceptions import GarminConnectAuthenticationError

from garmin_parse import sync
from garmin_parse.schema import normalize
from garmin_parse.storage import atomic_write, load_records, sync_lock


def summary(i, **kw):
    return {"activityId": i, "startTimeLocal": "2026-01-01 08:00:00", "activityType": {"typeKey": "running"}, "distance": 5000, **kw}


def fake(rows, page_size=100):
    client = MagicMock()
    client.get_activities.side_effect = lambda start, limit: rows[start:start + limit]
    client.get_activity.return_value = {"summaryDTO": {}}
    client.get_activity_splits.return_value = {"lapDTOs": []}
    client.get_activity_hr_in_timezones.return_value = []
    client.get_activity_details.return_value = {"metricDescriptors": [], "activityDetailMetrics": []}
    for endpoint in ("get_activity_typed_splits", "get_activity_split_summaries", "get_activity_power_in_timezones", "get_activity_weather", "get_activity_gear", "get_activity_exercise_sets"):
        getattr(client, endpoint).return_value = {}
    from garminconnect.exceptions import GarminConnectNotFoundError
    client.download_activity.side_effect = GarminConnectNotFoundError("No original recording")
    return client


def test_resume_backfill_idempotence_and_pagination(tmp_path):
    rows = [summary(i) for i in range(5)]
    client = fake(rows)
    stats = sync.run_sync(client, tmp_path, mode='backfill', page_size=2)
    assert (stats.new, stats.scanned, stats.history_scanned) == (5, 5, True)
    assert client.get_activities.call_count == 3
    client = fake(rows)
    stats = sync.run_sync(client, tmp_path, mode='backfill', page_size=2)
    assert stats.skipped == 5
    client.get_activity.assert_not_called()
    state = json.loads((tmp_path / '.sync-state.json').read_text())
    assert state['status'] == 'success'
    assert state['last_complete_history_scan_at']


def test_older_missed_metadata_changes_and_reconcile(tmp_path):
    sync.run_sync(fake([summary(3), summary(1)]), tmp_path)
    rows = [summary(3, distance=6000), summary(2), summary(1)]
    stats = sync.run_sync(fake(rows), tmp_path, page_size=1)
    assert (stats.new, stats.updated, stats.skipped) == (1, 1, 1)
    stats = sync.run_sync(fake(rows), tmp_path, mode='reconcile')
    assert stats.updated == 3


def test_failed_detail_partial_and_repair(tmp_path):
    client = fake([summary(1)])
    client.get_activity.side_effect = RuntimeError('detail unavailable')
    stats = sync.run_sync(client, tmp_path)
    assert stats.incomplete == 1 and not stats.successful
    assert json.loads((tmp_path / '.sync-state.json').read_text())['status'] == 'partial'
    stats = sync.run_sync(fake([summary(1)]), tmp_path)
    assert stats.updated == 1 and stats.incomplete == 0


def test_duplicate_id_not_fetched_twice(tmp_path):
    client = fake([summary(1), summary(1), summary(2)])
    stats = sync.run_sync(client, tmp_path, page_size=2)
    assert stats.new == stats.scanned == 2
    assert client.get_activity.call_count == 2


def test_interrupted_scan_keeps_progress(tmp_path):
    client = fake([summary(1), summary(2)])
    client.get_activities.side_effect = [[summary(1)], RuntimeError('network failed')]
    with pytest.raises(RuntimeError):
        sync.run_sync(client, tmp_path, page_size=1)
    assert len(load_records(tmp_path)[0]) == 1
    assert json.loads((tmp_path / '.sync-state.json').read_text())['status'] == 'failed'
    stats = sync.run_sync(fake([summary(1), summary(2)]), tmp_path)
    assert stats.skipped == 1 and stats.new == 1


def test_atomic_write_failure_and_pair_recovery(tmp_path, monkeypatch):
    import garmin_parse.storage as storage
    path = tmp_path / 'file'
    path.write_text('original')
    original = storage.os.replace
    monkeypatch.setattr(storage.os, 'replace', lambda *a: (_ for _ in ()).throw(OSError('disk failure')))
    with pytest.raises(OSError):
        atomic_write(path, 'new')
    assert path.read_text() == 'original'
    assert not list(tmp_path.glob('.pending-*'))
    monkeypatch.setattr(storage.os, 'replace', original)
    sync.run_sync(fake([summary(1)]), tmp_path)
    next(tmp_path.glob('*/*.md')).write_text('interrupted or changed')
    assert sync.run_sync(fake([summary(1)]), tmp_path).updated == 1


def test_auth_failure_not_silently_incomplete(tmp_path):
    client = fake([summary(1)])
    client.get_activity.side_effect = GarminConnectAuthenticationError('expired')
    with pytest.raises(GarminConnectAuthenticationError):
        sync.run_sync(client, tmp_path)


def test_legacy_markdown_backfill(tmp_path):
    year = tmp_path / '2026'
    year.mkdir()
    (year / '2026-01-01_running_1.md').write_text('legacy')
    assert sync.run_sync(fake([summary(1)]), tmp_path, mode='backfill').updated == 1
    assert len([p for p in tmp_path.glob('*/*.json') if not p.name.endswith('.details.json')]) == 1


def test_parse_error_is_partial_and_lock_excludes(tmp_path):
    stats = sync.run_sync(fake([summary(1, distance=-10), summary(2)]), tmp_path)
    assert stats.failed == 1 and stats.new == 1 and not stats.successful
    with sync_lock(tmp_path):
        with pytest.raises(RuntimeError, match='already running'):
            sync.run_sync(fake([]), tmp_path)


def test_network_retry_is_bounded_and_auth_not_retried(monkeypatch):
    from requests.exceptions import Timeout
    waits = []
    monkeypatch.setattr(sync.time, 'sleep', waits.append)
    fn = MagicMock(side_effect=[Timeout(), Timeout(), 'ok'])
    assert sync.retry(fn) == 'ok'
    assert waits == [1, 2]
    auth = MagicMock(side_effect=GarminConnectAuthenticationError('expired'))
    with pytest.raises(GarminConnectAuthenticationError):
        sync.retry(auth)
    assert auth.call_count == 1


def test_auth_failure_visible_without_losing_success(tmp_path):
    from garmin_parse.auth import GarminAuthError
    sync.run_sync(fake([]), tmp_path)
    previous = json.loads((tmp_path / '.sync-state.json').read_text())['last_successful_sync_at']
    def fail():
        raise GarminAuthError('expired')
    with pytest.raises(GarminAuthError):
        sync.sync_with_auth(fail, tmp_path)
    state = json.loads((tmp_path / '.sync-state.json').read_text())
    assert state['last_successful_sync_at'] == previous
    assert state['status'] == 'failed' and state['failure_phase'] == 'authentication'


def test_partial_refresh_retains_last_success_and_markdown(tmp_path):
    sync.run_sync(fake([summary(1, averageHR=140)]), tmp_path)
    old = load_records(tmp_path)[0]['1']
    text = next(tmp_path.glob('*/*.md')).read_text()
    client = fake([summary(1)])
    client.get_activity.side_effect = RuntimeError('temporary')
    assert sync.run_sync(client, tmp_path, mode='reconcile').incomplete == 1
    new = load_records(tmp_path)[0]['1']
    assert new.metrics.average_hr_bpm == old.metrics.average_hr_bpm == 140
    assert new.last_successful_fetch_at == old.last_successful_fetch_at
    assert new.fetched_at > old.fetched_at
    assert next(tmp_path.glob('*/*.md')).read_text() == text


def test_unavailable_legacy_history_not_claimed_complete(tmp_path):
    year = tmp_path / '2026'
    year.mkdir()
    (year / '2026-01-01_running_99.md').write_text('legacy')
    stats = sync.run_sync(fake([]), tmp_path, mode='backfill')
    assert not stats.successful and stats.incomplete == 1
    assert 'last_successful_sync_at' not in json.loads((tmp_path / '.sync-state.json').read_text())


def test_metadata_date_type_change_does_not_duplicate_files(tmp_path):
    sync.run_sync(fake([summary(1)]), tmp_path)
    original = next(p for p in tmp_path.glob('*/*.json') if not p.name.endswith('.details.json'))
    stats = sync.run_sync(fake([summary(1, startTimeLocal='2025-12-31 23:50:00', activityType={'typeKey': 'treadmill_running'})]), tmp_path)
    assert stats.updated == 1
    assert [p for p in tmp_path.glob('*/*.json') if not p.name.endswith('.details.json')] == [original]
    assert str(load_records(tmp_path)[0]['1'].local_date) == '2025-12-31'


def test_nonadvancing_pagination_is_bounded(tmp_path):
    client = fake([])
    client.get_activities.side_effect = None
    client.get_activities.return_value = [summary(1)]
    with pytest.raises(ValueError, match='pagination'):
        sync.run_sync(client, tmp_path, page_size=1)
    assert client.get_activities.call_count == 4
    assert len(load_records(tmp_path)[0]) == 1


def test_unrepaired_invalid_storage_prevents_success(tmp_path):
    year = tmp_path / '2026'
    year.mkdir()
    (year / 'broken.json').write_text('{}')
    stats = sync.run_sync(fake([]), tmp_path)
    assert stats.storage_warnings == 1 and not stats.successful
