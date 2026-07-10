"""Workspace path helpers for ChatBoard."""

from __future__ import annotations

from pathlib import Path

DEFAULT_AREAS = ("projects", "discussion", "archive", "discard")
DEFAULT_GITIGNORE_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "site",
}
DEFAULT_GITIGNORE_FILE_NAMES = {
    ".DS_Store",
}
WORKSPACE_SCAN_IGNORED_DIR_NAMES = DEFAULT_GITIGNORE_DIR_NAMES | {
    "playground",
    ".trash",
}


def resolve_workspace_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    from chatboard.config import workspace_root_from_chatenv

    return workspace_root_from_chatenv()


def as_workspace_relative(path: str | Path, root: str | Path | None = None) -> str:
    root_path = resolve_workspace_root(root)
    resolved = Path(path).expanduser().resolve()
    try:
        return resolved.relative_to(root_path).as_posix()
    except ValueError:
        return resolved.as_posix()


def area_path(root: str | Path | None, area: str) -> Path:
    if area == "trash":
        return resolve_workspace_root(root) / ".trash" / "chatboard"
    return resolve_workspace_root(root) / area


def is_ignored_dir(path: Path) -> bool:
    return path.name in WORKSPACE_SCAN_IGNORED_DIR_NAMES or path.name.startswith(".") and path.name != "."
