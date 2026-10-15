const $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
const esc = t => String(t ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const CSRF = $('meta[name=csrf]').content;

async function api(url, method = 'GET', body) {
  const o = {method, headers: {'X-CSRF-Token': CSRF}};
  if (body !== undefined) { o.headers['Content-Type'] = 'application/json'; o.body = JSON.stringify(body); }
  let r;
  try { r = await fetch(url, o); } catch { throw new Error('Cannot reach the Jarvis server. Is Flask running?'); }
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || 'Request failed');
  return d;
}
function toast(msg, err, extra) {
  const t = document.createElement('div');
  t.className = 'toast' + (err ? ' err' : '');
  t.innerHTML = `<div>${esc(msg)}</div>`;
  if (extra) t.append(extra); else setTimeout(() => t.remove(), 3500);
  $('#toasts').append(t);
  return t;
}
// Run an async action while disabling the button (prevents double submits)
async function busy(btn, fn) {
  if (btn.disabled) return;
  btn.disabled = true;
  try { await fn(); } catch (e) { toast(e.message, true); } finally { btn.disabled = false; }
}
const fmt = s => (s || '').replace('T', ' ');
const nowLocal = () => { const d = new Date(); d.setMinutes(d.getMinutes() - d.getTimezoneOffset()); return d.toISOString().slice(0, 16); };

/* ---------- navigation & clock ---------- */
function show(v) {
  $$('nav button').forEach(b => b.classList.toggle('on', b.dataset.view === v));
  $$('.view').forEach(s => s.classList.toggle('on', s.id === 'view-' + v));
  ({dashboard: loadDash, assistant: loadChat, tasks: loadTasks, reminders: loadRem, notes: loadNotes}[v] || (() => {}))()
    ?.catch?.(e => toast(e.message, true));
}
$$('nav button').forEach(b => b.onclick = () => show(b.dataset.view));
const tick = () => $('#clock').textContent = new Date().toLocaleString([], {weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit', second: '2-digit'});
setInterval(tick, 1000); tick();

/* ---------- dashboard ---------- */
async function loadDash() {
  const s = await api('/api/dashboard/stats');
  $('#d-total').textContent = s.total_tasks; $('#d-done').textContent = s.completed_tasks;
  $('#d-pend').textContent = s.pending_tasks; $('#d-up').textContent = s.upcoming_reminders;
  $('#d-bar').style.width = s.completion_percent + '%';
  $('#d-pct').textContent = s.completion_percent + '% of tasks completed';
  $('#d-rem').innerHTML = s.next_reminders.map(r => `<li>${esc(r.title)}<small>${esc(fmt(r.remind_at))}</small></li>`).join('') || '<li class="empty">No reminders yet</li>';
  $('#d-notes').innerHTML = s.recent_notes.map(n => `<li>${esc(n.title)}<small>${esc(n.updated_at)}</small></li>`).join('') || '<li class="empty">No notes yet</li>';
}

/* ---------- tasks ---------- */
let tasks = [], tFilter = 'all', tEdit = null;
async function loadTasks() {
  tasks = (await api('/api/tasks?status=' + tFilter)).items;
  const all = (await api('/api/tasks')).items, done = all.filter(t => t.completed).length;
  $('#t-count').textContent = `${all.length} total · ${done} completed · ${all.length - done} pending`;
  $('#t-list').innerHTML = tasks.map(t => `<li class="item p-${esc(t.priority)} ${t.completed ? 'done' : ''}">
    <input type="checkbox" data-a="toggle" data-id="${t.id}" ${t.completed ? 'checked' : ''}>
    <div class="body"><b class="t">${esc(t.title)}</b><p>${esc(t.description)}</p>
    <span class="badge">${esc(t.priority)}</span>${t.due_date ? `<small>Due ${esc(t.due_date)}</small>` : ''}</div>
    <div class="acts"><button data-a="edit" data-id="${t.id}">Edit</button><button data-a="del" data-id="${t.id}">Delete</button></div></li>`).join('')
    || '<li class="empty">No tasks here yet.</li>';
}
function tReset() { tEdit = null; $('#t-form').reset(); $('#t-head').textContent = 'Add task'; $('#t-cancel').hidden = true; }
$('#t-cancel').onclick = tReset;
$('#t-form').onsubmit = e => { e.preventDefault(); busy($('#t-save'), async () => {
  const title = $('#t-title').value.trim();
  if (!title) throw new Error('Task title is required');
  const data = {title, description: $('#t-desc').value, priority: $('#t-pri').value, due_date: $('#t-due').value || null};
  tEdit ? await api('/api/tasks/' + tEdit, 'PUT', data) : await api('/api/tasks', 'POST', data);
  toast(tEdit ? 'Task updated' : 'Task added'); tReset(); await loadTasks();
}); };
$('#t-filters').onclick = e => { const f = e.target.dataset.f; if (!f) return; tFilter = f;
  $$('#t-filters button').forEach(b => b.classList.toggle('on', b.dataset.f === f)); loadTasks().catch(x => toast(x.message, true)); };
$('#t-list').onclick = async e => {
  const a = e.target.dataset.a, id = e.target.dataset.id; if (!a) return;
  try {
    if (a === 'del') { if (!confirm('Delete this task?')) return; await api('/api/tasks/' + id, 'DELETE'); toast('Task deleted'); }
    if (a === 'edit') { const t = tasks.find(x => x.id == id); tEdit = t.id; $('#t-title').value = t.title; $('#t-desc').value = t.description;
      $('#t-pri').value = t.priority; $('#t-due').value = t.due_date || ''; $('#t-head').textContent = 'Edit task'; $('#t-cancel').hidden = false; scrollTo({top: 0, behavior: 'smooth'}); return; }
    if (a === 'toggle') await api('/api/tasks/' + id, 'PATCH', {completed: e.target.checked});
    await loadTasks();
  } catch (x) { toast(x.message, true); loadTasks().catch(() => {}); }
};

/* ---------- reminders ---------- */
let rems = [], shown = new Set();
async function loadRem() {
  rems = (await api('/api/reminders')).items;
  const now = nowLocal();
  const li = r => `<li class="item ${!r.done && r.remind_at < now ? 'over' : ''}"><div class="body"><b>${esc(r.title)}</b><p>${esc(r.description)}</p><small>${esc(fmt(r.remind_at))}</small></div>
    <div class="acts">${r.done ? '' : `<button data-a="done" data-id="${r.id}">Done</button>`}<button data-a="del" data-id="${r.id}">Delete</button></div></li>`;
  const f = (arr) => arr.map(li).join('') || '<li class="empty">Nothing here</li>';
  $('#r-over').innerHTML = f(rems.filter(r => !r.done && r.remind_at < now));
  $('#r-up').innerHTML = f(rems.filter(r => !r.done && r.remind_at >= now));
  $('#r-done').innerHTML = f(rems.filter(r => r.done));
}
$('#r-form').onsubmit = e => { e.preventDefault(); busy($('#r-save'), async () => {
  const title = $('#r-title').value.trim(), at = $('#r-at').value;
  if (!title) throw new Error('Reminder title is required');
  if (!at) throw new Error('Please pick a date and time');
  await api('/api/reminders', 'POST', {title, description: $('#r-desc').value, remind_at: at});
  toast('Reminder saved'); $('#r-form').reset(); await loadRem();
}); };
$('#view-reminders').onclick = async e => {
  const a = e.target.dataset.a, id = e.target.dataset.id; if (!a) return;
  try {
    if (a === 'del') { if (!confirm('Delete this reminder?')) return; await api('/api/reminders/' + id, 'DELETE'); }
    if (a === 'done') await api('/api/reminders/' + id, 'PATCH', {done: true});
    await loadRem();
  } catch (x) { toast(x.message, true); }
};
// In-app alerts while the page is open (no background/browser-closed notifications)
async function checkDue() {
  try {
    const list = (await api('/api/reminders')).items, now = nowLocal();
    list.filter(r => !r.done && r.remind_at <= now && !shown.has(r.id)).forEach(r => {
      shown.add(r.id);
      const b = document.createElement('button'); b.className = 'btn'; b.textContent = 'Dismiss';
      const t = toast('⏰ Reminder: ' + r.title, false, b);
      b.onclick = async () => { try { await api('/api/reminders/' + r.id, 'PATCH', {done: true}); t.remove(); if ($('#view-reminders').classList.contains('on')) loadRem(); } catch (x) { toast(x.message, true); } };
    });
  } catch {}
}
setInterval(checkDue, 15000); checkDue();

/* ---------- notes ---------- */
let notes = [], nEdit = null;
async function loadNotes() {
  const q = $('#n-search').value.trim();
  notes = (await api('/api/notes' + (q ? '?q=' + encodeURIComponent(q) : ''))).items;
  $('#n-list').innerHTML = notes.map(n => `<li class="item"><div class="body"><b>${esc(n.title)}</b><p>${esc(n.content)}</p>
    <small>Created ${esc(n.created_at)}${n.updated_at !== n.created_at ? ' · Edited ' + esc(n.updated_at) : ''}</small></div>
    <div class="acts"><button data-a="edit" data-id="${n.id}">Edit</button><button data-a="del" data-id="${n.id}">Delete</button></div></li>`).join('')
    || `<li class="empty">${q ? 'No notes match your search.' : 'No notes yet.'}</li>`;
}
function nReset() { nEdit = null; $('#n-form').reset(); $('#n-head').textContent = 'New note'; $('#n-cancel').hidden = true; }
$('#n-cancel').onclick = nReset;
$('#n-search').oninput = () => loadNotes().catch(e => toast(e.message, true));
$('#n-form').onsubmit = e => { e.preventDefault(); busy($('#n-save'), async () => {
  const title = $('#n-title').value.trim();
  if (!title) throw new Error('Note title is required');
  const data = {title, content: $('#n-content').value};
  nEdit ? await api('/api/notes/' + nEdit, 'PUT', data) : await api('/api/notes', 'POST', data);
  toast(nEdit ? 'Note updated' : 'Note saved'); nReset(); await loadNotes();
}); };
$('#n-list').onclick = async e => {
  const a = e.target.dataset.a, id = e.target.dataset.id; if (!a) return;
  try {
    if (a === 'del') { if (!confirm('Delete this note?')) return; await api('/api/notes/' + id, 'DELETE'); toast('Note deleted'); await loadNotes(); }
    if (a === 'edit') { const n = notes.find(x => x.id == id); nEdit = n.id; $('#n-title').value = n.title; $('#n-content').value = n.content;
      $('#n-head').textContent = 'Edit note'; $('#n-cancel').hidden = false; scrollTo({top: 0, behavior: 'smooth'}); }
  } catch (x) { toast(x.message, true); }
};

/* ---------- assistant ---------- */
const speechOK = 'speechSynthesis' in window;
const voiceOn = () => speechOK && localStorage.getItem('jarvis_voice') === '1';
function addMsg(role, text, action) {
  const d = document.createElement('div'); d.className = 'm ' + role; d.textContent = text;
  if (action && action.type === 'create_task') {
    const b = document.createElement('button'); b.className = 'btn'; b.textContent = 'Confirm: create task';
    b.onclick = () => busy(b, async () => { await api('/api/tasks', 'POST', {title: action.title}); b.remove(); addMsg('bot', `Task "${action.title}" created.`); });
    d.append(document.createElement('br'), b);
  }
  $('#msgs').append(d); $('#msgs').scrollTop = 1e9; return d;
}
let chatLoaded = false;
async function loadChat() {
  if (chatLoaded) return; chatLoaded = true;
  const h = (await api('/api/chat/history')).items;
  addMsg('bot', 'Jarvis online. I am a local, offline assistant — ask "What can you do?" to see my commands.');
  h.forEach(m => addMsg(m.role === 'user' ? 'user' : 'bot', m.content));
}
async function send(text) {
  text = text.trim(); if (!text) return;
  const btn = $('#chat-send'); if (btn.disabled) return;
  addMsg('user', text); $('#chat-in').value = '';
  const wait = addMsg('bot', ''); wait.innerHTML = '<span class="dots"><span></span><span></span><span></span></span>';
  btn.disabled = true;
  try {
    const r = await api('/api/chat', 'POST', {message: text}); wait.remove(); addMsg('bot', r.reply, r.action);
    if (voiceOn()) { speechSynthesis.cancel(); speechSynthesis.speak(new SpeechSynthesisUtterance(r.reply)); }
  } catch (e) { wait.remove(); addMsg('bot', '⚠ ' + e.message); } finally { btn.disabled = false; $('#chat-in').focus(); }
}
$('#chat-send').onclick = () => send($('#chat-in').value);
$('#chat-in').onkeydown = e => { if (e.key === 'Enter') send(e.target.value); };
$$('.quick button').forEach(b => b.onclick = () => send(b.dataset.q));

/* ---------- settings ---------- */
$('#s-voice').checked = voiceOn();
$('#s-voice').disabled = !speechOK;
$('#s-voice-note').textContent = speechOK ? '' : 'Speech output is not supported in this browser.';
$('#s-voice').onchange = e => localStorage.setItem('jarvis_voice', e.target.checked ? '1' : '0');
$('#s-clear').onclick = () => busy($('#s-clear'), async () => {
  if (!confirm('Clear all chat history?')) return;
  await api('/api/chat/clear', 'POST', {}); $('#msgs').innerHTML = ''; chatLoaded = false; toast('Chat history cleared');
});

show('dashboard');
