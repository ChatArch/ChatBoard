from datetime import datetime
import json
from pathlib import Path

from fastapi.testclient import TestClient

from chatboard.api import app


def _project(root: Path) -> None:
    path = root / "projects/chatarch/07-07-demo"
    path.mkdir(parents=True)
    (path / "PRD.md").write_text("# Demo API\n\nAPI task.\n", encoding="utf-8")
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
    first_card = catalog.json()["columns"][0]["cards"][0]
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


def test_column_endpoint_paginates_cards(tmp_path):
    for index in range(3):
        path = tmp_path / f"projects/chatarch/07-07-demo-{index}"
        path.mkdir(parents=True)
        (path / "PRD.md").write_text(f"# Demo {index}\n\nAPI task.\n", encoding="utf-8")
        (path / "progress.md").write_text("# Progress\n", encoding="utf-8")
    client = TestClient(app)

    first = client.get("/api/columns/project", params={"root": str(tmp_path), "limit": 2})

    assert first.status_code == 200
    payload = first.json()
    assert payload["key"] == "project"
    assert len(payload["cards"]) == 2
    assert payload["has_more"] is True
    assert payload["next_offset"] == 2

    second = client.get("/api/columns/project", params={"root": str(tmp_path), "limit": 2, "offset": payload["next_offset"]})
    assert second.status_code == 200
    assert len(second.json()["cards"]) == 1
    assert second.json()["has_more"] is False


def test_index_serves_static_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "ChatBoard" in response.text


def test_auth_gate_requires_login_when_password_enabled(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATBOARD_USERNAME", "admin")
    monkeypatch.setenv("CHATBOARD_PASSWORD", "secret")
    _project(tmp_path)
    client = TestClient(app)

    health = client.get("/api/health")
    assert health.status_code == 200
    assert client.get("/api/auth").json() == {"enabled": True, "authenticated": False, "username_required": True}

    root = client.get("/", follow_redirects=False)
    assert root.status_code == 303
    assert root.headers["location"] == "/login"

    login_page = client.get("/login")
    assert login_page.status_code == 200
    assert "ChatBoard Login" in login_page.text
    assert 'type="text"' in login_page.text
    assert 'type="email"' not in login_page.text

    blocked = client.get("/api/catalog", params={"root": str(tmp_path)})
    assert blocked.status_code == 401

    bad_login = client.post("/api/login", json={"username": "admin", "password": "wrong"})
    assert bad_login.status_code == 401

    bad_user = client.post("/api/login", json={"username": "other@example.com", "password": "secret"})
    assert bad_user.status_code == 401

    good_login = client.post("/api/login", json={"username": "admin", "password": "secret"})
    assert good_login.status_code == 200
    assert "chatboard_session" in client.cookies
    assert client.get("/api/auth").json() == {"enabled": True, "authenticated": True, "username_required": True}

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


def test_machines_endpoints_normalize_registry_fields(tmp_path):
    registry = tmp_path / ".chatboard" / "machines.json"
    registry.parent.mkdir()
    registry.write_text(
        json.dumps(
            {
                "schema": "chatboard.machines.v1",
                "machines": [
                    {
                        "id": "demo",
                        "title": "Demo",
                        "roles": "worker",
                        "aliases": None,
                        "evidence": "reports/demo.md",
                        "tools": "invalid",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(app)

    listing = client.get("/api/machines", params={"root": str(tmp_path)})
    detail = client.get("/api/machines/demo", params={"root": str(tmp_path)})

    assert listing.status_code == 200
    machine = listing.json()["machines"][0]
    assert machine["roles"] == ["worker"]
    assert machine["aliases"] == []
    assert machine["evidence"] == ["reports/demo.md"]
    assert machine["tools"] == {}
    assert detail.status_code == 200
