"""Domain models for ChatBoard workspace cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Area = Literal["projects", "discussion", "archive", "trash"]

CARD_SCHEMA_VERSION = "chatboard.project_card.v1"
VALID_AREAS = {"projects", "discussion", "archive", "trash"}
VALID_STAGES = {
    "scaffold",
    "prd",
    "ready",
    "development",
    "validation",
    "complete",
    "blocked",
    "paused",
    "review",
    "decision",
    "postprocess",
    "archive_ready",
    "archived",
    "discarded",
    "trashed",
}


def utc_now() -> str:
    """Return an ISO timestamp suitable for card metadata."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass
class CardLinks:
    prd: str | None = None
    progress: str | None = None
    feishu: list[str] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    repo: str | None = None


@dataclass
class DiscussionState:
    status: str = "not_started"
    questions: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    next_action: str | None = None


@dataclass
class ArchiveState:
    ready: bool = False
    target: str | None = None
    checklist: list[str] = field(default_factory=list)
    reason: str | None = None


@dataclass
class CardDependencies:
    parents: list[str] = field(default_factory=list)
    children: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)


@dataclass
class CardTimestamps:
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)


@dataclass
class ProjectCard:
    id: str
    title: str
    workspace_path: str
    area: Area = "projects"
    stage: str = "development"
    summary: str = ""
    schema_version: str = CARD_SCHEMA_VERSION
    type: str = "project"
    priority: int = 0
    owner: str | None = None
    assignee: str | None = None
    tags: list[str] = field(default_factory=list)
    links: CardLinks = field(default_factory=CardLinks)
    discussion: DiscussionState = field(default_factory=DiscussionState)
    archive: ArchiveState = field(default_factory=ArchiveState)
    dependencies: CardDependencies = field(default_factory=CardDependencies)
    timestamps: CardTimestamps = field(default_factory=CardTimestamps)

    @property
    def column(self) -> str:
        return column_for(self.area, self.stage)

    def touch(self) -> None:
        self.timestamps.updated_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["column"] = self.column
        return data


@dataclass
class DetailSection:
    key: str
    title: str
    kind: str
    data: Any


@dataclass
class CardDetail:
    card: ProjectCard
    sections: list[DetailSection]

    def to_dict(self) -> dict[str, Any]:
        return {
            "card": self.card.to_dict(),
            "sections": [asdict(section) for section in self.sections],
        }


@dataclass
class BoardColumn:
    key: str
    title: str
    cards: list[ProjectCard] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "title": self.title, "cards": [card.to_dict() for card in self.cards]}


DEFAULT_COLUMNS: list[tuple[str, str]] = [
    ("project", "Project"),
    ("discussion", "Discussion"),
    ("archive", "Archive"),
    ("discard", "Discard"),
]


def column_for(area: str, stage: str) -> str:
    if area == "trash" or stage == "trashed":
        return "trash"
    if area == "archive":
        if stage == "discarded":
            return "discard"
        return "archive"
    if area == "discussion":
        return "discussion"
    return "project"


def column_title(key: str) -> str:
    return dict(DEFAULT_COLUMNS).get(key, key.replace("_", " ").title())
