from __future__ import annotations

import importlib
from pathlib import Path

import yaml


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
    assert 'node("code","card-id",`card_id: ${task.id}`)' not in html
    assert 'return `K-${cardId.replace(/^kanban-/i,"").slice(0,8).toUpperCase()}`' in html
    assert "Copy full card_id ${shortId}" in html
    assert "copy.dataset.copyId=task.id" in html
    assert "navigator.clipboard?.writeText" in html
    assert 'document.execCommand("copy")' in html
    assert "cardIdCell.append(cardIdControl(task))" in html
    assert 'localStorage.getItem("simple-kanban.collapsed")' in html
    assert 'localStorage.setItem("simple-kanban.collapsed"' in html
    assert "writing-mode:vertical-rl" in html
    assert (
        ".column.collapsed .column-head{flex:1;min-height:180px;padding:8px 5px;flex-direction:column;justify-content:flex-start}"
        in html
    )
    assert ".column.collapsed .column-controls{flex-direction:column;order:-1}" in html
    assert 'id="condensed-mode"' in html
    assert 'localStorage.getItem("simple-kanban.condensed") === "true"' in html
    assert 'localStorage.setItem("simple-kanban.condensed",String(state.condensed))' in html
    assert 'board${state.condensed?" condensed":""}' in html
    assert (
        ".board.condensed .card-description,.board.condensed .epic-links,.board.condensed .meta,.board.condensed .card-actions{display:none}"
        in html
    )
    assert 'title.dataset.action="edit"' in html
    assert 'node("div","condensed-rank-actions")' in html
    assert ".board.condensed .condensed-rank-actions{display:flex" in html
    assert 'document.getElementById("condensed-mode").disabled=state.archived||state.mode!=="board"' in html
    assert "Archive all ${count} Closed cards" in html
    assert "Confirm archive all ${count} Closed cards" in html
    assert "archiveConfirmUntil" in html
    assert 'request("/tasks/archive-closed"' in html
    assert 'request(state.archived?"/tasks?archived=true":"/tasks")' in html
    assert "epic-badge" in html
    assert "Epic cannot close" in html
    assert "data-card-ref" in html
    assert "epicLinks" in html
    assert "--epic-purple" in html
    assert "confirm(" not in html
    assert 'id="confirm-dialog"' in html
    assert "requestConfirmation" in html
    assert 'id="demo-dialog"' in html
    assert 'id="demo-board"' in html
    assert 'request("/demo/load"' not in html  # path is selected explicitly at action time
    assert 'action==="load"?"/demo/load"' in html
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


def test_manifest_and_readme_document_complete_v030_how_to(plugin):
    root = Path(plugin.__file__).parent
    manifest = yaml.safe_load((root / "protoagent.plugin.yaml").read_text())
    readme = (root / "README.md").read_text()
    contract = (root / "docs" / "EPIC_PLANS.md").read_text()
    assert manifest["version"] == "0.3.1"
    for heading in (
        "## How to use Simple Kanban",
        "## How to use Epic plans",
        "### Epic syntax contract",
        "### Close and archive protection",
        "## Agent tools",
    ):
        assert heading in readme
    assert "v0.3.1 adds no table, column, or migration" in readme
    assert "Only exact level-two headings are interpreted" in contract
