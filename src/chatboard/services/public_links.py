"""Resolve backend-local workspace paths to shareable ChatBoard API links."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from urllib.parse import quote

from chatboard.config import load_runtime_config
from chatboard.paths import resolve_workspace_root


def service_base_url() -> str:
    """Return the configured public/service URL without credentials."""

    return str(load_runtime_config().get("service_url") or "http://127.0.0.1:8000/").rstrip("/")


def api_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{service_base_url()}{clean_path}"


def ui_url(path: str) -> str:
    clean_path = path if path.startswith("/") else f"/{path}"
    return f"{service_base_url()}{clean_path}"


def task_public_link(card_id: str) -> dict[str, Any]:
    """Return the stable ChatBoard task detail link contract."""

    encoded_card = quote(card_id, safe="")
    api_path = f"/api/tasks/{encoded_card}"
    ui_path = f"/#/tasks/{encoded_card}"
    return {
        "kind": "chatboard.task",
        "card_id": card_id,
        "api_path": api_path,
        "ui_path": ui_path,
        "public_url": ui_url(ui_path),
    }


def card_file_public_link(card_id: str, path: str) -> dict[str, Any]:
    encoded_card = quote(card_id, safe="")
    api_path = f"/api/cards/{encoded_card}/files/content?path={quote(path, safe='')}"
    return {
        "kind": "chatboard.card_file",
        "card_id": card_id,
        "path": path,
        "api_path": api_path,
        "public_url": api_url(api_path),
    }


def task_link_bundle(card_id: str, *, prd_path: str | None = "PRD.md") -> dict[str, Any]:
    return {
        "task_link": task_public_link(card_id),
        "prd_link": card_file_public_link(card_id, prd_path or "PRD.md"),
    }


def resolve_local_path(path: str | Path | None, *, root: str | Path | None = None, card_id: str | None = None) -> dict[str, Any] | None:
    """Resolve a local path using ChatBoard's workspace-relative share contract.

    ChatBoard already stores card-local paths as `workspace_path` plus relative
    file links. This function makes the public URL part explicit: when a path is
    inside the workspace and can be addressed through an existing card file API,
    it returns an absolute URL rooted at `CHATBOARD_SERVICE_URL`.
    """

    if path is None:
        return None
    root_path = resolve_workspace_root(root)
    local_path = Path(path).expanduser()
    if not local_path.is_absolute():
        local_path = root_path / local_path
    local_path = local_path.resolve()
    result: dict[str, Any] = {
        "local_path": local_path.as_posix(),
        "workspace_path": None,
        "api_path": None,
        "public_url": None,
        "resolvable": False,
        "reason": None,
    }
    try:
        workspace_path = local_path.relative_to(root_path).as_posix()
    except ValueError:
        result["reason"] = "path is outside workspace root"
        return result
    result["workspace_path"] = workspace_path
    if card_id:
        file_path = _card_file_path(workspace_path)
        if file_path is not None:
            result.update({**card_file_public_link(card_id, file_path), "resolvable": True})
            return result
    result["reason"] = "no card-scoped file API route is known for this path"
    return result


def _card_file_path(workspace_path: str) -> str | None:
    parts = Path(workspace_path).parts
    for marker in ("PRD.md", "progress.md", "card.md", "reports", "scripts", "playground", "assets"):
        if marker in parts:
            index = parts.index(marker)
            return Path(*parts[index:]).as_posix()
    return None


def run_public_links(run: dict[str, Any], *, root: str | Path | None = None) -> dict[str, Any]:
    run_id = str(run.get("run_id") or "")
    encoded_run = quote(run_id, safe="")
    card_id = run.get("task_id") or run.get("project_id")
    return {
        "run": {"api_path": f"/api/runs/{encoded_run}", "public_url": api_url(f"/api/runs/{encoded_run}")},
        "log": {"api_path": f"/api/runs/{encoded_run}/log", "public_url": api_url(f"/api/runs/{encoded_run}/log")},
        "workdir": resolve_local_path(run.get("workdir"), root=root, card_id=card_id),
        "prompt": resolve_local_path(run.get("prompt_path"), root=root, card_id=card_id),
        "report": resolve_local_path(run.get("report_path"), root=root, card_id=card_id),
    }
