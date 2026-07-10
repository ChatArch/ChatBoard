"""CLI entrypoint for ChatBoard."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import click
from chatstyle import (
    CommandField,
    CommandSchema,
    add_interactive_option,
    resolve_command_inputs,
)

from chatboard import __version__
from chatboard.services import archive as archive_service
from chatboard.services import discussion as discussion_service
from chatboard.services.cards import card_detail, ensure_card, find_card_path, move_card
from chatboard.services.workspace import catalog as build_catalog
from chatboard.services.workspace import scan as scan_workspace


CARD_ENSURE_SCHEMA = CommandSchema(
    name="project-card-ensure",
    fields=(CommandField("project_path", prompt="project path", required=True),),
)
CARD_SHOW_SCHEMA = CommandSchema(
    name="project-card-show",
    fields=(CommandField("card_id", prompt="card id", required=True),),
)
CARD_MOVE_SCHEMA = CommandSchema(
    name="project-card-move",
    fields=(
        CommandField("card_id", prompt="card id", required=True),
        CommandField(
            "area",
            prompt="target area",
            kind="select",
            required=True,
            choices=("projects", "discussion", "archive", "discard", "trash"),
        ),
    ),
)
DISCUSSION_CREATE_SCHEMA = CommandSchema(
    name="project-discussion-create",
    fields=(CommandField("title", prompt="title", required=True),),
)
DISCUSSION_ADD_ITEM_SCHEMA = CommandSchema(
    name="project-discussion-add-item",
    fields=(
        CommandField("discussion_id", prompt="discussion id", required=True),
        CommandField("card_id", prompt="card id", required=True),
    ),
)
ARCHIVE_RUN_SCHEMA = CommandSchema(
    name="project-archive-run",
    fields=(CommandField("card_id", prompt="card id", required=True),),
)
DISCARD_SCHEMA = CommandSchema(
    name="project-discard",
    fields=(
        CommandField("card_id", prompt="card id", required=True),
        CommandField("reason", prompt="reason", required=True),
    ),
)


def _resolve(
    schema: CommandSchema,
    provided: dict[str, Any],
    interactive: bool | None,
    usage: str,
) -> dict[str, Any]:
    return resolve_command_inputs(
        schema=schema,
        provided=provided,
        interactive=interactive,
        usage=usage,
    )


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
@click.argument("project_path", required=False, type=click.Path(path_type=Path))
@add_interactive_option
def project_card_ensure(project_path: Path | None, interactive: bool | None) -> None:
    """Create card.md metadata for an existing Project if missing."""

    values = _resolve(
        CARD_ENSURE_SCHEMA,
        {"project_path": project_path},
        interactive,
        "Usage: chatbd project card ensure [PROJECT_PATH]",
    )
    project_path_value = Path(values["project_path"])
    try:
        _json(ensure_card(project_path_value).to_dict())
    except FileNotFoundError as exc:
        raise click.ClickException(f"project directory not found: {project_path_value}") from exc


@project_card.command("show")
@click.argument("card_id", required=False)
@add_interactive_option
def project_card_show(card_id: str | None, interactive: bool | None) -> None:
    """Show the detail projection for a Project card."""

    values = _resolve(
        CARD_SHOW_SCHEMA,
        {"card_id": card_id},
        interactive,
        "Usage: chatbd project card show [CARD_ID]",
    )
    resolved_card_id = values["card_id"]
    project_path = find_card_path(resolved_card_id)
    if project_path is None:
        raise click.ClickException(f"card not found: {resolved_card_id}")
    _json(card_detail(project_path))


@project_card.command("move")
@click.argument("card_id", required=False)
@click.argument(
    "area",
    required=False,
    type=click.Choice(["projects", "discussion", "archive", "discard", "trash"]),
)
@click.option("--stage", default=None, help="Optional target stage.")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
@add_interactive_option
def project_card_move(
    card_id: str | None,
    area: str | None,
    stage: str | None,
    dry_run: bool,
    interactive: bool | None,
) -> None:
    """Move a Project card between workspace areas."""

    values = _resolve(
        CARD_MOVE_SCHEMA,
        {"card_id": card_id, "area": area},
        interactive,
        "Usage: chatbd project card move [CARD_ID] [AREA]",
    )
    try:
        _json(
            move_card(
                values["card_id"],
                area=values["area"],
                stage=stage,
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.group("discussion")
def project_discussion() -> None:
    """Create Discussion topics and add Project items."""


@project_discussion.command("create")
@click.argument("title", required=False)
@click.option("--slug", default=None, help="Optional MM-DD-prefixed directory name.")
@add_interactive_option
def project_discussion_create(
    title: str | None,
    slug: str | None,
    interactive: bool | None,
) -> None:
    """Create a project-like Discussion topic."""

    values = _resolve(
        DISCUSSION_CREATE_SCHEMA,
        {"title": title},
        interactive,
        "Usage: chatbd project discussion create [TITLE]",
    )
    try:
        _json(discussion_service.create_discussion(title=values["title"], slug=slug))
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc


@project_discussion.command("add-item")
@click.argument("discussion_id", required=False)
@click.argument("card_id", required=False)
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
@add_interactive_option
def project_discussion_add_item(
    discussion_id: str | None,
    card_id: str | None,
    dry_run: bool,
    interactive: bool | None,
) -> None:
    """Move a Project card into a Discussion topic's Items directory."""

    values = _resolve(
        DISCUSSION_ADD_ITEM_SCHEMA,
        {"discussion_id": discussion_id, "card_id": card_id},
        interactive,
        "Usage: chatbd project discussion add-item [DISCUSSION_ID] [CARD_ID]",
    )
    try:
        _json(
            discussion_service.add_item(
                discussion_id=values["discussion_id"],
                card_id=values["card_id"],
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.group("archive")
def project_archive() -> None:
    """Archive completed Project cards."""


@project_archive.command("run")
@click.argument("card_id", required=False)
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
@add_interactive_option
def project_archive_run(
    card_id: str | None,
    dry_run: bool,
    interactive: bool | None,
) -> None:
    """Move a Project card into the dated archive area."""

    values = _resolve(
        ARCHIVE_RUN_SCHEMA,
        {"card_id": card_id},
        interactive,
        "Usage: chatbd project archive run [CARD_ID]",
    )
    try:
        _json(archive_service.archive(values["card_id"], dry_run=dry_run))
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project.command("discard")
@click.argument("card_id", required=False)
@click.option("--reason", help="Why this Project is being discarded.")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
@add_interactive_option
def project_discard(
    card_id: str | None,
    reason: str | None,
    dry_run: bool,
    interactive: bool | None,
) -> None:
    """Move a Project card into the formal Discard area."""

    values = _resolve(
        DISCARD_SCHEMA,
        {"card_id": card_id, "reason": reason},
        interactive,
        "Usage: chatbd project discard [CARD_ID] [--reason TEXT]",
    )
    try:
        _json(
            archive_service.discard(
                values["card_id"],
                reason=values["reason"],
                dry_run=dry_run,
            )
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


if __name__ == "__main__":
    main()
