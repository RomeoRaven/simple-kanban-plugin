"use strict";
const kit = await import(window.__base + "/_ds/plugin-kit.js");
kit.initPluginView();

const STATUSES = ["open", "in_progress", "blocked", "deferred", "closed"];
const LABELS = {open:"Open",in_progress:"In progress",blocked:"Blocked",deferred:"Deferred",closed:"Closed"};
const PRIORITIES = ["Urgent","High","Normal","Low","Someday"];
const API = "/api/plugins/simple_kanban";
const ICON_PATHS = {
  up:["m18 15-6-6-6 6"], down:["m6 9 6 6 6-6"],
  edit:["M12 20h9","M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"],
  close:["m20 6-11 11-5-5"], reopen:["M3 12a9 9 0 1 0 3-6.7","M3 3v6h6"],
  delete:["M3 6h18","M8 6V4h8v2","M19 6l-1 14H6L5 6","M10 11v5","M14 11v5"],
  archive:["M3 6h18","M5 6v14h14V6","M9 10h6","M4 3h16v3"],
  collapse:["m15 18-6-6 6-6"], expand:["m9 18 6-6-6-6"],
  copy:["M8 8h11v11H8Z","M5 16H4V4h12v1"],
};
function savedCollapsed() {
  try { return new Set(JSON.parse(localStorage.getItem("simple-kanban.collapsed") || "[]").filter((status)=>STATUSES.includes(status))); }
  catch { return new Set(); }
}
function savedCondensed() {
  try { return localStorage.getItem("simple-kanban.condensed") === "true"; }
  catch { return false; }
}
const state = {tasks:[], mode:localStorage.getItem("simple-kanban.mode") || "board", archived:false, collapsed:savedCollapsed(), condensed:savedCondensed(), archiveConfirmUntil:0, query:"", dragging:null, moving:false, saving:false, needsRefresh:false, loaded:false};
const content = document.getElementById("content");
const notice = document.getElementById("notice");
const dialog = document.getElementById("task-dialog");
const form = document.getElementById("task-form");
let loadGeneration = 0;

function node(tag, cls, text) {
  const element = document.createElement(tag);
  if (cls) element.className = cls;
  if (text !== undefined) element.textContent = text;
  return element;
}
function message(text, error=false) {
  notice.textContent = text || "";
  notice.classList.toggle("error", error);
}
async function request(path, options={}) {
  const response = await kit.apiFetch(API + path, {
    ...options,
    headers:{"Content-Type":"application/json", ...(options.headers || {})},
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try { detail = (await response.json()).detail || detail; } catch { /* status is enough */ }
    const error = new Error(detail); error.status = response.status; throw error;
  }
  return response.status === 204 ? null : response.json();
}
function filteredTasks() {
  const query = state.query.toLocaleLowerCase();
  if (!query) return state.tasks;
  return state.tasks.filter((task) => [task.id,task.title,task.description,task.assignee,task.issue_type]
    .some((value) => String(value || "").toLocaleLowerCase().includes(query)));
}
function rankedTasks(status) { return state.tasks.filter((task) => task.status === status).sort((a,b) => a.position-b.position); }
function tasksIn(status) { const visible=new Set(filteredTasks().map((task)=>task.id));return rankedTasks(status).filter((task)=>visible.has(task.id)); }
function taskById(id) { return state.tasks.find((task) => task.id === id); }

function statusSelect(task) {
  const select = node("select", "pl-input status-select");
  select.disabled = state.moving;
  select.setAttribute("aria-label", `Status for ${task.title}`);
  for (const status of STATUSES) {
    const option = node("option", "", LABELS[status]); option.value = status; option.selected = status === task.status;
    if(status === "closed" && task.status !== "closed" && epicCannotClose(task)){option.disabled=true;option.title=epicBlockMessage(task);}
    select.append(option);
  }
  select.addEventListener("change", () => void moveTask(task.id, select.value, null));
  return select;
}
function icon(name) {
  const svg=document.createElementNS("http://www.w3.org/2000/svg","svg");svg.setAttribute("viewBox","0 0 24 24");svg.setAttribute("aria-hidden","true");
  for(const d of ICON_PATHS[name]){const path=document.createElementNS("http://www.w3.org/2000/svg","path");path.setAttribute("d",d);svg.append(path);}return svg;
}
function actionButton(action, title, iconName, disabled=false) {
  const button=node("button","icon-button");button.type="button";button.dataset.action=action;button.title=title;button.setAttribute("aria-label",title);button.disabled=state.moving||disabled;button.append(icon(iconName));return button;
}
function iconButton(title, iconName, disabled=false) {
  const button=node("button","icon-button");button.type="button";button.title=title;button.setAttribute("aria-label",title);button.disabled=state.moving||disabled;button.append(icon(iconName));return button;
}
function compactCardId(cardId) { return `K-${cardId.replace(/^kanban-/i,"").slice(0,8).toUpperCase()}`; }
function isEpic(task) { return task.issue_type === "epic"; }
function epicCannotClose(task) { return isEpic(task) && task.epic_plan && !task.epic_plan.can_close; }
function epicBlockMessage(task) {
  if(!epicCannotClose(task))return "";
  const plan=task.epic_plan;const reasons=[];
  if(plan.open_children)reasons.push(`${plan.open_children} open child task${plan.open_children===1?"":"s"}`);
  if(plan.broken_references)reasons.push(`${plan.broken_references} broken child reference${plan.broken_references===1?"":"s"}`);
  return `Epic cannot close: ${reasons.join(" and ")}`;
}
function epicSummary(task) {
  if(!isEpic(task))return null;
  const row=node("div","epic-summary");const badge=node("span","badge epic-badge","EPIC");badge.title="Epic planning card";row.append(badge);
  const plan=task.epic_plan;
  if(plan?.total_children)row.append(node("span","epic-progress",`${plan.completed_children}/${plan.total_children} complete`));
  else row.append(node("span","epic-progress","No child tasks"));
  if(plan?.open_children)row.append(node("span","epic-warning",`${plan.open_children} open`));
  if(plan?.broken_references)row.append(node("span","epic-error",`${plan.broken_references} broken`));
  if(plan?.related_count)row.append(node("span","epic-related",`↔ ${plan.related_count} related`));
  return row;
}
function epicLinks(task) {
  if(!isEpic(task)||!task.epic_plan)return null;
  const row=node("div","epic-links");
  for(const item of [...task.epic_plan.child_cards,...task.epic_plan.related_cards]){
    const label=item.kind==="card"?"Child":"Related";const ref=node("button",`card-reference${item.problem||item.missing?" broken-reference":""}`,`${label} ${item.compact_id}`);ref.type="button";ref.title=item.problem||item.missing?`${label} reference is broken`:`Open ${label.toLowerCase()} card ${item.card_id}`;if(item.problem||item.missing)ref.disabled=true;else ref.dataset.cardRef=item.card_id;row.append(ref);
  }
  return row.childElementCount?row:null;
}
function descriptionNode(task) {
  const wrap=node("div","card-description");const pattern=/\[\[(kanban-[0-9a-f]{12})\]\]/ig;let index=0;let match;
  while((match=pattern.exec(task.description))!==null){if(match.index>index)wrap.append(document.createTextNode(task.description.slice(index,match.index)));const ref=node("button","card-reference",compactCardId(match[1]));ref.type="button";ref.dataset.cardRef=match[1].toLowerCase();ref.title=`Open referenced card ${match[1].toLowerCase()}`;wrap.append(ref);index=pattern.lastIndex;}
  if(index<task.description.length)wrap.append(document.createTextNode(task.description.slice(index)));
  return wrap;
}
function cardIdControl(task) {
  const row=node("div","card-id-row");const shortId=compactCardId(task.id);const value=node("code","card-id",shortId);value.title=`Full card_id: ${task.id}`;value.setAttribute("aria-label",`Card ID ${shortId}`);const copy=iconButton(`Copy full card_id ${shortId}`,"copy");copy.classList.add("copy-card-id");copy.dataset.copyId=task.id;row.append(value,copy);return row;
}
async function copyCardId(cardId) {
  let copied=false;
  try{if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(cardId);copied=true;}}catch{/* fallback below */}
  if(!copied){const field=node("textarea","copy-fallback",cardId);field.setAttribute("aria-hidden","true");document.body.append(field);field.select();copied=document.execCommand("copy");field.remove();}
  message(copied?`Copied full card_id ${compactCardId(cardId)}`:"Could not copy card_id",!copied);
}
function toggleColumn(status) {
  if(state.collapsed.has(status))state.collapsed.delete(status);else state.collapsed.add(status);
  localStorage.setItem("simple-kanban.collapsed",JSON.stringify([...state.collapsed]));render();
}
function toggleCondensed() {
  if(state.archived||state.mode!=="board")return;
  state.condensed=!state.condensed;
  localStorage.setItem("simple-kanban.condensed",String(state.condensed));
  render();
}
function rankCapabilities(task) {
  const ranked=rankedTasks(task.status);const index=ranked.findIndex((item)=>item.id===task.id);return {earlier:index>0,later:index>=0&&index<ranked.length-1};
}
function card(task) {
  const article = node("article", `card${isEpic(task)?" epic-card":""}`); article.dataset.id=task.id; article.draggable=!state.moving;
  const handle = node("button", "drag-handle", "⠿"); handle.type="button"; handle.title="Drag to move"; handle.setAttribute("aria-label",`Drag ${task.title}`);
  handle.disabled=state.moving;
  handle.addEventListener("pointerdown", () => { article.dataset.armed="true"; });
  handle.addEventListener("pointerup", () => { delete article.dataset.armed; });
  article.addEventListener("dragstart", (event) => {
    if (article.dataset.armed !== "true") { event.preventDefault(); return; }
    state.dragging=task.id; article.classList.add("dragging"); event.dataTransfer.effectAllowed="move"; event.dataTransfer.setData("text/plain", task.id);
  });
  article.addEventListener("dragend", () => { state.dragging=null; delete article.dataset.armed; article.classList.remove("dragging"); document.querySelectorAll(".drop-before,.drag-over").forEach((x)=>x.classList.remove("drop-before","drag-over")); });
  article.addEventListener("dragover", (event) => { if (state.dragging && state.dragging !== task.id) { event.preventDefault(); article.classList.add("drop-before"); } });
  article.addEventListener("dragleave", () => article.classList.remove("drop-before"));
  article.addEventListener("drop", (event) => { event.preventDefault(); event.stopPropagation(); article.classList.remove("drop-before"); if (state.dragging && state.dragging !== task.id) void moveTask(state.dragging, task.status, task.id); });
  const body = node("div","card-body");
  body.append(cardIdControl(task));
  const summary=epicSummary(task);if(summary)body.append(summary);
  const links=epicLinks(task);if(links)body.append(links);
  const title=node("button","card-title",task.title);title.type="button";title.dataset.action="edit";title.title=`Edit ${task.title}`;title.setAttribute("aria-label",`Edit ${task.title}`);body.append(title);
  const condensedRank=node("div","condensed-rank-actions");const condensedCapability=rankCapabilities(task);condensedRank.append(actionButton("earlier",condensedCapability.earlier?"Move up":"Already first in column","up",!condensedCapability.earlier),actionButton("later",condensedCapability.later?"Move down":"Already last in column","down",!condensedCapability.later));body.append(condensedRank);
  if (task.description) body.append(descriptionNode(task));
  const meta=node("div","meta");const rank=node("span","badge rank-badge",`#${task.position}`);rank.title=`Rank ${task.position} in ${LABELS[task.status]}`;rank.setAttribute("aria-label",rank.title);meta.append(rank);
  meta.append(node("span",`badge priority-${task.priority}`,PRIORITIES[task.priority] || "Normal"));
  if(!isEpic(task))meta.append(node("span","badge",task.issue_type));
  if (task.assignee) meta.append(node("span","badge",task.assignee));
  meta.append(statusSelect(task));
  body.append(meta);
  const actions=node("div","card-actions");const capability=rankCapabilities(task);
  actions.append(actionButton("earlier",capability.earlier?"Move up":"Already first in column","up",!capability.earlier),actionButton("later",capability.later?"Move down":"Already last in column","down",!capability.later),actionButton("edit","Edit task","edit"));
  if (task.status === "closed") actions.append(actionButton("reopen","Reopen task","reopen")); else actions.append(actionButton("close",epicCannotClose(task)?epicBlockMessage(task):"Close task","close",epicCannotClose(task)));
  actions.append(actionButton("delete","Delete task","delete")); body.append(actions);
  article.append(handle,body); return article;
}
function renderBoard() {
  const board=node("div",`board${state.condensed?" condensed":""}`);
  for (const status of STATUSES) {
    const collapsed=state.collapsed.has(status);const column=node("section",`column${collapsed?" collapsed":""}`);column.dataset.status=status;column.setAttribute("aria-label",LABELS[status]);column.setAttribute("aria-expanded",String(!collapsed));
    const head=node("div","column-head");const heading=node("div","column-heading");heading.append(node("span","column-title",LABELS[status]),node("span","count",String(tasksIn(status).length)));const controls=node("div","column-controls");
    if(status==="closed"){const closed=rankedTasks("closed");const count=closed.length;const blocked=closed.filter(epicCannotClose);const armed=state.archiveConfirmUntil>Date.now();const archive=iconButton(blocked.length?`${blocked.length} Epic card${blocked.length===1?"":"s"} cannot archive with open tasks`:(count?(armed?`Confirm archive all ${count} Closed cards`:`Archive all ${count} Closed cards`):"No Closed cards to archive"),"archive",count===0||blocked.length>0);archive.classList.add("archive-closed");archive.classList.toggle("confirm",armed);archive.addEventListener("click",()=>void archiveClosed());controls.append(archive);}
    const toggle=iconButton(collapsed?`Expand ${LABELS[status]} column`:`Collapse ${LABELS[status]} column`,collapsed?"expand":"collapse");toggle.classList.add("column-toggle");toggle.setAttribute("aria-expanded",String(!collapsed));toggle.addEventListener("click",()=>toggleColumn(status));controls.append(toggle);head.append(heading,controls);column.append(head);
    const cards=node("div","cards");
    column.addEventListener("dragover",(event)=>{if(state.dragging){event.preventDefault();column.classList.add("drag-over");}});
    column.addEventListener("dragleave",(event)=>{if(!column.contains(event.relatedTarget))column.classList.remove("drag-over");});
    column.addEventListener("drop",(event)=>{event.preventDefault();column.classList.remove("drag-over");if(state.dragging)void moveTask(state.dragging,status,null);});
    const tasks=tasksIn(status); if(!tasks.length) cards.append(node("div","empty","Drop or add a task")); else tasks.forEach((task)=>cards.append(card(task)));
    column.append(cards); board.append(column);
  }
  return board;
}
function renderList() {
  const wrap=node("div","list-wrap"); const table=node("table","list");
  const thead=node("thead"); const tr=node("tr"); ["Rank","Card ID","Task","Status","Priority","Type","Assignee","Actions"].forEach((x)=>tr.append(node("th","",x))); thead.append(tr); table.append(thead);
  const tbody=node("tbody");
  for(const task of filteredTasks().sort((a,b)=>STATUSES.indexOf(a.status)-STATUSES.indexOf(b.status)||a.position-b.position)){
    const row=node("tr"); row.dataset.id=task.id;
    const cardIdCell=node("td","");cardIdCell.append(cardIdControl(task));row.append(node("td","",String(task.position)),cardIdCell,node("td","list-title",task.title));
    const s=node("td");s.append(statusSelect(task));const typeCell=node("td","");const summary=epicSummary(task);if(summary)typeCell.append(summary);else typeCell.textContent=task.issue_type;row.append(s,node("td",`priority-${task.priority}`,PRIORITIES[task.priority]),typeCell,node("td","",task.assignee||"—"));
    const capability=rankCapabilities(task);const actions=node("td","list-actions");actions.append(actionButton("earlier",capability.earlier?"Move up":"Already first in column","up",!capability.earlier),actionButton("later",capability.later?"Move down":"Already last in column","down",!capability.later),actionButton("edit","Edit task","edit"),task.status==="closed"?actionButton("reopen","Reopen task","reopen"):actionButton("close",epicCannotClose(task)?epicBlockMessage(task):"Close task","close",epicCannotClose(task)),actionButton("delete","Delete task","delete"));row.append(actions);tbody.append(row);
  }
  if(!filteredTasks().length){const row=node("tr");const cell=node("td","global-empty","No matching tasks");cell.colSpan=8;row.append(cell);tbody.append(row);}
  table.append(tbody);wrap.append(table);return wrap;
}
function renderArchived() {
  const wrap=node("div","list-wrap archived-wrap");const table=node("table","list archived-list");const thead=node("thead");const heading=node("tr");["Card ID","Task","Type","Closed","Archived"].forEach((label)=>heading.append(node("th","",label)));thead.append(heading);table.append(thead);const tbody=node("tbody");
  for(const task of filteredTasks()){const row=node("tr");row.dataset.id=task.id;const cardIdCell=node("td","");cardIdCell.append(cardIdControl(task));const typeCell=node("td","");const summary=epicSummary(task);if(summary)typeCell.append(summary);else typeCell.textContent=task.issue_type;row.append(cardIdCell,node("td","list-title",task.title),typeCell,node("td","",task.closed_at?new Date(task.closed_at).toLocaleString():"—"),node("td","",new Date(task.archived_at).toLocaleString()));tbody.append(row);}
  if(!filteredTasks().length){const row=node("tr");const cell=node("td","global-empty","No archived cards");cell.colSpan=5;row.append(cell);tbody.append(row);}table.append(tbody);wrap.append(table);return wrap;
}
function render() {
  content.replaceChildren(state.archived?renderArchived():(state.mode === "list" ? renderList() : renderBoard())); content.setAttribute("aria-busy","false");
  document.getElementById("board-mode").setAttribute("aria-pressed",String(state.mode==="board"));
  document.getElementById("list-mode").setAttribute("aria-pressed",String(state.mode==="list"));
  document.getElementById("condensed-mode").setAttribute("aria-pressed",String(state.condensed));
  document.getElementById("condensed-mode").disabled=state.archived||state.mode!=="board";
  document.getElementById("board-mode").disabled=state.archived;document.getElementById("list-mode").disabled=state.archived;document.getElementById("add-task").disabled=state.archived;document.getElementById("show-archive").setAttribute("aria-pressed",String(state.archived));document.querySelector(".topbar h1").textContent=state.archived?"Kanban archive":"Kanban";
}
async function load({quiet=false,required=false}={}) {
  const generation=++loadGeneration;
  try { const data=await request(state.archived?"/tasks?archived=true":"/tasks");if(generation!==loadGeneration)return required?load({quiet,required}):false;state.tasks=data.tasks;state.loaded=true;if(state.needsRefresh){state.needsRefresh=false;state.moving=false;if(state.saving){if(dialog.open)dialog.close();setDialogSaving(false);}}render();if(!quiet)message(`${state.tasks.length} ${state.archived?"archived card":"active card"}${state.tasks.length===1?"":"s"}`);return true; }
  catch(error){if(generation!==loadGeneration)return required?load({quiet,required}):false;if(required||!state.loaded){content.replaceChildren(node("div","global-empty","Kanban could not load."));content.setAttribute("aria-busy","false");}message(`Load failed: ${error.message}`,true);if(required)throw error;return false;}
}
function optimisticMove(id,status,beforeId){
  const task=taskById(id); if(!task)return;
  state.tasks=state.tasks.filter((item)=>item.id!==id);
  state.tasks.filter((item)=>item.status===task.status).sort((a,b)=>a.position-b.position).forEach((item,i)=>{item.position=i+1;});
  const destination=state.tasks.filter((item)=>item.status===status).sort((a,b)=>a.position-b.position);
  const index=beforeId?destination.findIndex((item)=>item.id===beforeId):destination.length;
  destination.splice(index<0?destination.length:index,0,{...task,status}); destination.forEach((item,i)=>item.position=i+1);
  const ids=new Set(destination.map((item)=>item.id)); state.tasks.push(...destination.filter((item)=>!state.tasks.some((existing)=>existing.id===item.id)));
  state.tasks.forEach((item)=>{if(ids.has(item.id)){const ranked=destination.find((x)=>x.id===item.id);item.status=status;item.position=ranked.position;}}); render();
}
async function moveTask(id,status,beforeId){
  if(state.moving){message("A move is already saving");return;}
  const task=taskById(id); if(!task || (task.status===status && beforeId===id))return;
  if(status==="closed"&&task.status!=="closed"&&epicCannotClose(task)){message(epicBlockMessage(task),true);return;}
  state.moving=true;const snapshot=structuredClone(state.tasks);let moved=false;optimisticMove(id,status,beforeId);message("Saving move…");
  try{await request(`/tasks/${encodeURIComponent(id)}/move`,{method:"POST",body:JSON.stringify({destination_status:status,before_id:beforeId,expected_version:task.version})});moved=true;await load({quiet:true,required:true});message("Move saved");}
  catch(error){if(!moved){state.tasks=snapshot;render();}try{await load({quiet:true,required:true});message(moved?"Move saved after refresh retry":`${error.message}. Board reloaded.`,!moved);}catch{state.needsRefresh=true;message(moved?`Move saved, but refresh failed: ${error.message}`:`${error.message}. Board reload failed.`,true);}}
  finally{if(!state.needsRefresh)state.moving=false;render();}
}
function openDialog(task=null){
  if(state.saving||state.moving)return;
  document.getElementById("dialog-title").textContent=task?"Edit task":"New task";document.getElementById("task-id").value=task?.id||"";document.getElementById("task-version").value=task?.version||"";document.getElementById("task-title").value=task?.title||"";document.getElementById("task-description").value=task?.description||"";document.getElementById("task-status").value=task?.status||"open";document.getElementById("task-priority").value=String(task?.priority??2);document.getElementById("task-type").value=task?.issue_type||"task";document.getElementById("task-assignee").value=task?.assignee||"";updateEpicHelp();dialog.showModal();document.getElementById("task-title").focus();
}
function updateEpicHelp(){document.getElementById("epic-help").hidden=document.getElementById("task-type").value!=="epic";}
function insertEpicTemplate(){
  const field=document.getElementById("task-description");if(field.value.trim()&&!confirm("Append the Epic plan template to the current description?"))return;
  const template="## Outcome\n\nDescribe the larger outcome.\n\n## Plan\n\n1. Describe the intended order.\n\n## Child tasks\n\n- [ ] Describe an inline task\n- [ ] Add a child card: [[kanban-REPLACE-ME]] — replace the placeholder with its full ID\n\n## Related cards\n\n- [[kanban-REPLACE-ME]] — Explain the relationship\n\n## Deferred follow-up\n\n- Describe non-blocking future work\n\n## Acceptance\n\n- Define completion.";
  field.value=`${field.value.trim()}${field.value.trim()?"\n\n":""}${template}`;field.focus();field.setSelectionRange(field.value.length,field.value.length);
}
function setDialogSaving(saving){state.saving=saving;form.querySelectorAll("input,textarea,select,button").forEach((element)=>{element.disabled=saving;});document.getElementById("cancel-x").disabled=saving;}
async function saveTask(event){
  event.preventDefault();if(state.saving||state.moving)return;const id=document.getElementById("task-id").value;const payload={title:document.getElementById("task-title").value,description:document.getElementById("task-description").value,status:document.getElementById("task-status").value,priority:Number(document.getElementById("task-priority").value),issue_type:document.getElementById("task-type").value,assignee:document.getElementById("task-assignee").value};const capturedVersion=Number(document.getElementById("task-version").value);state.moving=true;render();setDialogSaving(true);
  let saved=false;try{
    if(id){const current=taskById(id);const desiredStatus=payload.status;delete payload.status;if(current.status!==desiredStatus)await request(`/tasks/${encodeURIComponent(id)}/move`,{method:"POST",body:JSON.stringify({destination_status:desiredStatus,before_id:null,expected_version:capturedVersion,updates:payload})});else await request(`/tasks/${encodeURIComponent(id)}`,{method:"PATCH",body:JSON.stringify({...payload,expected_version:capturedVersion})});}
    else await request("/tasks",{method:"POST",body:JSON.stringify(payload)});
    saved=true;dialog.close();await load({quiet:true,required:true});message(id?"Task updated":"Task created");
  }catch(error){if(saved){try{await load({quiet:true,required:true});message(id?"Task updated after refresh retry":"Task created after refresh retry");}catch{state.needsRefresh=true;message(`Task saved, but refresh failed: ${error.message}`,true);}}else if(error.status===409||(id&&error.status===404)){try{await load({quiet:true,required:true});dialog.close();message("Save target changed; board reloaded.",true);}catch{state.needsRefresh=true;message(`Save target changed and board refresh failed: ${error.message}`,true);}}else if(error.status&&error.status<500)message(`Save failed: ${error.message}`,true);else{try{await load({quiet:true,required:true});dialog.close();message("Save response lost; board reconciled. Check the task before retrying.",true);}catch{state.needsRefresh=true;message(`Save response lost and board refresh failed: ${error.message}`,true);}}}finally{if(!state.needsRefresh)setDialogSaving(false);if(!state.needsRefresh)state.moving=false;render();}
}
async function simpleAction(task,action){
  if(action==="edit"){openDialog(task);return;}
  if(action==="earlier"||action==="later"){const column=rankedTasks(task.status);const index=column.findIndex((x)=>x.id===task.id);let before=null;if(action==="earlier"&&index>0)before=column[index-1].id;else if(action==="later"&&index<column.length-1)before=column[index+2]?.id||null;else return;await moveTask(task.id,task.status,before);return;}
  if(state.moving){message("A task change is already saving");return;}
  if(action==="close"&&epicCannotClose(task)){message(epicBlockMessage(task),true);return;}
  if(action==="delete"&&!confirm(`Delete “${task.title}”?`))return;
  state.moving=true;let applied=false;render();message("Saving change…");
  try{
    if(action==="close")await request(`/tasks/${encodeURIComponent(task.id)}/close`,{method:"POST",body:JSON.stringify({expected_version:task.version,reason:"Closed from Kanban"})});
    if(action==="reopen")await request(`/tasks/${encodeURIComponent(task.id)}/reopen`,{method:"POST",body:JSON.stringify({expected_version:task.version})});
    if(action==="delete")await request(`/tasks/${encodeURIComponent(task.id)}?expected_version=${task.version}`,{method:"DELETE"});
    applied=true;await load({quiet:true,required:true});message(action==="delete"?"Task deleted":"Task updated");
  }catch(error){if(applied){try{await load({quiet:true,required:true});message(action==="delete"?"Task deleted after refresh retry":"Task updated after refresh retry");}catch{state.needsRefresh=true;message(`Task changed, but refresh failed: ${error.message}`,true);}}else{message(`${action} failed: ${error.message}`,true);try{await load({quiet:true,required:true});}catch{state.needsRefresh=true;}}}
  finally{if(!state.needsRefresh)state.moving=false;render();}
}
async function archiveClosed(){
  if(state.moving||state.archived)return;const closed=rankedTasks("closed");const blocked=closed.filter(epicCannotClose);if(blocked.length){message(`${blocked.length} Epic card${blocked.length===1?"":"s"} cannot archive with open tasks.`,true);return;}const count=closed.length;if(!count)return;if(state.archiveConfirmUntil<=Date.now()){state.archiveConfirmUntil=Date.now()+8000;render();message(`Click Archive again to confirm all ${count} Closed cards. Records remain available in Archived.`);setTimeout(()=>{if(state.archiveConfirmUntil&&state.archiveConfirmUntil<=Date.now()){state.archiveConfirmUntil=0;render();}},8100);return;}state.archiveConfirmUntil=0;state.moving=true;render();message("Archiving Closed cards…");let applied=false;
  try{const result=await request("/tasks/archive-closed",{method:"POST"});applied=true;await load({quiet:true,required:true});message(`${result.archived} Closed card${result.archived===1?"":"s"} archived`);}
  catch(error){if(applied||!error.status||error.status>=500){try{await load({quiet:true,required:true});message("Archive response was uncertain; the board was reconciled. Check Archived before retrying.",true);}catch{state.needsRefresh=true;message(`Archive may have completed, but refresh failed: ${error.message}`,true);}}else message(`Archive failed: ${error.message}`,true);}
  finally{if(!state.needsRefresh)state.moving=false;render();}
}
async function toggleArchive(){
  if(state.moving||state.saving)return;const previous=state.archived;state.archived=!state.archived;content.setAttribute("aria-busy","true");try{await load({required:true});}catch{state.archived=previous;await load({quiet:true});}
}
async function followCardReference(cardId){
  if(state.moving||state.saving)return;
  try{
    const result=await request(`/tasks/${encodeURIComponent(cardId)}`);const target=result.task;
    if(target.archived_at){if(!state.archived){state.archived=true;await load({quiet:true,required:true});}message(`${compactCardId(cardId)} is archived: ${target.title}`);}
    else{if(state.archived){state.archived=false;await load({quiet:true,required:true});}const active=taskById(target.id)||target;openDialog(active);message(`Opened ${compactCardId(cardId)}`);}
    const visible=document.querySelector(`[data-id="${CSS.escape(cardId)}"]`);if(visible){visible.classList.add("reference-target");visible.scrollIntoView({block:"center",behavior:"smooth"});setTimeout(()=>visible.classList.remove("reference-target"),1800);}
  }catch(error){message(`Card reference failed: ${error.message}`,true);}
}
function subscribeToChanges(){
  window.addEventListener("message",(event)=>{if(event.source===window.parent&&event.data?.type==="protoagent:event"&&event.data.topic==="simple_kanban.changed")void load({quiet:true});});
  if(window.parent!==window)window.parent.postMessage({type:"protoagent:subscribe",patterns:["simple_kanban.changed"]},"*");
}
content.addEventListener("click",(event)=>{const copy=event.target.closest("button[data-copy-id]");if(copy){void copyCardId(copy.dataset.copyId);return;}const reference=event.target.closest("button[data-card-ref]");if(reference){void followCardReference(reference.dataset.cardRef);return;}const button=event.target.closest("button[data-action]");if(!button)return;const owner=button.closest("[data-id]");const task=taskById(owner?.dataset.id);if(task)void simpleAction(task,button.dataset.action);});
for(const status of STATUSES){const option=node("option","",LABELS[status]);option.value=status;document.getElementById("task-status").append(option);}
document.getElementById("add-task").addEventListener("click",()=>openDialog());document.getElementById("refresh").addEventListener("click",()=>void load());document.getElementById("condensed-mode").addEventListener("click",toggleCondensed);document.getElementById("show-archive").addEventListener("click",()=>void toggleArchive());document.getElementById("board-mode").addEventListener("click",()=>{state.mode="board";localStorage.setItem("simple-kanban.mode",state.mode);render();});document.getElementById("list-mode").addEventListener("click",()=>{state.mode="list";localStorage.setItem("simple-kanban.mode",state.mode);render();});document.getElementById("search").addEventListener("input",(event)=>{state.query=event.target.value;render();});document.getElementById("task-type").addEventListener("change",updateEpicHelp);document.getElementById("insert-epic-template").addEventListener("click",insertEpicTemplate);document.getElementById("cancel").addEventListener("click",()=>{if(!state.saving)dialog.close();});document.getElementById("cancel-x").addEventListener("click",()=>{if(!state.saving)dialog.close();});dialog.addEventListener("cancel",(event)=>{if(state.saving)event.preventDefault();});form.addEventListener("submit",saveTask);window.addEventListener("focus",()=>void load({quiet:true}));subscribeToChanges();setInterval(()=>{if(document.visibilityState==="visible"&&(!dialog.open||state.needsRefresh))void load({quiet:true});},15000);
await load();
