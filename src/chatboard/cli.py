"""CLI entrypoint for ChatBoard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click

from chatboard import __version__
from chatboard.services import archive as archive_service
from chatboard.services import discussion as discussion_service
from chatboard.services.cards import card_detail, ensure_card, find_card_path, move_card
from chatboard.services.workspace import catalog as build_catalog
from chatboard.services.workspace import scan as scan_workspace


def _json(data: Any) -> None:
    click.echo(json.dumps(data, ensure_ascii=False, indent=2))


@click.group()
@click.version_option(__version__, prog_name="chatbd")
def main() -> None:
    """Run the ChatBoard web app and Project management tools."""


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to bind.")
@click.option("--reload", is_flag=True, help="Enable uvicorn reload.")
def serve(host: str, port: int, reload: bool) -> None:
    """Start the ChatBoard web UI."""

    from chatboard.web.serve import serve as _serve

    _serve(host=host, port=port, reload=reload)


@main.group()
def project() -> None:
    """Inspect and manage ChatArch workspace Projects."""


@project.command("scan")
def project_scan() -> None:
    """Scan the workspace and list Project cards without writing metadata."""

    _json([card.to_dict() for card in scan_workspace()])


@project.command("catalog")
def project_catalog() -> None:
    """Print the Project board catalog grouped by columns."""

    _json(build_catalog())


@project.group("card")
def project_card() -> None:
    """Inspect and move Project cards."""


@project_card.command("ensure")
@click.argument("project_path", type=click.Path(path_type=Path))
def project_card_ensure(project_path: Path) -> None:
    """Create card.md metadata for an existing Project if missing."""

    _json(ensure_card(project_path).to_dict())


@project_card.command("show")
@click.argument("card_id")
def project_card_show(card_id: str) -> None:
    """Show the detail projection for a Project card."""

    project_path = find_card_path(card_id)
    if project_path is None:
        raise click.ClickException(f"card not found: {card_id}")
    _json(card_detail(project_path))


@project_card.command("move")
@click.argument("card_id")
@click.argument("area", type=click.Choice(["projects", "discussion", "archive", "discard", "trash"]))
@click.option("--stage", default=None, help="Optional target stage.")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
def project_card_move(card_id: str, area: str, stage: str | None, dry_run: bool) -> None:
    """Move a Project card between workspace areas."""

    try:
        _json(move_card(card_id, area=area, stage=stage, dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.group("discussion")
def project_discussion() -> None:
    """Create Discussion topics and add Project items."""


@project_discussion.command("create")
@click.argument("title")
@click.option("--slug", default=None, help="Optional MM-DD-prefixed directory name.")
def project_discussion_create(title: str, slug: str | None) -> None:
    """Create a project-like Discussion topic."""

    try:
        _json(discussion_service.create_discussion(title=title, slug=slug))
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc


@project_discussion.command("add-item")
@click.argument("discussion_id")
@click.argument("card_id")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
def project_discussion_add_item(discussion_id: str, card_id: str, dry_run: bool) -> None:
    """Move a Project card into a Discussion topic's Items directory."""

    try:
        _json(
            discussion_service.add_item(
                discussion_id=discussion_id,
                card_id=card_id,
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.group("archive")
def project_archive() -> None:
    """Archive completed Project cards."""


@project_archive.command("run")
@click.argument("card_id")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
def project_archive_run(card_id: str, dry_run: bool) -> None:
    """Move a Project card into the dated archive area."""

    try:
        _json(archive_service.archive(card_id, dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.command("discard")
@click.argument("card_id")
@click.option("--reason", required=True, help="Why this Project is being discarded.")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
def project_discard(card_id: str, reason: str, dry_run: bool) -> None:
    """Move a Project card into the formal Discard area."""

    try:
        _json(archive_service.discard(card_id, reason=reason, dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
