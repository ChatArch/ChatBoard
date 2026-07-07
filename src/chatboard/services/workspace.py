"""Workspace scanning and catalog services."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, Iterator

from chatboard.models import BoardColumn, DEFAULT_COLUMNS, ProjectCard, column_title
from chatboard.paths import DEFAULT_AREAS, WORKSPACE_SCAN_IGNORED_DIR_NAMES, area_path, is_ignored_dir, resolve_workspace_root
from chatboard.services.cards import ensure_card, load_card


def _looks_like_project_dir(path: Path) -> bool:
    if not path.is_dir() or is_ignored_dir(path):
        return False
    return any((path / name).exists() for name in ("PRD.md", "progress.md", "card.md"))


def _is_discussion_item_dir(path: Path, root: Path) -> bool:
    try:
        parts = path.resolve().relative_to(root).parts
    except ValueError:
        return False
    return len(parts) >= 4 and parts[0] == "discussion" and "Items" in parts[1:]


def _iter_project_dirs(
    root: str | Path | None = None,
    areas: Iterable[str] = DEFAULT_AREAS,
    include_nested: bool = False,
) -> Iterator[Path]:
    root_path = resolve_workspace_root(root)
    seen: set[Path] = set()
    ignored_parts = WORKSPACE_SCAN_IGNORED_DIR_NAMES
    for area in areas:
        base = area_path(root_path, area)
        if not base.exists():
            continue
        for dirpath, dirnames, _filenames in os.walk(base):
            path = Path(dirpath)
            dirnames[:] = sorted(
                name for name in dirnames
                if name not in ignored_parts and not (name.startswith(".") and name != ".")
            )
            if is_ignored_dir(path) or any(part in ignored_parts for part in path.parts):
                continue
            if not include_nested and _is_discussion_item_dir(path, root_path):
                dirnames[:] = []
                continue
            if _looks_like_project_dir(path):
                resolved = path.resolve()
                if resolved not in seen:
                    yield resolved
                    seen.add(resolved)


def iter_project_dirs(
    root: str | Path | None = None,
    areas: Iterable[str] = DEFAULT_AREAS,
    include_nested: bool = False,
) -> list[Path]:
    return list(_iter_project_dirs(root, areas=areas, include_nested=include_nested))


def scan(root: str | Path | None = None, ensure: bool = False) -> list[ProjectCard]:
    cards: list[ProjectCard] = []
    for project_path in iter_project_dirs(root):
        card = ensure_card(project_path, root) if ensure else load_card(project_path, root)
        cards.append(card)
    return sorted(cards, key=lambda card: (card.column, card.priority * -1, card.title.lower()))


def _areas_for_column(column: str) -> tuple[str, ...]:
    if column == "project":
        return ("projects",)
    if column == "discussion":
        return ("discussion",)
    if column == "archive":
        return ("archive",)
    if column == "discard":
        return ("discard",)
    return DEFAULT_AREAS


def column_page(
    column: str,
    root: str | Path | None = None,
    ensure: bool = False,
    offset: int = 0,
    limit: int = 24,
) -> dict:
    root_path = resolve_workspace_root(root)
    offset = max(offset, 0)
    limit = min(max(limit, 1), 100)
    cards: list[ProjectCard] = []
    matched = 0
    has_more = False
    for project_path in _iter_project_dirs(root_path, areas=_areas_for_column(column)):
        card = ensure_card(project_path, root_path) if ensure else load_card(project_path, root_path)
        if card.column != column:
            continue
        if matched < offset:
            matched += 1
            continue
        if len(cards) >= limit:
            has_more = True
            break
        cards.append(card)
        matched += 1
    cards.sort(key=lambda card: (card.priority * -1, card.title.lower()))
    next_offset = offset + len(cards)
    return {
        "root": root_path.as_posix(),
        "key": column,
        "title": column_title(column),
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset,
        "has_more": has_more,
        "cards": [card.to_dict() for card in cards],
    }


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
