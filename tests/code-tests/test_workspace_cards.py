from pathlib import Path

from chatboard.services.archive import discard
from chatboard.services.cards import card_detail, ensure_card, move_card
from chatboard.services.discussion import add_item, create_discussion
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
    assert not (project / "card.md").exists()


def test_ensure_writes_card_md_and_catalog_groups_columns(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")

    card = ensure_card(project, root=tmp_path)
    board = catalog(tmp_path)

    assert (project / "card.md").exists()
    assert card.id == "projects-chatarch-07-07-demo"
    project_column = next(col for col in board["columns"] if col["key"] == "project")
    assert [item["id"] for item in project_column["cards"]] == [card.id]


def test_nested_project_topic_dirs_are_individual_cards(tmp_path):
    topic = tmp_path / "projects/chatarch"
    topic.mkdir(parents=True)
    (topic / "README.md").write_text("# ChatArch\n", encoding="utf-8")
    _project(tmp_path, "projects/chatarch/07-07-demo", "Nested Project")

    cards = scan(tmp_path)

    assert len(cards) == 1
    assert cards[0].id == "projects-chatarch-07-07-demo"
    assert cards[0].title == "Nested Project"


def test_card_md_frontmatter_has_priority_over_inference(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo", "PRD Title")
    (project / "card.md").write_text(
        "---\n"
        "schema: chatboard.project_card.v1\n"
        "id: custom-card\n"
        "title: Frontmatter Title\n"
        "area: project\n"
        "stage: validation\n"
        "priority: 4\n"
        "tags:\n"
        "  - chatarch\n"
        "  - chatboard\n"
        "assets:\n"
        "  prd: PRD.md\n"
        "  progress: progress.md\n"
        "---\n\n"
        "# Body Title\n\nFrontmatter summary.\n",
        encoding="utf-8",
    )

    card = ensure_card(project, root=tmp_path)

    assert card.id == "custom-card"
    assert card.title == "Frontmatter Title"
    assert card.stage == "validation"
    assert card.priority == 4
    assert card.tags == ["chatarch", "chatboard"]
    assert card.links.prd == "PRD.md"
    assert (project / "card.md").exists()


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


def test_move_dry_run_does_not_create_card_metadata(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")
    card_id = "projects-chatarch-07-07-demo"

    result = move_card(card_id, "trash", root=tmp_path, dry_run=True)

    assert result["dry_run"] is True
    assert project.exists()
    assert not (project / "card.md").exists()


def test_discard_reason_survives_the_directory_move(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo")
    card = ensure_card(project, root=tmp_path)

    discard(card.id, reason="superseded", root=tmp_path)

    discarded = scan(tmp_path)[0]
    assert discarded.area == "discard"
    assert discarded.archive.reason == "superseded"


def test_discussion_card_lists_nested_items_without_top_level_duplicates(tmp_path):
    _project(tmp_path, "discussion/07-07-chatboard-v2", "ChatBoard v2 Discussion")
    item = _project(tmp_path, "discussion/07-07-chatboard-v2/Items/07-07-demo", "Nested Demo")

    cards = scan(tmp_path)

    assert [card.id for card in cards] == ["discussion-07-07-chatboard-v2"]
    assert cards[0].nested_items[0].title == "Nested Demo"
    assert cards[0].nested_items[0].workspace_path == "discussion/07-07-chatboard-v2/Items/07-07-demo"

    detail = card_detail(item, root=tmp_path)
    assert detail["card"]["title"] == "Nested Demo"
    assert detail["card"]["area"] == "discussion"


def test_create_discussion_and_add_item_moves_project_into_items(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo", "Nested Demo")
    card = ensure_card(project, root=tmp_path)
    discussion = create_discussion("ChatBoard v2", root=tmp_path, slug="07-07-chatboard-v2")

    result = add_item(discussion["id"], card.id, root=tmp_path)

    destination = tmp_path / "discussion/07-07-chatboard-v2/Items/07-07-demo"
    assert result["to"] == destination.as_posix()
    assert destination.exists()
    assert not project.exists()

    cards = scan(tmp_path)
    assert [item.id for item in cards] == [discussion["id"]]
    assert cards[0].nested_items[0].title == "Nested Demo"
    assert cards[0].nested_items[0].area == "discussion"


def test_discussion_add_item_dry_run_does_not_create_card_metadata(tmp_path):
    project = _project(tmp_path, "projects/chatarch/07-07-demo", "Nested Demo")
    discussion_path = _project(tmp_path, "discussion/07-07-topic", "Topic")
    (discussion_path / "Items").mkdir()

    result = add_item(
        "discussion-07-07-topic",
        "projects-chatarch-07-07-demo",
        root=tmp_path,
        dry_run=True,
    )

    assert result["dry_run"] is True
    assert project.exists()
    assert not (project / "card.md").exists()
    assert not (discussion_path / "card.md").exists()
