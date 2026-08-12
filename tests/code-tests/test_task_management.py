from pathlib import Path

import pytest

import chatboard.services.cards as cards


def test_create_task_writes_project_skeleton_and_target_metadata(tmp_path: Path):
    created = cards.create_task(
        title="Board task management infra",
        description="Implement board CRUD and stage transitions.",
        root=tmp_path,
        topic="chatarch",
        slug="08-12-board-task-management",
        source_platform="feishu",
        source_url="https://example.feishu.cn/thread/task",
        accept_mode="accept",
        side_effect_level="local_write",
        next_action="Implement the task management API and CLI.",
        assignee="hermes",
        tags=["board", "infra"],
    )

    project = tmp_path / "projects/chatarch/08-12-board-task-management"
    assert project.exists()
    assert (project / "PRD.md").read_text(encoding="utf-8").startswith("# Board task management infra\n")
    assert "Implement board CRUD and stage transitions." in (project / "PRD.md").read_text(encoding="utf-8")
    assert (project / "progress.md").exists()
    assert (project / "card.md").exists()
    assert (project / ".trash").is_dir()
    assert (project / "reports").is_dir()

    assert created.id == "projects-chatarch-08-12-board-task-management"
    assert created.type == "task"
    assert created.workspace_path == "projects/chatarch/08-12-board-task-management"
    assert created.stage == "inbox"
    assert created.source.platform == "feishu"
    assert created.source.url == "https://example.feishu.cn/thread/task"
    assert created.accept_mode == "accept"
    assert created.side_effect_level == "local_write"
    assert created.next_action == "Implement the task management API and CLI."
    assert created.assignee == "hermes"
    assert created.tags == ["chatarch", "board", "infra"]

    loaded = cards.load_card(project, root=tmp_path)
    assert loaded.source.platform == "feishu"
    assert loaded.accept_mode == "accept"
    assert loaded.side_effect_level == "local_write"
    assert loaded.next_action == "Implement the task management API and CLI."


def test_update_status_transition_and_soft_delete_task(tmp_path: Path):
    created = cards.create_task(
        title="Example current project card",
        description="Original task body.",
        root=tmp_path,
        topic="chatarch",
        slug="08-12-example-current-card",
    )

    updated = cards.update_card(
        created.id,
        {
            "title": "Updated example card",
            "description": "Updated task body.",
            "source": {"platform": "mattermost", "url": "https://mattermost.example/team/pl/thread"},
            "accept_mode": "auto",
            "side_effect_level": "read_only",
            "next_action": "Review the task status.",
            "tags": ["chatarch", "board", "example"],
        },
        root=tmp_path,
    )

    assert updated.title == "Updated example card"
    assert updated.description == "Updated task body."
    assert updated.source.platform == "mattermost"
    assert updated.accept_mode == "auto"
    assert updated.side_effect_level == "read_only"
    assert updated.next_action == "Review the task status."

    status = cards.card_status(created.id, root=tmp_path)
    assert status["id"] == created.id
    assert status["stage"] == "inbox"
    assert status["column"] == "inbox"
    assert "accept" in status["available_transitions"]

    accepted = cards.transition_card(created.id, "accept", reason="ready for worker", root=tmp_path)
    assert accepted.stage == "ready"
    assert accepted.next_action == "Review the task status."

    blocked = cards.transition_card(created.id, "block", reason="needs scope", need="choose target examples", root=tmp_path)
    assert blocked.stage == "blocked"
    assert blocked.next_action == "choose target examples"
    assert blocked.discussion.next_action == "choose target examples"
    assert "needs scope" in blocked.discussion.questions

    unblocked = cards.transition_card(created.id, "unblock", reason="scope chosen", root=tmp_path)
    assert unblocked.stage == "ready"

    done = cards.transition_card(created.id, "done", summary="Task management verified.", root=tmp_path)
    assert done.stage == "done"
    assert done.summary == "Task management verified."

    reopened = cards.transition_card(created.id, "move", stage="review", reason="needs human check", root=tmp_path)
    assert reopened.stage == "review"

    dry_run = cards.delete_card(created.id, reason="example cleanup", root=tmp_path, dry_run=True)
    assert dry_run["dry_run"] is True
    assert Path(dry_run["to"]).parts[-3:] == ("discard", "chatarch", "08-12-example-current-card")
    assert (tmp_path / "projects/chatarch/08-12-example-current-card").exists()

    deleted = cards.delete_card(created.id, reason="example cleanup", root=tmp_path)
    assert deleted["card"]["area"] == "discard"
    assert deleted["card"]["stage"] == "discarded"
    assert deleted["card"]["archive"]["reason"] == "example cleanup"
    assert not (tmp_path / "projects/chatarch/08-12-example-current-card").exists()
    assert (tmp_path / "discard/chatarch/08-12-example-current-card").exists()
    assert cards.task_catalog(root=tmp_path)["total_cards"] == 0
    with pytest.raises(FileNotFoundError):
        cards.card_status(created.id, root=tmp_path)


def test_create_task_rejects_paths_that_escape_the_workspace(tmp_path: Path):
    try:
        cards.create_task(
            title="Escaping task",
            root=tmp_path,
            topic="chatarch",
            slug="../../outside",
        )
    except ValueError as exc:
        assert "path escapes card root" in str(exc)
    else:  # pragma: no cover - documents the required failure mode
        raise AssertionError("create_task accepted an escaping slug")

    assert not (tmp_path.parent / "outside").exists()
