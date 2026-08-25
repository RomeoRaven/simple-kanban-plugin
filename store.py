"""Plugin-owned durable ranked task store for Simple Kanban."""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STATUSES = ("open", "in_progress", "blocked", "deferred", "closed")
STATUS_INDEX = {status: index for index, status in enumerate(STATUSES)}
PRIORITIES = (0, 1, 2, 3, 4)
ISSUE_TYPES = ("task", "bug", "feature", "chore", "epic")
_SCHEMA_LOCK = threading.Lock()


class KanbanError(Exception):
    """Base error with a stable API-facing message."""


class KanbanNotFound(KanbanError):
    pass


class KanbanConflict(KanbanError):
    pass


class KanbanValidation(KanbanError):
    pass


def _now() -> str:
    return datetime.now(UTC).isoformat()


def default_db_path() -> Path:
    """Resolve the selected host's documented per-instance store seam lazily."""
    try:
        from infra.paths import instance_paths  # type: ignore[import-not-found]
    except ImportError as exc:  # host-free tests inject a path directly
        raise RuntimeError("Simple Kanban requires protoAgent's documented infra.paths.instance_paths seam") from exc
    root = Path(instance_paths().store("simple_kanban"))
    return root / "simple_kanban.db"


def _text(value: Any, field: str, *, required: bool = False, limit: int = 20_000) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise KanbanValidation(f"{field} must be a string")
    if required and not text:
        raise KanbanValidation(f"{field} is required")
    if len(text) > limit:
        raise KanbanValidation(f"{field} is too long (max {limit})")
    return text


def _status(value: Any) -> str:
    status = _text(value, "status", required=True, limit=40)
    if status not in STATUSES:
        raise KanbanValidation(f"status must be one of {', '.join(STATUSES)}")
    return status


def _priority(value: Any) -> int:
    if isinstance(value, bool):
        raise KanbanValidation("priority must be an integer from 0 to 4")
    if isinstance(value, int):
        priority = value
    elif isinstance(value, str) and len(value) <= 1 and value.isascii() and value.isdigit():
        priority = int(value)
    else:
        raise KanbanValidation("priority must be an integer from 0 to 4")
    if priority not in PRIORITIES:
        raise KanbanValidation("priority must be an integer from 0 to 4")
    return priority


def _version(value: Any) -> int:
    if isinstance(value, bool):
        raise KanbanValidation("expected_version must be a positive integer")
    if isinstance(value, int):
        version = value
    elif isinstance(value, str) and len(value) <= 19 and value.isascii() and value.isdigit():
        version = int(value)
    else:
        raise KanbanValidation("expected_version must be a positive integer")
    if version < 1:
        raise KanbanValidation("expected_version must be a positive integer")
    return version


def _issue_type(value: Any) -> str:
    issue_type = _text(value, "issue_type", required=True, limit=40)
    if issue_type not in ISSUE_TYPES:
        raise KanbanValidation(f"issue_type must be one of {', '.join(ISSUE_TYPES)}")
    return issue_type


def _edits(fields: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(fields, dict):
        raise KanbanValidation("updates must be an object")
    allowed = {"title", "description", "priority", "issue_type", "assignee"}
    unknown = sorted(set(fields) - allowed)
    if unknown:
        raise KanbanValidation(f"unsupported field {unknown[0]}")
    values: dict[str, Any] = {}
    if "title" in fields:
        values["title"] = _text(fields["title"], "title", required=True, limit=500)
    if "description" in fields:
        values["description"] = _text(fields["description"], "description")
    if "priority" in fields:
        values["priority"] = _priority(fields["priority"])
    if "issue_type" in fields:
        values["issue_type"] = _issue_type(fields["issue_type"])
    if "assignee" in fields:
        values["assignee"] = _text(fields["assignee"], "assignee", limit=200)
    return values


class KanbanStore:
    """SQLite store with transactionally dense rank per status column."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self.path = Path(db_path) if db_path is not None else default_db_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        self._ensure_schema(conn)
        return conn

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        if self._initialized:
            return
        with _SCHEMA_LOCK:
            if self._initialized:
                return
            for attempt in range(5):
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript(
                        """
                CREATE TABLE IF NOT EXISTS kanban_tasks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL,
                    position INTEGER NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    priority INTEGER NOT NULL DEFAULT 2,
                    issue_type TEXT NOT NULL DEFAULT 'task',
                    assignee TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    closed_at TEXT,
                    close_reason TEXT,
                    source_kind TEXT,
                    source_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_kanban_tasks_status_position
                    ON kanban_tasks(status, position, id);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_kanban_tasks_source
                    ON kanban_tasks(source_kind, source_id)
                    WHERE source_kind IS NOT NULL AND source_id IS NOT NULL;
                PRAGMA user_version=1;
                        """
                    )
                    self._initialized = True
                    return
                except sqlite3.OperationalError as exc:
                    if "locked" not in str(exc).lower() or attempt == 4:
                        raise
                    time.sleep(0.05 * (2**attempt))

    @contextmanager
    def _write(self) -> Iterator[sqlite3.Connection]:
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _row(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise KanbanNotFound("task not found")
        return dict(row)

    @staticmethod
    def _ordered_ids(conn: sqlite3.Connection, status: str, *, without: str | None = None) -> list[str]:
        rows = conn.execute(
            "SELECT id FROM kanban_tasks WHERE status=? ORDER BY position, created_at, id", (status,)
        ).fetchall()
        return [row["id"] for row in rows if row["id"] != without]

    @staticmethod
    def _renumber(conn: sqlite3.Connection, status: str, ordered_ids: list[str]) -> None:
        for position, task_id in enumerate(ordered_ids, start=1):
            conn.execute("UPDATE kanban_tasks SET position=? WHERE id=?", (position, task_id))

    def integrity(self) -> str:
        with self._connect() as conn:
            return str(conn.execute("PRAGMA integrity_check").fetchone()[0])

    def list(self, statuses: list[str] | tuple[str, ...] | None = None) -> list[dict[str, Any]]:
        selected = tuple(_status(value) for value in (statuses or STATUSES))
        placeholders = ",".join("?" for _ in selected)
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT * FROM kanban_tasks WHERE status IN ({placeholders}) ORDER BY CASE status "
                + " ".join(f"WHEN '{status}' THEN {index}" for status, index in STATUS_INDEX.items())
                + " END, position, created_at, id",
                selected,
            ).fetchall()
        return [dict(row) for row in rows]

    def get(self, task_id: str) -> dict[str, Any]:
        with self._connect() as conn:
            return self._row(
                conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (_text(task_id, "id", required=True),)).fetchone()
            )

    def create(
        self,
        *,
        title: str,
        description: str = "",
        status: str = "open",
        priority: int = 2,
        issue_type: str = "task",
        assignee: str = "",
        source_kind: str | None = None,
        source_id: str | None = None,
    ) -> dict[str, Any]:
        title = _text(title, "title", required=True, limit=500)
        description = _text(description, "description")
        status = _status(status)
        priority = _priority(priority)
        issue_type = _issue_type(issue_type)
        assignee = _text(assignee, "assignee", limit=200)
        source_kind = _text(source_kind, "source_kind", limit=100) or None
        source_id = _text(source_id, "source_id", limit=500) or None
        task_id = "kanban-" + uuid.uuid4().hex[:12]
        now = _now()
        with self._write() as conn:
            position = int(
                conn.execute("SELECT COALESCE(MAX(position), 0) + 1 FROM kanban_tasks WHERE status=?", (status,)).fetchone()[0]
            )
            try:
                conn.execute(
                    """INSERT INTO kanban_tasks
                       (id,title,description,status,position,version,priority,issue_type,assignee,
                        created_at,updated_at,closed_at,close_reason,source_kind,source_id)
                       VALUES (?,?,?,?,?,1,?,?,?,?,?,?,?,?,?)""",
                    (
                        task_id,
                        title,
                        description,
                        status,
                        position,
                        priority,
                        issue_type,
                        assignee,
                        now,
                        now,
                        now if status == "closed" else None,
                        "created closed" if status == "closed" else None,
                        source_kind,
                        source_id,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                if source_kind and source_id:
                    existing = conn.execute(
                        "SELECT * FROM kanban_tasks WHERE source_kind=? AND source_id=?", (source_kind, source_id)
                    ).fetchone()
                    if existing:
                        return dict(existing)
                raise KanbanConflict("task conflicts with an existing record") from exc
            return self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())

    def update(self, task_id: str, *, expected_version: int, **fields: Any) -> dict[str, Any]:
        values = _edits(fields)
        expected_version = _version(expected_version)
        with self._write() as conn:
            current = self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())
            if int(current["version"]) != expected_version:
                raise KanbanConflict("task changed; reload and try again")
            if not values:
                return current
            sets = ", ".join(f"{key}=?" for key in values)
            conn.execute(
                f"UPDATE kanban_tasks SET {sets}, version=version+1, updated_at=? WHERE id=?",
                (*values.values(), _now(), task_id),
            )
            return self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())

    def move(
        self,
        task_id: str,
        *,
        destination_status: str,
        before_id: str | None,
        expected_version: int,
        close_reason: str | None = None,
        updates: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        destination_status = _status(destination_status)
        before_id = _text(before_id, "before_id", limit=100) or None
        expected_version = _version(expected_version)
        values = _edits({} if updates is None else updates)
        with self._write() as conn:
            current = self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())
            if int(current["version"]) != expected_version:
                raise KanbanConflict("task changed; reload and try again")
            source_status = str(current["status"])
            source_ids = self._ordered_ids(conn, source_status, without=task_id)
            destination_ids = source_ids if destination_status == source_status else self._ordered_ids(conn, destination_status)
            if before_id:
                if before_id == task_id or before_id not in destination_ids:
                    raise KanbanValidation("before_id must identify another task in the destination status")
                destination_ids.insert(destination_ids.index(before_id), task_id)
            else:
                destination_ids.append(task_id)
            now = _now()
            entering_closed = destination_status == "closed" and source_status != "closed"
            leaving_closed = destination_status != "closed" and source_status == "closed"
            closed_at = now if entering_closed else (None if leaving_closed else current["closed_at"])
            reason = (
                _text(close_reason, "close_reason", limit=1000)
                if entering_closed
                else (None if leaving_closed else current["close_reason"])
            )
            sets = ["status=?", "version=version+1", "updated_at=?", "closed_at=?", "close_reason=?"]
            params: list[Any] = [destination_status, now, closed_at, reason]
            for key, value in values.items():
                sets.append(f"{key}=?")
                params.append(value)
            params.append(task_id)
            conn.execute(f"UPDATE kanban_tasks SET {', '.join(sets)} WHERE id=?", params)
            if destination_status != source_status:
                self._renumber(conn, source_status, source_ids)
            self._renumber(conn, destination_status, destination_ids)
            return self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())

    def close(self, task_id: str, *, expected_version: int, reason: str = "") -> dict[str, Any]:
        return self.move(
            task_id,
            destination_status="closed",
            before_id=None,
            expected_version=expected_version,
            close_reason=reason,
        )

    def reopen(self, task_id: str, *, expected_version: int) -> dict[str, Any]:
        return self.move(task_id, destination_status="open", before_id=None, expected_version=expected_version)

    def delete(self, task_id: str, *, expected_version: int) -> dict[str, Any]:
        expected_version = _version(expected_version)
        with self._write() as conn:
            current = self._row(conn.execute("SELECT * FROM kanban_tasks WHERE id=?", (task_id,)).fetchone())
            if int(current["version"]) != expected_version:
                raise KanbanConflict("task changed; reload and try again")
            conn.execute("DELETE FROM kanban_tasks WHERE id=?", (task_id,))
            self._renumber(conn, str(current["status"]), self._ordered_ids(conn, str(current["status"])))
            return current
