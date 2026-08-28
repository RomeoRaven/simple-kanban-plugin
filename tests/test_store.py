from __future__ import annotations

import importlib
import sqlite3
import sys
import types
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def _store(plugin, tmp_path):
    module = importlib.import_module(plugin.__name__ + ".store")
    return module.KanbanStore(tmp_path / "simple_kanban.db"), module


def test_default_path_uses_selected_host_instance_store(plugin, tmp_path, monkeypatch):
    module = importlib.import_module(plugin.__name__ + ".store")
    infra = types.ModuleType("infra")
    paths = types.ModuleType("infra.paths")
    paths.instance_paths = lambda: types.SimpleNamespace(store=lambda name: tmp_path / name)  # type: ignore[attr-defined]
    infra.paths = paths  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "infra", infra)
    monkeypatch.setitem(sys.modules, "infra.paths", paths)
    assert module.default_db_path() == Path(tmp_path / "simple_kanban" / "simple_kanban.db")


def test_crud_rank_move_close_reopen_and_delete(plugin, tmp_path):
    store, _ = _store(plugin, tmp_path)
    first = store.create(title="First", priority=1)
    second = store.create(title="Second")
    third = store.create(title="Third", status="blocked")
    assert [(x["title"], x["position"]) for x in store.list(["open"])] == [("First", 1), ("Second", 2)]

    updated = store.update(first["id"], expected_version=1, title="First edited", assignee="Dennis")
    assert updated["version"] == 2
    moved = store.move(
        second["id"], destination_status="open", before_id=first["id"], expected_version=second["version"]
    )
    assert moved["position"] == 1
    assert [(x["title"], x["position"]) for x in store.list(["open"])] == [("Second", 1), ("First edited", 2)]

    cross = store.move(
        first["id"], destination_status="blocked", before_id=third["id"], expected_version=updated["version"]
    )
    assert cross["status"] == "blocked"
    assert [(x["title"], x["position"]) for x in store.list(["blocked"])] == [("First edited", 1), ("Third", 2)]
    assert [(x["title"], x["position"]) for x in store.list(["open"])] == [("Second", 1)]

    closed = store.close(second["id"], expected_version=moved["version"], reason="done")
    assert closed["closed_at"] and closed["close_reason"] == "done"
    reopened = store.reopen(second["id"], expected_version=closed["version"])
    assert reopened["status"] == "open" and reopened["closed_at"] is None and reopened["close_reason"] is None
    deleted = store.delete(second["id"], expected_version=reopened["version"])
    assert deleted["id"] == second["id"]
    assert store.integrity() == "ok"


def test_stale_writes_conflict_without_mutation(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    task = store.create(title="Original")
    newer = store.update(task["id"], expected_version=1, title="Newer")
    with pytest.raises(module.KanbanConflict):
        store.update(task["id"], expected_version=1, title="Stale")
    assert store.get(task["id"])["title"] == "Newer"
    assert store.get(task["id"])["version"] == newer["version"]


def test_compact_card_id_resolves_uniquely_and_rejects_ambiguity(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    task = store.create(title="Compact reference")
    compact = f"K-{task['id'].removeprefix('kanban-')[:8].upper()}"
    assert store.get(compact)["id"] == task["id"]

    other = store.create(title="Collision probe")
    with sqlite3.connect(store.path) as conn:
        conn.execute("UPDATE kanban_tasks SET id=? WHERE id=?", ("kanban-aaaaaaaa0001", task["id"]))
        conn.execute("UPDATE kanban_tasks SET id=? WHERE id=?", ("kanban-aaaaaaaa0002", other["id"]))
    with pytest.raises(module.KanbanConflict, match="ambiguous"):
        store.get("K-AAAAAAAA")


def test_closed_reorder_preserves_terminal_metadata(plugin, tmp_path):
    store, _ = _store(plugin, tmp_path)
    first = store.create(title="First")
    second = store.create(title="Second", status="closed")
    closed = store.close(first["id"], expected_version=first["version"], reason="accepted")
    reordered = store.move(
        first["id"],
        destination_status="closed",
        before_id=second["id"],
        expected_version=closed["version"],
    )
    assert reordered["closed_at"] == closed["closed_at"]
    assert reordered["close_reason"] == "accepted"


def test_epic_close_guard_uses_linked_status_and_inline_checkboxes(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    child = store.create(title="Implement child")
    epic = store.create(
        title="Larger outcome",
        issue_type="epic",
        description=(
            f"## Child tasks\n- [[{child['id']}]] — Implement child\n"
            "- [ ] Write operator notes\n\n"
            "## Related cards\n- [[kanban-ffffffffffff]] — Missing peers do not block"
        ),
    )
    assert epic["epic_plan"]["open_children"] == 2
    assert epic["epic_plan"]["can_close"] is False
    with pytest.raises(module.KanbanValidation, match="2 open child tasks"):
        store.close(epic["id"], expected_version=epic["version"])

    child = store.close(child["id"], expected_version=child["version"])
    epic = store.update(
        epic["id"],
        expected_version=epic["version"],
        description=(
            f"## Child tasks\n- [[{child['id']}]] — Implement child\n"
            "- [x] Write operator notes\n\n"
            "## Related cards\n- [[kanban-ffffffffffff]] — Missing peers do not block"
        ),
    )
    assert epic["epic_plan"]["can_close"] is True
    closed = store.close(epic["id"], expected_version=epic["version"])
    assert closed["status"] == "closed"


def test_epic_close_guard_rejects_missing_and_self_references(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    epic = store.create(title="Guarded epic", issue_type="epic")
    epic = store.update(
        epic["id"],
        expected_version=epic["version"],
        description=(f"## Child tasks\n- [[{epic['id']}]] — Self\n- [[kanban-aaaaaaaaaaaa]] — Missing"),
    )
    assert epic["epic_plan"]["broken_references"] == 2
    assert epic["epic_plan"]["open_children"] == 0
    with pytest.raises(module.KanbanValidation, match="2 broken child references"):
        store.close(epic["id"], expected_version=epic["version"])

    malformed = store.create(
        title="Malformed reference",
        issue_type="epic",
        description="## Child tasks\n- [[kanban-REPLACE-ME]] — Placeholder",
    )
    assert malformed["epic_plan"]["broken_references"] == 1
    with pytest.raises(module.KanbanValidation, match="1 broken child reference"):
        store.close(malformed["id"], expected_version=malformed["version"])


def test_epic_guard_covers_create_combined_move_and_closed_updates(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    with pytest.raises(module.KanbanValidation, match="1 open child task"):
        store.create(
            title="Created closed",
            status="closed",
            issue_type="epic",
            description="## Child tasks\n- [ ] Not finished",
        )

    task = store.create(title="Becoming an epic")
    with pytest.raises(module.KanbanValidation, match="1 open child task"):
        store.move(
            task["id"],
            destination_status="closed",
            before_id=None,
            expected_version=task["version"],
            updates={"issue_type": "epic", "description": "## Child tasks\n- [ ] Not finished"},
        )

    closed = store.close(task["id"], expected_version=task["version"])
    with pytest.raises(module.KanbanValidation, match="1 open child task"):
        store.update(
            closed["id"],
            expected_version=closed["version"],
            issue_type="epic",
            description="## Child tasks\n- [ ] Added after closure",
        )


def test_archive_closed_is_atomic_when_legacy_epic_has_open_plan(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    ordinary = store.create(title="Closed ordinary", status="closed")
    epic = store.create(title="Legacy epic", status="closed", issue_type="epic")
    with sqlite3.connect(store.path) as conn:
        conn.execute(
            "UPDATE kanban_tasks SET description=? WHERE id=?",
            ("## Child tasks\n- [ ] Legacy unfinished task", epic["id"]),
        )
    with pytest.raises(module.KanbanValidation, match="Legacy epic"):
        store.archive_closed()
    assert store.get(ordinary["id"])["archived_at"] is None
    assert store.get(epic["id"])["archived_at"] is None


def test_archive_closed_is_durable_non_destructive_and_idempotent(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    active = store.create(title="Still active")
    first = store.create(title="Closed one", status="closed")
    second = store.create(title="Closed two", status="closed")

    archived = store.archive_closed()
    assert [task["id"] for task in archived] == [first["id"], second["id"]]
    assert all(task["archived_at"] and task["version"] == 2 for task in archived)
    assert [task["id"] for task in store.list()] == [active["id"]]
    assert [task["id"] for task in store.list(archived=True)] == [first["id"], second["id"]]
    assert store.get(first["id"])["title"] == "Closed one"
    assert store.archive_closed() == []
    with pytest.raises(module.KanbanValidation, match="read-only"):
        store.update(first["id"], expected_version=2, title="No")
    with pytest.raises(module.KanbanValidation, match="cannot be moved"):
        store.reopen(first["id"], expected_version=2)
    assert store.integrity() == "ok"


def test_schema_migrates_existing_database_to_archive_column(plugin, tmp_path):
    module = importlib.import_module(plugin.__name__ + ".store")
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as conn:
        conn.execute(
            """CREATE TABLE kanban_tasks (
            id TEXT PRIMARY KEY,title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,position INTEGER NOT NULL,version INTEGER NOT NULL DEFAULT 1,
            priority INTEGER NOT NULL DEFAULT 2,issue_type TEXT NOT NULL DEFAULT 'task',
            assignee TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,updated_at TEXT NOT NULL,
            closed_at TEXT,close_reason TEXT,source_kind TEXT,source_id TEXT)"""
        )
    store = module.KanbanStore(path)
    created = store.create(title="Migrated")
    assert created["archived_at"] is None
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 2


def test_malformed_versions_are_validation_errors(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    task = store.create(title="Guarded")
    operations = (
        lambda: store.update(task["id"], expected_version="old", title="Changed"),
        lambda: store.move(task["id"], destination_status="blocked", before_id=None, expected_version="old"),
        lambda: store.close(task["id"], expected_version="old"),
        lambda: store.delete(task["id"], expected_version="old"),
    )
    for operation in operations:
        with pytest.raises(module.KanbanValidation, match="positive integer"):
            operation()
    with pytest.raises(module.KanbanValidation, match="positive integer"):
        store.update(task["id"], expected_version="²", title="Changed")
    assert store.get(task["id"])["version"] == 1


def test_validation_and_source_idempotency(plugin, tmp_path):
    store, module = _store(plugin, tmp_path)
    with pytest.raises(module.KanbanValidation):
        store.create(title="")
    with pytest.raises(module.KanbanValidation):
        store.create(title="Bad", status="invented")
    for field, value in (("title", ["not", "text"]), ("description", {"bad": "shape"}), ("assignee", 7)):
        with pytest.raises(module.KanbanValidation, match="must be a string"):
            store.create(**{"title": "Valid", field: value})
    for issue_type in ("", None):
        with pytest.raises(module.KanbanValidation, match="issue_type is required"):
            store.create(title="Bad type", issue_type=issue_type)
    for priority in (True, 1.9, "²"):
        with pytest.raises(module.KanbanValidation, match="priority must be an integer"):
            store.create(title="Bad priority", priority=priority)
    one = store.create(title="Imported", source_kind="test", source_id="1")
    same = store.create(title="Duplicate", source_kind="test", source_id="1")
    assert same["id"] == one["id"]
    assert len(store.list()) == 1


def test_concurrent_creates_have_dense_unique_rank(plugin, tmp_path):
    store, _ = _store(plugin, tmp_path)
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda index: store.create(title=f"Task {index}"), range(40)))
    tasks = store.list(["open"])
    assert len(tasks) == 40
    assert sorted(task["position"] for task in tasks) == list(range(1, 41))
    assert len({task["id"] for task in tasks}) == 40
    assert store.integrity() == "ok"


def test_concurrent_bulk_archive_has_one_atomic_winner(plugin, tmp_path):
    module = importlib.import_module(plugin.__name__ + ".store")
    path = tmp_path / "archive.db"
    first = module.KanbanStore(path)
    second = module.KanbanStore(path)
    for index in range(20):
        first.create(title=f"Closed {index}", status="closed")
    with ThreadPoolExecutor(max_workers=2) as pool:
        counts = list(pool.map(lambda store: len(store.archive_closed()), (first, second)))
    assert sorted(counts) == [0, 20]
    assert first.list() == []
    assert len(first.list(archived=True)) == 20
    assert first.integrity() == "ok"


def test_distinct_stores_coordinate_first_schema_use(plugin, tmp_path):
    module = importlib.import_module(plugin.__name__ + ".store")
    path = tmp_path / "shared.db"
    stores = [module.KanbanStore(path) for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda pair: pair[1].create(title=f"Task {pair[0]}"), enumerate(stores)))
    assert len(stores[0].list()) == 12
    assert stores[-1].integrity() == "ok"
