"""Command-line interface for garmin-parse.

Exposes a single ``sync`` command that:

1. Authenticates against Garmin Connect (``auth.get_client``).
2. Fetches every activity not yet saved locally
   (``activities.fetch_new_activities``), which returns a list of
   *bundles* shaped ``{"summary": ..., "detail": ..., "splits": ...,
   "hr_zones": ...}``.
3. Flattens each bundle (summary fields merged to the top level, alongside
   ``detail``/``splits``/``hr_zones``) into the flat shape expected by
   ``render.write_activity_file``, and writes it to disk.
4. Prints a one-line summary of how many new activities were saved.

``auth.py`` and ``activities.py``/``render.py`` disagree about shape (a
bundle vs. a flat dict) -- ``_flatten_bundle`` below is the glue that
adapts between them, kept local to the CLI so neither module needs to
change.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import typer

from garmin_parse import activities as activities_module
from garmin_parse import auth as auth_module
from garmin_parse import render as render_module
from garmin_parse.auth import GarminAuthError

app = typer.Typer()

DEFAULT_ACTIVITIES_DIR = Path("activities")


@app.callback()
def _callback() -> None:
    """garmin-parse: sync Garmin Connect activities to local Markdown files."""
    # Empty callback: its only purpose is to force Typer to keep "sync" as
    # a named subcommand (`garmin-parse sync ...`) instead of collapsing
    # to a single top-level command, which is Typer's default when an app
    # has exactly one registered command and no callback.


def _flatten_bundle(bundle: dict[str, Any]) -> dict[str, Any]:
    """Adapt an ``activities.fetch_new_activities`` bundle into the flat
    shape ``render.write_activity_file`` expects.

    A bundle looks like ``{"summary": {...}, "detail": ..., "splits": ...,
    "hr_zones": ...}``; ``render`` wants the summary's fields merged to the
    top level alongside ``detail``/``splits``/``hr_zones``.
    """
    summary = bundle.get("summary") or {}
    return {
        **summary,
        "detail": bundle.get("detail"),
        "splits": bundle.get("splits"),
        "hr_zones": bundle.get("hr_zones"),
    }


@app.command()
def sync(
    activities_dir: Path = typer.Option(
        DEFAULT_ACTIVITIES_DIR,
        "--activities-dir",
        help="Directory to read/write rendered activity Markdown files from/to.",
    ),
) -> None:
    """Sync new Garmin Connect activities to local Markdown files."""
    try:
        client = auth_module.get_client()
    except GarminAuthError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from None

    try:
        bundles = activities_module.fetch_new_activities(client, activities_dir)
    except Exception as exc:  # noqa: BLE001 - normalize into a clean CLI error
        typer.secho(
            f"Error: failed to fetch activities from Garmin Connect: {exc}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1) from None

    if not bundles:
        typer.echo("0 new activities — already up to date")
        return

    for bundle in bundles:
        flattened = _flatten_bundle(bundle)
        render_module.write_activity_file(flattened, activities_dir)

    typer.echo(f"{len(bundles)} new activities saved")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
