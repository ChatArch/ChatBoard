"""Workspace scanning and catalog services."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from chatboard.models import BoardColumn, DEFAULT_COLUMNS, ProjectCard, column_title
from chatboard.paths import DEFAULT_AREAS, area_path, is_ignored_dir, resolve_workspace_root
from chatboard.services.cards import ensure_card, load_card


def _looks_like_project_dir(path: Path) -> bool:
    if not path.is_dir() or is_ignored_dir(path):
        return False
    return any((path / name).exists() for name in ("PRD.md", "progress.md", "card.json"))


def iter_project_dirs(root: str | Path | None = None, areas: Iterable[str] = DEFAULT_AREAS) -> list[Path]:
    root_path = resolve_workspace_root(root)
    found: list[Path] = []
    seen: set[Path] = set()
    for area in areas:
        base = area_path(root_path, area)
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_dir() or is_ignored_dir(path):
                continue
            if any(part in {".git", "node_modules", ".venv", "__pycache__", "playground"} for part in path.parts):
                continue
            if _looks_like_project_dir(path):
                resolved = path.resolve()
                if resolved not in seen:
                    found.append(resolved)
                    seen.add(resolved)
    return found


def scan(root: str | Path | None = None, ensure: bool = False) -> list[ProjectCard]:
    cards: list[ProjectCard] = []
    for project_path in iter_project_dirs(root):
        card = ensure_card(project_path, root) if ensure else load_card(project_path, root)
        cards.append(card)
    return sorted(cards, key=lambda card: (card.column, card.priority * -1, card.title.lower()))


def catalog(root: str | Path | None = None, ensure: bool = False) -> dict:
    root_path = resolve_workspace_root(root)
    columns = {key: BoardColumn(key=key, title=title) for key, title in DEFAULT_COLUMNS}
    cards = scan(root_path, ensure=ensure)
    for card in cards:
        columns.setdefault(card.column, BoardColumn(key=card.column, title=column_title(card.column))).cards.append(card)
    tag_counts: dict[str, int] = {}
    area_counts: dict[str, int] = {}
    stage_counts: dict[str, int] = {}
    with_prd = with_progress = with_reports = with_feishu = 0
    for card in cards:
        area_counts[card.area] = area_counts.get(card.area, 0) + 1
        stage_counts[card.stage] = stage_counts.get(card.stage, 0) + 1
        for tag in card.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
        if card.links.prd:
            with_prd += 1
        if card.links.progress:
            with_progress += 1
        if card.links.reports:
            with_reports += 1
        if card.links.feishu:
            with_feishu += 1
    return {
        "root": root_path.as_posix(),
        "columns": [column.to_dict() for column in columns.values()],
        "total_cards": len(cards),
        "summary": {
            "areas": area_counts,
            "stages": stage_counts,
            "with_prd": with_prd,
            "with_progress": with_progress,
            "with_reports": with_reports,
            "with_feishu": with_feishu,
            "top_tags": sorted(tag_counts.items(), key=lambda item: (-item[1], item[0]))[:12],
        },
    }
