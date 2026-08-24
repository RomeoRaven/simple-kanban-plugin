# Contributing

Simple Kanban is an external protoAgent plugin. Contributions should keep it self-reliant and installable on an unmodified supported protoAgent host.

Before submitting a change:

1. Read `README.md` and `docs/PLAN.md`.
2. Use only documented host contracts; do not import another plugin or write a core database.
3. Keep task status and rank changes atomic.
4. Preserve optimistic-concurrency checks, keyboard/mobile fallbacks, and slug-aware authenticated API calls.
5. Run:

```sh
ruff check .
ruff format --check tests/
pytest -q
```

Open design and compatibility questions belong in GitHub Issues before broadening the public contract.
