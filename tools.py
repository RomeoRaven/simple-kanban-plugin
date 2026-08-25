"""Agent-facing Simple Kanban tools."""

from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from .events import emit_changed
from .store import KanbanStore

_STORE: KanbanStore | None = None


def store() -> KanbanStore:
    global _STORE
    if _STORE is None:
        _STORE = KanbanStore()
    return _STORE


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@tool
def simple_kanban_task_create(
    title: str,
    description: str = "",
    status: str = "open",
    priority: int = 2,
    issue_type: str = "task",
    assignee: str = "",
) -> str:
    """Create a ranked Simple Kanban task. New tasks append to the selected status."""
    task = store().create(
        title=title,
        description=description,
        status=status,
        priority=priority,
        issue_type=issue_type,
        assignee=assignee,
    )
    emit_changed("created", task)
    return _json(task)


@tool
def simple_kanban_task_list(statuses: list[str] | None = None, archived: bool = False) -> str:
    """List active or archived Simple Kanban cards in durable ranked order, including exact card IDs."""
    return _json(store().list(statuses, archived=archived))


@tool
def simple_kanban_task_get(card_id: str) -> str:
    """Get one active or archived Simple Kanban card by the exact visible card_id."""
    return _json(store().get(card_id))


@tool
def simple_kanban_task_update(
    task_id: str,
    expected_version: int,
    title: str | None = None,
    description: str | None = None,
    priority: int | None = None,
    issue_type: str | None = None,
    assignee: str | None = None,
) -> str:
    """Update task fields using expected_version to prevent stale overwrites."""
    fields = {
        key: value
        for key, value in {
            "title": title,
            "description": description,
            "priority": priority,
            "issue_type": issue_type,
            "assignee": assignee,
        }.items()
        if value is not None
    }
    task = store().update(task_id, expected_version=expected_version, **fields)
    emit_changed("updated", task)
    return _json(task)


@tool
def simple_kanban_task_move(
    task_id: str,
    destination_status: str,
    expected_version: int,
    before_id: str = "",
) -> str:
    """Atomically move/reorder a task before another destination task, or append when before_id is blank."""
    task = store().move(
        task_id,
        destination_status=destination_status,
        before_id=before_id or None,
        expected_version=expected_version,
    )
    emit_changed("moved", task)
    return _json(task)


@tool
def simple_kanban_task_close(task_id: str, expected_version: int, reason: str = "") -> str:
    """Close a task and persist terminal metadata, protected by expected_version."""
    task = store().close(task_id, expected_version=expected_version, reason=reason)
    emit_changed("closed", task)
    return _json(task)


@tool
def simple_kanban_task_delete(task_id: str, expected_version: int) -> str:
    """Delete a Simple Kanban task and densely repair the affected column order."""
    task = store().delete(task_id, expected_version=expected_version)
    emit_changed("deleted", task)
    return _json(task)


@tool
def simple_kanban_closed_archive() -> str:
    """Archive every active card in Closed without deleting its durable record."""
    tasks = store().archive_closed()
    for task in tasks:
        emit_changed("archived", task)
    return _json({"archived": len(tasks), "card_ids": [task["id"] for task in tasks]})


TOOLS = (
    simple_kanban_task_create,
    simple_kanban_task_list,
    simple_kanban_task_get,
    simple_kanban_task_update,
    simple_kanban_task_move,
    simple_kanban_task_close,
    simple_kanban_task_delete,
    simple_kanban_closed_archive,
)
