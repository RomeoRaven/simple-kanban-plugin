# Epic plan contract

Status: v0.3.1 candidate

## Purpose

Simple Kanban Epic plans organize work larger than one ordinary card without adding hierarchy or relationship fields to the plugin database. The Epic's existing `description` remains the durable plan document. Linked-card state is resolved from existing cards when the Epic is read, closed, or archived.

## Recognized syntax

Only exact level-two headings are interpreted:

```markdown
## Child tasks
## Related cards
## Deferred follow-up
```

All other headings and prose are ordinary description content.

### Child tasks

A bulleted full card reference is a linked child:

```markdown
- [[kanban-123456789abc]] — Explain the child outcome
```

The linked card's real status is authoritative. It blocks Epic completion unless its status is `closed`. Archived Closed children count as complete.

An unlinked Markdown checkbox is an inline child:

```markdown
- [ ] Open inline task
- [x] Completed inline task
```

If a child bullet contains a card reference, any checkbox on that same bullet is ignored to prevent manually checked text from overriding the card's real state.

Missing, malformed, placeholder, and self-referencing child IDs are broken references and block completion.

### Related cards

```markdown
- [[kanban-23456789abcd]] — Shares the provider boundary
```

Related cards are symmetric only in human meaning; the plugin does not write a reciprocal link. Their status and existence never block the Epic. Add a reciprocal reference manually when both cards need visible navigation.

### Deferred follow-up

Deferred follow-up text is intentionally non-blocking. Move an item here when it is no longer part of the Epic's accepted completion contract.

## Derived response

API and tool reads add an `epic_plan` object to Epic cards. It contains:

- total and completed child count;
- open child count;
- broken reference count;
- related-card count;
- `can_close`;
- resolved child, inline-task, and related-card details.

The object is derived and is never written to SQLite.

## Enforcement

The store rejects an Epic's transition to Closed when `can_close` is false. The same guard covers:

- creating an Epic directly in Closed;
- close operations;
- drag/status moves into Closed;
- a combined move that changes an ordinary card into an Epic;
- editing an already Closed card into an incomplete Epic;
- bulk Closed archival.

Bulk archival is atomic: one blocked legacy Epic rejects the entire operation before any record is archived.

There is no ordinary bypass. Complete the work, repair the reference, remove it from Child tasks, or move it to a non-blocking section.

## Presentation

- Epic cards and table rows retain the explicit text `EPIC` and use a purple pill; color is not the only signal.
- Board cards also receive a subtle purple edge.
- Child completion, open count, broken count, and related count are visible derived indicators.
- The Epic label and blocking state remain visible in Condensed mode.
- Full `[[kanban-…]]` references render as compact clickable `K-XXXXXXXX` chips while storage retains the complete ID.

## Deliberate non-goals

- Parent or relation database columns.
- Nested Epic trees.
- Multiple parents.
- Automatic parent status changes.
- Arbitrary relation types or dependency graphs.
- Cross-instance references.
- AI or fuzzy interpretation of prose.
