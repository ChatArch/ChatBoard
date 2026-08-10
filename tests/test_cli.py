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
    assert "--tree" in result.output
    assert "project" in result.output
    assert "serve" in result.output
    assert "trash" not in result.output
    assert "discussion" not in result.output


def test_tree_shows_registered_project_surface_with_purposes():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert "chatbd  # Run the ChatBoard web app and Project management tools." in result.output
    assert "--help  # Show this help message." in result.output
    assert "--version  # Show the installed package version." in result.output
    assert "--tree  # Print the registered command tree." in result.output
    assert "serve [--host <HOST>]" in result.output
    assert "project  # Inspect and manage ChatArch workspace Projects." in result.output
    assert "card  # Inspect and move Project cards." in result.output
    assert "ensure [<PROJECT-PATH>]" in result.output
    assert "discussion  # Create Discussion topics and add Project items." in result.output
    assert "archive  # Archive completed Project cards." in result.output
    assert "discard [<CARD-ID>]" in result.output
    assert "#" in result.output


def test_template_hello_command_is_not_registered():
    help_result = CliRunner().invoke(main, ["--help"])
    tree_result = CliRunner().invoke(main, ["--tree"])
    missing_result = CliRunner().invoke(main, ["hello"])

    assert help_result.exit_code == 0, help_result.output
    assert tree_result.exit_code == 0, tree_result.output
    assert "hello" not in help_result.output.lower()
    assert "hello" not in tree_result.output.lower()
    assert missing_result.exit_code != 0
    assert "No such command" in missing_result.output


def test_serve_help_exposes_optional_login_gate():
    result = CliRunner().invoke(main, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--username" in result.output
    assert "--password" in result.output
    assert "--password-file" in result.output
