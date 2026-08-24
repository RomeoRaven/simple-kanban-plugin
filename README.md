# simple-kanban-plugin

Design stub for **Kanban**, a self-reliant ranked task-board plugin for [protoAgent](https://github.com/protoLabsAI/protoAgent).

Status: **design review only**. The repository contains an importable Plugin DevKit scaffold and the proposed implementation plan; it does not yet provide the planned task store or Kanban workflow.

## Why it exists

Kanban is intended to provide a lightweight operator-and-agent task queue with durable manual ranking, List/Kanban views, and accessible card movement without changing protoAgent core. It is deliberately separate from the upstream Project Board coding-orchestration plugin.

## Review the proposal

Read [`docs/PLAN.md`](docs/PLAN.md). Feedback is welcome through [GitHub Issues](https://github.com/RomeoRaven/simple-kanban-plugin/issues).

## Current stub

The scaffold follows the upstream protoAgent Plugin DevKit contract and contributes only:

- a placeholder console view;
- `simple_kanban_status`, which reports that implementation is pending;
- host-free scaffold tests and CI.

## Compatibility

Design target: protoAgent `v0.147.0` or later. No release or production compatibility claim is made yet.

## Platform status

| Platform | Status | Evidence / follow-up |
|---|---|---|
| Linux | Tested | Host-free scaffold tests only |
| Windows | Not tested | Native qualification after implementation |
| macOS | Not tested | Qualification after implementation |

## License

MIT
