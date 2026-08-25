"""Best-effort plugin event publication."""

from __future__ import annotations

from typing import Any

_REGISTRY = None


def bind_registry(registry) -> None:
    global _REGISTRY
    _REGISTRY = registry


def emit_changed(action: str, task: dict[str, Any]) -> None:
    if _REGISTRY is None:
        return
    try:
        _REGISTRY.emit(
            "changed",
            {
                "action": action,
                "task_id": task.get("id"),
                "status": task.get("status"),
                "version": task.get("version"),
            },
        )
    except Exception:  # noqa: BLE001 - event delivery cannot invalidate the committed write
        # Persistence is authoritative. Event delivery is a refresh hint only.
        return
