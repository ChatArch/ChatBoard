import json
from pathlib import Path

from click.testing import CliRunner

from chatboard.cli import main


def _project(root: Path) -> Path:
    path = root / "projects/chatarch/07-07-demo"
    path.mkdir(parents=True)
    (path / "PRD.md").write_text("# Demo CLI\n\nCLI task.\n", encoding="utf-8")
    (path / "progress.md").write_text("# Progress\n", encoding="utf-8")
    return path


def _configure_workspace(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / ".chatarch"))
    monkeypatch.setenv("CHATBOARD_WORKSPACE_ROOT", str(tmp_path))


def test_project_command_tree_is_scoped_and_minimal():
    runner = CliRunner()

    project_help = runner.invoke(main, ["project", "--help"])
    task_help = runner.invoke(main, ["project", "task", "--help"])
    card_help = runner.invoke(main, ["project", "card", "--help"])
    discussion_help = runner.invoke(main, ["project", "discussion", "--help"])
    archive_help = runner.invoke(main, ["project", "archive", "--help"])

    assert project_help.exit_code == 0
    for command in ("scan", "catalog", "task", "card", "discussion", "archive", "discard"):
        assert command in project_help.output
    assert "trash" not in project_help.output

    assert task_help.exit_code == 0
    for command in ("create", "list", "status", "update", "transition", "delete"):
        assert command in task_help.output

    assert card_help.exit_code == 0
    for command in ("ensure", "show", "move"):
        assert command in card_help.output

    assert discussion_help.exit_code == 0
    assert "create" in discussion_help.output
    assert "add-item" in discussion_help.output
    assert "open" not in discussion_help.output
    assert "decide" not in discussion_help.output

    assert archive_help.exit_code == 0
    assert "run" in archive_help.output
    assert "ready" not in archive_help.output


def test_scan_and_catalog_are_read_only_commands():
    runner = CliRunner()

    scan_help = runner.invoke(main, ["project", "scan", "--help"])
    catalog_help = runner.invoke(main, ["project", "catalog", "--help"])
    show_help = runner.invoke(main, ["project", "card", "show", "--help"])

    assert scan_help.exit_code == 0
    assert catalog_help.exit_code == 0
    assert "--ensure" not in scan_help.output
    assert "--ensure" not in catalog_help.output
    assert "--root" not in scan_help.output
    assert "--root" not in catalog_help.output
    assert "-i, --interactive" in show_help.output
    assert "-I, --no-interactive" in show_help.output


def test_required_inputs_fail_fast_when_interaction_is_disabled():
    result = CliRunner().invoke(main, ["project", "card", "show", "-I"])

    assert result.exit_code != 0
    assert "Missing required value: card_id" in result.output


def test_card_ensure_prompts_for_missing_project_path(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)
    monkeypatch.setattr("chatstyle.core.interactive.is_interactive_available", lambda: True)
    monkeypatch.setattr(
        "chatstyle.tui.prompt.ask_text",
        lambda label, default="", password=False, style=None: str(project),
    )

    result = CliRunner().invoke(main, ["project", "card", "ensure"], catch_exceptions=False)

    assert result.exit_code == 0
    assert (project / "card.md").exists()


def test_card_ensure_rejects_missing_directory(monkeypatch, tmp_path):
    missing = tmp_path / "projects/missing"
    _configure_workspace(monkeypatch, tmp_path)

    result = CliRunner().invoke(
        main,
        ["project", "card", "ensure", str(missing), "-I"],
    )

    assert result.exit_code != 0
    assert "project directory not found" in result.output
    assert not missing.exists()


def test_catalog_uses_workspace_from_chatenv(monkeypatch, tmp_path):
    _project(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)

    result = CliRunner().invoke(main, ["project", "catalog"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root"] == tmp_path.as_posix()
    assert payload["total_cards"] == 1
    project_column = next(column for column in payload["columns"] if column["key"] == "project")
    assert project_column["cards"][0]["title"] == "Demo CLI"


def test_card_ensure_and_show_use_configured_workspace(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)
    runner = CliRunner()

    ensured = runner.invoke(main, ["project", "card", "ensure", str(project)])
    shown = runner.invoke(main, ["project", "card", "show", "projects-chatarch-07-07-demo"])

    assert ensured.exit_code == 0
    assert (project / "card.md").exists()
    assert shown.exit_code == 0
    assert "Demo CLI" in shown.output
    assert "sections" in shown.output


def test_card_move_keeps_trash_as_explicit_low_level_target(monkeypatch, tmp_path):
    project = _project(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["project", "card", "ensure", str(project)])

    result = runner.invoke(
        main,
        ["project", "card", "move", "projects-chatarch-07-07-demo", "trash", "--dry-run"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["area"] == "trash"
    assert payload["dry_run"] is True
    assert project.exists()


def test_task_cli_create_status_transition_update_and_delete_use_configured_workspace(monkeypatch, tmp_path):
    _configure_workspace(monkeypatch, tmp_path)
    runner = CliRunner()

    created = runner.invoke(
        main,
        [
            "project",
            "task",
            "create",
            "Board task CLI",
            "--description",
            "Create and manage a task from CLI.",
            "--topic",
            "chatarch",
            "--slug",
            "08-12-board-task-cli",
            "--source-platform",
            "feishu",
            "--source-url",
            "https://example.feishu.cn/thread/cli",
            "--accept-mode",
            "accept",
            "--side-effect-level",
            "local_write",
            "--next-action",
            "Accept from CLI.",
            "--tag",
            "board",
            "--tag",
            "cli",
            "-I",
        ],
    )
    assert created.exit_code == 0, created.output
    payload = json.loads(created.output)
    card_id = payload["card"]["id"]
    assert card_id == "projects-chatarch-08-12-board-task-cli"
    assert payload["card"]["type"] == "task"
    assert payload["card"]["stage"] == "inbox"

    project_catalog = runner.invoke(main, ["project", "catalog"])
    assert project_catalog.exit_code == 0
    assert json.loads(project_catalog.output)["total_cards"] == 0

    listed = runner.invoke(main, ["project", "task", "list"])
    assert listed.exit_code == 0
    listed_payload = json.loads(listed.output)
    assert [column["key"] for column in listed_payload["columns"]] == ["inbox", "ready", "running", "blocked", "review", "done"]
    assert listed_payload["total_cards"] == 1

    status = runner.invoke(main, ["project", "task", "status", card_id, "-I"])
    assert status.exit_code == 0
    assert "accept" in json.loads(status.output)["available_transitions"]

    updated = runner.invoke(
        main,
        [
            "project",
            "task",
            "update",
            card_id,
            "--next-action",
            "Worker can start from CLI.",
            "--accept-mode",
            "auto",
            "--side-effect-level",
            "read_only",
            "-I",
        ],
    )
    assert updated.exit_code == 0, updated.output
    assert json.loads(updated.output)["next_action"] == "Worker can start from CLI."

    accepted = runner.invoke(main, ["project", "task", "transition", card_id, "accept", "--reason", "ready", "-I"])
    assert accepted.exit_code == 0, accepted.output
    assert json.loads(accepted.output)["card"]["stage"] == "ready"

    deleted = runner.invoke(main, ["project", "task", "delete", card_id, "--reason", "example cleanup", "-I"])
    assert deleted.exit_code == 0, deleted.output
    assert json.loads(deleted.output)["card"]["area"] == "discard"
