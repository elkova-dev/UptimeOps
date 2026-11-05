'use strict';
const $ = id => document.getElementById(id);
const themes = ['indigo','ocean','forest','sunset','night'];
const picker = $('theme-picker');
const toggle = $('theme-toggle');
const menu = $('theme-menu');
function theme(name) {
  const value = themes.includes(name) ? name : 'night';
  document.documentElement.dataset.theme = value;
  document.querySelectorAll('[data-theme-choice]').forEach(el => {
    const active = el.dataset.themeChoice === value;
    el.classList.toggle('selected', active);
    el.setAttribute('aria-pressed', String(active));
  });
  try {localStorage.setItem('uptimeops-theme',value)} catch {}
}
try {theme(localStorage.getItem('uptimeops-theme') || 'night')} catch {theme('night')}
function closeTheme() {menu.hidden=true;toggle.setAttribute('aria-expanded','false')}
toggle.addEventListener('click',()=>{menu.hidden=!menu.hidden;toggle.setAttribute('aria-expanded',String(!menu.hidden))});
document.querySelectorAll('[data-theme-choice]').forEach(el=>el.addEventListener('click',()=>{theme(el.dataset.themeChoice);closeTheme()}));
document.addEventListener('click',e=>{if(!picker.contains(e.target))closeTheme()});
document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeTheme();closeModal()}});
const esc = v => String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ico = name => `<svg class="icon" aria-hidden="true"><use href="#i-${name}"></use></svg>`;
const date = v => v ? new Date(v).toLocaleString(undefined,{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'}) : 'Never';
const statusClass = s => s === 'up' ? 'up' : s === 'down' ? 'down' : 'pending';
const statusLabel = s => s === 'up' ? 'Operational' : s === 'down' ? 'Down' : 'Pending';
let monitors = [], selectedId=null, editingId=null, timer=null, busy=false;
function notify(message) {const t=$('toast');t.textContent=message;t.classList.add('visible');clearTimeout(timer);timer=setTimeout(()=>t.classList.remove('visible'),4200)}
async function api(url,options={}) {
  const res=await fetch(url,{...options,headers: options.body? {'Content-Type':'application/json',...(options.headers||{})}:(options.headers||{})});
  let data;try{data=await res.json()}catch{throw new Error('Unexpected server response')}
  if(!res.ok){const detail=Array.isArray(data.detail)?data.detail.map(x=>x.msg).join('; '):data.detail;throw new Error(typeof detail==='string'?detail:`HTTP ${res.status}`)}
  return data;
}
function renderRows() {
  $('monitors-body').innerHTML=monitors.length?monitors.map(m=>{
    const label = m.last_status==='down' && m.last_failure_type==='contract'?'Contract failed':statusLabel(m.last_status);
    return `<tr><td><div class="endpoint"><span class="endpoint-icon">${ico(m.contract_enabled?'code':'link')}</span><div><strong>${esc(m.name)}</strong><small title="${esc(m.url)}">${esc(m.url)}</small></div></div></td><td><span class="pill ${statusClass(m.last_status)}"><i class="tiny-dot"></i>${label}</span></td><td>${m.last_latency_ms===null?'—':m.last_latency_ms+' ms'}</td><td>${date(m.last_checked)}</td><td><div class="row-actions"><button class="action-btn" data-check="${m.id}" title="Check now" aria-label="Check ${esc(m.name)}">${ico('refresh')}</button><button class="action-btn" data-history="${m.id}" title="View history" aria-label="History for ${esc(m.name)}">${ico('clock')}</button><button class="action-btn" data-edit="${m.id}" title="Edit monitor" aria-label="Edit ${esc(m.name)}">${ico('edit')}</button><button class="action-btn delete" data-delete="${m.id}" title="Delete monitor" aria-label="Delete ${esc(m.name)}">${ico('trash')}</button></div></td></tr>`;
  }).join(''):'<tr><td colspan="5" class="empty">No monitors yet. Choose Add monitor, or try the built-in demo endpoint.</td></tr>';
  $('table-caption').textContent=`${monitors.length} configured monitor${monitors.length===1?'':'s'}`;
}
function donut(summary) {
  const total=summary.monitors, up=total?summary.up/total*100:0, down=total?summary.down/total*100:0;
  $('donut-number').textContent=`${Math.round(up)}%`;
  $('donut').style.background=`conic-gradient(var(--success) 0% ${up}%,var(--danger) ${up}% ${up+down}%,var(--border) ${up+down}% 100%)`;
}
async function loadData() {
  const [list,summary]=await Promise.all([api('/api/monitors'),api('/api/summary')]);
  monitors=list;renderRows();
  $('count-total').textContent=summary.monitors;
  $('count-up').textContent=summary.up;
  $('count-down').textContent=summary.down;
  $('count-latency').textContent=summary.avg_latency_ms??'—';
  $('contract-summary').textContent=`Including ${summary.contract_failures} contract failure${summary.contract_failures===1?'':'s'}`;
  $('legend-up').textContent=summary.up;$('legend-down').textContent=summary.down;$('legend-pending').textContent=summary.pending;donut(summary);
  if(selectedId!==null && !monitors.some(m=>m.id===selectedId)) {selectedId=null;resetHistory()}
}
function resetHistory(){selectedId=null;$('history-title').textContent='Select a monitor';$('activity-list').innerHTML='<div class="empty">Choose History on a monitor to inspect checks.</div>';$('download-csv').disabled=true;$('uptime-metric').textContent='Uptime: —';$('latency-metric').textContent='Average: —'}
async function loadHistory(id) {
  const [checks,stats]=await Promise.all([api(`/api/monitors/${id}/checks`),api(`/api/monitors/${id}/stats`)]);
  selectedId=id;
  const monitor=monitors.find(x=>x.id===id);
  $('history-title').textContent=monitor?.name||`Monitor ${id}`;
  $('download-csv').disabled=false;
  $('uptime-metric').textContent=`Uptime (last 100): ${stats.uptime_percent===null?'—':stats.uptime_percent+'%'}`;
  $('latency-metric').textContent=`Average: ${stats.avg_latency_ms===null?'—':stats.avg_latency_ms+' ms'}`;
  $('activity-list').innerHTML=checks.length?checks.slice(0,12).map(c=>`<div class="event-row"><div class="event-left"><strong>${esc(c.failure_type==='contract'?'Contract violation':c.http_code?`HTTP ${c.http_code}`:'Network error')}</strong><small>${esc(c.error||'Check passed')} · ${date(c.checked_at)}</small></div><span class="pill ${statusClass(c.status)}"><i class="tiny-dot"></i>${statusLabel(c.status)}${c.latency_ms!==null?' · '+c.latency_ms+'ms':''}</span></div>`).join(''):'<div class="empty">No check history yet.</div>';
}
async function loadIncidents() {
  const incidents=await api('/api/incidents');
  $('incident-count').textContent=`${incidents.filter(x=>x.resolved_at===null).length} open`;
  $('incidents-list').innerHTML=incidents.length?incidents.slice(0,12).map(i=>`<div class="event-row"><div class="event-left"><strong>${esc(i.monitor_name)} · ${esc(i.failure_type==='contract'?'API contract':'Availability')}</strong><small>${esc(i.reason)}<br>Started ${date(i.opened_at)}${i.resolved_at?' · Resolved '+date(i.resolved_at):''}</small></div><span class="pill ${i.resolved_at?'up':'down'}"><i class="tiny-dot"></i>${i.resolved_at?'Resolved':'Open'}</span></div>`).join(''):'<div class="empty">No incidents. Incidents open when checks fail and close automatically after recovery.</div>';
}
async function refreshAll() {await Promise.all([loadData(),loadIncidents()]);if(selectedId!==null)await loadHistory(selectedId)}
async function checkNow(id) {if(busy)return;busy=true;notify('Checking endpoint...');try{const out=await api(`/api/monitors/${id}/check`,{method:'POST'});await refreshAll();await loadHistory(id);notify(out.status==='up'?'Endpoint healthy':`Check failed: ${out.error}`)}catch(e){notify(e.message)}finally{busy=false}}
async function remove(id) {if(!confirm('Delete this monitor and all recorded checks and incidents?'))return;try{await api(`/api/monitors/${id}`,{method:'DELETE'});await refreshAll();notify('Monitor deleted')}catch(e){notify(e.message)}}
async function demo() {try{let monitor=monitors.find(x=>x.url==='http://127.0.0.1:8002/api/health');if(!monitor)monitor=await api('/api/monitors',{method:'POST',body:JSON.stringify({name:'UptimeOps local API',url:'http://127.0.0.1:8002/api/health',interval_seconds:60,contract_enabled:true,contract_path:'status',contract_operator:'equals',contract_expected:'ok'})});await checkNow(monitor.id)}catch(e){notify(e.message)}}
$('monitors-body').addEventListener('click',e=>{const btn=e.target.closest('button[data-check],button[data-history],button[data-edit],button[data-delete]');if(!btn)return;const id=Number(btn.dataset.check||btn.dataset.history||btn.dataset.edit||btn.dataset.delete);if(btn.dataset.check)checkNow(id);else if(btn.dataset.history)loadHistory(id).catch(e=>notify(e.message));else if(btn.dataset.edit)editMonitor(id);else remove(id)});
$('download-csv').addEventListener('click',()=>{if(selectedId!==null)window.location.href=`/api/monitors/${selectedId}/export.csv`});
const modal=$('modal');let previousFocus=null;
function openModal(){
  editingId=null;
  $('add-form').reset();
  $('contract-fields').hidden=true;
  $('add-form').elements.contract_expected.disabled=false;
  $('modal-title').textContent='Add monitor';
  $('modal-submit-label').textContent='Create monitor';
  previousFocus=document.activeElement;modal.hidden=false;$('add-form').elements.name.focus();
}
function editMonitor(id){
  const monitor=monitors.find(m=>m.id===id);if(!monitor)return;
  openModal();editingId=id;
  const form=$('add-form');
  for(const field of ['name','url','interval_seconds','contract_path','contract_operator','contract_expected'])form.elements[field].value=monitor[field]??'';
  form.elements.contract_enabled.checked=Boolean(monitor.contract_enabled);
  $('contract-fields').hidden=!monitor.contract_enabled;
  form.elements.contract_expected.disabled=monitor.contract_operator==='exists';
  $('modal-title').textContent='Edit monitor';
  $('modal-submit-label').textContent='Save changes';
}

function closeModal(){modal.hidden=true;editingId=null;previousFocus?.focus()}
$('open-add').addEventListener('click',openModal);$('modal-close').addEventListener('click',closeModal);$('cancel').addEventListener('click',closeModal);modal.addEventListener('click',e=>{if(e.target===modal)closeModal()});
$('enable-contract').addEventListener('change',e=>{$('contract-fields').hidden=!e.target.checked});
const contractOperator=$('add-form').elements.contract_operator;
contractOperator.addEventListener('change',()=>{$('add-form').elements.contract_expected.disabled=contractOperator.value==='exists'});
$('add-form').addEventListener('submit',async e=>{
  e.preventDefault();const form=e.currentTarget;
  const data=Object.fromEntries(new FormData(form));
  data.interval_seconds=Number(data.interval_seconds);data.contract_enabled=form.elements.contract_enabled.checked;
  try{
    const id=editingId;
    const monitor=await api(id===null?'/api/monitors':`/api/monitors/${id}`,{method:id===null?'POST':'PUT',body:JSON.stringify(data)});
    closeModal();await refreshAll();await checkNow(monitor.id);
  }catch(err){notify(err.message)}
});
$('quick-demo').addEventListener('click',demo);
$('check-all').addEventListener('click',async()=>{if(!monitors.length){notify('Add a monitor first');return}if(busy)return;busy=true;try{notify('Checking all endpoints...');await Promise.all(monitors.map(m=>api(`/api/monitors/${m.id}/check`,{method:'POST'})));await refreshAll();notify('All checks completed')}catch(e){notify(e.message)}finally{busy=false}});
$('clock').textContent=new Date().toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'});
refreshAll().catch(e=>notify(`Cannot connect: ${e.message}`));
setInterval(()=>refreshAll().catch(()=>{}),15000);
