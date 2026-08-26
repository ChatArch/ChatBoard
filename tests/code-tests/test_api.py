from datetime import datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient

import chatboard.api as api_module
from chatboard.api import _cors_origins, _is_public_auth_path, app
from chatboard.services.backends import BackendProfile, backend_api_url, load_backend_profiles, save_backend_profiles
from chatboard.services import executors as executor_service


def _project(root: Path) -> None:
    path = root / "projects/chatarch/07-07-demo"
    path.mkdir(parents=True)
    (path / "PRD.md").write_text("# Demo API\n\nAPI task.\n", encoding="utf-8")
    (path / "progress.md").write_text("# Progress\n", encoding="utf-8")


def _write_card(path: Path, *, title: str, area: str, stage: str) -> None:
    path.mkdir(parents=True)
    card_id = "-".join(path.parts[-3:]).replace("_", "-")
    (path / "card.md").write_text(
        f"""---
schema: chatboard.project_card.v1
id: {card_id}
title: {title}
area: {area}
stage: {stage}
date: 2026-08-05
---

# 摘要

{title}
""",
        encoding="utf-8",
    )
    (path / "PRD.md").write_text(f"# {title}\n\nTask.\n", encoding="utf-8")
    (path / "progress.md").write_text("# Progress\n", encoding="utf-8")


def test_health_endpoint():
    client = TestClient(app)

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_catalog_and_detail_endpoints(tmp_path):
    _project(tmp_path)
    client = TestClient(app)

    catalog = client.get("/api/catalog", params={"root": str(tmp_path), "ensure": "true"})

    assert catalog.status_code == 200
    assert catalog.json()["total_cards"] == 1
    project_column = next(column for column in catalog.json()["columns"] if column["key"] == "project")
    first_card = project_column["cards"][0]
    assert first_card["description"] == "API task."
    assert first_card["summary"] == "API task."
    assert first_card["date"] == f"{datetime.now().year}-07-07"

    detail = client.get("/api/cards/projects-chatarch-07-07-demo", params={"root": str(tmp_path)})

    assert detail.status_code == 200
    assert detail.json()["card"]["title"] == "Demo API"
    assert detail.json()["card"]["description"] == "API task."
    assert detail.json()["card"]["summary"] == "API task."
    assert detail.json()["card"]["date"] == f"{datetime.now().year}-07-07"
    assert {section["key"] for section in detail.json()["sections"]} >= {"overview", "files", "prd", "progress"}

    files = client.get("/api/cards/projects-chatarch-07-07-demo/files", params={"root": str(tmp_path)})
    assert files.status_code == 200
    assert any(item["path"] == "PRD.md" for item in files.json()["files"])

    content = client.get(
        "/api/cards/projects-chatarch-07-07-demo/files/content",
        params={"root": str(tmp_path), "path": "PRD.md"},
    )
    assert content.status_code == 200
    assert "# Demo API" in content.json()["content"]

    nested = tmp_path / "projects/chatarch/07-07-demo/reports"
    nested.mkdir()
    (nested / "note.md").write_text("# Note\n", encoding="utf-8")
    (tmp_path / "projects/chatarch/07-07-demo/playground").mkdir()
    (tmp_path / "projects/chatarch/07-07-demo/scripts").mkdir()
    (tmp_path / "projects/chatarch/07-07-demo/notes").mkdir()
    (tmp_path / "projects/chatarch/07-07-demo/.venv").mkdir()
    (tmp_path / "projects/chatarch/07-07-demo/card.json").write_text("{}\n", encoding="utf-8")
    listing = client.get(
        "/api/cards/projects-chatarch-07-07-demo/files/list",
        params={"root": str(tmp_path)},
    )
    assert listing.status_code == 200
    assert [item["name"] for item in listing.json()["children"]] == [
        "playground",
        "reports",
        "scripts",
        "card.md",
        "PRD.md",
        "progress.md",
    ]
    show_all = client.get(
        "/api/cards/projects-chatarch-07-07-demo/files/list",
        params={"root": str(tmp_path), "include_hidden": "true"},
    )
    assert show_all.status_code == 200
    show_all_names = [item["name"] for item in show_all.json()["children"]]
    assert "notes" in show_all_names
    assert ".venv" not in show_all_names
    assert "card.json" not in show_all_names
    reports = client.get(
        "/api/cards/projects-chatarch-07-07-demo/files/list",
        params={"root": str(tmp_path), "path": "reports"},
    )
    assert reports.status_code == 200
    assert reports.json()["children"][0]["path"] == "reports/note.md"


def test_ensure_endpoint_rejects_missing_project_directory(tmp_path):
    client = TestClient(app)
    missing = tmp_path / "projects/missing"

    response = client.post(
        "/api/cards/ensure",
        params={"root": str(tmp_path)},
        json={"project_path": str(missing)},
    )

    assert response.status_code == 404
    assert not missing.exists()


def test_pages_api_and_static_tabs_keep_projects_and_add_tasks(tmp_path):
    client = TestClient(app)

    pages = client.get("/api/pages", params={"root": str(tmp_path)})
    assert pages.status_code == 200
    assert [(page["key"], page["title"]) for page in pages.json()["pages"]] == [
        ("projects", "Projects"),
        ("tasks", "Tasks"),
        ("executors", "Executors"),
    ]

    index = client.get("/")
    assert index.status_code == 200
    assert 'data-page-tab="projects"' in index.text
    assert 'data-page-tab="tasks"' in index.text
    assert 'data-page-tab="executors"' in index.text
    assert 'id="settingsBtn"' in index.text
    assert 'id="settingsModal"' in index.text
    assert '/assets/styles.css?v=settings-assets-review-2' in index.text
    assert '/assets/app.js?v=executor-layer-1' in index.text
    assert 'settings-build-note' in index.text
    assert 'href="https://arch.gh.wzhecnu.cn/ChatBoard/"' in index.text
    assert 'href="https://github.com/ChatArch/ChatBoard"' in index.text
    assert 'data-page-tab="machines"' not in index.text


def test_index_injects_default_backend_from_environment(monkeypatch):
    monkeypatch.setenv("CHATBOARD_DEFAULT_BACKEND_NAME", "mini-default")
    monkeypatch.setenv("CHATBOARD_DEFAULT_BACKEND_URL", "172.25.236.90:8010")
    monkeypatch.setenv("CHATBOARD_DEFAULT_BACKEND_TOKEN", "test-token")
    client = TestClient(app)

    index = client.get("/")

    assert index.status_code == 200
    assert 'name="chatboard-default-backend-name" content="mini-default"' in index.text
    assert 'name="chatboard-default-backend-url" content="172.25.236.90:8010"' in index.text
    assert "test-token" not in index.text
    assert "chatboard-default-backend-token" not in index.text


def test_backend_profiles_are_redacted_and_default_is_unique(tmp_path, monkeypatch):
    registry = tmp_path / "backends.json"
    monkeypatch.setenv("CHATBOARD_BACKENDS_FILE", str(registry))
    save_backend_profiles(
        [
            BackendProfile(id="default", name="Mini", url="172.25.236.90:8010", api_key="secret-a", is_default=True),
            BackendProfile(id="other", name="Other", url="https://example.test/api", api_key="secret-b"),
        ]
    )
    client = TestClient(app)

    profiles = client.get("/api/backend-profiles")

    assert profiles.status_code == 200
    data = profiles.json()["profiles"]
    assert [profile["is_default"] for profile in data].count(True) == 1
    assert data[0]["has_token"] is True
    assert "secret-a" not in profiles.text

    allowed = client.post("/api/backend-profiles/other/default")
    assert allowed.status_code == 200
    assert allowed.json()["profile"]["is_default"] is True
    assert [profile.id for profile in load_backend_profiles() if profile.is_default] == ["other"]


def test_backend_url_builder_accepts_ip_port_and_api_prefix():
    assert backend_api_url("172.25.236.90:8010", "/api/health") == "http://172.25.236.90:8010/api/health"
    assert backend_api_url("https://example.test/api", "/api/health") == "https://example.test/api/health"


def test_backend_proxy_uses_backend_token_without_exposing_secret(tmp_path, monkeypatch):
    registry = tmp_path / "backends.json"
    monkeypatch.setenv("CHATBOARD_BACKENDS_FILE", str(registry))
    save_backend_profiles(
        [BackendProfile(id="default", name="Mini", url="https://backend.example/api", api_key="backend-secret", is_default=True)]
    )
    captured = {}

    class FakeResponse:
        status = 200
        headers = {"content-type": "application/json"}

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return b'{"ok": true}'

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["token"] = request.get_header("X-chatboard-token")
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr(api_module.urllib_request, "urlopen", fake_urlopen)
    client = TestClient(app)

    proxied = client.get("/api/backends/default/api/health", params={"check": "1"})

    assert proxied.status_code == 200
    assert proxied.json()["ok"] is True
    assert captured == {
        "url": "https://backend.example/api/health?check=1",
        "token": "backend-secret",
        "timeout": 8,
    }


def test_board_static_assets_support_resizable_columns():
    app_js = Path("src/chatboard/web_static/assets/app.js").read_text(encoding="utf-8")
    styles = Path("src/chatboard/web_static/assets/styles.css").read_text(encoding="utf-8")

    assert "chatboard.columnWidths.v1" in app_js
    assert "column-resize-handle" in app_js
    assert "data-resize-index" in app_js
    assert "gridTemplateColumns" in app_js
    assert "double-click to reset widths" in app_js
    assert "thoughts: hasCards('thoughts') ? 1.1 : 0.55" in app_js
    assert "project: hasCards('project') ? 2.5 : 1" in app_js
    assert ".column-resize-handle" in styles
    assert "body.resizing-columns" in styles
    assert ".board.mostly-project { grid-template-columns" not in styles


def test_board_static_assets_support_backend_switching():
    app_js = Path("src/chatboard/web_static/assets/app.js").read_text(encoding="utf-8")
    styles = Path("src/chatboard/web_static/assets/styles.css").read_text(encoding="utf-8")

    assert "chatboard.backends.v1" in app_js
    assert "chatboard.activeBackend.v1" in app_js
    assert "DEFAULT_BACKEND_ID = 'default'" in app_js
    assert "loadBackendProfiles" in app_js
    assert "X-ChatBoard-Registry-Token" not in app_js
    assert "registryToken" not in app_js
    assert "/api/backends/" in app_js
    assert "localStorage.setItem(BACKEND_STORAGE_KEY" not in app_js
    assert "X-ChatBoard-Token" not in app_js
    assert "Token configured; leave blank to keep it" in app_js
    index_html = Path("src/chatboard/web_static/index.html").read_text(encoding="utf-8")
    assert "Registry token" not in index_html
    assert "One-way auth" in index_html
    assert "Use for session" in index_html
    assert ".resource-nav a" in styles
    assert "text-decoration: none !important" in styles
    assert ".settings-panel" in styles
    assert ".settings-build-note" in styles
    assert ".backend-active-summary" in styles


def test_board_static_assets_show_executor_visibility():
    app_js = Path("src/chatboard/web_static/assets/app.js").read_text(encoding="utf-8")
    styles = Path("src/chatboard/web_static/assets/styles.css").read_text(encoding="utf-8")
    index_html = Path("src/chatboard/web_static/index.html").read_text(encoding="utf-8")

    assert 'data-page-tab="executors"' in index_html
    assert "loadExecutors" in app_js
    assert "/api/executors" in app_js
    assert "/api/runs" in app_js
    assert "executor_runs" in app_js
    assert "public_links" in app_js
    assert "Run Link" in app_js
    assert ".executor-board" in styles
    assert ".run-row" in styles


def test_board_static_assets_support_task_detail_deep_links():
    app_js = Path("src/chatboard/web_static/assets/app.js").read_text(encoding="utf-8")

    assert "parseBoardRoute" in app_js
    assert "#/tasks/" in app_js
    assert "taskDetailHash" in app_js
    assert "hashchange" in app_js
    assert "loadDetail(route.cardId, { preserveHash: true })" in app_js


def test_cors_origin_parser_trims_comma_separated_origins():
    assert _cors_origins(" https://front.example , https://board.example ,, ") == [
        "https://front.example",
        "https://board.example",
    ]


def test_public_auth_paths_include_static_assets():
    assert _is_public_auth_path("/assets/app.js")
    assert _is_public_auth_path("/assets/styles.css")
    assert _is_public_auth_path("/login")
    assert not _is_public_auth_path("/api/catalog")


def test_task_management_api_crud_status_and_transitions_use_tasks_tab(tmp_path):
    client = TestClient(app)

    created = client.post(
        "/api/tasks",
        params={"root": str(tmp_path)},
        json={
            "title": "Board task API",
            "description": "Create from REST and manage status.",
            "topic": "chatarch",
            "slug": "08-12-board-task-api",
            "source_platform": "feishu",
            "source_url": "https://example.feishu.cn/thread/api",
            "accept_mode": "accept",
            "side_effect_level": "local_write",
            "next_action": "Accept the task.",
            "tags": ["board", "api"],
        },
    )
    assert created.status_code == 200
    card = created.json()["card"]
    assert card["id"] == "projects-chatarch-08-12-board-task-api"
    assert card["type"] == "task"
    assert card["stage"] == "inbox"
    assert card["source"] == {"platform": "feishu", "url": "https://example.feishu.cn/thread/api"}
    assert card["accept_mode"] == "accept"
    assert card["side_effect_level"] == "local_write"
    assert (tmp_path / "projects/chatarch/08-12-board-task-api/PRD.md").exists()
    assert created.json()["task_link"]["api_path"] == f"/api/tasks/{card['id']}"
    assert created.json()["task_link"]["ui_path"] == f"/#/tasks/{card['id']}"
    assert created.json()["task_link"]["public_url"].endswith(f"/#/tasks/{card['id']}")
    assert created.json()["prd_link"]["api_path"] == f"/api/cards/{card['id']}/files/content?path=PRD.md"
    assert created.json()["prd_link"]["public_url"].endswith(f"/api/cards/{card['id']}/files/content?path=PRD.md")
    assert card["public_links"]["task_link"] == created.json()["task_link"]
    assert card["public_links"]["prd_link"] == created.json()["prd_link"]

    task_detail = client.get(f"/api/tasks/{card['id']}", params={"root": str(tmp_path)})
    assert task_detail.status_code == 200
    assert task_detail.json()["card"]["id"] == card["id"]
    assert task_detail.json()["task_link"] == created.json()["task_link"]
    assert task_detail.json()["prd_link"] == created.json()["prd_link"]

    card_detail = client.get(f"/api/cards/{card['id']}", params={"root": str(tmp_path)})
    assert card_detail.status_code == 200
    assert card_detail.json()["task_link"] == created.json()["task_link"]
    assert card_detail.json()["prd_link"] == created.json()["prd_link"]

    project_catalog = client.get("/api/catalog", params={"root": str(tmp_path)})
    assert project_catalog.status_code == 200
    assert project_catalog.json()["total_cards"] == 0

    tasks = client.get("/api/tasks", params={"root": str(tmp_path)})
    assert tasks.status_code == 200
    assert [column["key"] for column in tasks.json()["columns"]] == ["inbox", "ready", "running", "blocked", "review", "done"]
    inbox = next(column for column in tasks.json()["columns"] if column["key"] == "inbox")
    assert [item["id"] for item in inbox["cards"]] == [card["id"]]

    status = client.get(f"/api/tasks/{card['id']}/status", params={"root": str(tmp_path)})
    assert status.status_code == 200
    assert status.json()["stage"] == "inbox"
    assert "accept" in status.json()["available_transitions"]
    assert status.json()["task_link"] == created.json()["task_link"]
    assert status.json()["prd_link"] == created.json()["prd_link"]

    patched = client.patch(
        f"/api/tasks/{card['id']}",
        params={"root": str(tmp_path)},
        json={"next_action": "Worker can start.", "accept_mode": "auto", "side_effect_level": "read_only"},
    )
    assert patched.status_code == 200
    assert patched.json()["next_action"] == "Worker can start."
    assert patched.json()["accept_mode"] == "auto"

    accepted = client.post(
        f"/api/tasks/{card['id']}/transitions",
        params={"root": str(tmp_path)},
        json={"transition": "accept", "reason": "ready"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["card"]["stage"] == "ready"

    moved = client.post(
        f"/api/tasks/{card['id']}/transitions",
        params={"root": str(tmp_path)},
        json={"transition": "block", "reason": "needs examples", "need": "choose three cards"},
    )
    assert moved.status_code == 200
    assert moved.json()["card"]["stage"] == "blocked"
    assert moved.json()["card"]["next_action"] == "choose three cards"

    deleted = client.request(
        "DELETE",
        f"/api/tasks/{card['id']}",
        params={"root": str(tmp_path)},
        json={"reason": "example cleanup"},
    )
    assert deleted.status_code == 200
    assert deleted.json()["card"]["area"] == "discard"
    assert deleted.json()["card"]["archive"]["reason"] == "example cleanup"

    after_delete = client.get("/api/tasks", params={"root": str(tmp_path)})
    assert after_delete.status_code == 200
    assert after_delete.json()["total_cards"] == 0

    deleted_status = client.get(f"/api/tasks/{card['id']}/status", params={"root": str(tmp_path)})
    assert deleted_status.status_code == 404


def test_task_api_does_not_mutate_legacy_project_cards(tmp_path):
    client = TestClient(app)
    _write_card(tmp_path / "projects/chatarch/08-12-legacy", title="Legacy", area="projects", stage="development")
    card_id = "projects-chatarch-08-12-legacy"

    patched = client.patch(
        f"/api/tasks/{card_id}",
        params={"root": str(tmp_path)},
        json={"next_action": "should not land"},
    )
    transitioned = client.post(
        f"/api/tasks/{card_id}/transitions",
        params={"root": str(tmp_path)},
        json={"transition": "accept", "reason": "should not land"},
    )
    deleted = client.request(
        "DELETE",
        f"/api/tasks/{card_id}",
        params={"root": str(tmp_path)},
        json={"reason": "should not land"},
    )

    assert patched.status_code == 404
    assert transitioned.status_code == 404
    assert deleted.status_code == 404

    detail = client.get(f"/api/cards/{card_id}", params={"root": str(tmp_path)})
    assert detail.status_code == 200
    card = detail.json()["card"]
    assert card["stage"] == "development"
    assert card["area"] == "projects"


def test_executor_discovery_and_mock_run_api(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_HOME", str(tmp_path / ".chatarch" / "chatboard"))
    client = TestClient(app)

    executors = client.get("/api/executors")

    assert executors.status_code == 200
    executor_ids = {item["id"] for item in executors.json()["executors"]}
    assert {"codex", "cursor-agent", "opencode"} <= executor_ids
    assert executors.json()["permissions"]["safe_modes_without_executor_token"] == ["dry-run", "mock"]
    assert "CHATBOARD_EXECUTOR_API_KEY" in executors.json()["permissions"]["real_execution_requires"]

    created = client.post(
        "/api/runs",
        params={"root": str(tmp_path)},
        json={"executor": "codex", "mode": "mock", "prompt": "Mock executor smoke", "workdir": "."},
    )

    assert created.status_code == 200
    run = created.json()["run"]
    assert run["run_id"].startswith("run_")
    assert run["executor"] == "codex"
    assert run["status"] == "done"
    assert run["backend_session_id"].startswith("mock-run_")
    assert run["process_session_id"] is None
    assert run["os_pid"] is None
    assert run["prompt_path"].endswith("/prompt.md")
    assert run["report_path"].endswith("/report.md")
    assert run["resume_command_hint"]
    assert run["public_links"]["run"]["public_url"].endswith(f"/api/runs/{run['run_id']}")
    assert run["public_links"]["log"]["public_url"].endswith(f"/api/runs/{run['run_id']}/log")

    listing = client.get("/api/runs", params={"root": str(tmp_path)})
    assert listing.status_code == 200
    assert [item["run_id"] for item in listing.json()["runs"]] == [run["run_id"]]

    log = client.get(f"/api/runs/{run['run_id']}/log", params={"root": str(tmp_path)})
    assert log.status_code == 200
    assert "mock run accepted" in log.json()["log"]


def test_path_resolver_uses_card_file_api_when_path_is_card_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_SERVICE_URL", "https://board.public.example/")
    _write_card(tmp_path / "projects/chatarch/08-26-link-card", title="Link Card", area="projects", stage="development")
    client = TestClient(app)
    card_id = "projects-chatarch-08-26-link-card"

    resolved = client.get(
        "/api/resolve-path",
        params={"root": str(tmp_path), "card_id": card_id, "path": str(tmp_path / "projects/chatarch/08-26-link-card/PRD.md")},
    )

    assert resolved.status_code == 200
    link = resolved.json()["link"]
    assert link["workspace_path"] == "projects/chatarch/08-26-link-card/PRD.md"
    assert link["kind"] == "chatboard.card_file"
    assert link["card_id"] == card_id
    assert link["path"] == "PRD.md"
    assert link["api_path"] == f"/api/cards/{card_id}/files/content?path=PRD.md"
    assert link["public_url"] == f"https://board.public.example/api/cards/{card_id}/files/content?path=PRD.md"
    assert link["resolvable"] is True


def test_executor_real_and_control_routes_require_executor_permission(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_HOME", str(tmp_path / ".chatarch" / "chatboard"))
    client = TestClient(app)

    denied_real = client.post(
        "/api/runs",
        params={"root": str(tmp_path)},
        json={"executor": "codex", "mode": "real", "prompt": "No real process should start", "workdir": "."},
    )
    assert denied_real.status_code == 403

    dry_run = client.post(
        "/api/runs",
        params={"root": str(tmp_path)},
        json={"executor": "codex", "mode": "dry-run", "prompt": "Plan only", "workdir": "."},
    )
    assert dry_run.status_code == 200
    run_id = dry_run.json()["run"]["run_id"]

    denied_collect = client.post(f"/api/runs/{run_id}/collect", params={"root": str(tmp_path)})
    assert denied_collect.status_code == 403

    monkeypatch.setenv("CHATBOARD_EXECUTOR_API_KEY", "executor-secret")
    allowed_collect = client.post(
        f"/api/runs/{run_id}/collect",
        params={"root": str(tmp_path)},
        headers={"X-ChatBoard-Executor-Token": "executor-secret"},
    )
    assert allowed_collect.status_code == 200
    assert allowed_collect.json()["run"]["run_id"] == run_id

    yolo_without_ack = client.post(
        "/api/runs",
        params={"root": str(tmp_path)},
        headers={"X-ChatBoard-Executor-Token": "executor-secret"},
        json={
            "executor": "codex",
            "mode": "dry-run",
            "prompt": "Explicit full access test",
            "workdir": ".",
            "full_access": True,
        },
    )
    assert yolo_without_ack.status_code == 400
    assert "explicit_full_access" in yolo_without_ack.text


def test_real_executor_commands_use_supported_prompt_handoff(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("Reply exactly OK.\n", encoding="utf-8")

    for executor_id in ["codex", "cursor-agent", "opencode"]:
        command = executor_service._build_command(executor_id, prompt)
        assert command[0:2] == ["sh", "-c"]
        assert prompt.as_posix() in command
        assert "--prompt-file" not in command

    codex = executor_service._build_command("codex", prompt)
    assert "codex exec" in codex[2]
    assert "< \"$1\"" in codex[2]
    assert codex[-1] == "workspace-write"
    assert executor_service._build_command("codex", prompt, explicit_full_access=True)[-1] == "danger-full-access"

    cursor = executor_service._build_command("cursor-agent", prompt)
    assert "cursor-agent --print" in cursor[2]
    assert "--mode ask" in cursor[2]
    assert "--force" in cursor[2]
    assert cursor[-1] == "ask"
    assert executor_service._build_command("cursor-agent", prompt, explicit_full_access=True)[-1] == "full"

    opencode = executor_service._build_command("opencode", prompt)
    assert "opencode run" in opencode[2]
    assert "--file \"$1\"" in opencode[2]
    assert "--auto" not in opencode[2]
    assert "--auto" in executor_service._build_command("opencode", prompt, explicit_full_access=True)[2]


def test_card_detail_includes_related_executor_runs(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_HOME", str(tmp_path / ".chatarch" / "chatboard"))
    _write_card(tmp_path / "projects/chatarch/08-26-executor-card", title="Executor Card", area="projects", stage="development")
    client = TestClient(app)
    card_id = "projects-chatarch-08-26-executor-card"

    created = client.post(
        "/api/runs",
        params={"root": str(tmp_path)},
        json={"executor": "codex", "mode": "mock", "prompt": "Attach to project", "project_id": card_id},
    )
    assert created.status_code == 200

    detail = client.get(f"/api/cards/{card_id}", params={"root": str(tmp_path)})

    assert detail.status_code == 200
    runs_section = next(section for section in detail.json()["sections"] if section["key"] == "runs")
    assert runs_section["kind"] == "executor_runs"
    assert runs_section["data"][0]["run_id"] == created.json()["run"]["run_id"]


def test_catalog_uses_lifecycle_columns_and_hides_discard(tmp_path):
    _write_card(tmp_path / "discussion/08-05-idea", title="Idea", area="discussion", stage="review")
    _write_card(tmp_path / "projects/chatarch/08-05-active", title="Active", area="projects", stage="development")
    _write_card(tmp_path / "projects/chatarch/08-05-done", title="Done", area="projects", stage="complete")
    _write_card(tmp_path / "archive/2026-08-01/chatarch/07-01-old", title="Old", area="archive", stage="archived")
    _write_card(tmp_path / "discard/chatarch/07-01-hidden", title="Hidden", area="discard", stage="discarded")
    client = TestClient(app)

    response = client.get("/api/catalog", params={"root": str(tmp_path)})

    assert response.status_code == 200
    payload = response.json()
    assert [(column["key"], column["title"]) for column in payload["columns"]] == [
        ("thoughts", "想法"),
        ("project", "进行中"),
        ("archiving", "归档中"),
        ("archive", "已归档"),
    ]
    cards_by_column = {column["key"]: [card["title"] for card in column["cards"]] for column in payload["columns"]}
    assert cards_by_column == {
        "thoughts": ["Idea"],
        "project": ["Active"],
        "archiving": ["Done"],
        "archive": ["Old"],
    }
    assert payload["total_cards"] == 4
    assert "discard" not in {column["key"] for column in payload["columns"]}
    assert "Hidden" not in sum(cards_by_column.values(), [])


def test_lifecycle_column_endpoint_paginates_and_rejects_discard(tmp_path):
    for index in range(3):
        path = tmp_path / f"projects/chatarch/07-07-demo-{index}"
        path.mkdir(parents=True)
        (path / "PRD.md").write_text(f"# Demo {index}\n\nAPI task.\n", encoding="utf-8")
        (path / "progress.md").write_text("# Progress\n", encoding="utf-8")
    _write_card(tmp_path / "discussion/08-05-idea", title="Idea", area="discussion", stage="review")
    _write_card(tmp_path / "projects/chatarch/08-05-done", title="Done", area="projects", stage="archive_ready")
    client = TestClient(app)

    first = client.get("/api/columns/project", params={"root": str(tmp_path), "limit": 2})

    assert first.status_code == 200
    payload = first.json()
    assert payload["key"] == "project"
    assert payload["title"] == "进行中"
    assert len(payload["cards"]) == 2
    assert payload["has_more"] is True
    assert payload["next_offset"] == 2

    second = client.get("/api/columns/project", params={"root": str(tmp_path), "limit": 2, "offset": payload["next_offset"]})
    assert second.status_code == 200
    assert len(second.json()["cards"]) == 1
    assert second.json()["has_more"] is False

    thoughts = client.get("/api/columns/thoughts", params={"root": str(tmp_path)})
    archiving = client.get("/api/columns/archiving", params={"root": str(tmp_path)})
    discard = client.get("/api/columns/discard", params={"root": str(tmp_path)})

    assert thoughts.status_code == 200
    assert thoughts.json()["title"] == "想法"
    assert [card["title"] for card in thoughts.json()["cards"]] == ["Idea"]
    assert archiving.status_code == 200
    assert archiving.json()["title"] == "归档中"
    assert [card["title"] for card in archiving.json()["cards"]] == ["Done"]
    assert discard.status_code == 404


def test_index_serves_static_page_without_machines_tab():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "ChatBoard" in response.text
    assert 'data-page-tab="machines"' not in response.text
    assert ">Machines<" not in response.text


def test_auth_gate_requires_login_when_password_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_USERNAME", "admin")
    monkeypatch.setenv("CHATBOARD_PASSWORD", "secret")
    _project(tmp_path)
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert client.get("/api/auth").json() == {
        "enabled": True,
        "authenticated": False,
        "username_required": True,
        "api_token_enabled": False,
    }

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 303
    assert root.headers["location"] == "/login"

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "ChatBoard Login" in login_page.text
    assert 'href="https://arch.gh.wzhecnu.cn/ChatBoard/"' in login_page.text
    assert 'href="https://github.com/ChatArch/ChatBoard"' in login_page.text
    assert 'type="text"' in login_page.text
    assert 'type="email"' not in login_page.text

    styles = client.get("/assets/styles.css", follow_redirects=False)
    assert styles.status_code == 200
    assert "text/css" in styles.headers["content-type"]
    assert ".resource-link" in styles.text

    script = client.get("/assets/app.js", follow_redirects=False)
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]
    assert "settingsBtn" in script.text

    blocked = client.get("/api/catalog", params={"root": str(tmp_path)})
    assert blocked.status_code == 401

    bad_login = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    bad_user = client.post("/api/login", json={"username": "other@example.com", "password": "secret"})
    assert bad_user.status_code == 401

    good_login = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert good_login.status_code == 200
    assert "chatboard_session" in client.cookies
    assert client.get("/api/auth").json() == {
        "enabled": True,
        "authenticated": True,
        "username_required": True,
        "api_token_enabled": False,
    }

    catalog = client.get("/api/catalog", params={"root": str(tmp_path)})
    assert catalog.status_code == 200
    assert catalog.json()["total_cards"] == 1

    logout = client.post("/api/logout")
    assert logout.status_code == 200
    assert "chatboard_session" not in client.cookies
    assert client.get("/api/catalog", params={"root": str(tmp_path)}).status_code == 401


def test_auth_gate_supports_password_only(monkeypatch):
    monkeypatch.delenv("CHATBOARD_USERNAME", raising=False)
    monkeypatch.setenv("CHATBOARD_PASSWORD", "secret")
    client = TestClient(app)

    assert client.get("/api/auth").json()["username_required"] is False
    response = client.post("/api/login", json={"password": "secret"})

    assert response.status_code == 200
    assert "chatboard_session" in client.cookies


def test_auth_gate_accepts_api_token_without_login_cookie(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_USERNAME", "admin")
    monkeypatch.setenv("CHATBOARD_PASSWORD", "secret")
    monkeypatch.setenv("CHATBOARD_API_KEY", "opaque-api-token")
    _project(tmp_path)
    client = TestClient(app)

    blocked = client.get("/api/catalog", params={"root": str(tmp_path)})
    bearer = client.get(
        "/api/catalog",
        params={"root": str(tmp_path)},
        headers={"Authorization": "Bearer opaque-api-token"},
    )
    header = client.get(
        "/api/catalog",
        params={"root": str(tmp_path)},
        headers={"X-ChatBoard-Token": "opaque-api-token"},
    )
    wrong = client.get(
        "/api/catalog",
        params={"root": str(tmp_path)},
        headers={"Authorization": "Bearer wrong"},
    )

    assert blocked.status_code == 401
    assert bearer.status_code == 200
    assert bearer.json()["total_cards"] == 1
    assert header.status_code == 200
    assert wrong.status_code == 401


def test_auth_status_reports_token_without_exposing_secret(monkeypatch):
    monkeypatch.setenv("CHATBOARD_PASSWORD", "secret")
    monkeypatch.setenv("CHATBOARD_API_KEY", "opaque-api-token")
    client = TestClient(app)

    status = client.get("/api/auth")

    assert status.status_code == 200
    assert status.json() == {
        "enabled": True,
        "authenticated": False,
        "username_required": False,
        "api_token_enabled": True,
    }
    assert "opaque-api-token" not in status.text


def test_api_token_only_gates_workspace_api_without_web_login(tmp_path, monkeypatch):
    monkeypatch.delenv("CHATBOARD_USERNAME", raising=False)
    monkeypatch.delenv("CHATBOARD_PASSWORD", raising=False)
    monkeypatch.setenv("CHATBOARD_API_KEY", "opaque-api-token")
    _project(tmp_path)
    client = TestClient(app)

    root = client.get("/", follow_redirects=False)
    blocked = client.get("/api/catalog", params={"root": str(tmp_path)})
    allowed = client.get(
        "/api/catalog",
        params={"root": str(tmp_path)},
        headers={"Authorization": "Bearer opaque-api-token"},
    )

    assert root.status_code == 200
    assert blocked.status_code == 401
    assert allowed.status_code == 200
    assert allowed.json()["total_cards"] == 1


def test_machines_endpoints_are_removed(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_ENABLE_MACHINES", "true")
    registry = tmp_path / ".chatboard" / "machines.json"
    registry.parent.mkdir()
    registry.write_text(
        json.dumps({"schema": "chatboard.machines.v1", "machines": [{"id": "demo", "title": "Demo"}]}),
        encoding="utf-8",
    )
    client = TestClient(app)

    listing = client.get("/api/machines", params={"root": str(tmp_path)})
    detail = client.get("/api/machines/demo", params={"root": str(tmp_path)})

    assert listing.status_code == 404
    assert detail.status_code == 404
