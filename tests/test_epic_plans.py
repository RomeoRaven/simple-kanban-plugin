from __future__ import annotations

import importlib


def test_parser_uses_only_exact_plan_sections(plugin):
    module = importlib.import_module(plugin.__name__ + ".epic_plans")
    first = "kanban-123456789abc"
    second = "kanban-abcdef123456"
    description = f"""Background [[{second}]]

## Child tasks

- [[{first}]] — Implement the first child
- [ ] Write the operator notes
- [x] Record the accepted boundary

## Related cards

- [[{second}]] — Shares the provider boundary

## Deferred follow-up

- [ ] This does not block the epic
"""
    parsed = module.parse_epic_plan(description)
    assert parsed.child_refs == ((first, "Implement the first child"),)
    assert parsed.inline_tasks == (
        module.InlineTask("Write the operator notes", False),
        module.InlineTask("Record the accepted boundary", True),
    )
    assert parsed.related_refs == ((second, "Shares the provider boundary"),)
    assert parsed.malformed_child_refs == ()


def test_parser_fails_closed_for_malformed_child_reference_intent(plugin):
    module = importlib.import_module(plugin.__name__ + ".epic_plans")
    malformed = ("[[kanban-]]", "[[kanban-bad id]]", "[[not-a-kanban-id]]", "[[kanban-123456789abc]")
    for value in malformed:
        description = f"## Child tasks\n- {value} — Intended child"
        parsed = module.parse_epic_plan(description)
        summary = module.summarize_epic_plan(
            {"id": "kanban-eeeeeeeeeeee", "issue_type": "epic", "description": description}, {}
        )
        assert parsed.malformed_child_refs
        assert summary["broken_references"] == 1
        assert summary["total_children"] == 1
        assert summary["can_close"] is False


def test_summary_resolves_children_and_never_treats_related_as_blocking(plugin):
    module = importlib.import_module(plugin.__name__ + ".epic_plans")
    epic_id = "kanban-eeeeeeeeeeee"
    child_id = "kanban-111111111111"
    related_id = "kanban-222222222222"
    task = {
        "id": epic_id,
        "issue_type": "epic",
        "description": f"## Child tasks\n- [[{child_id}]] — Child\n\n## Related cards\n- [[{related_id}]] — Peer",
    }
    cards = {
        child_id: {"id": child_id, "title": "Child", "status": "closed", "archived_at": None},
        related_id: {"id": related_id, "title": "Peer", "status": "open", "archived_at": None},
    }
    summary = module.summarize_epic_plan(task, cards)
    assert summary["can_close"] is True
    assert summary["total_children"] == 1
    assert summary["open_children"] == 0
    assert summary["related_count"] == 1
    assert summary["related_cards"][0]["status"] == "open"
