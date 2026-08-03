"""Workspace path helpers for ChatBoard."""

from __future__ import annotations

import re
from datetime import datetime
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

_DATE_NAME_RE = re.compile(r"^(?:(?P<year>\d{4})-)?(?P<month>\d{2})-(?P<day>\d{2})(?:-|$)")


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


def date_from_name(name: str, default_year: int | None = None) -> str | None:
    """Infer an ISO date from a workspace directory name prefix."""

    match = _DATE_NAME_RE.match(name)
    if not match:
        return None
    year = int(match.group("year") or default_year or datetime.now().year)
    month = int(match.group("month"))
    day = int(match.group("day"))
    try:
        return datetime(year, month, day).date().isoformat()
    except ValueError:
        return None


def infer_workspace_date(path: str | Path, root: str | Path | None = None) -> str | None:
    """Infer a card date from the first dated path segment in a workspace path."""

    root_path = resolve_workspace_root(root) if root is not None else None
    resolved = Path(path).expanduser().resolve()
    try:
        parts = resolved.relative_to(root_path).parts if root_path else resolved.parts
    except ValueError:
        parts = resolved.parts
    for part in parts:
        inferred = date_from_name(part)
        if inferred:
            return inferred
    return None
