"""FastAPI app for ChatBoard."""

from __future__ import annotations

import os
from html import escape
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from chatboard import __version__
from chatboard.auth import (
    api_token_enabled,
    auth_enabled,
    auth_username,
    clear_session_cookie,
    executor_api_token_enabled,
    request_is_authenticated,
    set_session_cookie,
    verify_executor_api_token,
    verify_credentials,
)
from chatboard.config import load_runtime_config
from chatboard.models import VISIBLE_COLUMN_KEYS
from chatboard.paths import resolve_workspace_root
from chatboard.services import archive as archive_service
from chatboard.services.backends import (
    BackendRegistryError,
    backend_api_url,
    delete_backend_profile,
    get_backend_profile,
    load_backend_profiles,
    set_default_backend,
    upsert_backend_profile,
)
from chatboard.services import discussion as discussion_service
from chatboard.services import executors as executor_service
from chatboard.services.public_links import resolve_local_path, task_link_bundle
from chatboard.services.cards import (
    card_detail,
    card_file_content,
    card_file_list,
    card_files,
    card_status,
    create_task,
    delete_card,
    ensure_card,
    find_card_path,
    move_card,
    task_catalog,
    transition_card,
    update_card,
)
from chatboard.services.workspace import catalog as build_catalog
from chatboard.services.workspace import column_page as build_column_page
from chatboard.web.paths import package_static_dir


def _cors_origins(raw: str | None = None) -> list[str]:
    value = os.environ.get("CHATBOARD_CORS_ORIGINS", "") if raw is None else raw
    return [origin.strip() for origin in value.split(",") if origin.strip()]


def _install_cors(app: FastAPI) -> None:
    origins = _cors_origins()
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials="*" not in origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


app = FastAPI(title="ChatBoard API", version=__version__)
_install_cors(app)

_PUBLIC_AUTH_PATHS = {"/api/auth", "/api/health", "/api/login", "/login"}
_PUBLIC_AUTH_PREFIXES = ("/assets/",)


def _is_public_auth_path(path: str) -> bool:
    return path in _PUBLIC_AUTH_PATHS or any(path.startswith(prefix) for prefix in _PUBLIC_AUTH_PREFIXES)


@app.middleware("http")
async def require_login(request: Request, call_next):  # type: ignore[no-untyped-def]
    if request.method == "OPTIONS":
        return await call_next(request)
    auth_required = auth_enabled() or (api_token_enabled() and request.url.path.startswith("/api/"))
    if not auth_required or _is_public_auth_path(request.url.path) or request_is_authenticated(request):
        return await call_next(request)
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "authentication required"}, status_code=401)
    return RedirectResponse("/login", status_code=303)


def _root(root: str | None = None) -> Path:
    return resolve_workspace_root(root or os.environ.get("CHATBOARD_WORKSPACE_ROOT"))


def _executor_token_from_request(request: Request) -> str | None:
    token = request.headers.get("X-ChatBoard-Executor-Token")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    return token


def _request_can_execute(request: Request) -> bool:
    token = _executor_token_from_request(request)
    return verify_executor_api_token(token)


def _executor_permission_summary() -> dict[str, Any]:
    return {
        "executor_token_configured": executor_api_token_enabled(),
        "real_execution_requires": "X-ChatBoard-Executor-Token or Bearer token matching CHATBOARD_EXECUTOR_API_KEY",
        "safe_modes_without_executor_token": ["dry-run", "mock"],
        "full_access_policy": "full_access/yolo/force must be explicit_full_access=true and is never implied",
    }


def _decorate_task_links(payload: dict[str, Any], *, card_id: str) -> dict[str, Any]:
    links = task_link_bundle(card_id)
    card = payload.get("card")
    if isinstance(card, dict) and card.get("type") == "task":
        card["public_links"] = links
    return {**payload, **links}


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"ok": True, "version": __version__}


@app.get("/api/auth")
def auth_status(request: Request) -> dict[str, Any]:
    return {
        "enabled": auth_enabled(),
        "authenticated": request_is_authenticated(request),
        "username_required": auth_username() is not None,
        "api_token_enabled": api_token_enabled(),
    }


@app.post("/api/login")
def login(payload: dict[str, Any] = Body(...)) -> JSONResponse:
    if not auth_enabled():
        return JSONResponse({"ok": True, "auth": "disabled"})
    username = str(payload.get("username") or payload.get("account") or "")
    password = str(payload.get("password") or "")
    if not verify_credentials(username, password):
        raise HTTPException(401, "invalid credentials")
    response = JSONResponse({"ok": True})
    set_session_cookie(response)
    return response


@app.post("/api/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"ok": True})
    clear_session_cookie(response)
    return response


@app.get("/api/backend-profiles")
def backend_profiles() -> dict[str, Any]:
    profiles = load_backend_profiles()
    return {"profiles": [profile.redacted() for profile in profiles]}


@app.post("/api/backend-profiles")
def create_backend_profile(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    try:
        profile = upsert_backend_profile(payload)
    except BackendRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"profile": profile.redacted()}


@app.patch("/api/backend-profiles/{profile_id}")
def patch_backend_profile(profile_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    payload = {**payload, "id": profile_id}
    try:
        profile = upsert_backend_profile(payload)
    except BackendRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"profile": profile.redacted()}


@app.delete("/api/backend-profiles/{profile_id}")
def remove_backend_profile(profile_id: str) -> dict[str, Any]:
    try:
        delete_backend_profile(profile_id)
    except BackendRegistryError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"ok": True}


@app.post("/api/backend-profiles/{profile_id}/default")
def set_default_backend_profile(profile_id: str) -> dict[str, Any]:
    try:
        profile = set_default_backend(profile_id)
    except KeyError as exc:
        raise HTTPException(404, f"backend not found: {profile_id}") from exc
    return {"profile": profile.redacted()}


@app.post("/api/backend-profiles/{profile_id}/health")
def backend_profile_health(profile_id: str) -> dict[str, Any]:
    try:
        profile = get_backend_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(404, f"backend not found: {profile_id}") from exc
    response = _proxy_backend_request(profile.id, "GET", "health", b"", "")
    try:
        content = response.body.decode("utf-8") if isinstance(response.body, bytes) else str(response.body)
    except Exception:
        content = ""
    return {"backend": profile.redacted(), "status_code": response.status_code, "body": content}


@app.api_route("/api/backends/{profile_id}/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"])
async def proxy_backend_api(profile_id: str, path: str, request: Request) -> Response:
    body = await request.body()
    return _proxy_backend_request(profile_id, request.method, path, body, request.url.query, request.headers.get("content-type"))


def _proxy_backend_request(
    profile_id: str,
    method: str,
    path: str,
    body: bytes,
    query: str,
    content_type: str | None = None,
) -> Response:
    try:
        profile = get_backend_profile(profile_id)
    except KeyError as exc:
        raise HTTPException(404, f"backend not found: {profile_id}") from exc
    api_path = f"/api/{path}" if path else "/api"
    target = backend_api_url(profile.url, api_path)
    if query:
        target = f"{target}?{query}"
    headers = {"accept": "application/json"}
    if content_type:
        headers["content-type"] = content_type
    if profile.api_key:
        headers["X-ChatBoard-Token"] = profile.api_key
    req = urllib_request.Request(target, data=body or None, headers=headers, method=method)
    try:
        with urllib_request.urlopen(req, timeout=8) as upstream:  # noqa: S310 - URL comes from server-side profiles.
            data = upstream.read()
            return Response(
                content=data,
                status_code=int(upstream.status),
                media_type=upstream.headers.get("content-type") or "application/json",
            )
    except urllib_error.HTTPError as exc:
        return Response(
            content=exc.read(),
            status_code=exc.code,
            media_type=exc.headers.get("content-type") or "application/json",
        )
    except urllib_error.URLError as exc:
        raise HTTPException(502, f"backend request failed: {type(exc.reason).__name__}") from exc


@app.get("/api/catalog")
def catalog(root: str | None = None, ensure: bool = Query(False)) -> dict[str, Any]:
    return build_catalog(root=_root(root), ensure=ensure)


@app.get("/api/pages")
def pages(root: str | None = None) -> dict[str, Any]:
    return {
        "root": _root(root).as_posix(),
        "pages": [
            {"key": "projects", "title": "Projects", "endpoint": "/api/catalog"},
            {"key": "tasks", "title": "Tasks", "endpoint": "/api/tasks"},
            {"key": "executors", "title": "Executors", "endpoint": "/api/executors"},
        ],
    }


@app.get("/api/tasks")
def tasks(root: str | None = None, ensure: bool = Query(False)) -> dict[str, Any]:
    return task_catalog(root=_root(root), ensure=ensure)


@app.get("/api/executors")
def executors() -> dict[str, Any]:
    return {
        "executors": executor_service.list_executors(),
        "permissions": _executor_permission_summary(),
    }


@app.get("/api/executors/{executor_id}")
def executor_detail(executor_id: str) -> dict[str, Any]:
    try:
        return {"executor": executor_service.get_executor(executor_id), "permissions": _executor_permission_summary()}
    except KeyError as exc:
        raise HTTPException(404, f"executor not found: {executor_id}") from exc


@app.post("/api/runs")
def create_run(request: Request, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    try:
        run = executor_service.create_run(payload, root=_root(root), can_execute=_request_can_execute(request))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except executor_service.ExecutorError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"run": run, "permissions": _executor_permission_summary()}


@app.get("/api/runs")
def runs(
    root: str | None = None,
    project_id: str | None = None,
    task_id: str | None = None,
) -> dict[str, Any]:
    return {
        "runs": executor_service.list_runs(root=_root(root), project_id=project_id, task_id=task_id),
        "permissions": _executor_permission_summary(),
    }


@app.get("/api/runs/{run_id}")
def run_detail(run_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        return {"run": executor_service.get_run(run_id, root=_root(root)), "permissions": _executor_permission_summary()}
    except KeyError as exc:
        raise HTTPException(404, f"run not found: {run_id}") from exc


@app.get("/api/runs/{run_id}/log")
def run_log(run_id: str, root: str | None = None, tail: int = Query(12000, ge=0, le=200000)) -> dict[str, Any]:
    try:
        return executor_service.run_log(run_id, root=_root(root), tail=tail)
    except KeyError as exc:
        raise HTTPException(404, f"run not found: {run_id}") from exc


@app.get("/api/resolve-path")
def resolve_path(path: str, root: str | None = None, card_id: str | None = None) -> dict[str, Any]:
    return {"link": resolve_local_path(path, root=_root(root), card_id=card_id)}


@app.post("/api/runs/{run_id}/resume")
def resume_run(request: Request, run_id: str, payload: dict[str, Any] | None = Body(None), root: str | None = None) -> dict[str, Any]:
    try:
        run = executor_service.resume_run(run_id, payload or {}, root=_root(root), can_execute=_request_can_execute(request))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, f"run not found: {run_id}") from exc
    return {"run": run}


@app.post("/api/runs/{run_id}/stop")
def stop_run(request: Request, run_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        run = executor_service.stop_run(run_id, root=_root(root), can_execute=_request_can_execute(request))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, f"run not found: {run_id}") from exc
    return {"run": run}


@app.post("/api/runs/{run_id}/collect")
def collect_run(request: Request, run_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        return executor_service.collect_run(run_id, root=_root(root), can_execute=_request_can_execute(request))
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(404, f"run not found: {run_id}") from exc


@app.post("/api/tasks")
def create_task_api(payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    title = str(payload.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "title is required")
    try:
        card = create_task(
            title=title,
            description=str(payload.get("description") or payload.get("summary") or ""),
            root=_root(root),
            topic=str(payload.get("topic") or "tasks"),
            slug=payload.get("slug"),
            source_platform=payload.get("source_platform"),
            source_url=payload.get("source_url"),
            accept_mode=payload.get("accept_mode"),
            side_effect_level=payload.get("side_effect_level"),
            next_action=payload.get("next_action"),
            assignee=payload.get("assignee"),
            tags=list(payload.get("tags") or []),
            dry_run=bool(payload.get("dry_run", False)),
        )
        return _decorate_task_links({"card": card.to_dict()}, card_id=card.id)
    except FileExistsError as exc:
        raise HTTPException(400, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/tasks/{card_id}/status")
def get_task_status(card_id: str, root: str | None = None) -> dict[str, Any]:
    try:
        status = card_status(card_id, root=_root(root))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"task not found: {card_id}") from exc
    if status.get("type") != "task":
        raise HTTPException(404, f"task not found: {card_id}")
    return _decorate_task_links(status, card_id=card_id)


@app.get("/api/tasks/{card_id}")
def get_task(card_id: str, root: str | None = None) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"task not found: {card_id}")
    detail = card_detail(project_path, root=_root(root))
    if detail.get("card", {}).get("type") != "task":
        raise HTTPException(404, f"task not found: {card_id}")
    return _decorate_task_links(detail, card_id=card_id)


@app.patch("/api/tasks/{card_id}")
def patch_task(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    root_path = _root(root)
    try:
        card_status(card_id, root=root_path)
        card = update_card(card_id, payload, root=root_path)
    except FileNotFoundError as exc:
        raise HTTPException(404, f"task not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    payload = card.to_dict()
    return _decorate_task_links(payload, card_id=card_id) if card.type == "task" else payload


@app.post("/api/tasks/{card_id}/transitions")
def transition_task(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    transition = str(payload.get("transition") or "").strip()
    if not transition:
        raise HTTPException(400, "transition is required")
    try:
        card = transition_card(
            card_id,
            transition,
            reason=payload.get("reason"),
            need=payload.get("need"),
            summary=payload.get("summary"),
            stage=payload.get("stage"),
            root=_root(root),
        )
    except FileNotFoundError as exc:
        raise HTTPException(404, f"task not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if card.type != "task":
        raise HTTPException(404, f"task not found: {card_id}")
    return _decorate_task_links(
        {"card": card.to_dict(), "available_transitions": card_status(card_id, root=_root(root))["available_transitions"]},
        card_id=card_id,
    )


@app.delete("/api/tasks/{card_id}")
def delete_task(card_id: str, payload: dict[str, Any] = Body(...), root: str | None = None) -> dict[str, Any]:
    reason = str(payload.get("reason") or "").strip()
    if not reason:
        raise HTTPException(400, "reason is required")
    try:
        return delete_card(card_id, reason=reason, root=_root(root), dry_run=bool(payload.get("dry_run", False)))
    except FileNotFoundError as exc:
        raise HTTPException(404, f"task not found: {card_id}") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/api/columns/{column_key}")
def get_column(
    column_key: str,
    root: str | None = None,
    ensure: bool = Query(False),
    offset: int = Query(0, ge=0),
    limit: int = Query(24, ge=1, le=100),
) -> dict[str, Any]:
    if column_key not in VISIBLE_COLUMN_KEYS:
        raise HTTPException(404, f"column not found: {column_key}")
    return build_column_page(column_key, root=_root(root), ensure=ensure, offset=offset, limit=limit)



@app.get("/api/cards/{card_id}")
def get_card(card_id: str, root: str | None = None) -> dict[str, Any]:
    project_path = find_card_path(card_id, root=_root(root))
    if project_path is None:
        raise HTTPException(404, f"card not found: {card_id}")
    detail = card_detail(project_path, root=_root(root))
    if detail.get("card", {}).get("type") == "task":
        return _decorate_task_links(detail, card_id=card_id)
    return detail


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
    try:
        return ensure_card(project_path, root=_root(root)).to_dict()
    except FileNotFoundError as exc:
        raise HTTPException(404, f"project directory not found: {project_path}") from exc


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
def index() -> HTMLResponse:
    index_path = _static_dir / "index.html"
    if not index_path.exists():
        raise HTTPException(404, "web static assets not found")
    config = load_runtime_config()
    html = index_path.read_text(encoding="utf-8")
    replacements = {
        'name="chatboard-default-backend-name" content="default"': f'name="chatboard-default-backend-name" content="{escape(str(config["default_backend_name"]), quote=True)}"',
        'name="chatboard-default-backend-url" content=""': f'name="chatboard-default-backend-url" content="{escape(str(config["default_backend_url"]), quote=True)}"',
    }
    for old, new in replacements.items():
        html = html.replace(old, new)
    return HTMLResponse(html)


@app.get("/login")
def login_page() -> Any:
    if not auth_enabled():
        return RedirectResponse("/", status_code=303)
    login_path = _static_dir / "login.html"
    if not login_path.exists():
        raise HTTPException(404, "login page not found")
    return FileResponse(login_path)
