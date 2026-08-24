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
        json={"destination_status": "blocked", "before_id": None, "expected_version": changed_task["version"]},
    )
    assert moved.status_code == 200 and moved.json()["task"]["status"] == "blocked"
    listed = client.get("/api/plugins/simple_kanban/tasks").json()["tasks"]
    assert [item["title"] for item in listed] == ["Changed"]


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
