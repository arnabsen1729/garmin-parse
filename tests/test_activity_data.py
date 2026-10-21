"""Extended capture tests use synthetic data, including real generated FIT bytes."""
import io
import json
import struct
import zipfile
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest
from garminconnect import Garmin
from garminconnect.exceptions import GarminConnectAuthenticationError, GarminConnectNotFoundError

from garmin_parse.activity_data import capture_activity, decode_chart, decode_fit, sanitize
from garmin_parse.query import QueryService
from garmin_parse.storage import load_capture, load_records
from garmin_parse.sync import run_sync


def synthetic_fit():
    from fitdecode.utils import compute_crc
    def definition(local, number, fields):
        return bytes([0x40 | local, 0, 0]) + struct.pack('<H', number) + bytes([len(fields)]) + b''.join(bytes(f) for f in fields)
    body = definition(0, 20, [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (3, 1, 2), (4, 1, 2)])
    body += b'\x00' + struct.pack('<IiiBB', 1_000_000_000, 100_000_000, 200_000_000, 145, 86)
    body += definition(1, 78, [(0, 4, 0x84)])  # HRV RR intervals, ms → seconds
    body += b'\x01' + struct.pack('<HH', 800, 900)
    body += definition(2, 0, [(3, 4, 0x8C)])  # file_id serial number
    body += b'\x02' + struct.pack('<I', 123456789)
    header = struct.pack('<BBHI4s', 14, 0x20, 2180, len(body), b'.FIT')
    header += struct.pack('<H', compute_crc(header))
    return header + body + struct.pack('<H', compute_crc(header + body))


def chart():
    return {
        'metricDescriptors': [
            {'metricsIndex': 2, 'key': 'directHeartRate', 'unit': {'unitKey': 'bpm'}},
            {'metricsIndex': 0, 'key': 'directLatitude'},
            {'metricsIndex': 4, 'key': 'directLongitude'},
            {'metricsIndex': 1, 'key': 'directRunCadence', 'unit': {'unitKey': 'spm'}},
            {'metricsIndex': 3, 'key': 'newSensorMetric', 'unit': {'unitKey': 'custom'}},
        ],
        'activityDetailMetrics': [
            {'metrics': [12.345678, 170, 145, 10, 76.54321], 'timestamp': 1000},
            {'metrics': [12.345679, 172, 149, None, 76.54322], 'timestamp': 2000},
        ],
        'geoPolylineDTO': {'polyline': 'encoded-route'},
    }


def base_bundle():
    return {'summary': {'activityId': 42, 'activityType': {'typeKey': 'running'}, 'startTimeLocal': '2026-10-01 08:00:00', 'distance': 5000, 'movingDuration': 1600, 'avgRespirationRate': 32, 'ownerId': 'do-not-save'}, 'detail': {'summaryDTO': {'minStamina': 65, 'maxTemperature': 28, 'performanceCondition': 4}}, 'splits': {'lapDTOs': []}, 'hr_zones': [{'zoneNumber': 1, 'secsInZone': 20}]}


def client():
    bundle = base_bundle()
    result = MagicMock()
    result.get_activities.return_value = [bundle['summary']]
    result.get_activity.return_value = bundle['detail']
    result.get_activity_splits.return_value = bundle['splits']
    result.get_activity_hr_in_timezones.return_value = bundle['hr_zones']
    result.get_activity_details.return_value = chart()
    result.get_activity_typed_splits.return_value = {'splits': [{'type': 'run', 'distance': 1000}]}
    result.get_activity_split_summaries.return_value = {'summaries': []}
    result.get_activity_power_in_timezones.return_value = [{'zoneNumber': 2, 'secsInZone': 50}]
    result.get_activity_weather.return_value = {'temperature': 26, 'windSpeed': 3, 'latitude': 12.345678, 'stationId': 'sensitive-location'}
    result.get_activity_gear.return_value = [{'displayName': 'private-profile', 'customMakeModel': 'Running shoes', 'userProfileId': 98765}]
    result.get_activity_exercise_sets.return_value = []
    result.download_activity.return_value = synthetic_fit()
    return result


def test_chart_decoding_removes_values_and_preserves_unknown_measurements():
    result = decode_chart(chart())
    text = json.dumps(result)
    for forbidden in ['12.345678', '76.54321', 'Latitude', 'Longitude', 'encoded-route']:
        assert forbidden not in text
    assert result['samples'][0] == {'directHeartRate': 145, 'directRunCadence': 170, 'newSensorMetric': 10, 'timestamp': 1000}
    assert result['samples'][1]['newSensorMetric'] is None
    assert result['descriptors'][0]['unit']['unitKey'] == 'bpm'


@pytest.mark.parametrize('field', ['startLatitude', 'endLongitude', 'position_lat', 'compressedLat', 'route', 'coordinates', 'geometry', 'lat', 'lon', 'ownerId', 'accessToken', 'userProfilePK', 'locationName', 'deviceSerialNumber', 'weatherStationDTO'])
def test_recursive_sensitive_field_removal(field):
    result = sanitize({'nested': [{field: 'private', 'averageHeartRate': 150, 'verticalRatio': 7.1}]})
    assert 'private' not in json.dumps(result)
    assert result['nested'][0]['averageHeartRate'] == 150


def test_source_field_envelopes_and_opaque_data_fail_closed():
    assert sanitize({'key': 'directLatitude', 'value': 42}) is None
    assert sanitize({'arbitrary': 'https://map.example/?lat=42'})['arbitrary'] is None
    assert sanitize({'metrics': [42, 99], 'calories': 100}) == {'calories': 100}
    with pytest.raises(ValueError):
        sanitize({'unknown': b'opaque-route'})


@pytest.mark.parametrize('bad', [
    {'metricDescriptors': [{'key': 'heartRate'}], 'activityDetailMetrics': []},
    {'metricDescriptors': [{'key': 'a', 'metricsIndex': 0}, {'key': 'b', 'metricsIndex': 0}], 'activityDetailMetrics': []},
    {'metricDescriptors': [], 'activityDetailMetrics': [{'metrics': 'not-an-array'}]},
])
def test_malformed_chart_fails_without_retaining_positional_values(bad):
    with pytest.raises(ValueError):
        decode_chart(bad)


def test_real_fit_decode_includes_hr_cadence_rr_but_no_route_or_serial():
    result = decode_fit(synthetic_fit())
    record = next(m for m in result if m['message'] == 'record')
    assert record['fields']['heart_rate'] == {'value': 145, 'units': 'bpm'}
    assert record['fields']['cadence']['value'] == 86  # FIT cadence retains source units, not silently doubled
    hrv = next(m for m in result if m['message'] == 'hrv')
    assert hrv['fields']['time']['value'] == [0.8, 0.9]
    text = json.dumps(result)
    assert 'position_lat' not in text and 'position_long' not in text
    assert '123456789' not in text and '100000000' not in text and '200000000' not in text


def test_original_zip_in_memory_and_invalid_archives():
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('../../original.fit', synthetic_fit())
        archive.writestr('route.gpx', '<coordinates>secret</coordinates>')
    assert decode_fit(stream.getvalue()) == decode_fit(synthetic_fit())
    with pytest.raises(Exception):
        decode_fit(b'not a FIT file')
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, 'w') as archive:
        archive.writestr('route.gpx', '<coordinates>secret</coordinates>')
    with pytest.raises(ValueError, match='no FIT'):
        decode_fit(stream.getvalue())


def test_capture_full_endpoint_surface():
    c = client()
    result = capture_activity(c, base_bundle(), '42')
    assert set(result.statuses.values()) <= {'available', 'empty', 'not_linked'}
    assert result.resources['detail']['summaryDTO']['minStamina'] == 65
    assert result.resources['summary']['avgRespirationRate'] == 32
    assert result.resources['power_zones'][0]['secsInZone'] == 50
    assert result.resources['weather']['temperature'] == 26
    text = result.model_dump_json()
    assert 'do-not-save' not in text and 'sensitive-location' not in text and 'private-profile' not in text
    c.get_activity_details.assert_called_once_with('42', maxchart=1_000_000, maxpoly=0)
    c.download_activity.assert_called_once_with('42', dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL)


def test_not_found_is_distinct_from_transient_or_auth_failure():
    c = client()
    c.get_activity_weather.side_effect = GarminConnectNotFoundError('absent')
    c.get_activity_typed_splits.side_effect = RuntimeError('private-data-do-not-log')
    result = capture_activity(c, base_bundle(), '42')
    assert result.statuses['weather'] == 'not_found'
    assert result.statuses['typed_splits'] == 'failed'
    assert 'private-data' not in result.model_dump_json()
    c.get_activity_details.side_effect = GarminConnectAuthenticationError('expired')
    with pytest.raises(GarminConnectAuthenticationError):
        capture_activity(c, base_bundle(), '42')


def test_persistence_query_pagination_and_repairs(tmp_path):
    stats = run_sync(client(), tmp_path)
    assert stats.successful
    summaries, warnings = load_records(tmp_path)
    assert len(summaries) == 1 and not warnings  # sidecars do not masquerade as normalized records
    saved = summaries['42']
    assert saved.schema_version == 2 and saved.capture
    assert load_capture(tmp_path, saved).activity_id == '42'
    service = QueryService(tmp_path)
    result = service.get_activity_data('42', resource='time_series', limit=1)
    assert result['total'] == 2 and result['next_offset'] == 1
    assert result['data'][0]['directHeartRate'] == 145
    assert service.get_activity_data('42', resource='time_series', offset=1, limit=1)['data'][0]['directHeartRate'] == 149
    assert service.get_activity_data('42', resource='fit', message_type='hrv')['data'][0]['fields']['time']['value'] == [0.8, 0.9]
    assert service.get_activity_data('42', resource='detail', field='summaryDTO')['data']['minStamina'] == 65
    c = client()
    assert run_sync(c, tmp_path).skipped == 1
    c.get_activity_details.assert_not_called()
    path = next(tmp_path.glob('*/*.details.json'))
    path.write_text('{}')
    with pytest.raises(ValueError, match='checksum'):
        service.get_activity_data('42')
    assert run_sync(client(), tmp_path).updated == 1


def test_failed_resource_preserves_previous_data_and_retries(tmp_path):
    assert run_sync(client(), tmp_path).successful
    old = load_records(tmp_path)[0]['42']
    c = client()
    c.get_activity_weather.side_effect = RuntimeError('offline')
    stats = run_sync(c, tmp_path, mode='reconcile')
    assert stats.incomplete == 1 and not stats.successful
    new = load_records(tmp_path)[0]['42']
    assert new.last_successful_fetch_at == old.last_successful_fetch_at
    data = QueryService(tmp_path).get_activity_data('42', resource='weather')
    assert data['status'] == 'failed' and data['data']['temperature'] == 26
    assert run_sync(client(), tmp_path).updated == 1
    assert load_records(tmp_path)[0]['42'].complete


def test_existing_v1_running_records_are_upgraded(tmp_path):
    from garmin_parse.schema import normalize
    from garmin_parse.render import render_activity_markdown, activity_file_path
    from garmin_parse.storage import atomic_write, write_json
    import hashlib
    bundle = base_bundle()
    record = normalize(bundle)
    record.schema_version = 1
    flat = {**bundle['summary'], **{k: bundle[k] for k in ('detail', 'splits', 'hr_zones')}}
    path = activity_file_path(flat, tmp_path)
    text = render_activity_markdown(flat)
    record.markdown_sha256 = hashlib.sha256(text.encode()).hexdigest()
    atomic_write(path, text)
    write_json(path.with_suffix('.json'), record.model_dump(mode='json'))
    assert run_sync(client(), tmp_path).updated == 1
    assert load_records(tmp_path)[0]['42'].capture is not None


def test_linked_workout_is_fetched_and_sanitized():
    bundle = base_bundle()
    bundle['detail']['metadataDTO'] = {'associatedWorkoutId': 99}
    c = client()
    c.get_workout_by_id.return_value = {'workoutName': 'Intervals', 'workoutSegments': [{'steps': [{'durationValue': 300}]}], 'ownerId': 'private'}
    result = capture_activity(c, bundle, '42')
    assert result.resources['workout']['workoutName'] == 'Intervals'
    assert result.statuses['workout'] == 'available'
    assert 'ownerId' not in result.resources['workout']
    c.get_workout_by_id.assert_called_once_with(99)
    c = client()
    assert capture_activity(c, base_bundle(), '42').statuses['workout'] == 'not_linked'
    c.get_workout_by_id.assert_not_called()


def test_mcp_extended_protocol_and_invalid_inputs(tmp_path):
    import asyncio
    from mcp.shared.memory import create_connected_server_and_client_session
    from garmin_parse.mcp_server import create_server
    assert run_sync(client(), tmp_path).successful
    snapshot = {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}

    async def run():
        async with create_connected_server_and_client_session(create_server(tmp_path)) as session:
            tools = (await session.list_tools()).tools
            tool = next(t for t in tools if t.name == 'get_activity_data')
            assert tool.annotations.readOnlyHint and tool.outputSchema
            result = await session.call_tool('get_activity_data', {'activity_id': '42', 'resource': 'fit', 'message_type': 'hrv', 'limit': 1})
            assert not result.isError, result
            assert result.structuredContent['data'][0]['fields']['time']['value'] == [0.8, 0.9]
            for inputs in [
                {'activity_id': '../../secret', 'resource': 'detail'},
                {'activity_id': '42', 'resource': '/etc/passwd'},
                {'activity_id': '42', 'resource': 'fit', 'limit': 1001},
                {'activity_id': '42', 'resource': 'detail', 'offset': -1},
                {'activity_id': '42', 'resource': 'detail', 'message_type': 'record'},
                {'activity_id': '42', 'resource': 'detail', 'field': 'nonexistent'},
            ]:
                assert (await session.call_tool('get_activity_data', inputs)).isError
    asyncio.run(run())
    assert snapshot == {str(p): p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}


def test_sidecar_write_interruption_is_repaired(tmp_path, monkeypatch):
    import garmin_parse.sync as sync_module
    assert run_sync(client(), tmp_path).successful
    original_write = sync_module.write_json
    def fail_commit(path, value):
        if path.name.endswith('_42.json'):
            raise OSError('interrupted manifest write')
        return original_write(path, value)
    monkeypatch.setattr(sync_module, 'write_json', fail_commit)
    c = client()
    c.get_activity_details.return_value['activityDetailMetrics'][0]['metrics'][2] = 155
    with pytest.raises(OSError):
        run_sync(c, tmp_path, mode='reconcile')
    with pytest.raises(ValueError, match='checksum'):
        QueryService(tmp_path).get_activity_data('42', resource='time_series')
    monkeypatch.setattr(sync_module, 'write_json', original_write)
    assert run_sync(client(), tmp_path).updated == 1


def test_sidecar_symlink_is_rejected(tmp_path):
    assert run_sync(client(), tmp_path).successful
    sidecar = next(tmp_path.glob('*/*.details.json'))
    other = tmp_path / 'external.json'
    sidecar.rename(other)
    sidecar.symlink_to(other)
    with pytest.raises(ValueError, match='Invalid extended'):
        QueryService(tmp_path).get_activity_data('42')


def test_fit_crc_errors_are_not_silent_partial_imports():
    content = bytearray(synthetic_fit())
    content[-1] ^= 0xFF
    with pytest.raises(Exception):
        decode_fit(bytes(content))


def test_oversized_sidecar_fails_without_truncating(tmp_path, monkeypatch):
    import garmin_parse.sync as sync_module
    monkeypatch.setattr(sync_module, 'MAX_CAPTURE_BYTES', 10)
    stats = run_sync(client(), tmp_path)
    assert stats.failed == 1 and not stats.successful
    assert not list(tmp_path.glob('*/*.details.json'))
    assert not list(tmp_path.glob('*/*.md'))


def test_nonrunning_sync_does_not_fetch_running_resources(tmp_path):
    c = client()
    c.get_activities.return_value[0]['activityType']['typeKey'] = 'cycling'
    assert run_sync(c, tmp_path).successful
    c.get_activity_details.assert_not_called()
    c.download_activity.assert_not_called()
    assert load_records(tmp_path)[0]['42'].capture is None


def test_snapshot_contains_no_gps_or_raw_downloads(tmp_path):
    assert run_sync(client(), tmp_path).successful
    for path in tmp_path.rglob('*'):
        if path.is_file():
            text = path.read_text()
            assert '12.345678' not in text and '76.54321' not in text
            assert '100000000' not in text and '200000000' not in text
            assert path.suffix not in {'.fit', '.zip', '.gpx', '.tcx'}
