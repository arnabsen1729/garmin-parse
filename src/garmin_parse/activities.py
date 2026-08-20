"""Fetch new activity summaries and per-activity detail from Garmin Connect.

Pages through ``Garmin.get_activities`` (newest-first) and, for each
activity ID not already present on disk (per ``existing.existing_activity_ids``),
fetches the additional detail needed to render a stats-page-equivalent
record: full activity detail, splits, and HR-zone breakdown.

Design notes:

* Pagination stops once a run of consecutive already-known activity IDs
  has been seen (``stop_after_consecutive_known``), or once Garmin returns
  a short/empty page. This avoids re-walking a user's entire multi-year
  history on every run once they're caught up, while still coping with a
  first-ever sync (empty ``known_ids`` -> no early stop -> full history).
* A failure fetching the *list* of activities (``get_activities`` itself)
  is not caught here: it propagates, since it likely means something
  fundamental is wrong (e.g. an expired auth session) and continuing would
  silently produce partial/garbage results.
* A failure fetching one *sub-resource* of an otherwise-known-good
  activity (splits, HR zones, ...) is caught per-call so one flaky
  endpoint doesn't drop the whole activity; that field is set to ``None``
  and a warning is logged.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from garmin_parse.existing import existing_activity_ids

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = 100
DEFAULT_STOP_AFTER_CONSECUTIVE_KNOWN = 20


def _safe_fetch(activity_id: str, description: str, fn: Callable[[], Any]) -> Any | None:
    """Call ``fn`` and return its result, or ``None`` (with a warning) on failure."""
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - deliberately broad: isolate one sub-call
        logger.warning(
            "Failed to fetch %s for activity %s: %s", description, activity_id, exc
        )
        return None


def _fetch_activity_bundle(client: Any, summary: dict[str, Any], activity_id: str) -> dict[str, Any]:
    """Fetch additional detail for one new activity, tolerating partial failures."""
    detail = _safe_fetch(activity_id, "activity detail", lambda: client.get_activity(activity_id))
    splits = _safe_fetch(
        activity_id, "activity splits", lambda: client.get_activity_splits(activity_id)
    )
    hr_zones = _safe_fetch(
        activity_id,
        "HR time-in-zones",
        lambda: client.get_activity_hr_in_timezones(activity_id),
    )
    return {
        "summary": summary,
        "detail": detail,
        "splits": splits,
        "hr_zones": hr_zones,
    }


def fetch_new_activities(
    client: Any,
    activities_dir: Path | str,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    stop_after_consecutive_known: int = DEFAULT_STOP_AFTER_CONSECUTIVE_KNOWN,
) -> list[dict[str, Any]]:
    """Fetch summary + detail for every Garmin activity not yet synced locally.

    Pages through ``client.get_activities(start, limit=page_size)`` from
    newest to oldest. Activities whose ID is already in
    ``existing_activity_ids(activities_dir)`` are skipped (no detail
    fetched). Pagination stops once ``stop_after_consecutive_known``
    consecutive already-known IDs have been seen in a row, or once Garmin
    returns a page shorter than ``page_size`` (i.e. no more history).

    Returns a list of per-activity dicts, each with keys ``summary``,
    ``detail``, ``splits``, ``hr_zones`` (the latter three ``None`` if that
    particular sub-call failed).

    Raises whatever ``client.get_activities`` raises (e.g. on an expired
    auth session) rather than swallowing it, since a partial page listing
    is not safe to treat as "no more new activities".
    """
    known_ids = existing_activity_ids(activities_dir)

    new_activities: list[dict[str, Any]] = []
    start = 0
    consecutive_known = 0

    while True:
        page = client.get_activities(start=start, limit=page_size)
        if not page:
            break

        for summary in page:
            activity_id = str(summary.get("activityId"))

            if activity_id in known_ids:
                consecutive_known += 1
                if consecutive_known >= stop_after_consecutive_known:
                    return new_activities
                continue

            consecutive_known = 0
            new_activities.append(_fetch_activity_bundle(client, summary, activity_id))

        if len(page) < page_size:
            break
        start += page_size

    return new_activities
