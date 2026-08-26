# Opt-in demonstration board

Simple Kanban ships a versioned demonstration template at `examples/demo-board.json`. It is inert repository content until an operator explicitly loads it from the **Demo** dialog or calls the authenticated demo API.

## Purpose

The eight example cards demonstrate:

- task, bug, feature, chore, and Epic types;
- Open, In progress, Blocked, Deferred, and Closed statuses;
- varied priorities and assignees;
- manual per-status ranking;
- full durable card references rendered as compact chips;
- an incomplete Epic with one Closed linked child, one In-progress linked child, one Open linked child, one unchecked inline task, two non-blocking Related cards, Deferred follow-up, and Acceptance sections.

The example Epic is intentionally incomplete so its progress and server-side completion guard remain visible.

## Ownership boundary

Every example has:

```text
source_kind = simple-kanban-demo
source_id   = <stable per-example key>
```

Demo management selects only the exact `simple-kanban-demo` source namespace. It never uses title prefixes for ownership and never selects ordinary cards. Titles retain `DEMO ·` so operators can visually distinguish examples from real work.

The database remains instance-owned. The template does not include copied `kanban-…` IDs. On first load, ordinary and child cards are created first; their generated durable IDs are then substituted into the Epic description.

## Lifecycle

### Load

**Load demo** creates only missing source IDs. It is idempotent and preserves existing demo titles, descriptions, statuses, ranks, assignments, archives, and other edits. If all eight source IDs already exist, it creates nothing.

A partial demo remains operator-owned. Load fills missing source IDs but does not rewrite an existing Epic or reconcile edits. Use Reset when the intent is to return all examples to the installed template.

### Reset

**Reset demo** is destructive only within the demo namespace. After a plugin-owned confirmation dialog, it deletes every active or archived `simple-kanban-demo` card and recreates all eight cards from the currently installed template. Generated durable IDs therefore change, and edits to demo cards are lost.

### Remove

**Remove demo** is destructive only within the demo namespace. After confirmation, it deletes all active and archived demo cards. Ordinary cards and their ranks remain intact except for normal rank compaction after removed demo cards.

Cancel or Escape from either confirmation makes no mutation request.

## Plugin update behavior

Installing or updating Simple Kanban:

- updates the bundled repository template;
- does not load examples automatically;
- does not modify already-loaded demo cards;
- does not overwrite the plugin-owned SQLite database;
- does not duplicate examples on restart or update.

After an update, Load remains non-destructive and only adds missing source IDs. Reset is the explicit operation that replaces demo-owned state with the new installed template.

## Authenticated API

The UI uses these plugin routes:

```text
GET    /api/plugins/simple_kanban/demo
POST   /api/plugins/simple_kanban/demo/load
POST   /api/plugins/simple_kanban/demo/reset
DELETE /api/plugins/simple_kanban/demo
```

`GET /demo` reports the template version, expected and present counts, completeness, missing source IDs, and current demo cards. Load, Reset, and Remove report mutation counts and the resulting status.

The same-origin protoAgent authentication and Origin policy used by the task API apply. These endpoints are not an installation hook or migration path.

## Template evolution

When changing `examples/demo-board.json`:

1. Preserve `source_kind=simple-kanban-demo`.
2. Preserve a source ID when the example represents the same conceptual card.
3. Add a new stable source ID for a genuinely new example.
4. Keep the Epic last logically so referenced cards exist before description substitution.
5. Keep placeholders in the exact `{{key}}` form and ensure each key names another template card.
6. Update tests and this document when the denominator, behavior, or safety boundary changes.
7. Never add automatic install, startup, or update seeding.
