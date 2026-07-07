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

    detail = client.get("/api/cards/projects-chatarch-07-07-demo", params={"root": str(tmp_path)})

    assert detail.status_code == 200
    assert detail.json()["card"]["title"] == "Demo API"


def test_index_serves_static_page():
    client = TestClient(app)

    response = client.get("/")

    assert response.status_code == 200
    assert "ChatBoard" in response.text
