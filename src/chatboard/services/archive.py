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


def _move_with_reason(
    card_id: str,
    area: str,
    stage: str,
    reason: str,
    root: str | Path | None,
    dry_run: bool,
) -> dict:
    result = move_card(card_id, area, stage=stage, root=root, dry_run=dry_run)
    result["reason"] = reason
    if dry_run:
        return result
    destination = Path(result["to"])
    card = ensure_card(destination, root)
    card.archive.reason = reason
    save_card(destination, card)
    result["card"] = card.to_dict()
    return result


def discard(card_id: str, reason: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    return _move_with_reason(card_id, "discard", "discarded", reason, root, dry_run)


def trash(card_id: str, reason: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    return _move_with_reason(card_id, "trash", "trashed", reason, root, dry_run)
