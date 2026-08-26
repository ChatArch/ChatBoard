"""Workspace-scoped executor capability and run services."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import signal
import shutil
import subprocess
import time
from typing import Any
from uuid import uuid4

from chatboard.config import load_runtime_config
from chatboard.models import utc_now
from chatboard.paths import as_workspace_relative, resolve_workspace_root
from chatboard.services.cards import find_card_path
from chatboard.services.public_links import run_public_links

RUN_STATUSES = {"queued", "running", "blocked", "done", "failed", "stopped", "needs_review"}
SAFE_RUN_MODES = {"dry-run", "mock"}


@dataclass(frozen=True)
class ExecutorDefinition:
    id: str
    display_name: str
    command: str
    version_args: tuple[str, ...]
    supports_resume: bool
    supports_stop: bool
    supports_json_output: bool
    resume_id_kind: str | None
    resume_template: str | None


@dataclass
class ExecutorCapability:
    id: str
    display_name: str
    installed: bool
    authenticated: bool
    supports_resume: bool
    supports_stop: bool
    supports_json_output: bool
    version: str | None = None
    command_path: str | None = None
    resume_id_kind: str | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExecutorRun:
    run_id: str
    project_id: str | None
    task_id: str | None
    executor: str
    workdir: str
    prompt_path: str
    report_path: str
    log_path: str
    process_session_id: str | None = None
    os_pid: int | None = None
    backend_session_id: str | None = None
    status: str = "queued"
    mode: str = "dry-run"
    created_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    exit_code: int | None = None
    command_hint: str | None = None
    resume_command_hint: str | None = None
    explicit_full_access: bool = False
    public_links: dict[str, Any] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


EXECUTORS: dict[str, ExecutorDefinition] = {
    "codex": ExecutorDefinition(
        id="codex",
        display_name="Codex",
        command="codex",
        version_args=("--version",),
        supports_resume=True,
        supports_stop=True,
        supports_json_output=False,
        resume_id_kind="session_id",
        resume_template="codex resume {backend_session_id}",
    ),
    "cursor-agent": ExecutorDefinition(
        id="cursor-agent",
        display_name="Cursor Agent",
        command="cursor-agent",
        version_args=("--version",),
        supports_resume=True,
        supports_stop=True,
        supports_json_output=False,
        resume_id_kind="chat_id",
        resume_template="cursor-agent resume {backend_session_id}",
    ),
    "opencode": ExecutorDefinition(
        id="opencode",
        display_name="OpenCode",
        command="opencode",
        version_args=("--version",),
        supports_resume=True,
        supports_stop=True,
        supports_json_output=False,
        resume_id_kind="session_id",
        resume_template="opencode session {backend_session_id}",
    ),
}


class ExecutorError(ValueError):
    """Service-level error suitable for API 400 responses."""


def executor_permission_configured() -> bool:
    return bool(os.environ.get("CHATBOARD_EXECUTOR_API_KEY") or load_runtime_config().get("executor_api_key"))


def workspace_run_store_path(root: str | Path | None = None) -> Path:
    root_path = resolve_workspace_root(root)
    digest = sha256(root_path.as_posix().encode("utf-8")).hexdigest()[:16]
    home = Path(load_runtime_config()["chatboard_home"]).expanduser()
    return home / "executor-runs" / f"{digest}.json"


def _artifacts_dir(root: Path, run_id: str) -> Path:
    return workspace_run_store_path(root).parent / "artifacts" / run_id


def _load_runs(root: str | Path | None = None) -> list[ExecutorRun]:
    path = workspace_run_store_path(root)
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    runs = []
    for item in raw.get("runs", []):
        item.setdefault("public_links", {})
        runs.append(ExecutorRun(**item))
    return runs


def _save_runs(runs: list[ExecutorRun], root: str | Path | None = None) -> None:
    path = workspace_run_store_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema": "chatboard.executor_runs.v1",
        "workspace_root": resolve_workspace_root(root).as_posix(),
        "runs": [with_public_links(run, root).to_dict() for run in runs],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def with_public_links(run: ExecutorRun, root: str | Path | None = None) -> ExecutorRun:
    run.public_links = run_public_links(run.to_dict(), root=root)
    return run


def _update_process_status(run: ExecutorRun) -> ExecutorRun:
    if run.status != "running" or run.os_pid is None:
        return run
    try:
        result = os.waitpid(run.os_pid, os.WNOHANG)
    except ChildProcessError:
        return run
    except OSError:
        return run
    if result == (0, 0):
        return run
    _, raw_status = result
    run.exit_code = os.waitstatus_to_exitcode(raw_status)
    run.status = "done" if run.exit_code == 0 else "failed"
    run.completed_at = utc_now()
    run.updated_at = run.completed_at
    return run


def list_executors() -> list[dict[str, Any]]:
    return [get_executor(executor_id) for executor_id in EXECUTORS]


def get_executor(executor_id: str) -> dict[str, Any]:
    definition = EXECUTORS.get(executor_id)
    if definition is None:
        raise KeyError(executor_id)
    command_path = shutil.which(definition.command)
    installed = command_path is not None
    version = None
    notes: list[str] = []
    if installed:
        try:
            completed = subprocess.run(
                [definition.command, *definition.version_args],
                check=False,
                capture_output=True,
                text=True,
                timeout=3,
            )
            version = (completed.stdout or completed.stderr).strip().splitlines()[0][:160] if (completed.stdout or completed.stderr).strip() else None
        except Exception as exc:
            notes.append(f"version probe failed: {type(exc).__name__}")
    else:
        notes.append("command not found on PATH")
    return ExecutorCapability(
        id=definition.id,
        display_name=definition.display_name,
        installed=installed,
        authenticated=installed,
        supports_resume=definition.supports_resume,
        supports_stop=definition.supports_stop,
        supports_json_output=definition.supports_json_output,
        version=version,
        command_path=command_path,
        resume_id_kind=definition.resume_id_kind,
        notes=notes,
    ).to_dict()


def list_runs(root: str | Path | None = None, *, project_id: str | None = None, task_id: str | None = None) -> list[dict[str, Any]]:
    runs = [_update_process_status(run) for run in _load_runs(root)]
    if runs:
        _save_runs(runs, root)
    if project_id:
        runs = [run for run in runs if run.project_id == project_id]
    if task_id:
        runs = [run for run in runs if run.task_id == task_id]
    return [with_public_links(run, root).to_dict() for run in sorted(runs, key=lambda item: item.created_at, reverse=True)]


def get_run(run_id: str, root: str | Path | None = None) -> dict[str, Any]:
    runs = [_update_process_status(run) for run in _load_runs(root)]
    for run in runs:
        if run.run_id == run_id:
            _save_runs(runs, root)
            return with_public_links(run, root).to_dict()
    raise KeyError(run_id)


def _replace_run(updated: ExecutorRun, root: str | Path | None = None) -> ExecutorRun:
    runs = _load_runs(root)
    for index, run in enumerate(runs):
        if run.run_id == updated.run_id:
            runs[index] = updated
            _save_runs(runs, root)
            return updated
    raise KeyError(updated.run_id)


def _find_run_obj(run_id: str, root: str | Path | None = None) -> ExecutorRun:
    for run in _load_runs(root):
        if run.run_id == run_id:
            return _update_process_status(run)
    raise KeyError(run_id)


def _resolve_workdir(payload: dict[str, Any], root: Path) -> tuple[Path, str | None, str | None]:
    task_id = payload.get("task_id")
    project_id = payload.get("project_id")
    card_id = task_id or project_id
    if payload.get("workdir"):
        workdir = Path(str(payload["workdir"])).expanduser()
        if not workdir.is_absolute():
            workdir = root / workdir
    elif card_id:
        card_path = find_card_path(str(card_id), root)
        if card_path is None:
            raise ExecutorError(f"card not found: {card_id}")
        workdir = card_path
    else:
        workdir = root
    workdir = workdir.resolve()
    try:
        workdir.relative_to(root)
    except ValueError as exc:
        raise ExecutorError("workdir must stay inside workspace root") from exc
    if not workdir.exists() or not workdir.is_dir():
        raise ExecutorError(f"workdir not found: {workdir}")
    return workdir, str(project_id) if project_id else None, str(task_id) if task_id else None


def _write_prompt(payload: dict[str, Any], root: Path, run_id: str) -> Path:
    if payload.get("prompt_path"):
        prompt_path = Path(str(payload["prompt_path"])).expanduser()
        if not prompt_path.is_absolute():
            prompt_path = root / prompt_path
        prompt_path = prompt_path.resolve()
        try:
            prompt_path.relative_to(root)
        except ValueError as exc:
            raise ExecutorError("prompt_path must stay inside workspace root") from exc
        if not prompt_path.exists() or not prompt_path.is_file():
            raise ExecutorError(f"prompt_path not found: {prompt_path}")
        return prompt_path
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ExecutorError("prompt or prompt_path is required")
    prompt_path = _artifacts_dir(root, run_id) / "prompt.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt + "\n", encoding="utf-8")
    return prompt_path


def _default_report_path(payload: dict[str, Any], workdir: Path, root: Path, run_id: str) -> Path:
    if payload.get("report_path"):
        report_path = Path(str(payload["report_path"])).expanduser()
        if not report_path.is_absolute():
            report_path = workdir / report_path
        return report_path.resolve()
    if (workdir / "reports").exists():
        return (workdir / "reports" / f"{run_id}.md").resolve()
    return (_artifacts_dir(root, run_id) / "report.md").resolve()


def _build_command(executor_id: str, prompt_path: Path, *, explicit_full_access: bool = False) -> list[str]:
    if executor_id == "codex":
        sandbox = "danger-full-access" if explicit_full_access else "workspace-write"
        return [
            "sh",
            "-c",
            "exec codex exec --skip-git-repo-check -s \"$2\" -c 'approval_policy=\"never\"' - < \"$1\"",
            "chatboard-codex",
            prompt_path.as_posix(),
            sandbox,
        ]
    if executor_id == "cursor-agent":
        mode = "full" if explicit_full_access else "ask"
        return [
            "sh",
            "-c",
            "if [ \"$2\" = full ]; then exec cursor-agent --print --trust --force --workspace \"$PWD\" \"$(cat \"$1\")\"; fi; exec cursor-agent --print --trust --mode ask --workspace \"$PWD\" \"$(cat \"$1\")\"",
            "chatboard-cursor-agent",
            prompt_path.as_posix(),
            mode,
        ]
    if executor_id == "opencode":
        command = "exec opencode run --file \"$1\" 'Follow the instructions in the attached prompt file.'"
        if explicit_full_access:
            command = "exec opencode run --auto --file \"$1\" 'Follow the instructions in the attached prompt file.'"
        return ["sh", "-c", command, "chatboard-opencode", prompt_path.as_posix()]
    raise ExecutorError(f"unknown executor: {executor_id}")


def create_run(payload: dict[str, Any], root: str | Path | None = None, *, can_execute: bool = False) -> dict[str, Any]:
    root_path = resolve_workspace_root(root)
    executor_id = str(payload.get("executor") or "").strip()
    if executor_id not in EXECUTORS:
        raise ExecutorError(f"unknown executor: {executor_id}")
    mode = str(payload.get("mode") or payload.get("execution_mode") or "dry-run").strip().lower()
    if mode not in {"dry-run", "mock", "real"}:
        raise ExecutorError("mode must be dry-run, mock, or real")
    if mode == "real" and not can_execute:
        raise PermissionError("executor permission required for real runs")
    full_access = bool(payload.get("full_access") or payload.get("yolo") or payload.get("force"))
    if full_access and not bool(payload.get("explicit_full_access")):
        raise ExecutorError("full_access/yolo/force requires explicit_full_access=true")
    if mode == "real" and not get_executor(executor_id)["installed"]:
        raise ExecutorError(f"executor unavailable: {executor_id}")

    run_id = f"run_{int(time.time())}_{uuid4().hex[:8]}"
    workdir, project_id, task_id = _resolve_workdir(payload, root_path)
    prompt_path = _write_prompt(payload, root_path, run_id)
    report_path = _default_report_path(payload, workdir, root_path, run_id)
    log_path = _artifacts_dir(root_path, run_id) / "run.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    definition = EXECUTORS[executor_id]
    command = _build_command(executor_id, prompt_path, explicit_full_access=full_access)
    command_hint = " ".join([command[0], *command[1:]])
    run = ExecutorRun(
        run_id=run_id,
        project_id=project_id,
        task_id=task_id,
        executor=executor_id,
        workdir=workdir.as_posix(),
        prompt_path=prompt_path.as_posix(),
        report_path=report_path.as_posix(),
        log_path=log_path.as_posix(),
        mode=mode,
        command_hint=command_hint,
        explicit_full_access=full_access,
        notes=["real execution requires CHATBOARD_EXECUTOR_API_KEY"] if mode != "real" else [],
    )

    if mode == "mock":
        log_path.write_text(f"[{utc_now()}] mock run accepted for {executor_id}\n", encoding="utf-8")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(f"# Mock Executor Report\n\n- run_id: {run_id}\n- executor: {executor_id}\n", encoding="utf-8")
        run.backend_session_id = f"mock-{run_id}"
        run.status = "done"
        run.completed_at = utc_now()
        run.updated_at = run.completed_at
    elif mode == "real":
        log_file = log_path.open("ab")
        process = subprocess.Popen(command, cwd=workdir, stdout=log_file, stderr=subprocess.STDOUT, start_new_session=True)
        log_file.close()
        run.os_pid = process.pid
        run.process_session_id = str(process.pid)
        run.status = "running"
        run.updated_at = utc_now()
    else:
        log_path.write_text(f"[{utc_now()}] dry-run prepared command only; no executor process started\n", encoding="utf-8")
        run.status = "queued"

    if definition.resume_template and run.backend_session_id:
        run.resume_command_hint = definition.resume_template.format(backend_session_id=run.backend_session_id)
    elif definition.resume_template:
        run.resume_command_hint = definition.resume_template.replace("{backend_session_id}", f"<{definition.resume_id_kind or 'session_id'}>")

    runs = _load_runs(root_path)
    runs.append(run)
    _save_runs(runs, root_path)
    return with_public_links(run, root_path).to_dict()


def run_log(run_id: str, root: str | Path | None = None, *, tail: int = 12000) -> dict[str, Any]:
    run = get_run(run_id, root)
    path = Path(run["log_path"])
    text = ""
    if path.exists():
        text = path.read_text(encoding="utf-8", errors="replace")
    if tail > 0 and len(text) > tail:
        text = text[-tail:]
    return {"run_id": run_id, "log": text, "truncated": bool(tail > 0 and path.exists() and path.stat().st_size > tail), "log_path": path.as_posix()}


def stop_run(run_id: str, root: str | Path | None = None, *, can_execute: bool = False) -> dict[str, Any]:
    if not can_execute:
        raise PermissionError("executor permission required to stop runs")
    run = _find_run_obj(run_id, root)
    if run.status == "running" and run.os_pid:
        try:
            os.killpg(run.os_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        except PermissionError:
            raise
    run.status = "stopped"
    run.completed_at = utc_now()
    run.updated_at = run.completed_at
    return with_public_links(_replace_run(run, root), root).to_dict()


def resume_run(run_id: str, payload: dict[str, Any], root: str | Path | None = None, *, can_execute: bool = False) -> dict[str, Any]:
    if not can_execute:
        raise PermissionError("executor permission required to resume runs")
    run = _find_run_obj(run_id, root)
    run.status = "queued"
    run.updated_at = utc_now()
    run.notes.append("resume requested; backend session resume process is not yet attached")
    if payload.get("backend_session_id"):
        run.backend_session_id = str(payload["backend_session_id"])
    definition = EXECUTORS.get(run.executor)
    if definition and definition.resume_template and run.backend_session_id:
        run.resume_command_hint = definition.resume_template.format(backend_session_id=run.backend_session_id)
    return with_public_links(_replace_run(run, root), root).to_dict()


def collect_run(run_id: str, root: str | Path | None = None, *, can_execute: bool = False) -> dict[str, Any]:
    if not can_execute:
        raise PermissionError("executor permission required to collect runs")
    run = _find_run_obj(run_id, root)
    report = Path(run.report_path)
    if not report.exists():
        report.parent.mkdir(parents=True, exist_ok=True)
        log = run_log(run_id, root).get("log", "")
        report.write_text(f"# Executor Run {run_id}\n\n```text\n{log}\n```\n", encoding="utf-8")
    run.status = "needs_review" if run.status in {"done", "failed", "stopped"} else run.status
    run.updated_at = utc_now()
    updated = _replace_run(run, root)
    return {
        "run": with_public_links(updated, root).to_dict(),
        "report_path": report.as_posix(),
        "workspace_report_path": as_workspace_relative(report, resolve_workspace_root(root)),
    }
