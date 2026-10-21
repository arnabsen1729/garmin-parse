from copy import deepcopy

import pytest
from pydantic import ValidationError

from garmin_parse.schema import Activity, normalize


@pytest.fixture
def bundle():
    return {"summary": {"activityId": 123, "activityName": "Workout", "startTimeLocal": "2026-09-13 23:55:00", "startTimeGMT": "2026-09-13 18:25:00", "activityType": {"typeKey": "treadmill_running"}, "distance": 5000, "movingDuration": 1500}, "detail": {"summaryDTO": {"avgStrideLength": 125, "avgGroundContactTime": 230, "avgVerticalOscillation": 8.2}, "latitude": 23, "owner": {"email": "secret"}}, "splits": {"lapDTOs": [{"distance": 1000, "movingDuration": 300, "averageHR": 140}]}, "hr_zones": [{"zoneNumber": 1, "secsInZone": 0}, {"zoneNumber": 2, "secondsInZone": 600}]}


def test_normalize_units_privacy_and_roundtrip(bundle):
    record = normalize(bundle)
    assert record.metrics.stride_length_m == 1.25
    assert record.metrics.ground_contact_time_ms == 230
    assert record.metrics.vertical_oscillation_cm == 8.2
    assert record.metrics.average_pace_s_km == 300
    assert record.metrics.average_hr_bpm is None
    assert record.hr_zones_s == {"1": 0, "2": 600}
    assert record.laps[0].metrics.average_pace_s_km == 300
    assert str(record.local_date) == "2026-09-13"
    assert record.start_timestamp.utcoffset().total_seconds() == 0
    text = record.model_dump_json()
    assert 'latitude' not in text and 'secret' not in text
    assert Activity.model_validate_json(text) == record


@pytest.mark.parametrize('kind', ['running', 'cycling', 'track_running', 'virtual_run', 'strength_training', 'unknown'])
def test_types_and_missing_metrics(bundle, kind):
    bundle['summary']['activityType']['typeKey'] = kind
    bundle['summary'].pop('distance')
    bundle['detail'] = None
    record = normalize(bundle)
    assert record.metrics.distance_m is None
    assert record.metrics.average_pace_s_km is None
    assert record.missing_resources == ['detail']


@pytest.mark.parametrize('value', [-1, float('nan'), float('inf'), '5000', True])
def test_invalid_measurements_rejected(bundle, value):
    bundle['summary']['distance'] = value
    with pytest.raises(ValueError):
        normalize(bundle)


def test_zero_distance_and_unknown_fields(bundle):
    bundle['summary'].update(distance=0, newUnknownField={'gps': [1, 2]})
    assert normalize(bundle).metrics.average_pace_s_km is None
    assert 'newUnknownField' not in normalize(bundle).model_dump()


def test_invalid_identity_and_hr_zone(bundle):
    bundle['summary']['activityId'] = '../../secret'
    with pytest.raises(ValidationError):
        normalize(bundle)
    bundle['summary']['activityId'] = 1
    bundle['hr_zones'][0]['secsInZone'] = -2
    with pytest.raises(ValidationError):
        normalize(bundle)


@pytest.mark.parametrize('key,value', [('detail', []), ('splits', []), ('hr_zones', {}), ('hr_zones', [1])])
def test_malformed_resources_rejected(bundle, key, value):
    bundle[key] = value
    with pytest.raises(ValueError):
        normalize(bundle)


def test_date_consistency_and_schema_version(bundle):
    data = normalize(bundle).model_dump(mode='json')
    data['local_date'] = '2026-09-14'
    with pytest.raises(ValueError, match='local_date'):
        Activity.model_validate(data)
    data['local_date'] = '2026-09-13'
    data['schema_version'] = 99
    with pytest.raises(ValidationError):
        Activity.model_validate(data)
