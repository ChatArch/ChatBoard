import json

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
    assert "--tree-brief" in result.output
    assert "project" in result.output
    assert "serve" in result.output
    assert "trash" not in result.output
    assert "discussion" not in result.output


def test_paths_reports_chatenv_and_chatarch_owned_paths_without_secrets(tmp_path, monkeypatch):
    for key in [
        "CHATBOARD_HOME",
        "CHATBOARD_BACKENDS_FILE",
        "CHATBOARD_USERNAME",
        "CHATBOARD_PASSWORD",
        "CHATBOARD_API_KEY",
        "CHATBOARD_REGISTRY_TOKEN",
        "CHATBOARD_DEFAULT_BACKEND_TOKEN",
    ]:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / ".chatarch"))

    result = CliRunner().invoke(main, ["paths"])

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["paths"]["chatarch_home"] == str(tmp_path / ".chatarch")
    assert data["paths"]["chatenv_provider_dir"] == str(tmp_path / ".chatarch/envs/Chatboard")
    assert data["paths"]["chatboard_home"] == str(tmp_path / ".chatarch/chatboard")
    assert data["paths"]["backend_registry_file"] == str(tmp_path / ".chatarch/chatboard/backends.json")
    assert data["config"]["username_configured"] is False
    assert "REDACTED" not in result.output
    assert "secret" not in result.output.lower()


def test_tree_shows_registered_project_surface_with_signatures_and_purposes():
    result = CliRunner().invoke(main, ["--tree"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0] == "chatbd"
    assert result.output.splitlines().count("chatbd") == 1
    assert "--help  # Show this message and exit." in result.output
    assert "--version  # Show the version and exit." in result.output
    assert "--tree  # Print the registered CLI tree and exit." in result.output
    assert "--tree-brief  # Print the registered CLI tree without parameter signatures and exit." in result.output
    assert "serve [--host HOST]" in result.output
    assert "paths  # Print ChatEnv and ChatArch-owned ChatBoard runtime paths." in result.output
    assert "project  # Inspect and manage ChatArch workspace Projects." in result.output
    assert "task  # Manage Tasks shown on the Tasks board tab." in result.output
    assert "create [TITLE] [--description DESCRIPTION]" in result.output
    assert "list  # Print the Tasks board grouped by task stages." in result.output
    assert "status [CARD-ID]" in result.output
    assert "update [CARD-ID] [--title TITLE]" in result.output
    assert "transition [CARD-ID] [TRANSITION]" in result.output
    assert "delete [CARD-ID] [--reason REASON]" in result.output
    assert "card  # Inspect and move Project cards." in result.output
    assert "ensure [PROJECT-PATH]" in result.output
    assert "show [CARD-ID]" in result.output
    assert "move [CARD-ID] [AREA]" in result.output
    assert "discussion  # Create Discussion topics and add Project items." in result.output
    assert "add-item [DISCUSSION-ID] [CARD-ID]" in result.output
    assert "archive  # Archive completed Project cards." in result.output
    assert "run [CARD-ID]" in result.output
    assert "discard [CARD-ID]" in result.output
    assert "#" in result.output


def test_tree_brief_keeps_registered_surface_without_parameter_signatures():
    result = CliRunner().invoke(main, ["--tree-brief"])

    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0] == "chatbd"
    assert "paths  # Print ChatEnv and ChatArch-owned ChatBoard runtime paths." in result.output
    assert "serve  # Start the ChatBoard web UI." in result.output
    assert "project  # Inspect and manage ChatArch workspace Projects." in result.output
    assert "task  # Manage Tasks shown on the Tasks board tab." in result.output
    assert "create  # Create a Task card and task project skeleton." in result.output
    assert "transition  # Move a Task card between task stages." in result.output
    assert "card  # Inspect and move Project cards." in result.output
    assert "discussion  # Create Discussion topics and add Project items." in result.output
    assert "archive  # Archive completed Project cards." in result.output
    assert "discard  # Move a Project card into the formal Discard area." in result.output
    assert "[--host HOST]" not in result.output
    assert "[TITLE]" not in result.output
    assert "[--interactive]" not in result.output


def test_template_hello_command_is_not_registered():
    help_result = CliRunner().invoke(main, ["--help"])
    tree_result = CliRunner().invoke(main, ["--tree"])
    brief_tree_result = CliRunner().invoke(main, ["--tree-brief"])
    missing_result = CliRunner().invoke(main, ["hello"])

    assert help_result.exit_code == 0, help_result.output
    assert tree_result.exit_code == 0, tree_result.output
    assert brief_tree_result.exit_code == 0, brief_tree_result.output
    assert "hello" not in help_result.output.lower()
    assert "hello" not in tree_result.output.lower()
    assert "hello" not in brief_tree_result.output.lower()
    assert missing_result.exit_code != 0
    assert "No such command" in missing_result.output


def test_serve_help_exposes_optional_login_gate():
    result = CliRunner().invoke(main, ["serve", "--help"])

    assert result.exit_code == 0
    assert "--username" in result.output
    assert "--password" in result.output
    assert "--password-file" in result.output


def test_tree_root_uses_public_console_command_even_in_python_module_mode():
    result = CliRunner().invoke(main, ["--tree"], prog_name="python -m chatboard.cli")

    assert result.exit_code == 0, result.output
    assert result.output.splitlines()[0] == "chatbd"
    assert "python -m chatboard.cli" not in result.output
