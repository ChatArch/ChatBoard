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
    add_tree_option,
    resolve_command_inputs,
)

from chatboard import __version__
from chatboard.services import archive as archive_service
from chatboard.services import discussion as discussion_service
from chatboard.services.cards import (
    card_detail,
    card_status,
    create_task,
    delete_card,
    ensure_card,
    find_card_path,
    move_card,
    task_catalog,
    transition_card,
    update_card,
)
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
TASK_CREATE_SCHEMA = CommandSchema(
    name="project-task-create",
    fields=(CommandField("title", prompt="task title", required=True),),
)
TASK_CARD_SCHEMA = CommandSchema(
    name="project-task-card",
    fields=(CommandField("card_id", prompt="task card id", required=True),),
)
TASK_TRANSITION_SCHEMA = CommandSchema(
    name="project-task-transition",
    fields=(
        CommandField("card_id", prompt="task card id", required=True),
        CommandField(
            "transition",
            prompt="transition",
            kind="select",
            required=True,
            choices=("accept", "start", "review", "block", "unblock", "done", "move"),
        ),
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


@click.group(name="chatbd", context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(__version__, prog_name="chatbd")
@add_tree_option(renderer_options={"root_name": "chatbd"})
def main() -> None:
    """Run the ChatBoard web app and Project management tools."""


@main.command("paths")
def paths_command() -> None:
    """Print ChatEnv and ChatArch-owned ChatBoard runtime paths."""

    from chatboard.config import load_runtime_config, state_paths

    config = load_runtime_config()
    paths = state_paths(chatboard_home=config["chatboard_home"], backends_file=config["backends_file"])
    _json(
        {
            "paths": paths.safe_summary(),
            "config": {
                "service_url": config["service_url"],
                "workspace_root": str(config["workspace_root"]),
                "default_backend_name": config["default_backend_name"],
                "default_backend_url": config["default_backend_url"],
                "username_configured": bool(config["username"]),
                "password_configured": bool(config["password"]),
                "api_key_configured": bool(config["api_key"]),
                "default_backend_token_configured": bool(config["default_backend_token"]),
                "backends_json_configured": bool(config["backends_json"]),
                "session_ttl_seconds": config["session_ttl_seconds"],
                "cookie_secure_configured": bool(config["cookie_secure"]),
            },
        }
    )


@main.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind.")
@click.option("--port", default=8000, show_default=True, type=int, help="Port to bind.")
@click.option("--root", type=click.Path(path_type=Path), default=None, help="Workspace root. Defaults to ~/Playground.")
@click.option("--reload", is_flag=True, help="Enable uvicorn reload.")
@click.option("--username", default=None, help="Require this account name when login is enabled.")
@click.option("--password", default=None, help="Enable login with this password. Prefer CHATBOARD_PASSWORD for shared environments.")
@click.option("--password-file", type=click.Path(path_type=Path), default=None, help="Read login password from a file.")
def serve(
    host: str,
    port: int,
    root: Path | None,
    reload: bool,
    username: str | None,
    password: str | None,
    password_file: Path | None,
) -> None:
    """Start the ChatBoard web UI."""

    from chatboard.web.serve import serve as _serve

    _serve(host=host, port=port, root=root, reload=reload, username=username, password=password, password_file=password_file)


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


@project.group("task")
def project_task() -> None:
    """Manage Tasks shown on the Tasks board tab."""


@project_task.command("create")
@click.argument("title", required=False)
@click.option("--description", default="", help="Task body written to PRD.md.")
@click.option("--topic", default="tasks", show_default=True, help="Topic folder under projects/.")
@click.option("--slug", default=None, help="Project/task directory slug.")
@click.option("--source-platform", default=None, help="Origin platform, e.g. feishu or mattermost.")
@click.option("--source-url", default=None, help="Origin thread/message URL.")
@click.option("--accept-mode", type=click.Choice(["accept", "auto"]), default="accept", show_default=True)
@click.option(
    "--side-effect-level",
    type=click.Choice(["read_only", "local_write", "external_write", "infra", "irreversible"]),
    default="local_write",
    show_default=True,
)
@click.option("--next-action", default=None, help="Next action visible on the task card.")
@click.option("--assignee", default=None, help="Task assignee.")
@click.option("--tag", "tags", multiple=True, help="Task tag; can be repeated.")
@click.option("--dry-run", is_flag=True, help="Show the card without writing files.")
@add_interactive_option
def project_task_create(
    title: str | None,
    description: str,
    topic: str,
    slug: str | None,
    source_platform: str | None,
    source_url: str | None,
    accept_mode: str,
    side_effect_level: str,
    next_action: str | None,
    assignee: str | None,
    tags: tuple[str, ...],
    dry_run: bool,
    interactive: bool | None,
) -> None:
    """Create a Task card and task project skeleton."""

    values = _resolve(
        TASK_CREATE_SCHEMA,
        {"title": title},
        interactive,
        "Usage: chatbd project task create [TITLE]",
    )
    try:
        card = create_task(
            values["title"],
            description=description,
            topic=topic,
            slug=slug,
            source_platform=source_platform,
            source_url=source_url,
            accept_mode=accept_mode,
            side_effect_level=side_effect_level,
            next_action=next_action,
            assignee=assignee,
            tags=list(tags),
            dry_run=dry_run,
        )
        _json({"card": card.to_dict(), "dry_run": dry_run})
    except (FileExistsError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


@project_task.command("list")
def project_task_list() -> None:
    """Print the Tasks board grouped by task stages."""

    _json(task_catalog())


@project_task.command("status")
@click.argument("card_id", required=False)
@add_interactive_option
def project_task_status(card_id: str | None, interactive: bool | None) -> None:
    """Show a Task card's current status and available transitions."""

    values = _resolve(TASK_CARD_SCHEMA, {"card_id": card_id}, interactive, "Usage: chatbd project task status [CARD_ID]")
    try:
        status = card_status(values["card_id"])
    except FileNotFoundError as exc:
        raise click.ClickException(f"task not found: {values['card_id']}") from exc
    if status.get("type") != "task":
        raise click.ClickException(f"task not found: {values['card_id']}")
    _json(status)


@project_task.command("update")
@click.argument("card_id", required=False)
@click.option("--title", default=None, help="New task title.")
@click.option("--description", default=None, help="New task description.")
@click.option("--summary", default=None, help="New short summary.")
@click.option("--next-action", default=None, help="New next action.")
@click.option("--accept-mode", type=click.Choice(["accept", "auto"]), default=None)
@click.option(
    "--side-effect-level",
    type=click.Choice(["read_only", "local_write", "external_write", "infra", "irreversible"]),
    default=None,
)
@click.option("--assignee", default=None, help="New assignee.")
@click.option("--tag", "tags", multiple=True, help="Replace tags when supplied; can be repeated.")
@add_interactive_option
def project_task_update(
    card_id: str | None,
    title: str | None,
    description: str | None,
    summary: str | None,
    next_action: str | None,
    accept_mode: str | None,
    side_effect_level: str | None,
    assignee: str | None,
    tags: tuple[str, ...],
    interactive: bool | None,
) -> None:
    """Update Task metadata."""

    values = _resolve(TASK_CARD_SCHEMA, {"card_id": card_id}, interactive, "Usage: chatbd project task update [CARD_ID]")
    patch: dict[str, Any] = {}
    for key, value in {
        "title": title,
        "description": description,
        "summary": summary,
        "next_action": next_action,
        "accept_mode": accept_mode,
        "side_effect_level": side_effect_level,
        "assignee": assignee,
    }.items():
        if value is not None:
            patch[key] = value
    if tags:
        patch["tags"] = list(tags)
    try:
        card_status(values["card_id"])
        card = update_card(values["card_id"], patch)
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    _json(card.to_dict())


@project_task.command("transition")
@click.argument("card_id", required=False)
@click.argument("transition", required=False, type=click.Choice(["accept", "start", "review", "block", "unblock", "done", "move"]))
@click.option("--reason", default=None, help="Decision or blocking reason.")
@click.option("--need", default=None, help="Next action when blocking.")
@click.option("--summary", default=None, help="Completion summary when marking done.")
@click.option("--stage", default=None, help="Explicit target stage for move.")
@add_interactive_option
def project_task_transition(
    card_id: str | None,
    transition: str | None,
    reason: str | None,
    need: str | None,
    summary: str | None,
    stage: str | None,
    interactive: bool | None,
) -> None:
    """Move a Task card between task stages."""

    values = _resolve(
        TASK_TRANSITION_SCHEMA,
        {"card_id": card_id, "transition": transition},
        interactive,
        "Usage: chatbd project task transition [CARD_ID] [TRANSITION]",
    )
    try:
        card = transition_card(
            values["card_id"],
            values["transition"],
            reason=reason,
            need=need,
            summary=summary,
            stage=stage,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc
    if card.type != "task":
        raise click.ClickException(f"task not found: {values['card_id']}")
    _json({"card": card.to_dict(), "available_transitions": card_status(values["card_id"])["available_transitions"]})


@project_task.command("delete")
@click.argument("card_id", required=False)
@click.option("--reason", help="Why this Task is being soft-deleted.")
@click.option("--dry-run", is_flag=True, help="Show the destination without moving files.")
@add_interactive_option
def project_task_delete(card_id: str | None, reason: str | None, dry_run: bool, interactive: bool | None) -> None:
    """Soft-delete a Task card into the formal Discard area."""

    values = _resolve(DISCARD_SCHEMA, {"card_id": card_id, "reason": reason}, interactive, "Usage: chatbd project task delete [CARD_ID] --reason TEXT")
    try:
        _json(delete_card(values["card_id"], reason=values["reason"], dry_run=dry_run))
    except (FileNotFoundError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc


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
