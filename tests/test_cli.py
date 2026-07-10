from click.testing import CliRunner

from chatboard import __version__
from chatboard.cli import main


def test_version_option_reports_package_version():
    result = CliRunner().invoke(main, ["--version"])

    assert result.exit_code == 0
    assert f"chatbd, version {__version__}" in result.output


def test_top_level_cli_only_exposes_runtime_and_project_tools():
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "project" in result.output
    assert "serve" in result.output
    assert "trash" not in result.output
    assert "discussion" not in result.output
