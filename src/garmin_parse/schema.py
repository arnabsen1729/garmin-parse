"""Versioned, location-free analytical records. Garmin DTOs stay at this boundary."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import date, datetime, timezone
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Number = Annotated[float, Field(ge=0, allow_inf_nan=False, strict=True)]
Identifier = Annotated[str, StringConstraints(pattern=r"^[0-9]+$", max_length=32)]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Metrics(Model):
    distance_m: Number | None = None
    moving_duration_s: Number | None = None
    elapsed_duration_s: Number | None = None
    average_speed_m_s: Number | None = None
    maximum_speed_m_s: Number | None = None
    average_pace_s_km: Number | None = None
    calories_kcal: Number | None = None
    elevation_gain_m: Number | None = None
    elevation_loss_m: Number | None = None
    average_hr_bpm: Number | None = None
    maximum_hr_bpm: Number | None = None
    aerobic_training_effect: Number | None = None
    anaerobic_training_effect: Number | None = None
    average_cadence_spm: Number | None = None
    maximum_cadence_spm: Number | None = None
    stride_length_m: Number | None = None
    ground_contact_time_ms: Number | None = None
    vertical_oscillation_cm: Number | None = None
    vertical_ratio_percent: Number | None = None
    ground_contact_balance_percent: Number | None = None
    average_power_w: Number | None = None


class Segment(Model):
    index: int = Field(ge=0)
    metrics: Metrics


class CaptureManifest(Model):
    capture_version: Literal[1] = 1
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    statuses: dict[str, Literal["available", "empty", "not_found", "not_linked", "failed"]]
    warnings: list[str] = Field(default_factory=list)


class Activity(Model):
    schema_version: Literal[1, 2] = 2
    source: Literal["garmin_connect"] = "garmin_connect"
    activity_id: Identifier
    activity_type: str = Field(max_length=100)
    activity_name: str | None = Field(default=None, max_length=500)
    start_timestamp: datetime | None = None
    local_start: datetime
    local_date: date
    timezone: str | None = Field(default=None, max_length=100)
    metrics: Metrics
    hr_zones_s: dict[Annotated[str, StringConstraints(pattern=r"^[0-9]{1,2}$")], Number] = Field(default_factory=dict, max_length=20)
    laps: list[Segment] = Field(default_factory=list, max_length=2000)
    fetched_at: datetime
    last_successful_fetch_at: datetime | None = None
    missing_resources: list[Literal["detail", "splits", "hr_zones"]] = Field(default_factory=list)
    summary_fingerprint: str
    markdown_sha256: str | None = None
    capture: CaptureManifest | None = None

    @model_validator(mode="after")
    def check_dates(self):
        if self.local_start.date() != self.local_date:
            raise ValueError("local_date must match local_start")
        if self.fetched_at.tzinfo is None or self.start_timestamp is not None and self.start_timestamp.tzinfo is None:
            raise ValueError("fetched_at and start_timestamp require timezone offsets")
        if self.last_successful_fetch_at is not None and self.last_successful_fetch_at.tzinfo is None:
            raise ValueError("last_successful_fetch_at requires a timezone offset")
        return self

    @property
    def complete(self) -> bool:
        return not self.missing_resources and (self.capture is None or "failed" not in self.capture.statuses.values())


# Units follow Garmin's summary DTO: distance m, durations s, speed m/s,
# stride cm, oscillation cm, contact time ms. No guessing unknown DTO fields.
FIELDS = {
    "distance_m": ("distance",),
    "moving_duration_s": ("movingDuration",),
    "elapsed_duration_s": ("elapsedDuration", "duration"),
    "average_speed_m_s": ("averageSpeed",),
    "maximum_speed_m_s": ("maxSpeed",),
    "calories_kcal": ("calories",),
    "elevation_gain_m": ("elevationGain",),
    "elevation_loss_m": ("elevationLoss",),
    "average_hr_bpm": ("averageHR",),
    "maximum_hr_bpm": ("maxHR",),
    "aerobic_training_effect": ("aerobicTrainingEffect", "trainingEffect"),
    "anaerobic_training_effect": ("anaerobicTrainingEffect",),
    "average_cadence_spm": ("averageRunningCadenceInStepsPerMinute", "averageRunningCadence"),
    "maximum_cadence_spm": ("maxRunningCadenceInStepsPerMinute", "maxRunningCadence"),
    "stride_length_m": ("avgStrideLength",),
    "ground_contact_time_ms": ("avgGroundContactTime",),
    "vertical_oscillation_cm": ("avgVerticalOscillation",),
    "vertical_ratio_percent": ("avgVerticalRatio",),
    "ground_contact_balance_percent": ("avgGroundContactBalance",),
    "average_power_w": ("avgPower", "averagePower"),
}


def is_running(kind: str) -> bool:
    return kind in {"running", "street_running", "road_running", "track_running", "treadmill_running", "indoor_running", "trail_running", "ultra_run", "virtual_run", "obstacle_run"} or kind.endswith("_running")


def metric_values(*sources: dict, running: bool = False) -> Metrics:
    values = {}
    for target, keys in FIELDS.items():
        value = next((s[k] for k in keys for s in sources if s.get(k) is not None), None)
        if value is not None:
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
                raise ValueError(f"Invalid numeric metric: {target}")
            values[target] = value / 100 if target == "stride_length_m" else value
    distance, duration = values.get("distance_m"), values.get("moving_duration_s")
    if running and distance and duration is not None:
        values["average_pace_s_km"] = duration * 1000 / distance
    return Metrics(**values)


def fingerprint(summary: dict) -> str:
    # Hash the listing, including modification metadata; persist no raw personal DTO.
    return hashlib.sha256(json.dumps(summary, sort_keys=True, allow_nan=False).encode()).hexdigest()


def normalize(bundle: dict) -> Activity:
    summary = bundle["summary"]
    for key in ("detail", "splits"):
        if bundle.get(key) is not None and not isinstance(bundle[key], dict):
            raise ValueError(f"Invalid {key} resource")
    zones_input = bundle.get("hr_zones")
    if zones_input is not None and (not isinstance(zones_input, list) or any(not isinstance(z, dict) for z in zones_input)):
        raise ValueError("Invalid HR zone resource")
    detail = bundle.get("detail") or {}
    dto = detail.get("summaryDTO") or {}
    if not isinstance(dto, dict):
        raise ValueError("Invalid summaryDTO")
    if not isinstance(summary.get("activityType") or {}, dict):
        raise ValueError("Invalid activity type")
    kind = (summary.get("activityType") or {}).get("typeKey", "unknown")
    local = datetime.fromisoformat(summary["startTimeLocal"])
    utc = summary.get("startTimeGMT")
    timestamp = datetime.fromisoformat(utc) if utc else None
    if timestamp and timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    zone_meta = summary.get("timeZoneUnitDTO") or {}
    if not isinstance(zone_meta, dict):
        raise ValueError("Invalid timezone metadata")
    now = datetime.now(timezone.utc)
    zones = {}
    for zone in bundle.get("hr_zones") or []:
        number = zone.get("zoneNumber", zone.get("zone"))
        seconds = zone.get("secsInZone", zone.get("secondsInZone"))
        if number is not None and seconds is not None:
            zones[str(number)] = seconds
    splits = bundle.get("splits") or {}
    laps = splits.get("lapDTOs", [])
    if not isinstance(laps, list) or any(not isinstance(lap, dict) for lap in laps):
        raise ValueError("Invalid lapDTOs")
    return Activity(
        activity_id=str(summary["activityId"]), activity_type=kind,
        activity_name=summary.get("activityName"), local_start=local,
        local_date=local.date(), start_timestamp=timestamp,
        timezone=zone_meta.get("timeZone"),
        metrics=metric_values(summary, detail, dto, running=is_running(kind)),
        hr_zones_s=zones,
        laps=[Segment(index=i, metrics=metric_values(lap, running=is_running(kind))) for i, lap in enumerate(laps)],
        fetched_at=now,
        last_successful_fetch_at=now if all(bundle.get(key) is not None for key in ("detail", "splits", "hr_zones")) else None,
        missing_resources=[key for key in ("detail", "splits", "hr_zones") if bundle.get(key) is None],
        summary_fingerprint=fingerprint(summary),
    )
