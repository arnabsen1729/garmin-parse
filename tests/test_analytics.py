from datetime import date

import pytest

from garmin_parse.analytics import compare, filter_activities, rolling, summarize, trends
from garmin_parse.schema import normalize


def record(i, day, distance=5000, duration=1500, kind='running', hr=None):
    return normalize({'summary': {'activityId': i, 'startTimeLocal': day + ' 23:50:00', 'startTimeGMT': day + ' 18:20:00', 'activityType': {'typeKey': kind}, 'distance': distance, 'movingDuration': duration, 'averageHR': hr}, 'detail': {}, 'splits': {}, 'hr_zones': []})


def test_weighted_pace_is_not_mean_and_hr_missing():
    rows = [record(1, '2026-01-01', 1000, 300, hr=140), record(2, '2026-01-02', 9000, 3600)]
    s = summarize(rows)
    assert s['aggregate_pace_s_km'] == 390
    assert s['mean_activity_pace_s_km'] == 350
    assert s['median_activity_pace_s_km'] == 350
    assert s['average_activity_hr_bpm'] == 140 and s['hr_sample_count'] == 1
    assert s['total_distance_m'] == 10000
    assert s['longest_activity_id'] == '2'


def test_zero_missing_and_nonrunning():
    rows = [record(1, '2026-01-01', 0, 100), record(2, '2026-01-01', None, None), record(3, '2026-01-01', kind='cycling')]
    selected = filter_activities(rows)
    assert len(selected) == 2
    s = summarize(selected)
    assert s['aggregate_pace_s_km'] is None
    assert s['missing_distance_count'] == 1
    assert s['missing_moving_duration_count'] == 1
    assert summarize([])['total_distance_m'] is None
    assert summarize([])['activity_count'] == 0


def test_calendar_buckets_local_dates_and_partial_weeks():
    rows = [record(1, '2026-08-31'), record(2, '2026-09-01', 6000), record(3, '2026-09-07', 7000)]
    monthly = trends(rows, granularity='monthly')
    assert [b['distance_m'] for b in monthly] == [5000, 13000]
    weekly = trends(rows, start_date=date(2026, 9, 1), end_date=date(2026, 9, 8))
    assert [b['distance_m'] for b in weekly] == [6000, 7000]
    assert all(b['partial_period'] for b in weekly)
    assert weekly[1]['change_percent'] == pytest.approx(100 / 6)
    assert len(filter_activities(rows, start_date=date(2026, 9, 1), end_date=date(2026, 9, 1))) == 1


def test_rolling_and_comparison():
    rows = [record(1, '2026-09-01', 1000), record(2, '2026-09-08', 2000), record(3, '2026-09-15', 4000)]
    result = rolling(rows, date(2026, 9, 15))
    assert result['distance_7d_m'] == 4000
    assert result['distance_28d_m'] == 7000
    assert result['week_over_week_change_percent'] == 100
    c = compare(rows[:1], rows[1:])
    assert c['difference_b_minus_a']['total_distance_m'] == 5000


def test_filters_subtypes_dedup_and_invalid_ranges():
    rows = [record(1, '2026-09-01', kind='treadmill_running'), record(2, '2026-09-02', kind='virtual_run')]
    assert len(filter_activities(rows + rows)) == 2
    assert len(filter_activities(rows, running_subtype='treadmill_running', min_distance_m=4000, max_distance_m=6000)) == 1
    with pytest.raises(ValueError):
        filter_activities(rows, start_date=date(2026, 10, 1), end_date=date(2026, 9, 1))
    with pytest.raises(ValueError):
        filter_activities(rows, min_distance_m=10, max_distance_m=1)
    with pytest.raises(ValueError):
        trends(rows, granularity='daily')


def test_hr_zone_aggregation_and_frequency_partial_week():
    rows = [record(1, '2026-09-01'), record(2, '2026-09-02')]
    for row in rows:
        row.hr_zones_s = {'1': 60, '2': 0}
    s = summarize(rows, start_date=date(2026, 9, 1), end_date=date(2026, 9, 2))
    assert s['hr_zones_s'] == {'1': 120, '2': 0}
    assert s['frequency_per_week'] == 7


def test_rolling_uses_preceding_history_outside_query_range(tmp_path):
    from garmin_parse.query import QueryService
    from garmin_parse.storage import write_json
    for row in [record(1, '2026-09-01'), record(2, '2026-09-02')]:
        write_json(tmp_path / '2026' / f'x_{row.activity_id}.json', row.model_dump(mode='json'))
    result = QueryService(tmp_path).get_training_summary(start_date=date(2026, 9, 2), end_date=date(2026, 9, 2))
    assert result['summary']['activity_count'] == 1
    assert result['rolling']['distance_7d_m'] == 10000
