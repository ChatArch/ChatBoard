"""Archive/discard/trash helpers for project cards."""

from __future__ import annotations

from pathlib import Path

from chatboard.services.cards import ensure_card, find_card_path, move_card
from chatboard.storage.markdown_card import save_card


def mark_ready(card_id: str, root: str | Path | None = None) -> dict:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    card.stage = "archive_ready"
    card.archive.ready = True
    save_card(project_path, card)
    return card.to_dict()


def archive(card_id: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    return move_card(card_id, "archive", stage="archived", root=root, dry_run=dry_run)


def discard(card_id: str, reason: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    card.area = "discard"
    card.stage = "discarded"
    card.archive.reason = reason
    save_card(project_path, card)
    return move_card(card_id, "discard", stage="discarded", root=root, dry_run=dry_run)


def trash(card_id: str, reason: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    card.stage = "trashed"
    card.archive.reason = reason
    save_card(project_path, card)
    return move_card(card_id, "trash", stage="trashed", root=root, dry_run=dry_run)
