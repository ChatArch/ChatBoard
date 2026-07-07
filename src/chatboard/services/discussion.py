"""Discussion helpers for project cards."""

from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from chatboard.models import CardLinks, ProjectCard
from chatboard.paths import area_path, resolve_workspace_root
from chatboard.services.cards import ensure_card, find_card_path, slugify_id
from chatboard.storage.markdown_card import save_card


def _date_prefix() -> str:
    return datetime.now().strftime("%m-%d")


def _slug(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower() or "discussion"


def create_discussion(title: str, root: str | Path | None = None, slug: str | None = None) -> dict:
    root_path = resolve_workspace_root(root)
    name = slug or f"{_date_prefix()}-{_slug(title)}"
    if not re.match(r"^\d{2}-\d{2}-", name):
        name = f"{_date_prefix()}-{name}"
    discussion_path = area_path(root_path, "discussion") / name
    if discussion_path.exists():
        raise FileExistsError(discussion_path)
    (discussion_path / "Items").mkdir(parents=True)
    (discussion_path / "PRD.md").write_text(f"# {title}\n\n## Goal\n\nDigest related projects and decide output routes.\n", encoding="utf-8")
    (discussion_path / "progress.md").write_text("# Progress\n\n- created discussion\n", encoding="utf-8")
    card = ProjectCard(
        id=slugify_id(f"discussion/{name}"),
        title=title,
        workspace_path=f"discussion/{name}",
        area="discussion",
        stage="review",
        summary="Digest related projects and decide output routes.",
        tags=[],
        links=CardLinks(prd="PRD.md", progress="progress.md"),
    )
    save_card(discussion_path, card)
    return card.to_dict()


def open_discussion(card_id: str, root: str | Path | None = None) -> dict:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    card.discussion.status = "review"
    save_card(project_path, card)
    return card.to_dict()


def add_decision(card_id: str, text: str, root: str | Path | None = None) -> dict:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    card.discussion.status = "decision"
    card.discussion.decisions.append(text)
    save_card(project_path, card)
    return card.to_dict()


def add_item(discussion_id: str, card_id: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    root_path = resolve_workspace_root(root)
    discussion_path = find_card_path(discussion_id, root_path)
    item_path = find_card_path(card_id, root_path)
    if discussion_path is None:
        raise FileNotFoundError(discussion_id)
    if item_path is None:
        raise FileNotFoundError(card_id)
    discussion_card = ensure_card(discussion_path, root_path)
    if discussion_card.area != "discussion":
        raise ValueError(f"not a discussion card: {discussion_id}")
    ensure_card(item_path, root_path)
    destination = discussion_path / "Items" / item_path.name
    if destination.exists():
        raise FileExistsError(destination)
    result = {
        "discussion_id": discussion_id,
        "card_id": card_id,
        "from": item_path.as_posix(),
        "to": destination.as_posix(),
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(item_path.as_posix(), destination.as_posix())
    updated_discussion = ensure_card(discussion_path, root_path)
    result["discussion"] = updated_discussion.to_dict()
    return result
