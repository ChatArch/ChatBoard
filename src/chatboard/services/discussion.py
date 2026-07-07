"""Discussion helpers for project cards."""

from __future__ import annotations

from pathlib import Path

from chatboard.services.cards import find_card_path, ensure_card
from chatboard.storage.json_sidecar import save_card


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
