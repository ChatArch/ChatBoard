"""JSON sidecar storage for project cards."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Any, TypeVar

from chatboard.models import (
    ArchiveState,
    CardDependencies,
    CardLinks,
    CardTimestamps,
    DiscussionState,
    ProjectCard,
    utc_now,
)

T = TypeVar("T")
CARD_FILENAME = "card.json"


def card_path(project_path: str | Path) -> Path:
    return Path(project_path) / CARD_FILENAME


def _dataclass_from_dict(cls: type[T], data: dict[str, Any] | None) -> T:
    data = data or {}
    names = {field.name for field in fields(cls)}
    kwargs = {key: value for key, value in data.items() if key in names}
    return cls(**kwargs)  # type: ignore[arg-type]


def card_from_dict(data: dict[str, Any]) -> ProjectCard:
    links = _dataclass_from_dict(CardLinks, data.get("links"))
    discussion = _dataclass_from_dict(DiscussionState, data.get("discussion"))
    archive = _dataclass_from_dict(ArchiveState, data.get("archive"))
    dependencies = _dataclass_from_dict(CardDependencies, data.get("dependencies"))
    timestamps = _dataclass_from_dict(CardTimestamps, data.get("timestamps"))

    known = {field.name for field in fields(ProjectCard)}
    kwargs = {key: value for key, value in data.items() if key in known}
    kwargs.update(
        {
            "links": links,
            "discussion": discussion,
            "archive": archive,
            "dependencies": dependencies,
            "timestamps": timestamps,
        }
    )
    return ProjectCard(**kwargs)


def load_card(project_path: str | Path) -> ProjectCard | None:
    path = card_path(project_path)
    if not path.exists():
        return None
    return card_from_dict(json.loads(path.read_text(encoding="utf-8")))


def _json_default(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _json_default(item) for key, item in value.__dict__.items()}
    if isinstance(value, Path):
        return value.as_posix()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def save_card(project_path: str | Path, card: ProjectCard) -> Path:
    path = card_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    card.touch()
    path.write_text(json.dumps(card.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def update_card(project_path: str | Path, updates: dict[str, Any]) -> ProjectCard:
    card = load_card(project_path)
    if card is None:
        raise FileNotFoundError(card_path(project_path))
    for key, value in updates.items():
        if key in {"links", "discussion", "archive", "dependencies", "timestamps"}:
            continue
        if hasattr(card, key):
            setattr(card, key, value)
    card.timestamps.updated_at = utc_now()
    save_card(project_path, card)
    return card
