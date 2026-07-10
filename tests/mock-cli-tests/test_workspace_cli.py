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
    card_help = runner.invoke(main, ["project", "card", "--help"])
    discussion_help = runner.invoke(main, ["project", "discussion", "--help"])
    archive_help = runner.invoke(main, ["project", "archive", "--help"])

    assert project_help.exit_code == 0
    for command in ("scan", "catalog", "card", "discussion", "archive", "discard"):
        assert command in project_help.output
    assert "trash" not in project_help.output

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

    assert scan_help.exit_code == 0
    assert catalog_help.exit_code == 0
    assert "--ensure" not in scan_help.output
    assert "--ensure" not in catalog_help.output
    assert "--root" not in scan_help.output
    assert "--root" not in catalog_help.output


def test_catalog_uses_workspace_from_chatenv(monkeypatch, tmp_path):
    _project(tmp_path)
    _configure_workspace(monkeypatch, tmp_path)

    result = CliRunner().invoke(main, ["project", "catalog"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["root"] == tmp_path.as_posix()
    assert payload["total_cards"] == 1
    assert payload["columns"][0]["cards"][0]["title"] == "Demo CLI"


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
