"""Host-free smoke tests for the Kanban design stub."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def test_register_runs_host_free(plugin, registry):
    plugin.register(registry)
    assert [tool.name for tool in registry.tools] == ["simple_kanban_status"]
    assert len(registry.routers) == 2


def test_manifest_and_plan_are_present():
    manifest = yaml.safe_load((ROOT / "protoagent.plugin.yaml").read_text(encoding="utf-8"))
    assert manifest["id"] == "simple_kanban"
    assert manifest["version"] == "0.0.0"
    assert manifest["repository"].endswith("/simple-kanban-plugin")
    assert (ROOT / "docs" / "PLAN.md").is_file()
