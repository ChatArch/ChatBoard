"""FastAPI app for ChatBoard."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from chatboard import __version__
from chatboard.paths import resolve_workspace_root
from chatboard.services import archive as archive_service
from chatboard.services import discussion as discussion_service
from chatboard.services.cards import card_detail, card_file_content, card_file_list, card_files, ensure_card, find_card_path, move_card, update_card
from chatboard.services.workspace import catalog as build_catalog
from chatboard.services.workspace import column_page as build_column_page
from chatboard.web.paths import package_static_dir

app = FastAPI(title="ChatBoard API", version=__version__)


def _root(root: str | None = None) -> Path:
    return resolve_workspace_root(root or os.environ.get("CHATBOARD_WORKSPACE_ROOT"))


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__}


@app.get("/api/catalog")
def catalog(root: str | None = None, ensure: bool = Query(False)) -> dict[str, Any]:
    return build_catalog(root=_root(root), ensure=ensure)


@app.get("/api/columns/{column_key}")
def get_column(
    column_key: str,
    root: str | None = None,
    ensure: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
) -> dict[str, Any]:
    if column_key not in {"project", "discussion", "archive", "discard"}:
        raise HTTPException(404, f"column not found: {column_key}")
    return build_column_page(column_key, root=_root(root), ensure=ensure, offset=offset, limit=limit)


@app.get("/api/cards/{card_id}")
def get_card(card_id: str, root: str | None = None) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"card not found: {card_id}")
    return card_detail(project_path, root=_root(root))


@app.get("/api/cards/{card_id}/files")
def get_card_files(card_id: str, root: str | None = None, include_hidden: bool = Query(False)) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"card not found: {card_id}")
    return {"files": card_files(project_path, include_hidden=include_hidden)}


@app.get("/api/cards/{card_id}/files/list")
def list_card_files(
    card_id: str,
    path: str = "",
    root: str | None = None,
    include_hidden: bool = Query(False),
) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"card not found: {card_id}")
    try:
        return card_file_list(project_path, path, include_hidden=include_hidden)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"directory not found: {path}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/cards/{card_id}/files/content")
def get_card_file_content(card_id: str, path: str, root: str | None = None) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"card not found: {card_id}")
    try:
        return card_file_content(project_path, path)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"file not found: {path}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/cards/ensure")
def ensure_card_api(payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    project_path = payload.get("project_path") or payload.get("path")
    if not project_path:
        raise HTTPException(400, "project_path is required")
    return ensure_card(project_path, root=_root(root)).to_dict()


@app.patch("/api/cards/{card_id}")
def patch_card(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    try:
        return update_card(card_id, payload, root=_root(root)).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/cards/{card_id}/move")
def move_card_api(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    try:
        return move_card(
            card_id,
            area=payload.get("area", "projects"),
            stage=payload.get("stage"),
            root=_root(root),
            dry_run=bool(payload.get("dry_run", False)),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc
    except (FileExistsError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/discussions")
def create_discussion(payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")
    try:
        return discussion_service.create_discussion(title=title, slug=payload.get("slug"), root=_root(root))
    except FileExistsError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/discussions/{discussion_id}/items")
def add_discussion_item(discussion_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    card_id = str(payload.get("card_id") or "").strip()
    if not card_id:
        raise HTTPException(400, "card_id is required")
    try:
        return discussion_service.add_item(
            discussion_id=discussion_id,
            card_id=card_id,
            root=_root(root),
            dry_run=bool(payload.get("dry_run", False)),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except (FileExistsError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/api/cards/{card_id}/discussion/open")
def open_discussion(card_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        return discussion_service.open_discussion(card_id, root=_root(root))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


@app.post("/api/cards/{card_id}/discussion/decisions")
def add_decision(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    text = str(payload.get("text") or "").strip()
    if not text:
        raise HTTPException(400, "text is required")
    try:
        return discussion_service.add_decision(card_id, text=text, root=_root(root))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


@app.post("/api/cards/{card_id}/archive/ready")
def mark_archive_ready(card_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        return archive_service.mark_ready(card_id, root=_root(root))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


@app.post("/api/cards/{card_id}/archive")
def archive_card(card_id: str, payload: dict[str, Any] | None = Body(None), root: str | None = None) -> dict[str, Any]:
    try:
        return archive_service.archive(card_id, root=_root(root), dry_run=bool((payload or {}).get("dry_run", False)))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


@app.post("/api/cards/{card_id}/discard")
def discard_card(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reason is required")
    try:
        return archive_service.discard(card_id, reason=reason, root=_root(root), dry_run=bool(payload.get("dry_run", False)))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


@app.post("/api/cards/{card_id}/trash")
def trash_card(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reason is required")
    try:
        return archive_service.trash(card_id, reason=reason, root=_root(root), dry_run=bool(payload.get("dry_run", False)))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"card not found: {card_id}") from exc


_static_dir = package_static_dir()
if _static_dir.exists():
    app.mount("/assets", StaticFiles(directory=_static_dir / "assets"), name="assets")


@app.get("/")
def index() -> FileResponse:
    index_path = _static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "web static assets not found")
    return FileResponse(index_path)
