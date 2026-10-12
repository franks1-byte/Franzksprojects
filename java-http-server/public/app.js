const list = document.getElementById('list');
const errorEl = document.getElementById('error');
let filter = '';

async function api(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error);
  }
  return res.status === 204 ? null : res.json();
}

async function refresh() {
  try {
    const todos = await api('GET', '/api/todos' + (filter ? '?done=' + filter : ''));
    list.replaceChildren(...todos.map(render));
    errorEl.textContent = '';
  } catch (e) { errorEl.textContent = e.message; }
  refreshStats();
}

function render(todo) {
  const li = document.createElement('li');
  li.className = todo.done ? 'done' : '';
  const box = Object.assign(document.createElement('input'), { type: 'checkbox', checked: todo.done });
  box.onchange = () => api('PATCH', '/api/todos/' + todo.id, { done: box.checked }).then(refresh);
  const span = Object.assign(document.createElement('span'), { textContent: todo.title });
  const del = Object.assign(document.createElement('button'), { textContent: '✕', title: 'Delete' });
  del.onclick = () => api('DELETE', '/api/todos/' + todo.id).then(refresh);
  li.append(box, span, del);
  return li;
}

document.getElementById('add').onsubmit = async e => {
  e.preventDefault();
  const input = document.getElementById('title');
  try {
    await api('POST', '/api/todos', { title: input.value });
    input.value = '';
    refresh();
  } catch (err) { errorEl.textContent = err.message; }
};

document.querySelectorAll('.filters button').forEach(btn => btn.onclick = () => {
  filter = btn.dataset.filter;
  document.querySelectorAll('.filters button').forEach(b => b.classList.toggle('active', b === btn));
  refresh();
});

async function refreshStats() {
  const s = await api('GET', '/api/stats').catch(() => null);
  if (s) document.getElementById('stats').textContent =
    `${s.requests} requests served · up ${s.uptimeSeconds}s · ${s.todos} todos · ${s.threads} JVM threads`;
}

refresh();
