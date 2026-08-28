from __future__ import annotations

import importlib


def test_demo_is_opt_in_idempotent_and_namespace_scoped(plugin, tmp_path):
    store_module = importlib.import_module(plugin.__name__ + ".store")
    demo = importlib.import_module(plugin.__name__ + ".demo")
    store = store_module.KanbanStore(tmp_path / "kanban.db")
    ordinary = store.create(title="Operator card")

    empty = demo.status(store)
    assert empty["present_count"] == 0
    assert empty["expected_count"] == 8
    assert empty["complete"] is False
    assert [task["id"] for task in store.list()] == [ordinary["id"]]

    first = demo.load(store)
    assert len(first["created"]) == 8
    assert first["status"]["complete"] is True
    cards = first["status"]["cards"]
    assert {task["issue_type"] for task in cards} == {"task", "bug", "feature", "chore", "epic"}
    assert {task["status"] for task in cards} == {"open", "in_progress", "blocked", "deferred", "closed"}
    epic = next(task for task in cards if task["issue_type"] == "epic")
    assert epic["epic_plan"]["completed_children"] == 1
    assert epic["epic_plan"]["total_children"] == 4
    assert epic["epic_plan"]["open_children"] == 3
    assert epic["epic_plan"]["related_count"] == 2
    assert epic["epic_plan"]["can_close"] is False

    second = demo.load(store)
    assert second["created"] == []
    assert {task["id"] for task in second["status"]["cards"]} == {task["id"] for task in cards}
    assert store.get(ordinary["id"])["title"] == "Operator card"


def test_demo_load_preserves_edits_reset_replaces_only_demo_and_remove_handles_archived(plugin, tmp_path):
    store_module = importlib.import_module(plugin.__name__ + ".store")
    demo = importlib.import_module(plugin.__name__ + ".demo")
    store = store_module.KanbanStore(tmp_path / "kanban.db")
    ordinary = store.create(title="Never touch me")
    loaded = demo.load(store)
    task = next(card for card in loaded["status"]["cards"] if card["source_id"] == "ordinary-task")
    edited = store.update(task["id"], expected_version=task["version"], title="Edited demo task")

    preserved = demo.load(store)
    assert preserved["created"] == []
    assert store.get(edited["id"])["title"] == "Edited demo task"

    reset = demo.reset(store)
    assert len(reset["removed"]) == 8
    assert len(reset["created"]) == 8
    replacement = next(card for card in reset["status"]["cards"] if card["source_id"] == "ordinary-task")
    assert replacement["id"] != edited["id"]
    assert replacement["title"] == "DEMO · Task — Draft the release notes"
    assert store.get(ordinary["id"])["title"] == "Never touch me"

    archived = store.archive_closed()
    assert any(card.get("source_kind") == "simple-kanban-demo" for card in archived)
    removed = demo.remove(store)
    assert len(removed["removed"]) == 8
    assert removed["status"]["present_count"] == 0
    assert [task["id"] for task in store.list()] == [ordinary["id"]]
    assert store.list(archived=True) == []
