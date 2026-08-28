# Kanban plugin — extraction specification

Status: v0.3.0 accepted release candidate on S1 Stable; Windows remains unqualified
Date: 2026-08-27
Source behavior: accepted public v0.2.0 at `aee5236c93b691bee62c78294aafc6c991c041e8`
Target host reviewed: official protoAgent `v0.153.1`
Placement: external plugin (`new with reuse`)

## Decision

Create a standalone Kanban plugin if we want our ranked task queue without maintaining a protoAgent fork. It owns its records, ordering, tools, API, events, and Kanban/List view. It installs beside stock core and does not patch or replace native Tasks.

The existing upstream `projectBoard-plugin` was checked first. It is a different product: coding orchestration over beads, ACP coders, git worktrees, PRs, review gates, and a six-state project board. It is not a substitute for a lightweight operator-agent task queue.

## Product boundary

The plugin is the agent's immediate working queue:

- lightweight tasks, bugs, features, chores, and epics;
- List and Kanban views over the same records;
- manual backlog order within each status;
- operator and agent share one order;
- no git, GitHub, beads, coder delegation, PR, or Ready-for-Done machinery.

It may coexist with native Tasks and Project Board. It must use a distinct product name, plugin id, routes, tool names, and event topics so there is no accidental cross-write.

Product name: `Kanban`.

Repository: `simple-kanban-plugin`.

Plugin id: `simple_kanban`.

## Behavior extracted from the accepted candidate

### Record contract

- `id`;
- `title`, `description`;
- `status`;
- `position` scoped to status;
- integer `version` for stale-write detection;
- `priority` separate from position;
- `issue_type`, `assignee`;
- `created_at`, `updated_at`;
- `closed_at`, `close_reason`;
- `archived_at` for non-destructive removal from the active board;
- optional source/import metadata.

Default statuses: `open`, `in_progress`, `blocked`, `deferred`, `closed`.

### Ordering and transition rules

- New tasks append to the bottom of Open.
- Manual rank is local to one status column.
- Priority never silently reorders a groomed queue.
- Clients submit placement intent (`destination_status`, `before_id`, `expected_version`), never raw positions.
- Same-column reorder and cross-column status movement are one transactional operation.
- Existing non-positional status changes append to the destination.
- Closing sets terminal metadata; reopening clears stale close metadata.
- Deletion renumbers the affected column.
- Stale versions return a conflict without overwriting newer work.
- Agent listing uses the same ranked order as the operator view.
- Archive-all affects only active Closed cards, preserves complete records, and is idempotent.

### Interaction rules

- Dedicated drag handle for pointer/touch movement.
- Exact before/after insertion marker and drag overlay.
- Earlier/later controls for non-drag ranking.
- Status selector remains the keyboard, screen-reader, and mobile fallback.
- Optimistic UI serializes local moves, rolls back failures, explains conflicts, and reloads authoritative state.
- Cards, buttons, menus, and board scrolling remain usable while drag is enabled.
- Every vertical status column can collapse to a slim persisted rail without changing card state.
- One persisted Board-wide Condensed toggle hides descriptions, metadata, and lifecycle actions so each card keeps its drag handle, compact copyable ID, clickable edit title, and earlier/later controls; List and Archived views remain unchanged.
- Every card displays a compact `K-XXXXXXXX` reference beside a copy control for the exact durable `card_id`; agents can resolve either a unique compact reference or the copied full ID directly.
- Epic cards keep plans in the existing description using exact Child tasks, Related cards, and Deferred follow-up sections; no relationship schema is added.
- Linked child status, inline checkboxes, related counts, and reference integrity are derived at read time.
- A purple text-labeled EPIC indicator remains visible across Board, Condensed, List, and Archived views.
- Store-level guards reject incomplete Epic closure and atomically reject bulk archival when a legacy Closed Epic is still incomplete.
- Destructive UI actions use a plugin-owned accessible confirmation dialog; sandbox-dependent browser-native dialogs are not part of the contract.
- A versioned repository demo template is inert by default and can be explicitly loaded, reset, or removed only within its exact source namespace.

## Self-reliant architecture

```text
simple-kanban-plugin/
  protoagent.plugin.yaml
  __init__.py
  store.py
  demo.py
  api.py
  tools.py
  view/
    tasks.html
    tasks.js
    tasks.css
  examples/demo-board.json
  skills/simple-kanban/SKILL.md
  tests/
  README.md
```

### Storage

- Start from the selected protoAgent revision's Plugin DevKit scaffold, plugin guide, SDK, and maker-owned persistence examples; do not infer a database convention from a prior plugin or private core implementation.
- protoAgent has multiple per-instance stores, not one central SQLite schema for plugins to extend.
- Plugin-owned SQLite database with WAL, busy timeout, guarded schema migrations, and atomic transactions.
- Use only a documented per-instance persistence-path seam supported by the target host. If the selected host revision exposes no such public seam, treat that as a compatibility blocker rather than importing a private path helper or inventing a fixed path.
- Runtime state stays outside the installed plugin source directory.
- The plugin owns its schema, migrations, transactions, backup, recovery, and retention.
- No imports from core `tasks.store`, no reads of core `issues.db`, no plugin tables in a core database, and no schema patching of native Tasks.
- Interoperate with native Tasks and other plugins only through documented APIs, SDK functions, tools, and events—not shared SQLite access.

### Plugin API

Gated plugin-owned routes under `/api/plugins/simple_kanban`:

- list/get/create/update/delete;
- close/reopen;
- atomic move/reorder;
- bulk Closed archival and archived-card listing;
- opt-in demonstration status/load/reset/remove operations scoped to `simple-kanban-demo`;
- optional one-time import preview/execute.

Public page route: `/plugins/simple_kanban/view`.

### Agent tools

Distinct names avoid collisions with core tools and future official plugins:

- `simple_kanban_task_create`;
- `simple_kanban_task_list`;
- `simple_kanban_task_get`;
- `simple_kanban_task_update`;
- `simple_kanban_task_move`;
- `simple_kanban_task_close`;
- `simple_kanban_task_delete`.
- `simple_kanban_closed_archive`.

A bundled skill tells the agent when to use Kanban versus Project Board or native Tasks. Host configuration may prefer these tools, but the plugin must not require removal of core tools.

### Events

Emit a documented plugin-owned topic such as `simple_kanban.changed`. The iframe subscribes through the standard event bridge and reconciles from the plugin API. Do not publish `task.changed` or impersonate core.

### View

- Standalone rail view declared in `protoagent.plugin.yaml`.
- Sandboxed iframe; no host rebuild.
- Host bearer/theme handshake and fleet-slug-aware `plugin-kit.apiFetch`.
- Host design-system tokens/components from `/_ds/plugin-kit.*`.
- Plugin-owned List/Kanban rendering and DnD implementation.
- No dependency on fork-only Focus or a private native Tasks slot.

## Reuse from core and prior work

Reuse public platform capability:

- plugin manifest/loader/lifecycle;
- routes, tools, skills, settings, and event bus;
- plugin view handshake, auth, fleet proxy support, and design-system kit;
- standard SQLite/runtime-path conventions exposed for the selected host;
- DevKit scaffold, vendored testkit, install/update/lock workflow.

Reuse the accepted candidate's proven domain rules and test cases by porting them into plugin-owned modules. Do not copy imports from native `TasksPanel`, React Query state, `tasks.store`, operator routes, or private console utilities.

## Optional migration from native Tasks

Migration is explicit and reversible:

1. Read native records through documented `GET /api/tasks/issues` only.
2. Show an import preview and collision count.
3. Copy records into the plugin store, preserving source ids as metadata where useful.
4. Deterministically backfill positions and versions.
5. Never delete or modify native Tasks during import.
6. Make repeat imports idempotent or require an explicit duplicate policy.

Native Tasks remains the rollback source until the operator separately archives it.

## Compatibility reality

Stock upstream `v0.147.0` provides native Tasks CRUD but not the accepted candidate's durable rank/version/move contract. A self-reliant plugin therefore cannot use native Tasks as its write store and still guarantee ranking. Owning a separate store is the clean no-core-change solution.

The plugin cannot invisibly replace the native Work → Tasks panel through the documented plugin contract. It will have its own rail icon/view. That visible separation is preferable to a private console override or fork seam.

## Extraction map from the accepted candidate

- `tasks/store.py` → plugin-owned `store.py` semantics and migration tests.
- `operator_api/routes.py` → plugin-owned `api.py`, namespaced routes only.
- `tools/lg_tools.py` → plugin-owned, collision-free agent tools.
- `TasksPanel.tsx`, `tasks.ts`, `theme.css` → plugin-owned iframe HTML/JS/CSS using the DS kit.
- Tasks unit/E2E tests → plugin host-free store/API tests plus live plugin-view tests.
- `docs/plans/tasks-ranking-drag-drop.md` → product invariants and acceptance contract.

## Definition of Done

1. Re-check current upstream core and existing task/board plugins before implementation.
2. Scaffold a standalone repository from the current maker-owned Plugin DevKit.
3. Install and run on an unmodified upstream-compatible host.
4. Prove CRUD, atomic cross-column movement, same-column ranking, stale conflicts, persistence, restart, concurrent writes, and migration recovery.
5. Prove operator/agent order parity, events, optimistic rollback, keyboard, pointer, touch, narrow layout, theme switching, fleet proxy, and error states.
6. Prove native Tasks and Project Board remain untouched and usable.
7. Prove install, enable, update, disable, uninstall, backup, and restore.
8. Publish with immutable tags, compatibility metadata, documentation, and exact GitHub topic `protoagent-plugin`.
9. Qualify on isolated S1 development; route native Windows qualification to PLA/PC1 afterward.
