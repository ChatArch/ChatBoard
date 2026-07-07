from pathlib import Path

from click.testing import CliRunner

from chatboard.cli import main


def _project(root: Path) -> Path:
    path = root / "projects/chatarch/07-07-demo"
    path.mkdir(parents=True)
    (path / "PRD.md").write_text("# Demo CLI\n\nCLI task.\n", encoding="utf-8")
    (path / "progress.md").write_text("# Progress\n", encoding="utf-8")
    return path


def test_catalog_command_outputs_workspace_cards(tmp_path):
    _project(tmp_path)

    result = CliRunner().invoke(main, ["catalog", "--root", str(tmp_path), "--ensure"])

    assert result.exit_code == 0
    assert "Demo CLI" in result.output
    assert "project" in result.output


def test_card_show_outputs_detail(tmp_path):
    _project(tmp_path)
    CliRunner().invoke(main, ["catalog", "--root", str(tmp_path), "--ensure"])

    result = CliRunner().invoke(main, ["card", "show", "projects-chatarch-07-07-demo", "--root", str(tmp_path)])

    assert result.exit_code == 0
    assert "Demo CLI" in result.output
    assert "sections" in result.output
