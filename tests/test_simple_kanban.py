from __future__ import annotations

import importlib


def test_registers_complete_plugin(plugin, registry):
    plugin.register(registry)
    assert [tool.name for tool in registry.tools] == [
        "simple_kanban_task_create",
        "simple_kanban_task_list",
        "simple_kanban_task_update",
        "simple_kanban_task_move",
        "simple_kanban_task_close",
        "simple_kanban_task_delete",
    ]
    assert registry.skill_dirs == ["skills"]
    assert [prefix for prefix, _router in registry.routers] == [
        "/plugins/simple_kanban",
        "/api/plugins/simple_kanban",
    ]


def test_view_is_single_slug_aware_page(plugin):
    html = plugin._view_html()
    assert "Kanban" in html
    assert "window.__base=location.pathname.split('/plugins/')[0]" in html
    assert "kit.apiFetch" in html
    assert "/api/plugins/simple_kanban" in html
    assert "{{CSS}}" not in html
    assert "{{JS}}" not in html
    assert "http://localhost" not in html
    assert "Authorization" not in html
    assert 'event.preventDefault(); event.stopPropagation(); article.classList.remove("drop-before")' in html
    assert "moving:false" in html
    assert "updates:payload" in html
    assert 'type:"protoagent:subscribe",patterns:["simple_kanban.changed"]' in html
    assert 'event.data.topic==="simple_kanban.changed"' in html
    assert "expected_version:capturedVersion" in html
    assert 'dialog.addEventListener("cancel",(event)=>{if(state.saving)event.preventDefault();})' in html
    assert 'form.querySelectorAll("input,textarea,select,button")' in html
    assert "const column=rankedTasks(task.status)" in html
    assert "generation!==loadGeneration" in html
    assert 'if(state.moving){message("A task change is already saving")' in html


def test_event_is_namespaced_by_registry(plugin, registry, tmp_path):
    plugin.register(registry)
    events = importlib.import_module(plugin.__name__ + ".events")
    events.emit_changed("created", {"id": "k-1", "status": "open", "version": 1})
    assert registry.emitted[-1] == (
        "changed",
        {"action": "created", "task_id": "k-1", "status": "open", "version": 1},
    )
