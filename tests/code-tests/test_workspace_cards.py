from pathlib import Path

from chatboard.services.cards import card_detail, ensure_card, move_card
from chatboard.services.workspace import catalog, scan


def _project(root: Path, rel: str, title: str = "Demo Project") -> Path:
    path = root / rel
    path.mkdir(parents=True)
    (path / "PRD.md").write_text(f"# {title}\n\nA useful task.\n", encoding="utf-8")
    (path / "progress.md").write_text("# Progress\n\n- started\n", encoding="utf-8")
    return path


def test_scan_infers_cards_without_writing(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo", "Demo Card")

    cards = scan(tmp_path)

    assert len(cards) == 1
    assert cards[0].title == "Demo Card"
    assert cards[0].area == "projects"
    assert cards[0].stage == "development"
    assert not (project / "card.json").exists()


def test_ensure_writes_card_json_and_catalog_groups_columns(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")

    card = ensure_card(project, root=tmp_path)
    board = catalog(tmp_path)

    assert (project / "card.json").exists()
    assert card.id == "projects-chatarch-07-07-demo"
    project_column = next(col for col in board["columns"] if col["key"] == "project")
    assert [item["id"] for item in project_column["cards"]] == [card.id]


def test_card_detail_contains_expected_sections(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")
    ensure_card(project, root=tmp_path)

    detail = card_detail(project, root=tmp_path)

    assert detail["card"]["title"] == "Demo Project"
    assert {section["key"] for section in detail["sections"]} >= {"overview", "prd", "progress", "discussion", "archive"}


def test_move_card_to_discussion_moves_directory_and_updates_card(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")
    card = ensure_card(project, root=tmp_path)

    result = move_card(card.id, "discussion", root=tmp_path)

    new_path = tmp_path / "discussion/chatarch/07-07-demo"
    assert result["to"] == new_path.as_posix()
    assert new_path.exists()
    assert not project.exists()
    moved = scan(tmp_path)[0]
    assert moved.area == "discussion"
    assert moved.stage == "review"
