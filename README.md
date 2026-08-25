# Simple Kanban

A self-reliant ranked List/Kanban working queue for [protoAgent](https://github.com/protoLabsAI/protoAgent).

Status: **v0.1.0 development candidate**. Linux source qualification is complete; S1-dev live review is the next acceptance gate. S1-stable and Windows are not yet qualified.

## What it provides

- Native primary-rail **Kanban** view with Board and List modes.
- Five durable states: Open, In progress, Blocked, Deferred, and Closed.
- Atomic same-column rank and cross-column move operations.
- Individually collapsible vertical status columns with the layout preference retained in the browser.
- Drag/drop plus status selectors and earlier/later controls for keyboard, screen-reader, and mobile fallback.
- Create, edit, move, close, reopen, and delete controls.
- Exact, small `card_id` labels on cards and in List mode for direct agent lookup.
- Non-destructive **Archive all** for Closed cards plus a read-only Archived view.
- Search, optimistic move display, stale-write conflict detection, rollback, and authoritative refresh.
- Eight namespaced agent tools, including exact-card lookup and bulk Closed archival.
- Plugin-owned SQLite state under the active protoAgent instance root; no core schema edits or private plugin imports.
- A `simple_kanban.changed` event hint after committed mutations.

This is deliberately separate from protoAgent core Tasks and the Project Board coding-orchestration plugin. It is a lightweight daily queue, not a repository orchestration system.

## Compatibility

- protoAgent `>=0.147.0`
- Python `>=3.11`
- No third-party runtime dependencies beyond libraries provided by the host

The selected v0.147.0 host documents `infra.paths.instance_paths()` as its instance-store invariant. Simple Kanban uses that exact host seam and keeps its database at `simple_kanban/simple_kanban.db` under the active instance root. Upstream issue #1 remains open for an explicit long-term external-plugin persistence contract.

## Install

```sh
python -m server plugin install https://github.com/RomeoRaven/simple-kanban-plugin --ref <exact-ref>
```

CLI installation is fetch-only. Enable `simple_kanban` explicitly in the selected instance's `plugins.enabled`, then restart or reload that instance. Git installation records the resolved commit in `plugins.lock`.

## Development

```sh
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt ruff
.venv/bin/ruff check .
.venv/bin/ruff format --check tests/
.venv/bin/pytest -q
```

## Data model

Each task owns a stable ID, title, description, status, dense per-status position, optimistic-concurrency version, priority, issue type, assignee, lifecycle timestamps, close/archive metadata, and optional source identity. Every move runs in one SQLite transaction and renumbers affected columns before commit. Archival is distinct from deletion: it atomically timestamps every active Closed card, keeps the complete records addressable by `card_id`, and removes them from the active Board/List.

## Platform status

| Platform | Status | Evidence / follow-up |
|---|---|---|
| Linux source | Tested | Store/API/registration/concurrency tests, Ruff, manifest and JS syntax checks |
| S1-dev | Pending live acceptance | Exact candidate deployment and Dennis review |
| S1-stable | Not deployed | Requires Dennis acceptance and separate promotion |
| Windows | Not tested | Deferred; no PC1 work in this tranche |

## License

MIT
