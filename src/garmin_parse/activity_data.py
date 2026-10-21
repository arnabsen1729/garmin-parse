"""Extended activity capture, including sensor samples, with route/identity removal.

Sanitized source fields retain Garmin/FIT names and units. Analytical metrics
remain in schema.py; source fields are never silently treated as normalized SI.
"""
from __future__ import annotations

import io
import math
import re
import time
import zipfile
from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

CAPTURE_VERSION = 1
MAX_CHART_SAMPLES = 1_000_000
MAX_CAPTURE_BYTES = 64_000_000
ResourceStatus = Literal["available", "empty", "not_found", "not_linked", "failed"]
RESOURCE_NAMES = (
    "summary", "detail", "splits", "hr_zones", "time_series", "typed_splits",
    "split_summaries", "power_zones", "weather", "gear", "exercise_sets", "fit", "workout",
)
ResourceName = Literal[
    "summary", "detail", "splits", "hr_zones", "time_series", "typed_splits",
    "split_summaries", "power_zones", "weather", "gear", "exercise_sets", "fit", "workout",
]


def _key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def private_field(name: str) -> bool:
    key = _key(name)
    words = set(re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name).lower().replace("-", "_").split("_"))
    return (
        bool(words & {"lat", "lon", "lng", "coords"}) or
        any(token in key for token in (
            "latitude", "longitude", "latlng", "latlon", "polyline", "coordinate",
            "geometry", "geoposition", "geolocation", "waypoint", "boundingbox",
            "position", "location", "gps", "route", "course", "mapurl", "mappoly", "stationid",
            "password", "token", "authorization", "credential", "email", "serialnumber",
            "userprofile", "owner", "displayname", "profileimage", "weatherstation",
        ))
        or key in {
            "lat", "lon", "lng", "startlat", "endlat", "startlon", "endlon", "startlng", "endlng",
            "position", "positions", "location", "locations", "map", "maps", "course", "courseid",
            "startpoint", "endpoint", "north", "south", "east", "west", "bounds", "bbox",
            "userid", "profileid", "useruuid", "deviceid", "deviceuuid", "deviceinfo", "fileid",
            "creator", "createdby", "contact", "address", "city", "country", "state", "url", "uri",
            "metrics", "activitydetailmetrics",  # positional arrays require named decoding first
        }
    )


def sanitize(value, *, depth: int = 0):
    """Remove location/identity fields recursively; never serialize opaque binaries."""
    if depth > 40:
        raise ValueError("Activity payload exceeds nesting limit")
    if isinstance(value, dict):
        # Garmin descriptors and FIT field envelopes can encode a field's name as a value.
        if any(isinstance(value.get(k), str) and private_field(value[k]) for k in ("key", "fieldName")):
            return None
        return {k: sanitize(v, depth=depth + 1) for k, v in value.items() if isinstance(k, str) and not private_field(k)}
    if isinstance(value, (list, tuple)):
        return [sanitize(v, depth=depth + 1) for v in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        # URLs/embedded GeoJSON can carry encoded routes despite an innocuous key.
        if "://" in value or '"coordinates"' in value.lower():
            return None
        return value
    raise ValueError("Unsupported activity payload type")


def decode_chart(payload: dict) -> dict:
    """Decode indexed metrics before filtering; dropping only descriptors leaks GPS."""
    descriptors = payload.get("metricDescriptors") or []
    rows = payload.get("activityDetailMetrics") or []
    if not isinstance(descriptors, list) or not isinstance(rows, list):
        raise ValueError("Invalid chart arrays")
    if rows and not descriptors:
        raise ValueError("Chart samples have no descriptors; cannot safely classify columns")
    selected = []
    indexes, names = set(), set()
    for descriptor in descriptors:
        if not isinstance(descriptor, dict):
            raise ValueError("Invalid metric descriptor")
        index, name = descriptor.get("metricsIndex"), descriptor.get("key")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0 or not isinstance(name, str):
            raise ValueError("Cannot safely decode unnamed chart column")
        if index in indexes or name in names:
            raise ValueError("Ambiguous chart metric descriptors")
        indexes.add(index)
        names.add(name)
        if not private_field(name) and "semicircle" not in str(descriptor).lower():
            selected.append((index, name, sanitize(descriptor)))
    samples = []
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get("metrics"), list):
            raise ValueError("Invalid chart sample")
        # Only described columns are emitted. Unknown positional columns cannot leak.
        sample = {name: sanitize(row["metrics"][index]) for index, name, _ in selected if index < len(row["metrics"])}
        # Preserve explicitly named timestamps and other sample attributes.
        sample.update(sanitize({k: v for k, v in row.items() if k != "metrics"}))
        samples.append(sample)
    metadata = sanitize({k: v for k, v in payload.items() if k not in {"metricDescriptors", "activityDetailMetrics"}})
    return {"metadata": metadata, "descriptors": [d for _, _, d in selected], "samples": samples,
            "sample_count": len(samples), "requested_max_samples": MAX_CHART_SAMPLES,
            "resolution_warning": "Garmin chart responses may be downsampled; FIT records preserve the original recorded samples when available."}


def decode_fit(download: bytes) -> list[dict]:
    """Decode original FIT/ZIP entirely in memory; no raw file is written to disk."""
    import fitdecode

    if not isinstance(download, bytes) or len(download) > MAX_CAPTURE_BYTES:
        raise ValueError("Invalid or oversized FIT download")
    streams = [download]
    if zipfile.is_zipfile(io.BytesIO(download)):
        with zipfile.ZipFile(io.BytesIO(download)) as archive:
            files = [info for info in archive.infolist() if not info.is_dir() and info.filename.lower().endswith('.fit')]
            if not files:
                raise ValueError("Original download contains no FIT recording")
            if sum(info.file_size for info in files) > MAX_CAPTURE_BYTES:
                raise ValueError("Uncompressed FIT exceeds safety limit")
            streams = [archive.read(info) for info in files]
    messages = []
    excluded = {"file_id", "file_creator", "device_info", "user_profile", "developer_data_id", "field_description", "software", "capabilities"}
    for content in streams:
        with fitdecode.FitReader(io.BytesIO(content), check_crc=fitdecode.CrcCheck.RAISE, error_handling=fitdecode.ErrorHandling.RAISE) as reader:
            for frame in reader:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                name = frame.name
                if not name or name in excluded or private_field(name):
                    continue
                fields = {}
                for field in frame.fields:
                    key = field.name
                    # Unnamed binary/developer fields cannot be classified safely.
                    if not isinstance(key, str) or key.startswith("unknown_") or private_field(key):
                        continue
                    units = field.units
                    if units and "semicircle" in units.lower():
                        continue
                    if frame.name == "record" and getattr(getattr(field, "field", None), "native_field_num", None) in {0, 1}:
                        continue
                    envelope = {"value": sanitize(field.value), "units": units}
                    if key in fields:
                        previous = fields[key]
                        fields[key] = [*previous, envelope] if isinstance(previous, list) else [previous, envelope]
                    else:
                        fields[key] = envelope
                if fields:
                    messages.append({"message": name, "fields": fields})
    return messages


class ExtendedCapture(BaseModel):
    model_config = ConfigDict(extra="forbid")
    capture_version: Literal[1] = CAPTURE_VERSION
    activity_id: str
    fetched_at: datetime
    resources: dict[str, JsonValue]
    statuses: dict[str, ResourceStatus]
    warnings: list[str]


def capture_activity(client, bundle: dict, activity_id: str) -> ExtendedCapture:
    """Read activity-only endpoints. A real 404 means unavailable, never API success."""
    from garminconnect import Garmin
    from garminconnect.exceptions import GarminConnectAuthenticationError, GarminConnectTooManyRequestsError, GarminConnectNotFoundError
    from requests.exceptions import ConnectionError, Timeout

    resources, statuses = {}, {}
    warnings = ["Location/route fields, account/device identity and unnamed FIT fields are excluded by the capture policy."]
    for name in ("summary", "detail", "splits", "hr_zones"):
        value = bundle.get(name)
        resources[name] = sanitize(value)
        statuses[name] = "failed" if value is None else "available" if value else "empty"
    endpoints = {
        "time_series": (lambda: client.get_activity_details(activity_id, maxchart=MAX_CHART_SAMPLES, maxpoly=0), decode_chart),
        "typed_splits": (lambda: client.get_activity_typed_splits(activity_id), sanitize),
        "split_summaries": (lambda: client.get_activity_split_summaries(activity_id), sanitize),
        "power_zones": (lambda: client.get_activity_power_in_timezones(activity_id), sanitize),
        "weather": (lambda: client.get_activity_weather(activity_id), sanitize),
        "gear": (lambda: client.get_activity_gear(activity_id), sanitize),
        "exercise_sets": (lambda: client.get_activity_exercise_sets(activity_id), sanitize),
        "fit": (lambda: client.download_activity(activity_id, dl_fmt=Garmin.ActivityDownloadFormat.ORIGINAL), decode_fit),
    }
    summary, detail = bundle.get("summary") or {}, bundle.get("detail") or {}
    metadata = detail.get("metadataDTO") or {}
    workout_id = next((source.get(key) for source in (metadata, detail, summary) if isinstance(source, dict)
                       for key in ("associatedWorkoutId", "workoutId") if source.get(key) not in (None, 0, "0", "")), None)
    if workout_id is None:
        resources["workout"], statuses["workout"] = None, "not_linked"
    else:
        def fetch_workout():
            if not str(workout_id).isdigit():
                raise ValueError("Invalid linked workout ID")
            return client.get_workout_by_id(workout_id)
        endpoints["workout"] = (fetch_workout, sanitize)
    for name, (fetch, decode) in endpoints.items():
        try:
            for attempt in range(3):
                try:
                    value = fetch()
                    break
                except (ConnectionError, Timeout):
                    if attempt == 2:
                        raise
                    time.sleep(2 ** attempt)
            if value is None:
                raise ValueError("Endpoint returned no response")
            resources[name] = decode(value)
            present = bool(resources[name])
            if name == "time_series":
                present = bool(resources[name]["samples"])
            statuses[name] = "available" if present else "empty"
        except (GarminConnectAuthenticationError, GarminConnectTooManyRequestsError):
            raise
        except GarminConnectNotFoundError:
            resources[name] = None
            statuses[name] = "not_found"
            warnings.append(f"{name}: Garmin has no resource for this activity (404)")
        except Exception as exc:
            # Exception messages and raw payloads can contain locations or personal data.
            resources[name] = None
            statuses[name] = "failed"
            warnings.append(f"{name}: fetch or parsing failed ({type(exc).__name__}); retry on next sync")
    if statuses["fit"] in {"not_found", "empty"}:
        warnings.append("No original FIT samples available; chart data may be downsampled")
    return ExtendedCapture(activity_id=activity_id, fetched_at=datetime.now(timezone.utc), resources=resources, statuses=statuses, warnings=warnings)
