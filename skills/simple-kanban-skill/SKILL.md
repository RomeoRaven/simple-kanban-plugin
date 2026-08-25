---
name: simple-kanban
description: Use for the operator's ranked Simple Kanban working queue.
summary: Use for the operator's ranked Simple Kanban working queue.
---

# Simple Kanban

Use the `simple_kanban_*` tools when the operator wants a lightweight ranked working queue separate from core project tracking.

## Rules

- List first when an existing task might already represent the work.
- When the operator supplies a visible compact `K-XXXXXXXX` reference or a copied full `card_id`, call `simple_kanban_task_get` rather than guessing from titles. A compact collision is rejected instead of guessed.
- Preserve the returned `version`; pass it as `expected_version` on every update, move, close, or delete.
- Treat `priority` as importance and the server-owned per-status position as manual rank. Never emulate rank by changing priority.
- Use `simple_kanban_task_move` for both same-column reorder and cross-column status changes. Leave `before_id` blank to append.
- On a stale-version conflict, list again and ask only when the operator's intent is no longer unambiguous.
- Close rather than delete completed work unless the operator explicitly wants removal.
- Use `simple_kanban_closed_archive` only when the operator wants every active Closed card archived. Archival preserves records and exact IDs; deletion does not.

## Tools

- `simple_kanban_task_create`
- `simple_kanban_task_list`
- `simple_kanban_task_get`
- `simple_kanban_task_update`
- `simple_kanban_task_move`
- `simple_kanban_task_close`
- `simple_kanban_task_delete`
- `simple_kanban_closed_archive`
