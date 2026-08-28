"""Gated Simple Kanban JSON API."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Query

from . import demo
from .events import emit_changed
from .store import STATUSES, KanbanConflict, KanbanError, KanbanNotFound, KanbanStore, KanbanValidation

_STORE: KanbanStore | None = None


def store() -> KanbanStore:
    global _STORE
    if _STORE is None:
        _STORE = KanbanStore()
    return _STORE


def _run(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except KanbanNotFound as exc:
        raise HTTPException(404, str(exc)) from exc
    except KanbanConflict as exc:
        raise HTTPException(409, str(exc)) from exc
    except KanbanValidation as exc:
        raise HTTPException(422, str(exc)) from exc
    except KanbanError as exc:
        raise HTTPException(400, str(exc)) from exc


def build_data_router():
    router = APIRouter()

    @router.get("/status")
    def status():
        return {
            "plugin": "simple_kanban",
            "version": "0.3.1",
            "status": "ready",
            "schema": 2,
            "integrity": store().integrity(),
        }

    @router.get("/tasks")
    def list_tasks(
        status: Annotated[list[str] | None, Query()] = None,
        archived: Annotated[bool, Query()] = False,
    ):
        return {"tasks": _run(lambda: store().list(status, archived=archived)), "statuses": list(STATUSES)}

    @router.get("/demo")
    def demo_status():
        return _run(lambda: demo.status(store()))

    @router.post("/demo/load")
    def load_demo():
        result = _run(lambda: demo.load(store()))
        for task in result["created"]:
            emit_changed("demo_created", task)
        return {
            "created": len(result["created"]),
            "task_ids": [task["id"] for task in result["created"]],
            "demo": result["status"],
        }

    @router.post("/demo/reset")
    def reset_demo():
        result = _run(lambda: demo.reset(store()))
        for task in result["removed"]:
            emit_changed("demo_deleted", task)
        for task in result["created"]:
            emit_changed("demo_created", task)
        return {
            "removed": len(result["removed"]),
            "created": len(result["created"]),
            "task_ids": [task["id"] for task in result["created"]],
            "demo": result["status"],
        }

    @router.delete("/demo")
    def remove_demo():
        result = _run(lambda: demo.remove(store()))
        for task in result["removed"]:
            emit_changed("demo_deleted", task)
        return {
            "removed": len(result["removed"]),
            "task_ids": [task["id"] for task in result["removed"]],
            "demo": result["status"],
        }

    @router.get("/tasks/{task_id}")
    def get_task(task_id: str):
        return {"task": _run(lambda: store().get(task_id))}

    @router.post("/tasks", status_code=201)
    def create_task(payload: Annotated[dict[str, Any], Body()]):
        task = _run(
            lambda: store().create(
                title=payload.get("title", ""),
                description=payload.get("description", ""),
                status=payload.get("status", "open"),
                priority=payload.get("priority", 2),
                issue_type=payload.get("issue_type", "task"),
                assignee=payload.get("assignee", ""),
                source_kind=payload.get("source_kind"),
                source_id=payload.get("source_id"),
            )
        )
        emit_changed("created", task)
        return {"task": task}

    @router.post("/tasks/archive-closed")
    def archive_closed_tasks():
        tasks = _run(lambda: store().archive_closed())
        for task in tasks:
            emit_changed("archived", task)
        return {"archived": len(tasks), "task_ids": [task["id"] for task in tasks]}

    @router.patch("/tasks/{task_id}")
    def update_task(task_id: str, payload: Annotated[dict[str, Any], Body()]):
        expected = payload.pop("expected_version", None)
        if expected is None:
            return _run(lambda: (_ for _ in ()).throw(KanbanValidation("expected_version is required")))
        task = _run(lambda: store().update(task_id, expected_version=expected, **payload))
        emit_changed("updated", task)
        return {"task": task}

    @router.post("/tasks/{task_id}/move")
    def move_task(task_id: str, payload: Annotated[dict[str, Any], Body()]):
        task = _run(
            lambda: store().move(
                task_id,
                destination_status=payload.get("destination_status", ""),
                before_id=payload.get("before_id"),
                expected_version=payload.get("expected_version", -1),
                close_reason=payload.get("close_reason"),
                updates=payload.get("updates"),
            )
        )
        emit_changed("moved", task)
        return {"task": task}

    @router.post("/tasks/{task_id}/close")
    def close_task(task_id: str, payload: Annotated[dict[str, Any], Body()]):
        task = _run(
            lambda: store().close(
                task_id,
                expected_version=payload.get("expected_version", -1),
                reason=payload.get("reason", ""),
            )
        )
        emit_changed("closed", task)
        return {"task": task}

    @router.post("/tasks/{task_id}/reopen")
    def reopen_task(task_id: str, payload: Annotated[dict[str, Any], Body()]):
        task = _run(lambda: store().reopen(task_id, expected_version=payload.get("expected_version", -1)))
        emit_changed("reopened", task)
        return {"task": task}

    @router.delete("/tasks/{task_id}")
    def delete_task(task_id: str, expected_version: Annotated[int, Query()]):
        task = _run(lambda: store().delete(task_id, expected_version=expected_version))
        emit_changed("deleted", task)
        return {"task": task}

    return router
