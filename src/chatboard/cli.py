"""CLI entrypoint for chatboard."""

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
@click.version_option(__version__, prog_name="chatboard")
def main() -> None:
    """ChatArch workspace board."""


@main.command()
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--ensure", is_flag=True, help="Create missing card.md files.")
def scan(root: Path | None, ensure: bool) -> None:
    """Scan workspace project areas and list cards."""

    _json([card.to_dict() for card in scan_workspace(root=root, ensure=ensure)])


@main.command()
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--ensure", is_flag=True, help="Create missing card.md files.")
def catalog(root: Path | None, ensure: bool) -> None:
    """Print board catalog grouped by columns."""

    _json(build_catalog(root=root, ensure=ensure))


@main.group()
def card() -> None:
    """Project card operations."""


@card.command("ensure")
@click.argument("project_path", type=click.Path(path_type=Path))
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def card_ensure(project_path: Path, root: Path | None) -> None:
    """Create card.md for a project if missing."""

    _json(ensure_card(project_path, root=root).to_dict())


@card.command("show")
@click.argument("card_id")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def card_show(card_id: str, root: Path | None) -> None:
    """Show a card detail projection."""

    project_path = find_card_path(card_id, root=root)
    if project_path is None:
        raise click.ClickException(f"card not found: {card_id}")
    _json(card_detail(project_path, root=root))


@card.command("move")
@click.argument("card_id")
@click.argument("area", type=click.Choice(["projects", "discussion", "archive", "discard", "trash"]))
@click.option("--stage", default=None, help="Optional target stage.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--dry-run", is_flag=True, help="Show destination without moving files.")
def card_move(card_id: str, area: str, stage: str | None, root: Path | None, dry_run: bool) -> None:
    """Move a card between workspace areas."""

    try:
        _json(move_card(card_id, area=area, stage=stage, root=root, dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@main.group()
def discussion() -> None:
    """Discussion workflow operations."""


@discussion.command("create")
@click.argument("title")
@click.option("--slug", default=None, help="Optional MM-DD-prefixed directory name.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def discussion_create(title: str, slug: str | None, root: Path | None) -> None:
    """Create a project-like discussion topic."""

    try:
        _json(discussion_service.create_discussion(title=title, slug=slug, root=root))
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc


@discussion.command("add-item")
@click.argument("discussion_id")
@click.argument("card_id")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--dry-run", is_flag=True, help="Show destination without moving files.")
def discussion_add_item(discussion_id: str, card_id: str, root: Path | None, dry_run: bool) -> None:
    """Move a project card into a discussion's Items directory."""

    try:
        _json(discussion_service.add_item(discussion_id=discussion_id, card_id=card_id, root=root, dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@discussion.command("open")
@click.argument("card_id")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def discussion_open(card_id: str, root: Path | None) -> None:
    """Mark a card discussion as open for review."""

    _json(discussion_service.open_discussion(card_id, root=root))


@discussion.command("decide")
@click.argument("card_id")
@click.argument("text")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def discussion_decide(card_id: str, text: str, root: Path | None) -> None:
    """Record a discussion decision."""

    _json(discussion_service.add_decision(card_id, text=text, root=root))


@main.group()
def archive() -> None:
    """Archive workflow operations."""


@archive.command("ready")
@click.argument("card_id")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
def archive_ready(card_id: str, root: Path | None) -> None:
    """Mark a card as archive-ready."""

    _json(archive_service.mark_ready(card_id, root=root))


@archive.command("run")
@click.argument("card_id")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--dry-run", is_flag=True, help="Show destination without moving files.")
def archive_run(card_id: str, root: Path | None, dry_run: bool) -> None:
    """Move a card into archive."""

    _json(archive_service.archive(card_id, root=root, dry_run=dry_run))


@main.command()
@click.argument("card_id")
@click.option("--reason", required=True, help="Discard reason.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--dry-run", is_flag=True, help="Show destination without moving files.")
def discard(card_id: str, reason: str, root: Path | None, dry_run: bool) -> None:
    """Soft-delete a card into the discard area."""

    _json(archive_service.discard(card_id, reason=reason, root=root, dry_run=dry_run))


@main.command("trash")
@click.argument("card_id")
@click.option("--reason", required=True, help="Trash reason.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--dry-run", is_flag=True, help="Show destination without moving files.")
def trash_cmd(card_id: str, reason: str, root: Path | None, dry_run: bool) -> None:
    """Move a card into workspace .trash."""

    _json(archive_service.trash(card_id, reason=reason, root=root, dry_run=dry_run))


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to bind.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--reload", is_flag=True, help="Enable uvicorn reload.")
def serve(host: str, port: int, root: Path | None, reload: bool) -> None:
    """Start the ChatBoard web UI."""

    from chatboard.web.serve import serve as _serve

    _serve(host=host, port=port, root=root, reload=reload)


if __name__ == "__main__":
    main()
