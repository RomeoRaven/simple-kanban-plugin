"""Opt-in, namespace-scoped demonstration board management."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .store import KanbanStore

_TEMPLATE_PATH = Path(__file__).parent / "examples" / "demo-board.json"


def template() -> dict[str, Any]:
    data = json.loads(_TEMPLATE_PATH.read_text(encoding="utf-8"))
    if data.get("version") != 1 or data.get("source_kind") != "simple-kanban-demo":
        raise RuntimeError("unsupported Simple Kanban demo template")
    return data


def _all_demo_cards(store: KanbanStore) -> list[dict[str, Any]]:
    source_kind = template()["source_kind"]
    return [task for task in [*store.list(), *store.list(archived=True)] if task.get("source_kind") == source_kind]


def status(store: KanbanStore) -> dict[str, Any]:
    data = template()
    expected = {card["source_id"] for card in data["cards"]}
    cards = _all_demo_cards(store)
    present = {card["source_id"] for card in cards if card.get("source_id") in expected}
    return {
        "template_version": data["version"],
        "source_kind": data["source_kind"],
        "expected_count": len(expected),
        "present_count": len(present),
        "complete": present == expected,
        "missing_source_ids": sorted(expected - present),
        "cards": cards,
    }


def _description(spec: dict[str, Any], ids: dict[str, str]) -> str:
    value = str(spec.get("description", ""))
    for key, card_id in ids.items():
        value = value.replace("{{" + key + "}}", card_id)
    return value


def load(store: KanbanStore) -> dict[str, Any]:
    """Create only missing demo-owned cards; never overwrite existing cards."""
    data = template()
    current = {card.get("source_id"): card for card in _all_demo_cards(store)}
    ids = {spec["key"]: current[spec["source_id"]]["id"] for spec in data["cards"] if spec["source_id"] in current}
    created: list[dict[str, Any]] = []
    specs = sorted(data["cards"], key=lambda spec: spec["issue_type"] == "epic")
    for spec in specs:
        existing = current.get(spec["source_id"])
        if existing:
            ids[spec["key"]] = existing["id"]
            continue
        task = store.create(
            title=spec["title"],
            description=_description(spec, ids),
            status=spec["status"],
            priority=spec["priority"],
            issue_type=spec["issue_type"],
            assignee=spec["assignee"],
            source_kind=data["source_kind"],
            source_id=spec["source_id"],
        )
        current[spec["source_id"]] = task
        ids[spec["key"]] = task["id"]
        created.append(task)
    return {"created": created, "status": status(store)}


def remove(store: KanbanStore) -> dict[str, Any]:
    """Delete only exact demo-namespace cards, including archived examples."""
    cards = sorted(_all_demo_cards(store), key=lambda task: task.get("issue_type") != "epic")
    removed = [store.delete(task["id"], expected_version=task["version"]) for task in cards]
    return {"removed": removed, "status": status(store)}


def reset(store: KanbanStore) -> dict[str, Any]:
    """Explicitly replace demo-owned cards with the current repository template."""
    removed = remove(store)["removed"]
    loaded = load(store)
    return {"removed": removed, "created": loaded["created"], "status": loaded["status"]}
