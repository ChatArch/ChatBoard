"""Markdown frontmatter storage for workspace cards."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from chatboard.models import ArchiveState, CardLinks, CardTimestamps, DiscussionState, ProjectCard
from chatboard.paths import as_workspace_relative, resolve_workspace_root

CARD_FILENAME = "card.md"
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)(.*)\Z", re.S)
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def card_path(project_path: str | Path) -> Path:
    return Path(project_path) / CARD_FILENAME


def _parse_scalar(value: str) -> Any:
    value = value.strip()
    if value in {"true", "false"}:
        return value == "true"
    if value in {"null", "None", "~"}:
        return None
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    try:
        return int(value)
    except ValueError:
        return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse the limited YAML subset used by ChatBoard card.md files."""

    match = _FRONTMATTER_RE.match(text)
    if not match:
        return {}, text
    raw, body = match.groups()
    data: dict[str, Any] = {}
    current_key: str | None = None
    current_child: str | None = None
    for raw_line in raw.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if indent == 0 and ":" in line:
            key, value = line.split(":", 1)
            key = key.strip()
            value = value.strip()
            current_key = key
            current_child = None
            data[key] = {} if value == "" else _parse_scalar(value)
            continue
        if current_key is None:
            continue
        if line.startswith("- "):
            target = data[current_key]
            if current_child and isinstance(target, dict):
                target = target.setdefault(current_child, [])
            if not isinstance(target, list):
                data[current_key] = []
                target = data[current_key]
            target.append(_parse_scalar(line[2:]))
            continue
        if indent >= 2 and ":" in line and isinstance(data.get(current_key), dict):
            child_key, value = line.split(":", 1)
            child_key = child_key.strip()
            value = value.strip()
            current_child = child_key
            data[current_key][child_key] = [] if value == "" else _parse_scalar(value)
    return data, body


def _derive_area(project_path: Path, root: Path) -> str:
    try:
        first = project_path.relative_to(root).parts[0]
    except (ValueError, IndexError):
        return "projects"
    if first in {"projects", "discussion", "archive", "discard", "trash"}:
        return first
    return "projects"


def _normalize_area(value: Any, project_path: Path, root: Path) -> str:
    derived = _derive_area(project_path, root)
    if derived in {"projects", "discussion", "archive", "discard", "trash"}:
        return derived
    area = str(value or derived).strip().lower()
    if area == "project":
        return "projects"
    if area in {"projects", "discussion", "archive", "discard", "trash"}:
        return area
    return derived


def _frontmatter_area(area: str) -> str:
    return "project" if area == "projects" else area


def _summary_from_body(body: str) -> str:
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        return stripped[:240]
    return ""


def _title_from_body_or_path(body: str, project_path: Path) -> str:
    match = _HEADING_RE.search(body)
    if match:
        return match.group(1).strip()
    return re.sub(r"^\d{2}-\d{2}-", "", project_path.name).replace("-", " ").strip().title() or project_path.name


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _format_scalar(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    if not text or text.strip() != text or any(ch in text for ch in [":", "#", "[", "]", "{", "}"]):
        return "\"" + text.replace("\\", "\\\\").replace("\"", "\\\"") + "\""
    return text


def _write_list(lines: list[str], key: str, values: list[str]) -> None:
    if not values:
        return
    lines.append(f"{key}:")
    for value in values:
        lines.append(f"  - {_format_scalar(value)}")


def _existing_body(path: Path) -> str | None:
    markdown_path = card_path(path)
    if not markdown_path.exists():
        return None
    _, body = parse_frontmatter(markdown_path.read_text(encoding="utf-8"))
    return body.strip() or None


def save_card(project_path: str | Path, card: ProjectCard) -> Path:
    path = Path(project_path).expanduser().resolve()
    markdown_path = card_path(path)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    card.touch()

    lines = ["---"]
    lines.append(f"schema: {_format_scalar(card.schema_version)}")
    lines.append(f"id: {_format_scalar(card.id)}")
    lines.append(f"title: {_format_scalar(card.title)}")
    lines.append(f"area: {_format_scalar(_frontmatter_area(card.area))}")
    lines.append(f"stage: {_format_scalar(card.stage)}")
    if card.priority:
        lines.append(f"priority: {card.priority}")
    if card.owner:
        lines.append(f"owner: {_format_scalar(card.owner)}")
    if card.assignee:
        lines.append(f"assignee: {_format_scalar(card.assignee)}")
    _write_list(lines, "tags", card.tags)
    lines.append("assets:")
    if card.links.prd:
        lines.append(f"  prd: {_format_scalar(card.links.prd)}")
    if card.links.progress:
        lines.append(f"  progress: {_format_scalar(card.links.progress)}")
    if card.links.reports:
        lines.append("  reports_dir: reports")
    if card.links.feishu or card.links.repo:
        lines.append("links:")
        if card.links.repo:
            lines.append(f"  repo: {_format_scalar(card.links.repo)}")
        if card.links.feishu:
            lines.append("  feishu:")
            for url in card.links.feishu:
                lines.append(f"    - {_format_scalar(url)}")
    if card.archive.reason:
        key = "discard_reason" if card.area == "discard" or card.stage == "discarded" else "archive_reason"
        lines.append(f"{key}: {_format_scalar(card.archive.reason)}")
    lines.append("---")

    body = _existing_body(path) or f"# Summary\n\n{card.summary or 'TODO'}\n"
    markdown_path.write_text("\n".join(lines) + "\n\n" + body.rstrip() + "\n", encoding="utf-8")
    return markdown_path


def load_card(project_path: str | Path, root: str | Path | None = None) -> ProjectCard | None:
    path = Path(project_path).expanduser().resolve()
    markdown_path = card_path(path)
    if not markdown_path.exists():
        return None
    root_path = resolve_workspace_root(root)
    metadata, body = parse_frontmatter(markdown_path.read_text(encoding="utf-8"))
    relative = as_workspace_relative(path, root_path)
    area = _normalize_area(metadata.get("area"), path, root_path)
    assets = metadata.get("assets") if isinstance(metadata.get("assets"), dict) else {}
    links_meta = metadata.get("links") if isinstance(metadata.get("links"), dict) else {}
    feishu = links_meta.get("feishu") if isinstance(links_meta, dict) else []
    reports_dir = assets.get("reports_dir") or "reports"
    reports_path = path / str(reports_dir)
    reports = []
    if reports_path.exists() and reports_path.is_dir():
        reports = [item.relative_to(path).as_posix() for item in sorted(reports_path.glob("*")) if item.is_file()][:50]
    return ProjectCard(
        id=str(metadata.get("id") or re.sub(r"[^a-zA-Z0-9]+", "-", relative).strip("-").lower()),
        title=str(metadata.get("title") or _title_from_body_or_path(body, path)),
        workspace_path=relative,
        area=area,  # type: ignore[arg-type]
        stage=str(metadata.get("stage") or ("review" if area == "discussion" else "development")),
        summary=str(metadata.get("summary") or _summary_from_body(body)),
        schema_version=str(metadata.get("schema") or metadata.get("schema_version") or "chatboard.project_card.v1"),
        priority=int(metadata.get("priority") or 0),
        owner=metadata.get("owner"),
        assignee=metadata.get("assignee"),
        tags=_as_list(metadata.get("tags")),
        links=CardLinks(
            prd=str(assets.get("prd") or "PRD.md") if (path / str(assets.get("prd") or "PRD.md")).exists() else None,
            progress=str(assets.get("progress") or "progress.md") if (path / str(assets.get("progress") or "progress.md")).exists() else None,
            feishu=_as_list(feishu),
            reports=reports,
        ),
        discussion=DiscussionState(status="review" if area == "discussion" else "not_started"),
        archive=ArchiveState(
            ready=str(metadata.get("stage") or "") == "archive_ready",
            reason=metadata.get("discard_reason") or metadata.get("archive_reason"),
        ),
        timestamps=CardTimestamps(),
    )
