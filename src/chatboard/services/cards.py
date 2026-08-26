"""Project card services."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from chatboard.models import (
    ArchiveState,
    BoardColumn,
    CardLinks,
    CardRef,
    CardSource,
    CardTimestamps,
    DetailSection,
    DiscussionState,
    ProjectCard,
    TASK_COLUMNS,
    VALID_AREAS,
    VALID_STAGES,
    utc_now,
)
from chatboard.paths import DEFAULT_GITIGNORE_DIR_NAMES, DEFAULT_GITIGNORE_FILE_NAMES, area_path, as_workspace_relative, infer_workspace_date, resolve_workspace_root
from chatboard.storage.markdown_card import load_card as load_markdown_card
from chatboard.storage.markdown_card import save_card

_URL_RE = re.compile(r'https?://[^\s)>"\']+')
_HEADING_RE = re.compile(r"^#\s+(.+?)\s*$", re.M)


def slugify_id(relative_path: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", relative_path).strip("-").lower()
    return slug or "workspace-card"


def _read_text(path: Path, limit: int | None = None) -> str:
    if not path.exists() or not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if limit is not None and len(text) > limit:
        return text[:limit] + "\n..."
    return text


def _safe_child_path(root: Path, relative_path: str) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("path escapes card root") from exc
    return candidate


def _safe_relative_parts(value: str) -> tuple[str, ...]:
    path = Path(value)
    parts = path.parts
    if path.is_absolute() or not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError("path escapes card root")
    return parts


def _load_task_card(card_id: str, root: str | Path | None = None) -> tuple[Path, ProjectCard]:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = load_card(project_path, root)
    if card.type != "task" or card.area == "discard":
        raise FileNotFoundError(card_id)
    return project_path, card


def _title_from_project(project_path: Path) -> str:
    prd = _read_text(project_path / "PRD.md", 20000)
    match = _HEADING_RE.search(prd)
    if match:
        return match.group(1).strip()
    name = project_path.name
    return re.sub(r"^\d{2}-\d{2}-", "", name).replace("-", " ").strip().title() or name


def _summary_from_prd(project_path: Path) -> str:
    prd = _read_text(project_path / "PRD.md", 20000)
    for line in prd.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped.startswith("-"):
            continue
        return stripped[:240]
    return ""


def _tags_from_relative(relative_path: str) -> list[str]:
    parts = [part for part in Path(relative_path).parts[:-1] if part not in {"projects", "discussion", "archive", "Items"}]
    return parts[:6]


def _looks_like_card_dir(path: Path) -> bool:
    return any((path / name).exists() for name in ("PRD.md", "progress.md", "card.md"))


def _card_ref_for_path(project_path: Path, root: Path) -> CardRef:
    sidecar = load_markdown_card(project_path, root)
    relative = as_workspace_relative(project_path, root)
    area = _area_for_path(project_path, root)
    stage = sidecar.stage if sidecar else infer_stage(project_path, area)
    tags = sidecar.tags if sidecar else _tags_from_relative(relative)
    return CardRef(
        id=sidecar.id if sidecar else slugify_id(relative),
        title=sidecar.title if sidecar else _title_from_project(project_path),
        workspace_path=relative,
        area=area,
        stage=stage,
        tags=tags,
    )


def _discussion_item_refs(project_path: Path, root: Path) -> list[CardRef]:
    items_dir = project_path / "Items"
    if not items_dir.exists() or not items_dir.is_dir():
        return []
    refs: list[CardRef] = []
    for item in sorted(items_dir.iterdir()):
        if item.is_dir() and _looks_like_card_dir(item):
            refs.append(_card_ref_for_path(item.resolve(), root))
    return refs


def _area_for_path(project_path: Path, root: Path) -> str:
    try:
        parts = project_path.resolve().relative_to(root).parts
    except ValueError:
        return "projects"
    if not parts:
        return "projects"
    first = parts[0]
    if first in {"projects", "discussion", "archive", "discard"}:
        return first
    if first == ".trash":
        return "trash"
    return "projects"


def infer_stage(project_path: Path, area: str) -> str:
    card = load_markdown_card(project_path)
    if card:
        return card.stage
    if area == "archive":
        return "archived"
    if area == "discard":
        return "discarded"
    if area == "discussion":
        return "review"
    if not (project_path / "PRD.md").exists():
        return "scaffold"
    if not (project_path / "progress.md").exists():
        return "prd"
    return "development"


def infer_card(project_path: str | Path, root: str | Path | None = None) -> ProjectCard:
    root_path = resolve_workspace_root(root)
    path = Path(project_path).expanduser().resolve()
    relative = as_workspace_relative(path, root_path)
    area = _area_for_path(path, root_path)
    stage = infer_stage(path, area)
    feishu_links = [url for url in _URL_RE.findall(_read_text(path / "PRD.md") + "\n" + _read_text(path / "progress.md")) if "feishu" in url]
    reports = []
    reports_dir = path / "reports"
    if reports_dir.exists():
        reports = [p.relative_to(path).as_posix() for p in sorted(reports_dir.glob("*")) if p.is_file()][:50]
    return ProjectCard(
        id=slugify_id(relative),
        title=_title_from_project(path),
        description=_summary_from_prd(path),
        summary=_summary_from_prd(path),
        date=infer_workspace_date(path, root_path),
        area=area,  # type: ignore[arg-type]
        stage=stage,
        workspace_path=relative,
        tags=_tags_from_relative(relative),
        links=CardLinks(
            prd="PRD.md" if (path / "PRD.md").exists() else None,
            progress="progress.md" if (path / "progress.md").exists() else None,
            feishu=feishu_links,
            reports=reports,
        ),
        discussion=DiscussionState(status="not_started" if area == "projects" else "review"),
        archive=ArchiveState(ready=stage == "archive_ready"),
        timestamps=CardTimestamps(),
        nested_items=_discussion_item_refs(path, root_path) if area == "discussion" else [],
    )


def load_card(project_path: str | Path, root: str | Path | None = None) -> ProjectCard:
    path = Path(project_path).expanduser().resolve()
    root_path = resolve_workspace_root(root)
    card = load_markdown_card(path, root_path)
    if card is None:
        return infer_card(path, root_path)
    if _area_for_path(path, root_path) == "discussion":
        card.nested_items = _discussion_item_refs(path, root_path)
    return card


def ensure_card(project_path: str | Path, root: str | Path | None = None) -> ProjectCard:
    path = Path(project_path).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise FileNotFoundError(path)
    root_path = resolve_workspace_root(root)
    card = load_markdown_card(path, root_path)
    if card is None:
        card = infer_card(path, root_path)
        save_card(path, card)
    if _area_for_path(path, root_path) == "discussion":
        card.nested_items = _discussion_item_refs(path, root_path)
    return card


def save_existing_card(project_path: str | Path, card: ProjectCard) -> ProjectCard:
    save_card(Path(project_path).expanduser().resolve(), card)
    return card


def _dedupe_tags(values: list[str]) -> list[str]:
    tags: list[str] = []
    for value in values:
        tag = str(value).strip()
        if tag and tag not in tags:
            tags.append(tag)
    return tags


def create_task(
    title: str,
    *,
    description: str = "",
    root: str | Path | None = None,
    topic: str = "tasks",
    slug: str | None = None,
    source_platform: str | None = None,
    source_url: str | None = None,
    accept_mode: str | None = None,
    side_effect_level: str | None = None,
    next_action: str | None = None,
    assignee: str | None = None,
    tags: list[str] | None = None,
    dry_run: bool = False,
) -> ProjectCard:
    """Create a task card skeleton for the separate Tasks board tab."""

    clean_title = title.strip()
    if not clean_title:
        raise ValueError("title is required")
    root_path = resolve_workspace_root(root)
    clean_topic = (topic or "tasks").strip("/")
    task_slug = slug or slugify_id(clean_title)
    project_path = root_path / "projects" / Path(*_safe_relative_parts(clean_topic)) / Path(*_safe_relative_parts(task_slug))
    if project_path.exists():
        raise FileExistsError(project_path)
    relative = as_workspace_relative(project_path, root_path)
    summary = description.strip()
    card = ProjectCard(
        id=slugify_id(relative),
        title=clean_title,
        type="task",
        description=summary,
        summary=summary,
        workspace_path=relative,
        area="projects",
        stage="inbox",
        date=infer_workspace_date(project_path, root_path),
        tags=_dedupe_tags([clean_topic, *(tags or [])]),
        assignee=assignee,
        links=CardLinks(prd="PRD.md", progress="progress.md"),
        source=CardSource(platform=source_platform, url=source_url),
        accept_mode=accept_mode or "accept",
        side_effect_level=side_effect_level or "local_write",
        next_action=next_action,
        discussion=DiscussionState(next_action=next_action),
        timestamps=CardTimestamps(),
    )
    if dry_run:
        return card
    project_path.mkdir(parents=True, exist_ok=False)
    (project_path / ".trash").mkdir()
    (project_path / "reports").mkdir()
    prd_body = summary or "TODO"
    (project_path / "PRD.md").write_text(f"# {clean_title}\n\n{prd_body}\n", encoding="utf-8")
    (project_path / "progress.md").write_text(f"# Progress\n\n- {utc_now()} created task card.\n", encoding="utf-8")
    save_card(project_path, card)
    return card


def find_card_path(card_id: str, root: str | Path | None = None) -> Path | None:
    from chatboard.services.workspace import iter_project_dirs

    for project in iter_project_dirs(root, include_nested=True):
        card = load_card(project, root)
        if card.id == card_id:
            return project
    return None


def card_detail(project_path: str | Path, root: str | Path | None = None) -> dict:
    path = Path(project_path).expanduser().resolve()
    card = load_card(path, root)
    prd = _read_text(path / "PRD.md", 12000)
    progress = _read_text(path / "progress.md", 12000)
    progress_tail = "\n".join(progress.splitlines()[-80:]) if progress else ""
    reports = []
    reports_dir = path / "reports"
    if reports_dir.exists():
        for item in sorted(reports_dir.iterdir()):
            if item.is_file():
                reports.append({"path": item.relative_to(path).as_posix(), "size": item.stat().st_size})
    from chatboard.services.executors import list_runs

    related_runs = list_runs(root=root, project_id=card.id)
    if card.type == "task":
        task_runs = list_runs(root=root, task_id=card.id)
        seen = {run["run_id"] for run in related_runs}
        related_runs.extend(run for run in task_runs if run["run_id"] not in seen)
    sections = [
        DetailSection("overview", "Overview", "fields", card.to_dict()),
        DetailSection("files", "Files", "file_tree", card_files(path)),
        DetailSection("runs", "Runs", "executor_runs", related_runs),
        DetailSection("prd", "PRD", "markdown", prd),
        DetailSection("progress", "Progress", "markdown", progress_tail),
        DetailSection("discussion", "Discussion", "json", card.discussion.__dict__),
        DetailSection("artifacts", "Artifacts", "list", reports),
        DetailSection("archive", "Archive", "json", card.archive.__dict__),
    ]
    return {"card": card.to_dict(), "sections": [section.__dict__ for section in sections]}


FILE_EXPLORER_IGNORED_DIR_NAMES = DEFAULT_GITIGNORE_DIR_NAMES | {".trash"}
FILE_EXPLORER_IGNORED_FILE_NAMES = DEFAULT_GITIGNORE_FILE_NAMES | {"card.json"}
TASK_FOCUSED_ROOT_NAMES = {"card.md", "PRD.md", "progress.md", "reports", "scripts", "playground", "assets", "Items"}
PREVIEWABLE_SUFFIXES = {".md", ".txt", ".json", ".yaml", ".yml", ".py", ".js", ".css", ".html"}


def _is_file_explorer_ignored(item: Path) -> bool:
    return item.name in FILE_EXPLORER_IGNORED_DIR_NAMES or (item.is_file() and item.name in FILE_EXPLORER_IGNORED_FILE_NAMES)


def _hide_from_file_explorer(item: Path, root: Path, include_hidden: bool) -> bool:
    if _is_file_explorer_ignored(item):
        return True
    if include_hidden:
        return False
    return item.parent == root and item.name not in TASK_FOCUSED_ROOT_NAMES


def card_files(project_path: str | Path, max_depth: int = 3, include_hidden: bool = False) -> list[dict[str, Any]]:
    root = Path(project_path).expanduser().resolve()
    def walk(path: Path, depth: int) -> list[dict[str, Any]]:
        if depth > max_depth or not path.is_dir():
            return []
        nodes = []
        for item in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if _hide_from_file_explorer(item, root, include_hidden):
                continue
            relative = item.relative_to(root).as_posix()
            node: dict[str, Any] = {
                "name": item.name,
                "path": relative,
                "type": "directory" if item.is_dir() else "file",
            }
            if item.is_file():
                node["size"] = item.stat().st_size
                node["previewable"] = item.suffix.lower() in PREVIEWABLE_SUFFIXES
            else:
                node["children"] = walk(item, depth + 1)
            nodes.append(node)
        return nodes

    return walk(root, 1)


def card_file_content(project_path: str | Path, relative_path: str, limit: int = 50000) -> dict[str, Any]:
    root = Path(project_path).expanduser().resolve()
    target = _safe_child_path(root, relative_path)
    if not target.exists() or not target.is_file():
        raise FileNotFoundError(relative_path)
    if target.stat().st_size > limit:
        content = _read_text(target, limit)
        truncated = True
    else:
        content = _read_text(target)
        truncated = False
    return {
        "path": target.relative_to(root).as_posix(),
        "size": target.stat().st_size,
        "content": content,
        "truncated": truncated,
    }


def card_file_list(project_path: str | Path, relative_path: str = "", include_hidden: bool = False) -> dict[str, Any]:
    root = Path(project_path).expanduser().resolve()
    target = _safe_child_path(root, relative_path) if relative_path else root
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(relative_path)
    children = []
    for item in sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
        if _hide_from_file_explorer(item, root, include_hidden):
            continue
        relative = item.relative_to(root).as_posix()
        node: dict[str, Any] = {
            "name": item.name,
            "path": relative,
            "type": "directory" if item.is_dir() else "file",
        }
        if item.is_dir():
            try:
                node["has_children"] = any(
                    not _hide_from_file_explorer(child, root, include_hidden)
                    for child in item.iterdir()
                )
            except PermissionError:
                node["has_children"] = False
        else:
            node["size"] = item.stat().st_size
            node["previewable"] = item.suffix.lower() in PREVIEWABLE_SUFFIXES
        children.append(node)
    return {"path": target.relative_to(root).as_posix() if target != root else "", "children": children}


def update_card(card_id: str, patch: dict, root: str | Path | None = None) -> ProjectCard:
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    card = ensure_card(project_path, root)
    for key in (
        "title",
        "description",
        "summary",
        "stage",
        "priority",
        "owner",
        "assignee",
        "tags",
        "accept_mode",
        "side_effect_level",
        "next_action",
    ):
        if key in patch:
            setattr(card, key, patch[key])
    if "source" in patch and isinstance(patch["source"], dict):
        card.source = CardSource(platform=patch["source"].get("platform"), url=patch["source"].get("url"))
    if "source_platform" in patch or "source_url" in patch:
        card.source = CardSource(
            platform=patch.get("source_platform", card.source.platform),
            url=patch.get("source_url", card.source.url),
        )
    if card.next_action:
        card.discussion.next_action = card.next_action
    if "stage" in patch and card.stage not in VALID_STAGES:
        raise ValueError(f"invalid stage: {card.stage}")
    save_card(project_path, card)
    return card


def available_transitions(card: ProjectCard) -> list[str]:
    if card.stage == "inbox":
        return ["accept", "block", "move"]
    if card.stage == "ready":
        return ["start", "block", "done", "move"]
    if card.stage == "running":
        return ["review", "block", "done", "move"]
    if card.stage == "blocked":
        return ["unblock", "move"]
    if card.stage == "review":
        return ["done", "block", "move"]
    if card.stage == "done":
        return ["move"]
    return ["move"]


def card_status(card_id: str, root: str | Path | None = None) -> dict:
    _, card = _load_task_card(card_id, root)
    data = card.to_dict()
    data["available_transitions"] = available_transitions(card)
    return data


def transition_card(
    card_id: str,
    transition: str,
    *,
    reason: str | None = None,
    need: str | None = None,
    summary: str | None = None,
    stage: str | None = None,
    root: str | Path | None = None,
) -> ProjectCard:
    project_path, card = _load_task_card(card_id, root)
    if transition == "accept":
        card.stage = "ready"
    elif transition == "start":
        card.stage = "running"
    elif transition == "review":
        card.stage = "review"
    elif transition == "block":
        card.stage = "blocked"
        if reason:
            card.discussion.questions.append(reason)
        if need:
            card.next_action = need
            card.discussion.next_action = need
    elif transition == "unblock":
        card.stage = "ready"
    elif transition == "done":
        card.stage = "done"
        if summary:
            card.summary = summary
    elif transition == "move":
        if not stage:
            raise ValueError("stage is required for move transition")
        if stage not in VALID_STAGES:
            raise ValueError(f"invalid stage: {stage}")
        card.stage = stage
    else:
        raise ValueError(f"invalid transition: {transition}")
    if reason and transition != "block":
        card.discussion.decisions.append(reason)
    save_card(project_path, card)
    return card


def delete_card(card_id: str, *, reason: str, root: str | Path | None = None, dry_run: bool = False) -> dict:
    if not reason.strip():
        raise ValueError("reason is required")
    _load_task_card(card_id, root)
    result = move_card(card_id, "discard", stage="discarded", root=root, dry_run=dry_run)
    result["reason"] = reason
    if dry_run:
        return result
    destination = Path(result["to"])
    card = ensure_card(destination, root)
    card.archive.reason = reason
    save_card(destination, card)
    result["card"] = card.to_dict()
    return result


def task_catalog(root: str | Path | None = None, ensure: bool = False) -> dict:
    from chatboard.services.workspace import iter_project_dirs

    root_path = resolve_workspace_root(root)
    columns = {key: BoardColumn(key=key, title=title) for key, title in TASK_COLUMNS}
    cards: list[ProjectCard] = []
    for project_path in iter_project_dirs(root_path, include_nested=True):
        card = ensure_card(project_path, root_path) if ensure else load_card(project_path, root_path)
        if card.type != "task" or card.area == "discard":
            continue
        cards.append(card)
        columns.setdefault(card.column, BoardColumn(key=card.column, title=card.column)).cards.append(card)
    return {
        "root": root_path.as_posix(),
        "columns": [column.to_dict() for column in columns.values()],
        "total_cards": len(cards),
    }


def move_card(
    card_id: str,
    area: str,
    stage: str | None = None,
    root: str | Path | None = None,
    dry_run: bool = False,
) -> dict:
    if area not in VALID_AREAS:
        raise ValueError(f"invalid area: {area}")
    project_path = find_card_path(card_id, root)
    if project_path is None:
        raise FileNotFoundError(card_id)
    root_path = resolve_workspace_root(root)
    card = load_card(project_path, root_path)
    old_relative = Path(card.workspace_path)
    if area == "archive":
        date_prefix = utc_now()[:10]
        destination = area_path(root_path, area) / date_prefix / Path(*old_relative.parts[1:])
        stage = stage or "archived"
    elif area == "trash":
        stamp = utc_now().replace(":", "").replace("-", "")
        destination = area_path(root_path, area) / stamp / Path(*old_relative.parts[1:])
        stage = stage or "trashed"
    else:
        destination = area_path(root_path, area) / Path(*old_relative.parts[1:])
        if area == "discussion":
            stage = stage or "review"
        elif area == "discard":
            stage = stage or "discarded"
        else:
            stage = stage or "development"
    if destination.exists():
        raise FileExistsError(destination)
    result = {
        "card_id": card_id,
        "from": project_path.as_posix(),
        "to": destination.as_posix(),
        "dry_run": dry_run,
        "area": area,
        "stage": stage,
    }
    if dry_run:
        return result
    card = ensure_card(project_path, root_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(project_path.as_posix(), destination.as_posix())
    card.area = area  # type: ignore[assignment]
    card.stage = stage
    card.workspace_path = as_workspace_relative(destination, root_path)
    if area == "discussion":
        card.discussion.status = "review"
    if area == "archive":
        card.archive.ready = False
        card.archive.target = card.workspace_path
    if area == "trash":
        card.archive.reason = card.archive.reason or "trashed"
    save_card(destination, card)
    result["card"] = card.to_dict()
    return result
