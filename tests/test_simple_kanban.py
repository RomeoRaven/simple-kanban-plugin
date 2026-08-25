from __future__ import annotations

import importlib


def test_registers_complete_plugin(plugin, registry):
    plugin.register(registry)
    assert [tool.name for tool in registry.tools] == [
        "simple_kanban_task_create",
        "simple_kanban_task_list",
        "simple_kanban_task_get",
        "simple_kanban_task_update",
        "simple_kanban_task_move",
        "simple_kanban_task_close",
        "simple_kanban_task_delete",
        "simple_kanban_closed_archive",
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
    assert "required?load({quiet,required}):false" in html
    assert "required:true" in html
    assert 'if(state.moving){message("A task change is already saving")' in html
    assert "color-scheme:light dark" in html
    assert "if(state.saving||state.moving)return" in html
    assert "state.moving=true;render();setDialogSaving(true)" in html
    assert "needsRefresh:false" in html
    assert "if(!state.needsRefresh)state.moving=false" in html
    assert "item.status===task.status" in html
    assert "error.status&&error.status<500" in html
    assert "Save response lost; board reconciled" in html
    assert "if(dialog.open)dialog.close();setDialogSaving(false)" in html
    assert "error.status===409||(id&&error.status===404)" in html
    assert "Save target changed; board reloaded." in html
    assert "(!dialog.open||state.needsRefresh)" in html
    assert "loaded:false" in html
    assert "if(required||!state.loaded)" in html
    assert 'setAttribute("aria-label",title)' in html
    assert (
        'actionButton("earlier",capability.earlier?"Move up":"Already first in column","up",!capability.earlier)'
        in html
    )
    assert 'actionButton("edit","Edit task","edit")' in html
    assert 'actionButton("delete","Delete task","delete")' in html
    assert "rankCapabilities(task)" in html
    assert "rank-badge" in html
    assert ".icon-button svg" in html
    assert "card_id: ${task.id}" in html
    assert 'localStorage.getItem("simple-kanban.collapsed")' in html
    assert 'localStorage.setItem("simple-kanban.collapsed"' in html
    assert "writing-mode:vertical-rl" in html
    assert "Archive all ${count} Closed cards" in html
    assert 'request("/tasks/archive-closed"' in html
    assert 'request(state.archived?"/tasks?archived=true":"/tasks")' in html
    assert (
        "filteredTasks().sort((a,b)=>STATUSES.indexOf(a.status)-STATUSES.indexOf(b.status)||a.position-b.position)"
        in html
    )


def test_event_is_namespaced_by_registry(plugin, registry, tmp_path):
    plugin.register(registry)
    events = importlib.import_module(plugin.__name__ + ".events")
    events.emit_changed("created", {"id": "k-1", "status": "open", "version": 1})
    assert registry.emitted[-1] == (
        "changed",
        {"action": "created", "task_id": "k-1", "status": "open", "version": 1},
    )
