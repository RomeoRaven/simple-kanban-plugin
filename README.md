# Simple Kanban

A self-reliant ranked List/Kanban working queue for [protoAgent](https://github.com/protoLabsAI/protoAgent).

Status: **v0.3.1 malformed-reference hotfix candidate**. v0.3.0 passed source, S1-dev, and S1-stable acceptance on official protoAgent v0.153.1; this hotfix makes malformed intended Epic child references fail closed. Windows and macOS remain untested.

## What it provides

- Native primary-rail **Kanban** view with Board, List, and Archived modes.
- Five durable states: Open, In progress, Blocked, Deferred, and Closed.
- Atomic same-column ranking and cross-column movement.
- Drag/drop plus status selectors and earlier/later controls for keyboard, screen-reader, and mobile use.
- Individually collapsible status columns and a browser-persisted Board-wide **Condensed** mode.
- Create, edit, move, close, reopen, delete, and non-destructive bulk archival.
- Compact `K-XXXXXXXX` references with one-click copy of the complete durable `kanban-…` ID.
- Purple **EPIC** cards with schema-free Markdown plans, child-task progress, related-card references, and server-enforced close/archive protection.
- Eight namespaced agent tools with optimistic-version protection.
- Plugin-owned SQLite state under the active protoAgent instance root; no core schema edits or private plugin imports.
- A `simple_kanban.changed` event hint after committed mutations.

Simple Kanban is deliberately separate from protoAgent core Tasks and the Project Board coding-orchestration plugin. It is a lightweight operator-agent queue, not a repository orchestration system.

## How to use Simple Kanban

### Open the board

Select **Kanban** from protoAgent's primary rail. The toolbar provides:

- **Board** — cards grouped into status columns.
- **List** — the same active records in ranked tabular form.
- **Condensed** — Board-only dense cards retaining identity, title, rank controls, and Epic state.
- **Archived** — read-only records removed from the active queue.
- **Refresh** — reload authoritative server state.
- **Demo** — inspect, explicitly load, reset, or remove the repository's optional example board.
- **+ Task** — create a card.

Search matches title, description, assignee, type, and full card ID.

### Create or edit a card

Select **+ Task**, or select an existing card title. Each card has:

- **Title** and **Description**.
- **Status**: Open, In progress, Blocked, Deferred, or Closed.
- **Priority**: Urgent through Someday. Priority is importance; it does not change manual rank.
- **Type**: task, bug, feature, chore, or epic.
- **Assignee**.

Save writes with optimistic concurrency. If another operator or agent changed the card first, the stale write is rejected and the board reloads rather than overwriting newer work.

### Rank and move cards

- Drag only from the card's drag handle.
- Drop before a card for exact insertion or into a column to append.
- Use the up/down controls when drag is unsuitable.
- Use the status selector as the keyboard, screen-reader, and mobile fallback.

Rank is local to each status column. A status move and its destination rank commit in one transaction.

### Reference a card

Every card displays a compact `K-XXXXXXXX` token. Its copy button copies the complete durable ID, for example:

```text
kanban-123456789abc
```

Agents should mutate by the complete ID. A unique compact token can be used for direct lookup; ambiguous compact tokens are rejected.

Inside descriptions, write a full reference as:

```markdown
[[kanban-123456789abc]]
```

The UI renders a recognized reference as a compact clickable card chip. Selecting it opens an active card or locates an archived card.

## How to use Epic plans

An Epic is a larger outcome whose plan remains ordinary text in the existing Description field. Simple Kanban does not add parent, relationship, order, or progress columns to its database.

Set **Type** to `epic`. The purple **EPIC** label distinguishes the card in Board, List, Condensed, and Archived views. The editor's **Insert epic template** action can add the supported headings.

Recommended plan:

```markdown
## Outcome

Deliver Google Workspace as an accepted AO Common capability.

## Plan

1. Establish the OAuth and scope boundary.
2. Qualify provider behavior.
3. Decide whether to include it in AO Common.

## Child tasks

- [[kanban-123456789abc]] — Define OAuth scopes
- [[kanban-23456789abcd]] — Qualify Gmail and Drive
- [ ] Write the operator acceptance notes
- [x] Record the already accepted provider boundary

## Related cards

- [[kanban-3456789abcde]] — Calendar owns human events; Google owns provider operations

## Deferred follow-up

- Consider notification integration after provider adoption

## Acceptance

- Approved OAuth boundary
- Provider behavior proven
- Inclusion decision recorded
```

### Epic syntax contract

Only these exact level-two headings have special meaning:

- `## Child tasks` — blocking work.
- `## Related cards` — non-blocking peer context.
- `## Deferred follow-up` — non-blocking future work.

Under `## Child tasks`:

- A bullet containing `[[kanban-…]]` derives completion from that card's real status. A manual checkbox beside a card reference is ignored.
- An unlinked `- [ ]` item is an open inline task.
- An unlinked `- [x]` item is a completed inline task.
- A missing, malformed, placeholder, or self-referencing child card is a broken reference.

References under `## Related cards`, prose elsewhere, and Deferred follow-up items never block completion.

### Close and archive protection

An Epic cannot enter Closed while it has:

- an Open, In progress, Blocked, or Deferred linked child card;
- an unchecked inline child task;
- a missing child-card reference; or
- a self-reference.

The guard runs in the server store, so Board drag/drop, status selection, the close button, JSON API calls, and agent tools follow the same rule. The card reports completed/total children, open children, broken references, and related-card count without persisting derived relationship data.

Bulk **Archive all** is atomic. If a legacy Closed Epic still has open or broken child items, the whole archive request is rejected and no Closed cards are archived. Resolve the child work, remove it from `## Child tasks`, or move it to a non-blocking section before retrying.

## Optional demonstration board

The repository includes `examples/demo-board.json`, an eight-card example covering all five card types, all five statuses, priorities, assignees, ranking, durable references, and an incomplete Epic with linked and inline child work.

Nothing is inserted at install, startup, or update time. Select **Demo** and then **Load demo** to opt in. The operations are namespace-scoped:

- **Load demo** creates only missing cards and preserves every existing demo edit.
- **Reset demo** requires confirmation, removes only `source_kind=simple-kanban-demo` cards, and recreates them from the currently installed template.
- **Remove demo** requires confirmation and deletes only that exact demo namespace, including archived examples.
- Ordinary user cards are never selected by title or prefix and are not changed by any demo operation.

Stable per-example `source_id` values make Load idempotent. Generated durable card IDs are inserted into the Epic after its child and related cards exist; IDs are never copied from another installation. Updating the plugin updates the bundled template but does not mutate already-loaded demo cards. Use **Reset demo** only when you deliberately want the installed template to replace demo edits.

See [`docs/DEMO_BOARD.md`](docs/DEMO_BOARD.md) for the complete lifecycle and API contract.

## Close, reopen, archive, and delete

- **Close** preserves terminal time and reason.
- **Reopen** returns the card to Open and clears stale close metadata.
- **Archive all** requires a second click and moves every eligible active Closed card into Archived without deleting records.
- **Delete** opens a plugin-owned confirmation dialog, then permanently removes one card and repairs the affected column rank. Cancel or Escape makes no request. Prefer Close/Archive for completed work.

Archived cards remain addressable by exact ID but are read-only.

## Agent tools

- `simple_kanban_task_create`
- `simple_kanban_task_list`
- `simple_kanban_task_get`
- `simple_kanban_task_update`
- `simple_kanban_task_move`
- `simple_kanban_task_close`
- `simple_kanban_task_delete`
- `simple_kanban_closed_archive`

Agents should list/get first, preserve the returned `version`, and pass it as `expected_version` on every mutation. Epic close/archive guards apply to tools exactly as they do to the UI.

## Compatibility

- protoAgent `>=0.147.0`
- Python `>=3.11`
- No third-party runtime dependencies beyond host-provided libraries

The selected host documents `infra.paths.instance_paths()` as its instance-store invariant. Simple Kanban keeps its database at `simple_kanban/simple_kanban.db` under the active instance root. Upstream issue #1 remains open for a long-term external-plugin persistence contract.

## Install

```sh
python -m server plugin install https://github.com/RomeoRaven/simple-kanban-plugin --ref <exact-ref>
```

Installation is fetch-only. Add `simple_kanban` to the selected instance's `plugins.enabled`, then restart or reload that instance. Git installation records the resolved commit in `plugins.lock`.

## Development

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/ruff check .
.venv/bin/ruff format --check .
.venv/bin/pytest -q
node --check view/board.js
```

## Data model

Each task owns a stable ID, title, description, status, dense per-status position, optimistic-concurrency version, priority, issue type, assignee, lifecycle timestamps, close/archive metadata, and optional source identity. Every move runs in one SQLite transaction.

Epic structure remains text in `description`. Child and related references, inline checkboxes, progress, and completion eligibility are parsed and resolved at read/mutation time; v0.3.1 adds no table, column, or migration.

## Platform status

| Platform | Status | Evidence / follow-up |
|---|---|---|
| Linux source | Tested | 35 store/API/parser/registration/concurrency tests, Ruff, formatting, manifest, and JS syntax |
| S1-dev | Tested | Exact candidate deployment, desktop/mobile collapse behavior, persistence, health, and restart acceptance on protoAgent v0.153.1 |
| S1-stable | v0.3.0 tested | Exact v0.3.0 deployment and operator acceptance on protoAgent v0.153.1; v0.3.1 promotion follows hotfix review and release |
| Windows | Not tested | Route only an accepted candidate to PC1/PLA |

## License

MIT
