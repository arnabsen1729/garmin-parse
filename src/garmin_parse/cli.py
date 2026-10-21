"""Typer commands for synchronization and read-only analytics MCP."""
from __future__ import annotations

import os
from pathlib import Path

import typer


app = typer.Typer()

DEFAULT_ACTIVITIES_DIR = Path("activities")


@app.callback()
def _callback() -> None:
    """Sync Garmin activities and query deterministic training analytics."""
    # Keep the command group explicit as additional commands are registered.


@app.command()
def sync(
    activities_dir: Path = typer.Option(DEFAULT_ACTIVITIES_DIR, "--activities-dir"),
    backfill: bool = typer.Option(False, "--backfill", help="Populate and repair JSON across all history."),
    reconcile: bool = typer.Option(False, "--reconcile", help="Refetch all records, including detail-only changes."),
) -> None:
    """Sync Garmin activities to Markdown and validated JSON."""
    from garmin_parse import auth as auth_module
    from garmin_parse.auth import GarminAuthError
    from garmin_parse.sync import sync_with_auth
    from garminconnect.exceptions import GarminConnectAuthenticationError

    if backfill and reconcile:
        raise typer.BadParameter("Choose either --backfill or --reconcile")
    try:
        stats = sync_with_auth(auth_module.get_client, activities_dir, mode="backfill" if backfill else "reconcile" if reconcile else "incremental")
    except (GarminAuthError, GarminConnectAuthenticationError) as exc:
        typer.secho(f"Authentication failure: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    except OSError as exc:
        typer.secho(f"Filesystem persistence failure: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    except Exception as exc:
        typer.secho(f"Garmin sync failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1) from None
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with Path(summary_path).open("a") as stream:
            stream.write("\n### Garmin sync\n\n")
            stream.write("| Scanned | New | Updated | Incomplete | Skipped | Failed | Storage warnings |\n|---|---|---|---|---|---|---|\n")
            stream.write(f"| {stats.scanned} | {stats.new} | {stats.updated} | {stats.incomplete} | {stats.skipped} | {stats.failed} | {stats.storage_warnings} |\n")
    typer.echo("Garmin sync completed" if stats.successful else "Garmin sync partial")
    for label, value in (("Activities scanned", stats.scanned), ("New activities", stats.new),
                         ("Updated activities", stats.updated), ("Incomplete activities", stats.incomplete),
                         ("Skipped activities", stats.skipped), ("Failed activities", stats.failed), ("Storage warnings", stats.storage_warnings)):
        typer.echo(f"{label}: {value}")
    if not stats.successful:
        raise typer.Exit(2)


@app.command()
def mcp(
    activities_dir: Path = typer.Option(DEFAULT_ACTIVITIES_DIR, "--activities-dir"),
    transport: str = typer.Option("stdio", "--transport", help="stdio or streamable-http (OAuth required)."),
    host: str = typer.Option("127.0.0.1", "--host"),
    port: int = typer.Option(8000, "--port", min=1, max=65535),
) -> None:
    """Start a read-only analytics server; does not authenticate with Garmin."""
    from garmin_parse.mcp_server import create_server

    if transport not in {"stdio", "streamable-http"}:
        raise typer.BadParameter("Unsupported transport")
    try:
        server = create_server(activities_dir, remote=transport == "streamable-http", host=host, port=port)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None
    server.run(transport=transport)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
