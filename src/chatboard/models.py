"""Domain models for ChatBoard workspace cards."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

Area = Literal["projects", "discussion", "archive", "discard", "trash"]

CARD_SCHEMA_VERSION = "chatboard.project_card.v1"
VALID_AREAS = {"projects", "discussion", "archive", "discard", "trash"}
VALID_STAGES = {
    "inbox",
    "scaffold",
    "prd",
    "ready",
    "running",
    "development",
    "validation",
    "complete",
    "done",
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
    public_url: str | None = None


@dataclass
class CardSource:
    platform: str | None = None
    url: str | None = None


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
class CardRef:
    id: str
    title: str
    workspace_path: str
    area: str
    stage: str
    tags: list[str] = field(default_factory=list)


@dataclass
class ProjectCard:
    id: str
    title: str
    workspace_path: str
    area: Area = "projects"
    stage: str = "development"
    description: str = ""
    summary: str = ""
    date: str | None = None
    schema_version: str = CARD_SCHEMA_VERSION
    type: str = "project"
    priority: int = 0
    owner: str | None = None
    assignee: str | None = None
    tags: list[str] = field(default_factory=list)
    links: CardLinks = field(default_factory=CardLinks)
    source: CardSource = field(default_factory=CardSource)
    accept_mode: str | None = None
    side_effect_level: str | None = None
    next_action: str | None = None
    discussion: DiscussionState = field(default_factory=DiscussionState)
    archive: ArchiveState = field(default_factory=ArchiveState)
    dependencies: CardDependencies = field(default_factory=CardDependencies)
    timestamps: CardTimestamps = field(default_factory=CardTimestamps)
    nested_items: list[CardRef] = field(default_factory=list)

    @property
    def column(self) -> str:
        if self.type == "task":
            return task_column_for(self.stage)
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


ARCHIVING_STAGES = {"archive_ready", "complete", "postprocess"}

DEFAULT_COLUMNS: list[tuple[str, str]] = [
    ("thoughts", "想法"),
    ("project", "进行中"),
    ("archiving", "归档中"),
    ("archive", "已归档"),
]
VISIBLE_COLUMN_KEYS = {key for key, _title in DEFAULT_COLUMNS}

TASK_COLUMNS: list[tuple[str, str]] = [
    ("inbox", "Inbox"),
    ("ready", "Ready"),
    ("running", "Running"),
    ("blocked", "Blocked"),
    ("review", "Review"),
    ("done", "Done"),
]
VISIBLE_TASK_COLUMN_KEYS = {key for key, _title in TASK_COLUMNS}


def task_column_for(stage: str) -> str:
    if stage == "inbox":
        return "inbox"
    if stage == "ready":
        return "ready"
    if stage == "running":
        return "running"
    if stage == "blocked":
        return "blocked"
    if stage in {"review", "validation", "decision"}:
        return "review"
    if stage in {"done", "complete", "archive_ready", "archived"}:
        return "done"
    return "inbox"


def column_for(area: str, stage: str) -> str:
    if area == "trash" or stage == "trashed":
        return "trash"
    if area == "discard" or stage == "discarded":
        return "discard"
    if area == "archive" or stage == "archived":
        return "archive"
    if area == "discussion":
        return "thoughts"
    if area == "projects" and stage in ARCHIVING_STAGES:
        return "archiving"
    return "project"


def column_title(key: str) -> str:
    return dict(DEFAULT_COLUMNS).get(key, key.replace("_", " ").title())
