from __future__ import annotations

import importlib
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


def test_distinct_stores_coordinate_first_schema_use(plugin, tmp_path):
    module = importlib.import_module(plugin.__name__ + ".store")
    path = tmp_path / "shared.db"
    stores = [module.KanbanStore(path) for _ in range(12)]
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda pair: pair[1].create(title=f"Task {pair[0]}"), enumerate(stores)))
    assert len(stores[0].list()) == 12
    assert stores[-1].integrity() == "ok"
