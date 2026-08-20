"""Detection of already-synced Garmin activity files.

Activity files are written elsewhere as
``activities/<YYYY>/<YYYY-MM-DD>_<ActivityType>_<ActivityID>.md``. Before
syncing, the CLI needs to know which activity IDs already have a file on
disk so it can skip re-fetching/re-rendering them.
"""

from __future__ import annotations

import re
from pathlib import Path

_ACTIVITY_FILENAME_RE = re.compile(r"_(\d+)\.md$")


def existing_activity_ids(activities_dir: Path | str) -> set[str]:
    """Return the set of Garmin activity IDs already saved on disk.

    Walks ``activities_dir`` for ``*/*.md`` files (one level of year
    subfolders) and extracts the trailing ``<ActivityID>`` component from
    each filename, i.e. the digits between the last ``_`` and ``.md``.

    Tolerates ``activities_dir`` not existing (returns an empty set) and
    skips any filename that doesn't match the expected
    ``..._<digits>.md`` pattern instead of raising.
    """
    directory = Path(activities_dir)
    if not directory.is_dir():
        return set()

    ids: set[str] = set()
    for path in directory.glob("*/*.md"):
        match = _ACTIVITY_FILENAME_RE.search(path.name)
        if match:
            ids.add(match.group(1))
    return ids
