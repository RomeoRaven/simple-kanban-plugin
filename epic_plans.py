"""Schema-free Epic plan parsing and derived completion state."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_CARD_TOKEN = re.compile(r"\[\[(kanban-[^\]\s]+)\]\]", re.IGNORECASE)
_HEADING = re.compile(r"^\s*##\s+(.+?)\s*$")
_BULLET = re.compile(r"^\s*[-*]\s+(.*?)\s*$")
_CHECKBOX = re.compile(r"^\[([ xX])\]\s*(.*?)\s*$")
_SECTION_NAMES = {
    "child tasks": "children",
    "related cards": "related",
    "deferred follow-up": "deferred",
}


@dataclass(frozen=True)
class InlineTask:
    text: str
    complete: bool


@dataclass(frozen=True)
class EpicPlan:
    child_refs: tuple[tuple[str, str], ...]
    inline_tasks: tuple[InlineTask, ...]
    related_refs: tuple[tuple[str, str], ...]


def compact_card_id(card_id: str) -> str:
    return f"K-{card_id.removeprefix('kanban-')[:8].upper()}"


def _note(text: str) -> str:
    without_checkbox = _CHECKBOX.sub(lambda match: match.group(2), text, count=1)
    without_refs = _CARD_TOKEN.sub("", without_checkbox)
    return without_refs.strip(" \t—–-:")


def parse_epic_plan(description: str) -> EpicPlan:
    """Parse only explicit H2 plan sections; prose and later sections stay inert."""
    section: str | None = None
    child_refs: list[tuple[str, str]] = []
    related_refs: list[tuple[str, str]] = []
    inline_tasks: list[InlineTask] = []
    seen_children: set[str] = set()
    seen_related: set[str] = set()

    for line in description.splitlines():
        heading = _HEADING.match(line)
        if heading:
            section = _SECTION_NAMES.get(heading.group(1).strip().casefold())
            continue
        bullet = _BULLET.match(line)
        if not bullet or section not in {"children", "related"}:
            continue
        content = bullet.group(1)
        refs = [match.casefold() for match in _CARD_TOKEN.findall(content)]
        note = _note(content)
        if section == "children":
            if refs:
                for card_id in refs:
                    if card_id not in seen_children:
                        child_refs.append((card_id, note))
                        seen_children.add(card_id)
                continue
            checkbox = _CHECKBOX.match(content)
            if checkbox:
                inline_tasks.append(InlineTask(checkbox.group(2).strip(), checkbox.group(1).casefold() == "x"))
        elif refs:
            for card_id in refs:
                if card_id not in seen_related:
                    related_refs.append((card_id, note))
                    seen_related.add(card_id)

    return EpicPlan(tuple(child_refs), tuple(inline_tasks), tuple(related_refs))


def summarize_epic_plan(task: dict[str, Any], cards: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Resolve an Epic description into non-persisted child/relationship state."""
    plan = parse_epic_plan(str(task.get("description") or ""))
    task_id = str(task.get("id") or "")
    child_cards: list[dict[str, Any]] = []
    broken = 0
    open_children = 0

    for card_id, note in plan.child_refs:
        linked = cards.get(card_id)
        problem = "self_reference" if card_id == task_id else ("missing" if linked is None else "")
        if problem:
            broken += 1
        is_open = bool(not problem and linked and linked.get("status") != "closed")
        if is_open:
            open_children += 1
        child_cards.append(
            {
                "kind": "card",
                "card_id": card_id,
                "compact_id": compact_card_id(card_id),
                "title": linked.get("title", "") if linked else "",
                "status": linked.get("status", "missing") if linked else "missing",
                "archived": bool(linked and linked.get("archived_at")),
                "open": is_open,
                "problem": problem,
                "note": note,
            }
        )

    inline = []
    for item in plan.inline_tasks:
        if not item.complete:
            open_children += 1
        inline.append({"kind": "inline", "text": item.text, "complete": item.complete, "open": not item.complete})

    related_cards = []
    for card_id, note in plan.related_refs:
        linked = cards.get(card_id)
        related_cards.append(
            {
                "card_id": card_id,
                "compact_id": compact_card_id(card_id),
                "title": linked.get("title", "") if linked else "",
                "status": linked.get("status", "missing") if linked else "missing",
                "archived": bool(linked and linked.get("archived_at")),
                "missing": linked is None,
                "note": note,
            }
        )

    total_children = len(child_cards) + len(inline)
    completed_children = total_children - open_children - broken
    return {
        "total_children": total_children,
        "completed_children": max(0, completed_children),
        "open_children": open_children,
        "broken_references": broken,
        "related_count": len(related_cards),
        "can_close": open_children == 0 and broken == 0,
        "child_cards": child_cards,
        "inline_tasks": inline,
        "related_cards": related_cards,
    }


def blocked_message(task: dict[str, Any], summary: dict[str, Any]) -> str:
    """Return a compact deterministic mutation error for an incomplete Epic."""
    open_count = int(summary["open_children"])
    broken = int(summary["broken_references"])
    reasons = []
    if open_count:
        reasons.append(f"{open_count} open child task{'s' if open_count != 1 else ''}")
    if broken:
        reasons.append(f"{broken} broken child reference{'s' if broken != 1 else ''}")
    return f"Epic cannot close or archive: {task.get('title', task.get('id', 'Epic'))} has " + " and ".join(reasons)
