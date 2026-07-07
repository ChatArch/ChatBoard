"""Workspace path helpers for ChatBoard."""

from __future__ import annotations

from pathlib import Path

DEFAULT_AREAS = ("projects", "discussion", "archive")
IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "__pycache__",
    "node_modules",
    "site",
    "dist",
    "playground",
    ".trash",
}


def resolve_workspace_root(root: str | Path | None = None) -> Path:
    if root is not None:
        return Path(root).expanduser().resolve()
    return Path.home().joinpath("Playground").resolve()


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
    return path.name in IGNORED_DIR_NAMES or path.name.startswith(".") and path.name != "."
