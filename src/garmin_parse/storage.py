"""Validated reads and atomic replacement; no Garmin imports or credentials."""
from __future__ import annotations

import json
import hashlib
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from garmin_parse.schema import Activity


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=".pending-", delete=False) as stream:
            name = stream.name
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def write_json(path: Path, value: dict) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def load_records(directory: Path) -> tuple[dict[str, Activity], list[str]]:
    records, warnings = {}, []
    for path in sorted(directory.glob("*/*.json")):
        if path.name.endswith(".details.json"):
            continue
        try:
            if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > 2_000_000:
                raise ValueError("unsupported file")
            record = Activity.model_validate_json(path.read_text(encoding="utf-8"))
            if record.activity_id in records:
                warnings.append(f"Duplicate activity ID {record.activity_id}")
                if records[record.activity_id].fetched_at >= record.fetched_at:
                    continue
            records[record.activity_id] = record
        except (ValueError, OSError):
            warnings.append(f"Invalid activity record: {path.name}")
    return records, warnings


@contextmanager
def sync_lock(directory: Path):
    import fcntl

    directory.mkdir(parents=True, exist_ok=True)
    with (directory / ".sync.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another sync is already running") from None
        try:
            yield
        finally:
            fcntl.flock(stream, fcntl.LOCK_UN)


def load_capture(directory: Path, record: Activity):
    """Locate only this ID's sidecar under the configured root; verify commit digest."""
    from garmin_parse.activity_data import ExtendedCapture, MAX_CAPTURE_BYTES

    if record.capture is None:
        raise ValueError("Extended data has not been fetched; run sync --backfill")
    paths = list(directory.glob(f"*/*_{record.activity_id}.details.json"))
    if len(paths) != 1:
        raise ValueError("Extended data is missing or duplicated; run sync --reconcile")
    path = paths[0]
    if path.is_symlink() or path.parent.is_symlink() or path.stat().st_size > MAX_CAPTURE_BYTES:
        raise ValueError("Invalid extended activity file")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != record.capture.sha256:
        raise ValueError("Extended data checksum mismatch; run sync to repair")
    result = ExtendedCapture.model_validate_json(data)
    if result.activity_id != record.activity_id:
        raise ValueError("Extended activity identity mismatch")
    return result
