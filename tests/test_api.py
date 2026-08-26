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
    status = client.get("/api/plugins/simple_kanban/status").json()
    assert status["integrity"] == "ok" and status["version"] == "0.3.0" and status["schema"] == 2
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
    assert (
        client.patch(
            f"/api/plugins/simple_kanban/tasks/{task['id']}", json={"expected_version": "²", "title": "Changed"}
        ).status_code
        == 422
    )
    assert (
        client.patch(
            f"/api/plugins/simple_kanban/tasks/{task['id']}",
            json={"expected_version": "9" * 5000, "title": "Changed"},
        ).status_code
        == 422
    )
    for priority in (True, 1.9, "²", "9" * 5000):
        assert (
            client.post("/api/plugins/simple_kanban/tasks", json={"title": "Bad", "priority": priority}).status_code
            == 422
        )
    for issue_type in ("", None):
        assert (
            client.post("/api/plugins/simple_kanban/tasks", json={"title": "Bad", "issue_type": issue_type}).status_code
            == 422
        )
    for field, value in (("title", ["not", "text"]), ("description", {"bad": "shape"}), ("assignee", 7)):
        assert client.post("/api/plugins/simple_kanban/tasks", json={"title": "Valid", field: value}).status_code == 422


def test_api_archives_all_closed_and_preserves_card_lookup(plugin, tmp_path):
    client = client_for(plugin, tmp_path)
    active = client.post("/api/plugins/simple_kanban/tasks", json={"title": "Active"}).json()["task"]
    closed = [
        client.post(
            "/api/plugins/simple_kanban/tasks",
            json={"title": f"Closed {index}", "status": "closed"},
        ).json()["task"]
        for index in range(2)
    ]

    archived = client.post("/api/plugins/simple_kanban/tasks/archive-closed")
    assert archived.status_code == 200
    assert archived.json() == {"archived": 2, "task_ids": [task["id"] for task in closed]}
    assert [task["id"] for task in client.get("/api/plugins/simple_kanban/tasks").json()["tasks"]] == [active["id"]]
    archived_tasks = client.get("/api/plugins/simple_kanban/tasks?archived=true").json()["tasks"]
    assert [task["id"] for task in archived_tasks] == [task["id"] for task in closed]
    exact = client.get(f"/api/plugins/simple_kanban/tasks/{closed[0]['id']}").json()["task"]
    assert exact["archived_at"] and exact["id"] == closed[0]["id"]
    assert client.post("/api/plugins/simple_kanban/tasks/archive-closed").json()["archived"] == 0


def test_api_returns_epic_summary_and_blocks_close(plugin, tmp_path):
    client = client_for(plugin, tmp_path)
    epic = client.post(
        "/api/plugins/simple_kanban/tasks",
        json={
            "title": "API epic",
            "issue_type": "epic",
            "description": "## Child tasks\n- [ ] API child",
        },
    ).json()["task"]
    assert epic["epic_plan"]["open_children"] == 1
    blocked = client.post(
        f"/api/plugins/simple_kanban/tasks/{epic['id']}/close",
        json={"expected_version": epic["version"]},
    )
    assert blocked.status_code == 422
    assert "1 open child task" in blocked.json()["detail"]
