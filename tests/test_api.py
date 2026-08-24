from __future__ import annotations

import importlib

from fastapi import FastAPI
from fastapi.testclient import TestClient


def client_for(plugin, tmp_path):
    api = importlib.import_module(plugin.__name__ + ".api")
    store_module = importlib.import_module(plugin.__name__ + ".store")
    api._STORE = store_module.KanbanStore(tmp_path / "api.db")
    app = FastAPI()
    app.include_router(api.build_data_router(), prefix="/api/plugins/simple_kanban")
    return TestClient(app)


def test_api_crud_and_conflict(plugin, tmp_path):
    client = client_for(plugin, tmp_path)
    assert client.get("/api/plugins/simple_kanban/status").json()["integrity"] == "ok"
    created = client.post("/api/plugins/simple_kanban/tasks", json={"title": "API task"})
    assert created.status_code == 201
    task = created.json()["task"]

    changed = client.patch(
        f"/api/plugins/simple_kanban/tasks/{task['id']}",
        json={"expected_version": task["version"], "title": "Changed"},
    )
    assert changed.status_code == 200
    changed_task = changed.json()["task"]
    stale = client.patch(
        f"/api/plugins/simple_kanban/tasks/{task['id']}",
        json={"expected_version": task["version"], "title": "Stale"},
    )
    assert stale.status_code == 409

    moved = client.post(
        f"/api/plugins/simple_kanban/tasks/{task['id']}/move",
        json={
            "destination_status": "blocked",
            "before_id": None,
            "expected_version": changed_task["version"],
            "updates": {"title": "Moved and changed", "priority": 1},
        },
    )
    moved_task = moved.json()["task"]
    assert moved.status_code == 200
    assert moved_task["status"] == "blocked" and moved_task["title"] == "Moved and changed"
    assert moved_task["priority"] == 1 and moved_task["version"] == changed_task["version"] + 1
    listed = client.get("/api/plugins/simple_kanban/tasks").json()["tasks"]
    assert [item["title"] for item in listed] == ["Moved and changed"]


def test_api_requires_version_and_valid_fields(plugin, tmp_path):
    client = client_for(plugin, tmp_path)
    task = client.post("/api/plugins/simple_kanban/tasks", json={"title": "Guarded"}).json()["task"]
    assert (
        client.patch(f"/api/plugins/simple_kanban/tasks/{task['id']}", json={"title": "No version"}).status_code == 422
    )
    assert (
        client.patch(
            f"/api/plugins/simple_kanban/tasks/{task['id']}",
            json={"expected_version": task["version"], "status": "closed"},
        ).status_code
        == 422
    )
    for suffix in ("", "/move", "/close", "/reopen"):
        method = client.patch if not suffix else client.post
        payload: dict[str, object] = {"expected_version": "old"}
        if suffix == "/move":
            payload.update({"destination_status": "blocked", "before_id": None})
        if not suffix:
            payload["title"] = "Changed"
        assert method(f"/api/plugins/simple_kanban/tasks/{task['id']}{suffix}", json=payload).status_code == 422
    for priority in (True, 1.9):
        assert (
            client.post("/api/plugins/simple_kanban/tasks", json={"title": "Bad", "priority": priority}).status_code
            == 422
        )
    for issue_type in ("", None):
        assert (
            client.post("/api/plugins/simple_kanban/tasks", json={"title": "Bad", "issue_type": issue_type}).status_code
            == 422
        )
