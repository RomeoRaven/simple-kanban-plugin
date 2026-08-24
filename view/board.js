"use strict";
const kit = await import(window.__base + "/_ds/plugin-kit.js");
kit.initPluginView();

const STATUSES = ["open", "in_progress", "blocked", "deferred", "closed"];
const LABELS = {open:"Open",in_progress:"In progress",blocked:"Blocked",deferred:"Deferred",closed:"Closed"};
const PRIORITIES = ["Urgent","High","Normal","Low","Someday"];
const API = "/api/plugins/simple_kanban";
const state = {tasks:[], mode:localStorage.getItem("simple-kanban.mode") || "board", query:"", dragging:null, moving:false, saving:false};
const content = document.getElementById("content");
const notice = document.getElementById("notice");
const dialog = document.getElementById("task-dialog");
const form = document.getElementById("task-form");

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
  return state.tasks.filter((task) => [task.title,task.description,task.assignee,task.issue_type]
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
    const option = node("option", "", LABELS[status]); option.value = status; option.selected = status === task.status; select.append(option);
  }
  select.addEventListener("change", () => void moveTask(task.id, select.value, null));
  return select;
}
function actionButton(label, action, title=label) {
  const button = node("button", "", label); button.type="button"; button.dataset.action=action; button.title=title; button.disabled=state.moving; return button;
}
function card(task) {
  const article = node("article", "card"); article.dataset.id=task.id; article.draggable=!state.moving;
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
  body.append(node("div","card-title",task.title));
  if (task.description) body.append(node("div","card-description",task.description));
  const meta=node("div","meta");
  meta.append(node("span",`badge priority-${task.priority}`,PRIORITIES[task.priority] || "Normal"));
  meta.append(node("span","badge",task.issue_type));
  if (task.assignee) meta.append(node("span","badge",task.assignee));
  meta.append(statusSelect(task));
  body.append(meta);
  const actions=node("div","card-actions");
  actions.append(actionButton("←","earlier","Move earlier"),actionButton("→","later","Move later"),actionButton("Edit","edit"));
  if (task.status === "closed") actions.append(actionButton("Reopen","reopen")); else actions.append(actionButton("Close","close"));
  actions.append(actionButton("Delete","delete")); body.append(actions);
  article.append(handle,body); return article;
}
function renderBoard() {
  const board=node("div","board");
  for (const status of STATUSES) {
    const column=node("section","column"); column.dataset.status=status; column.setAttribute("aria-label",LABELS[status]);
    const head=node("div","column-head"); head.append(node("span","column-title",LABELS[status]),node("span","count",String(tasksIn(status).length))); column.append(head);
    const cards=node("div","cards");
    cards.addEventListener("dragover",(event)=>{ if(state.dragging){event.preventDefault();column.classList.add("drag-over");} });
    cards.addEventListener("dragleave",(event)=>{if(!cards.contains(event.relatedTarget))column.classList.remove("drag-over");});
    cards.addEventListener("drop",(event)=>{event.preventDefault();column.classList.remove("drag-over");if(state.dragging)void moveTask(state.dragging,status,null);});
    const tasks=tasksIn(status); if(!tasks.length) cards.append(node("div","empty","Drop or add a task")); else tasks.forEach((task)=>cards.append(card(task)));
    column.append(cards); board.append(column);
  }
  return board;
}
function renderList() {
  const wrap=node("div","list-wrap"); const table=node("table","list");
  const thead=node("thead"); const tr=node("tr"); ["Rank","Task","Status","Priority","Type","Assignee","Actions"].forEach((x)=>tr.append(node("th","",x))); thead.append(tr); table.append(thead);
  const tbody=node("tbody");
  for(const task of filteredTasks()){
    const row=node("tr"); row.dataset.id=task.id;
    row.append(node("td","",String(task.position)),node("td","list-title",task.title));
    const s=node("td");s.append(statusSelect(task));row.append(s,node("td",`priority-${task.priority}`,PRIORITIES[task.priority]),node("td","",task.issue_type),node("td","",task.assignee||"—"));
    const actions=node("td","list-actions");actions.append(actionButton("←","earlier"),actionButton("→","later"),actionButton("Edit","edit"),actionButton(task.status==="closed"?"Reopen":"Close",task.status==="closed"?"reopen":"close"));row.append(actions);tbody.append(row);
  }
  if(!filteredTasks().length){const row=node("tr");const cell=node("td","global-empty","No matching tasks");cell.colSpan=7;row.append(cell);tbody.append(row);}
  table.append(tbody);wrap.append(table);return wrap;
}
function render() {
  content.replaceChildren(state.mode === "list" ? renderList() : renderBoard()); content.setAttribute("aria-busy","false");
  document.getElementById("board-mode").setAttribute("aria-pressed",String(state.mode==="board"));
  document.getElementById("list-mode").setAttribute("aria-pressed",String(state.mode==="list"));
}
async function load({quiet=false}={}) {
  try { const data=await request("/tasks"); state.tasks=data.tasks; render(); if(!quiet) message(`${state.tasks.length} task${state.tasks.length===1?"":"s"}`); }
  catch(error){ content.replaceChildren(node("div","global-empty","Kanban could not load.")); content.setAttribute("aria-busy","false"); message(`Load failed: ${error.message}`,true); }
}
function optimisticMove(id,status,beforeId){
  const task=taskById(id); if(!task)return;
  state.tasks=state.tasks.filter((item)=>item.id!==id);
  const destination=state.tasks.filter((item)=>item.status===status).sort((a,b)=>a.position-b.position);
  const index=beforeId?destination.findIndex((item)=>item.id===beforeId):destination.length;
  destination.splice(index<0?destination.length:index,0,{...task,status}); destination.forEach((item,i)=>item.position=i+1);
  const ids=new Set(destination.map((item)=>item.id)); state.tasks.push(...destination.filter((item)=>!state.tasks.some((existing)=>existing.id===item.id)));
  state.tasks.forEach((item)=>{if(ids.has(item.id)){const ranked=destination.find((x)=>x.id===item.id);item.status=status;item.position=ranked.position;}}); render();
}
async function moveTask(id,status,beforeId){
  if(state.moving){message("A move is already saving");return;}
  const task=taskById(id); if(!task || (task.status===status && beforeId===id))return;
  state.moving=true;const snapshot=structuredClone(state.tasks); optimisticMove(id,status,beforeId); message("Saving move…");
  try{await request(`/tasks/${encodeURIComponent(id)}/move`,{method:"POST",body:JSON.stringify({destination_status:status,before_id:beforeId,expected_version:task.version})});await load({quiet:true});message("Move saved");}
  catch(error){state.tasks=snapshot;render();message(`${error.message}. Board reloaded.`,true);await load({quiet:true});}
  finally{state.moving=false;render();}
}
function openDialog(task=null){
  if(state.saving)return;
  document.getElementById("dialog-title").textContent=task?"Edit task":"New task";document.getElementById("task-id").value=task?.id||"";document.getElementById("task-version").value=task?.version||"";document.getElementById("task-title").value=task?.title||"";document.getElementById("task-description").value=task?.description||"";document.getElementById("task-status").value=task?.status||"open";document.getElementById("task-priority").value=String(task?.priority??2);document.getElementById("task-type").value=task?.issue_type||"task";document.getElementById("task-assignee").value=task?.assignee||"";dialog.showModal();document.getElementById("task-title").focus();
}
function setDialogSaving(saving){state.saving=saving;form.querySelectorAll("input,textarea,select,button").forEach((element)=>{element.disabled=saving;});document.getElementById("cancel-x").disabled=saving;}
async function saveTask(event){
  event.preventDefault();if(state.saving)return;const id=document.getElementById("task-id").value;const payload={title:document.getElementById("task-title").value,description:document.getElementById("task-description").value,status:document.getElementById("task-status").value,priority:Number(document.getElementById("task-priority").value),issue_type:document.getElementById("task-type").value,assignee:document.getElementById("task-assignee").value};const capturedVersion=Number(document.getElementById("task-version").value);setDialogSaving(true);
  try{
    if(id){const current=taskById(id);const desiredStatus=payload.status;delete payload.status;if(current.status!==desiredStatus)await request(`/tasks/${encodeURIComponent(id)}/move`,{method:"POST",body:JSON.stringify({destination_status:desiredStatus,before_id:null,expected_version:capturedVersion,updates:payload})});else await request(`/tasks/${encodeURIComponent(id)}`,{method:"PATCH",body:JSON.stringify({...payload,expected_version:capturedVersion})});}
    else await request("/tasks",{method:"POST",body:JSON.stringify(payload)});
    dialog.close();await load({quiet:true});message(id?"Task updated":"Task created");
  }catch(error){message(`Save failed: ${error.message}`,true);}finally{setDialogSaving(false);}
}
async function simpleAction(task,action){
  try{
    if(action==="edit"){openDialog(task);return;}
    if(action==="earlier"||action==="later"){const column=rankedTasks(task.status);const index=column.findIndex((x)=>x.id===task.id);let before=null;if(action==="earlier"&&index>0)before=column[index-1].id;else if(action==="later"&&index<column.length-1)before=column[index+2]?.id||null;else return;await moveTask(task.id,task.status,before);return;}
    if(action==="close")await request(`/tasks/${encodeURIComponent(task.id)}/close`,{method:"POST",body:JSON.stringify({expected_version:task.version,reason:"Closed from Kanban"})});
    if(action==="reopen")await request(`/tasks/${encodeURIComponent(task.id)}/reopen`,{method:"POST",body:JSON.stringify({expected_version:task.version})});
    if(action==="delete"){if(!confirm(`Delete “${task.title}”?`))return;await request(`/tasks/${encodeURIComponent(task.id)}?expected_version=${task.version}`,{method:"DELETE"});}
    await load({quiet:true});message(action==="delete"?"Task deleted":"Task updated");
  }catch(error){message(`${action} failed: ${error.message}`,true);await load({quiet:true});}
}
function subscribeToChanges(){
  window.addEventListener("message",(event)=>{if(event.source===window.parent&&event.data?.type==="protoagent:event"&&event.data.topic==="simple_kanban.changed")void load({quiet:true});});
  if(window.parent!==window)window.parent.postMessage({type:"protoagent:subscribe",patterns:["simple_kanban.changed"]},"*");
}
content.addEventListener("click",(event)=>{const button=event.target.closest("button[data-action]");if(!button)return;const owner=button.closest("[data-id]");const task=taskById(owner?.dataset.id);if(task)void simpleAction(task,button.dataset.action);});
for(const status of STATUSES){const option=node("option","",LABELS[status]);option.value=status;document.getElementById("task-status").append(option);}
document.getElementById("add-task").addEventListener("click",()=>openDialog());document.getElementById("refresh").addEventListener("click",()=>void load());document.getElementById("board-mode").addEventListener("click",()=>{state.mode="board";localStorage.setItem("simple-kanban.mode",state.mode);render();});document.getElementById("list-mode").addEventListener("click",()=>{state.mode="list";localStorage.setItem("simple-kanban.mode",state.mode);render();});document.getElementById("search").addEventListener("input",(event)=>{state.query=event.target.value;render();});document.getElementById("cancel").addEventListener("click",()=>{if(!state.saving)dialog.close();});document.getElementById("cancel-x").addEventListener("click",()=>{if(!state.saving)dialog.close();});dialog.addEventListener("cancel",(event)=>{if(state.saving)event.preventDefault();});form.addEventListener("submit",saveTask);window.addEventListener("focus",()=>void load({quiet:true}));subscribeToChanges();setInterval(()=>{if(document.visibilityState==="visible"&&!dialog.open)void load({quiet:true});},15000);
await load();
