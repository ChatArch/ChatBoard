const COLUMN_DEFS = [
  { key: 'thoughts', title: '想法' },
  { key: 'project', title: '进行中' },
  { key: 'archiving', title: '归档中' },
  { key: 'archive', title: '已归档' },
];
const TASK_COLUMN_DEFS = [
  { key: 'inbox', title: 'Inbox' },
  { key: 'ready', title: 'Ready' },
  { key: 'running', title: 'Running' },
  { key: 'blocked', title: 'Blocked' },
  { key: 'review', title: 'Review' },
  { key: 'done', title: 'Done' },
];
const PAGE_SIZE = 24;
const COLUMN_WIDTH_STORAGE_KEY = 'chatboard.columnWidths.v1';
const BACKEND_STORAGE_KEY = 'chatboard.backends.v1';
const ACTIVE_BACKEND_SESSION_KEY = 'chatboard.activeBackend.v1';
const COLUMN_MIN_WEIGHT = 0.45;
const BOARD_MOBILE_MEDIA = '(max-width: 980px)';
const state = {
  catalog: null,
  activePage: 'projects',
  selected: null,
  fullscreen: false,
  fileExplorerShowAll: false,
  columnWidths: loadColumnWidthState(),
  backends: loadBackendState(),
  activeBackendId: loadActiveBackendId(),
  resizing: null,
};

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
const ISO_DATE_RE = /^(\d{4})-(\d{2})-(\d{2})$/;

function cardDate(card) {
  if (card.date) return String(card.date);
  const match = String(card.workspace_path || '').match(/(?:^|\/)(?:(\d{4})-)?(\d{2})-(\d{2})(?:-|\/|$)/);
  if (!match) return '';
  const year = match[1] || String(new Date().getFullYear());
  return `${year}-${match[2]}-${match[3]}`;
}

function dateLabel(date) {
  const match = String(date || '').match(ISO_DATE_RE);
  if (!match) return date || 'Undated';
  return `${match[2]}-${match[3]}`;
}

function isMobileBoard() {
  return window.matchMedia(BOARD_MOBILE_MEDIA).matches;
}

function loadColumnWidthState() {
  try {
    return JSON.parse(localStorage.getItem(COLUMN_WIDTH_STORAGE_KEY) || '{}') || {};
  } catch (err) {
    return {};
  }
}

function persistColumnWidthState() {
  try {
    localStorage.setItem(COLUMN_WIDTH_STORAGE_KEY, JSON.stringify(state.columnWidths));
  } catch (err) {
    // Browser storage can be disabled; resizing still works for the session.
  }
}

function defaultColumnWeights(columns) {
  if (state.activePage === 'tasks') return Object.fromEntries(columns.map((column) => [column.key, 1]));
  const hasCards = (key) => Boolean((columns.find((column) => column.key === key)?.cards || []).length);
  return {
    thoughts: hasCards('thoughts') ? 1.1 : 0.55,
    project: hasCards('project') ? 2.5 : 1,
    archiving: hasCards('archiving') ? 1 : 0.75,
    archive: hasCards('archive') ? 1 : 0.75,
  };
}

function columnWeights(columns) {
  const saved = state.columnWidths[state.activePage] || {};
  const defaults = defaultColumnWeights(columns);
  return columns.map((column) => Math.max(COLUMN_MIN_WEIGHT, Number(saved[column.key]) || defaults[column.key] || 1));
}

function applyBoardTemplate(columns = state.catalog?.columns || []) {
  const board = $('board');
  if (!board) return;
  if (isMobileBoard()) {
    board.style.gridTemplateColumns = '';
    return;
  }
  const weights = columnWeights(columns);
  board.style.gridTemplateColumns = weights.map((weight) => `minmax(150px, ${weight.toFixed(3)}fr)`).join(' ');
}

function setColumnWeights(columns, weights) {
  state.columnWidths[state.activePage] = Object.fromEntries(columns.map((column, index) => [column.key, weights[index]]));
  applyBoardTemplate(columns);
}

function resetColumnWidths() {
  delete state.columnWidths[state.activePage];
  persistColumnWidthState();
  applyBoardTemplate();
}

function startColumnResize(event, columns) {
  if (isMobileBoard()) return;
  const index = Number(event.currentTarget.dataset.resizeIndex);
  if (!Number.isFinite(index) || !columns[index + 1]) return;
  event.preventDefault();
  const board = $('board');
  const weights = columnWeights(columns);
  const pairTotal = weights[index] + weights[index + 1];
  state.resizing = {
    columns,
    index,
    startX: event.clientX,
    startWeights: weights,
    totalWeight: weights.reduce((total, weight) => total + weight, 0),
    pairTotal,
    boardWidth: Math.max(1, board.getBoundingClientRect().width - 16 * Math.max(0, columns.length - 1)),
  };
  document.body.classList.add('resizing-columns');
  document.addEventListener('pointermove', onColumnResize);
  document.addEventListener('pointerup', stopColumnResize, { once: true });
}

function onColumnResize(event) {
  const resize = state.resizing;
  if (!resize) return;
  const weights = [...resize.startWeights];
  const delta = ((event.clientX - resize.startX) / resize.boardWidth) * resize.totalWeight;
  const maxLeft = Math.max(COLUMN_MIN_WEIGHT, resize.pairTotal - COLUMN_MIN_WEIGHT);
  const left = Math.min(Math.max(COLUMN_MIN_WEIGHT, resize.startWeights[resize.index] + delta), maxLeft);
  weights[resize.index] = left;
  weights[resize.index + 1] = resize.pairTotal - left;
  setColumnWeights(resize.columns, weights);
}

function stopColumnResize() {
  if (!state.resizing) return;
  state.resizing = null;
  persistColumnWidthState();
  document.body.classList.remove('resizing-columns');
  document.removeEventListener('pointermove', onColumnResize);
}

function bindColumnResizeHandles(columns) {
  document.querySelectorAll('[data-resize-index]').forEach((node) => {
    node.addEventListener('pointerdown', (event) => startColumnResize(event, columns));
    node.addEventListener('dblclick', (event) => {
      event.preventDefault();
      resetColumnWidths();
    });
  });
}

function currentSiteBackend() {
  return { id: 'current', name: 'This site', url: window.location.origin, token: '', builtin: true };
}

function normalizeBackendUrl(value) {
  const raw = String(value || window.location.origin).trim() || window.location.origin;
  const url = new URL(raw, window.location.origin);
  url.hash = '';
  url.search = '';
  return url.toString().replace(/\/$/, '');
}

function loadBackendState() {
  try {
    const parsed = JSON.parse(localStorage.getItem(BACKEND_STORAGE_KEY) || '{}') || {};
    const backends = Array.isArray(parsed.backends) ? parsed.backends : [];
    return { backends: backends.filter((backend) => backend && backend.id && backend.url) };
  } catch (err) {
    return { backends: [] };
  }
}

function persistBackendState() {
  try {
    localStorage.setItem(BACKEND_STORAGE_KEY, JSON.stringify({ backends: state.backends.backends || [] }));
  } catch (err) {
    setBackendStatus('Backend list could not be saved in this browser.', true);
  }
}

function loadActiveBackendId() {
  try {
    return sessionStorage.getItem(ACTIVE_BACKEND_SESSION_KEY) || 'current';
  } catch (err) {
    return 'current';
  }
}

function persistActiveBackendId(id) {
  state.activeBackendId = id || 'current';
  try {
    sessionStorage.setItem(ACTIVE_BACKEND_SESSION_KEY, state.activeBackendId);
  } catch (err) {
    // Session storage is optional; keep the in-memory selection for this tab.
  }
}

function allBackends() {
  const saved = state.backends.backends || [];
  return [currentSiteBackend(), ...saved];
}

function activeBackend() {
  return allBackends().find((backend) => backend.id === state.activeBackendId) || currentSiteBackend();
}

function backendApiUrl(path, backend = activeBackend()) {
  const route = String(path || '').startsWith('/') ? String(path) : `/${path}`;
  return `${normalizeBackendUrl(backend.url)}${route}`;
}

function backendHeaders(backend, options = {}) {
  const headers = { 'Content-Type': 'application/json', ...(options.headers || {}) };
  if (backend.token) headers['X-ChatBoard-Token'] = backend.token;
  return headers;
}

async function api(path, options = {}) {
  const backend = activeBackend();
  const response = await fetch(backendApiUrl(path, backend), {
    ...options,
    credentials: options.credentials || (backend.token ? 'same-origin' : 'include'),
    headers: backendHeaders(backend, options),
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function initAuthControls() {
  const logoutBtn = $('logoutBtn');
  if (!logoutBtn) return;
  try {
    const auth = await api('/api/auth');
    logoutBtn.hidden = !auth.enabled;
    logoutBtn.onclick = async () => {
      await api('/api/logout', { method: 'POST', body: '{}' });
      if (activeBackend().id === 'current') window.location.assign('/login');
      else refresh();
    };
  } catch (err) {
    logoutBtn.hidden = true;
  }
}

function setBackendStatus(message, isError = false) {
  const node = $('backendSettingsStatus');
  if (!node) return;
  node.textContent = message;
  node.classList.toggle('error-text', Boolean(isError));
}

function renderBackendSummary() {
  const backend = activeBackend();
  const summary = $('backendActiveSummary');
  if (summary) summary.innerHTML = `<strong>${esc(backend.name)}</strong><span>${esc(normalizeBackendUrl(backend.url))}</span>`;
  const link = $('openBackendLink');
  if (link) link.href = normalizeBackendUrl(backend.url);
}

function fillBackendForm(backend) {
  $('backendName').value = backend?.builtin ? '' : (backend?.name || '');
  $('backendUrl').value = backend?.builtin ? window.location.origin : (backend?.url || '');
  $('backendToken').value = backend?.builtin ? '' : (backend?.token || '');
}

function renderBackendSelect() {
  const select = $('backendSelect');
  if (!select) return;
  const backends = allBackends();
  select.innerHTML = backends.map((backend) => `<option value="${esc(backend.id)}">${esc(backend.name)} — ${esc(normalizeBackendUrl(backend.url))}</option>`).join('');
  const selected = backends.find((backend) => backend.id === state.activeBackendId) ? state.activeBackendId : 'current';
  select.value = selected;
  fillBackendForm(backends.find((backend) => backend.id === selected));
  renderBackendSummary();
}

function openSettings() {
  renderBackendSelect();
  setBackendStatus('Current site is always available and is the default for new sessions. Saved tokens stay in this browser.');
  $('settingsModal').classList.add('open');
  $('settingsModal').setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}

function closeSettings() {
  $('settingsModal').classList.remove('open');
  $('settingsModal').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
}

function selectedBackendFromForm() {
  const id = $('backendSelect').value || 'current';
  return allBackends().find((backend) => backend.id === id) || currentSiteBackend();
}

function useBackend(id) {
  persistActiveBackendId(id || 'current');
  renderBackendSelect();
  initAuthControls();
  refresh();
}

function saveBackendFromForm() {
  let url;
  try {
    url = normalizeBackendUrl($('backendUrl').value);
  } catch (err) {
    setBackendStatus('Backend URL is not valid.', true);
    return;
  }
  const selected = selectedBackendFromForm();
  const id = selected.builtin ? `backend-${Date.now().toString(36)}` : selected.id;
  const name = $('backendName').value.trim() || new URL(url).host;
  const token = $('backendToken').value.trim();
  const next = { id, name, url, token };
  const backends = (state.backends.backends || []).filter((backend) => backend.id !== id && normalizeBackendUrl(backend.url) !== url);
  state.backends.backends = [...backends, next];
  persistBackendState();
  persistActiveBackendId(id);
  renderBackendSelect();
  setBackendStatus(`Saved and selected ${name} for this session.`);
  initAuthControls();
  refresh();
}

function removeSelectedBackend() {
  const selected = selectedBackendFromForm();
  if (selected.builtin) {
    setBackendStatus('The current site backend cannot be removed.', true);
    return;
  }
  state.backends.backends = (state.backends.backends || []).filter((backend) => backend.id !== selected.id);
  persistBackendState();
  persistActiveBackendId('current');
  renderBackendSelect();
  setBackendStatus(`Removed ${selected.name}; using this site for the session.`);
  initAuthControls();
  refresh();
}

async function testBackendFromForm() {
  let candidate;
  try {
    candidate = {
      ...selectedBackendFromForm(),
      name: $('backendName').value.trim() || selectedBackendFromForm().name,
      url: normalizeBackendUrl($('backendUrl').value || selectedBackendFromForm().url),
      token: $('backendToken').value.trim(),
    };
  } catch (err) {
    setBackendStatus('Backend URL is not valid.', true);
    return;
  }
  setBackendStatus('Checking backend health...');
  try {
    const response = await fetch(backendApiUrl('/api/health', candidate), {
      credentials: candidate.token ? 'same-origin' : 'include',
      headers: backendHeaders(candidate),
    });
    if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
    const health = await response.json();
    setBackendStatus(`Backend is reachable. Version: ${health.version || 'unknown'}.`);
  } catch (err) {
    setBackendStatus(`Backend health check failed: ${err.message || err}. Check URL, CORS, login, or API token.`, true);
  }
}

function setActivePage(page) {
  state.activePage = page;
  state.selected = null;
  document.querySelectorAll('[data-page-tab]').forEach((button) => {
    button.classList.toggle('active', button.dataset.pageTab === page);
  });
  const ensure = $('ensureCards');
  if (ensure) ensure.closest('label').style.display = page === 'projects' ? '' : 'none';
  refresh();
}

function emptyCatalog() {
  const definitions = state.activePage === 'tasks' ? TASK_COLUMN_DEFS : COLUMN_DEFS;
  return {
    root: '',
    columns: definitions.map((column) => ({
      ...column,
      cards: [],
      loading: false,
      loaded: false,
      error: null,
      has_more: false,
      next_offset: 0,
    })),
  };
}

function columnState(key) {
  return state.catalog.columns.find((column) => column.key === key);
}

function updateColumn(key, patch) {
  const column = columnState(key);
  Object.assign(column, patch);
}

function loadedCardCount() {
  return (state.catalog?.columns || []).reduce((total, column) => total + (column.cards || []).length, 0);
}

function cardHtml(card) {
  const active = state.selected === card.id ? ' active' : '';
  const date = cardDate(card);
  const description = card.description || card.summary || '';
  const tags = (card.tags || []).slice(0, 3).map((tag) => `<span class="badge">#${esc(tag)}</span>`).join('');
  const links = card.links || {};
  const assets = [
    links.prd ? '<span class="badge asset">PRD</span>' : '',
    links.progress ? '<span class="badge asset">Progress</span>' : '',
    (links.reports || []).length ? `<span class="badge asset">Reports ${(links.reports || []).length}</span>` : '',
    (links.feishu || []).length ? `<span class="badge asset">Feishu ${(links.feishu || []).length}</span>` : '',
  ].join('');
  const nested = card.nested_items || [];
  const nestedItems = nested.length ? `<div class="nested-items">
    <div class="nested-label">Items ${esc(nested.length)}</div>
    ${nested.slice(0, 6).map((item) => `<button class="nested-item" type="button" data-nested-card-id="${esc(item.id)}">${esc(item.title)}</button>`).join('')}
    ${nested.length > 6 ? `<div class="nested-more">+${esc(nested.length - 6)} more</div>` : ''}
  </div>` : '';
  return `<article class="card${active}" data-card-id="${esc(card.id)}">
    <div class="card-title">${esc(card.title)}</div>
    ${date ? `<div class="card-date">${esc(dateLabel(date))}</div>` : ''}
    ${description ? `<div class="card-description">${esc(description)}</div>` : ''}
    ${nestedItems}
    <div class="card-meta">
      <span class="badge area">${esc(card.area)}</span>
      <span class="badge stage">${esc(card.stage)}</span>
      ${date ? `<span class="badge date">${esc(date)}</span>` : ''}
      ${tags}
      ${assets}
    </div>
  </article>`;
}

function renderSummary() {
  const columns = state.catalog?.columns || [];
  const loaded = loadedCardCount();
  const loading = columns.some((column) => column.loading);
  const complete = columns.every((column) => column.loaded && !column.has_more);
  const backend = activeBackend();
  $('summary').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Loaded</span><strong>${esc(loaded)}${complete ? '' : '+'}</strong></div>
      ${columns.map((column) => `<div class="stat-card"><span>${esc(column.title)}</span><strong>${esc((column.cards || []).length)}${column.has_more ? '+' : ''}</strong></div>`).join('')}
      <div class="stat-card"><span>Status</span><strong>${loading ? 'Loading' : 'Ready'}</strong></div>
    </div>
    <div class="tag-strip"><span class="tag-chip muted">Progressive loading: columns render first, cards arrive in pages.</span></div>
    <div class="root-line"><span>Workspace: ${esc(state.catalog?.root || 'loading...')}</span><span>Backend: ${esc(backend.name)} · ${esc(normalizeBackendUrl(backend.url))}</span></div>
  `;
}

function archiveColumnCardsHtml(cards = []) {
  if (!cards.length) return '';
  const groups = {};
  cards.forEach((card) => {
    const match = String(card.workspace_path || '').match(/archive\/(\d{4}-\d{2}-\d{2})\//);
    const day = match ? match[1] : 'undated';
    const month = day === 'undated' ? 'undated' : day.slice(0, 7);
    groups[month] = groups[month] || {};
    groups[month][day] = groups[month][day] || [];
    groups[month][day].push(card);
  });
  return Object.keys(groups).sort().reverse().map((month, monthIndex) => `
    <details class="archive-month" ${monthIndex === 0 ? 'open' : ''}>
      <summary>${esc(month)}</summary>
      ${Object.keys(groups[month]).sort().reverse().map((day, dayIndex) => `
        <details class="archive-day" ${monthIndex === 0 && dayIndex === 0 ? 'open' : ''}>
          <summary>${esc(day)} <span>${groups[month][day].length}</span></summary>
          <div class="card-list">${groups[month][day].map(cardHtml).join('')}</div>
        </details>
      `).join('')}
    </details>
  `).join('');
}

function dateGroupedCardsHtml(cards = []) {
  if (!cards.length) return '';
  const groups = {};
  cards.forEach((card) => {
    const date = cardDate(card) || 'undated';
    groups[date] = groups[date] || [];
    groups[date].push(card);
  });
  return Object.keys(groups).sort().reverse().map((date, index) => `
    <details class="date-group" ${index < 3 ? 'open' : ''}>
      <summary>${esc(dateLabel(date))} <span>${groups[date].length}</span></summary>
      <div class="card-list">${groups[date].map(cardHtml).join('')}</div>
    </details>
  `).join('');
}

function columnFooterHtml(column) {
  if (column.error) return `<div class="error">${esc(column.error)}</div>`;
  if (column.loading) return '<div class="column-loading"><span></span> Loading cards...</div>';
  if (column.has_more) return `<button class="load-more" type="button" data-load-more="${esc(column.key)}">Load more</button>`;
  if (!column.cards.length) return '<div class="empty-column-note">No cards yet</div>';
  return '';
}

function columnCardsHtml(column) {
  const cards = column.cards || [];
  const body = column.key === 'archive'
    ? archiveColumnCardsHtml(cards)
    : ['thoughts', 'project', 'archiving'].includes(column.key)
      ? dateGroupedCardsHtml(cards)
      : `<div class="card-list">${cards.map(cardHtml).join('')}</div>`;
  return `${body}${columnFooterHtml(column)}`;
}

function renderCatalog() {
  const columns = state.catalog?.columns || [];
  const nonEmpty = columns.filter((column) => (column.cards || []).length > 0);
  renderSummary();
  $('emptyColumns').innerHTML = '';
  $('board').className = 'board';
  if (nonEmpty.length <= 1) $('board').classList.add('mostly-project');
  $('board').innerHTML = columns.map((column, index) => `
    <section class="column" data-column="${esc(column.key)}">
      ${index < columns.length - 1 ? `<button class="column-resize-handle" type="button" data-resize-index="${index}" aria-label="Resize ${esc(column.title)} column" title="Drag to resize columns; double-click to reset widths"></button>` : ''}
      <div class="column-head"><span class="column-title">${esc(column.title)}</span><span class="count">${(column.cards || []).length}${column.has_more ? '+' : ''}</span></div>
      ${columnCardsHtml(column)}
    </section>
  `).join('');
  applyBoardTemplate(columns);
  bindColumnResizeHandles(columns);
  document.querySelectorAll('.card').forEach((node) => {
    node.addEventListener('click', () => loadDetail(node.dataset.cardId));
  });
  document.querySelectorAll('.nested-item').forEach((node) => {
    node.addEventListener('click', (event) => {
      event.stopPropagation();
      loadDetail(node.dataset.nestedCardId);
    });
  });
  document.querySelectorAll('[data-load-more]').forEach((node) => {
    node.addEventListener('click', () => loadColumn(node.dataset.loadMore, columnState(node.dataset.loadMore).next_offset || 0));
  });
}

function fileIcon(node) {
  if (node.type === 'directory') return '▸';
  const name = String(node.name || '').toLowerCase();
  if (name.endsWith('.md')) return 'M';
  if (name.endsWith('.json')) return '{}';
  if (name.endsWith('.py')) return 'py';
  if (name.endsWith('.js')) return 'js';
  return '•';
}

function explorerNodeHtml(node, depth = 0) {
  const isDir = node.type === 'directory';
  const label = esc(node.name);
  const path = esc(node.path || '');
  const cls = isDir ? 'directory' : 'file';
  return `<div class="explorer-row ${cls}" data-node-type="${esc(node.type)}" data-file-path="${path}" style="--depth:${depth}">
    <span class="explorer-caret">${esc(fileIcon(node))}</span>
    <span class="explorer-name">${label}</span>
    ${!isDir && node.size ? `<span class="explorer-size">${esc(node.size)}b</span>` : ''}
  </div>${isDir ? `<div class="explorer-children" data-children-for="${path}"></div>` : ''}`;
}

function filesExplorerHtml() {
  return `<div class="files-layout ide-files">
    <div class="explorer-pane">
      <div class="explorer-toolbar">
        <span>Explorer</span>
        <div class="explorer-actions">
          <label class="mini-toggle"><input type="checkbox" id="showAllFilesToggle"> Show all</label>
          <button class="ghost mini" type="button" id="reloadFilesBtn">Reload</button>
        </div>
      </div>
      <div class="explorer-root" id="fileExplorer"><div class="column-loading"><span></span> Loading files...</div></div>
    </div>
    <div class="preview-pane">
      <div class="preview-path" id="filePreviewPath">No file selected</div>
      <pre id="filePreview" class="file-preview">Select a text file to preview.</pre>
    </div>
  </div>`;
}

function sectionHtml(section) {
  let body = '';
  const keyClass = esc(section.key || 'section');
  if (section.kind === 'markdown') {
    body = section.data ? `<pre>${esc(section.data)}</pre>` : '<div class="card-summary">Empty</div>';
  } else if (section.kind === 'file_tree') {
    body = filesExplorerHtml();
  } else if (section.kind === 'fields') {
    const card = section.data || {};
    body = `<div class="kv">
      <div>ID</div><div>${esc(card.id)}</div>
      <div>Area</div><div>${esc(card.area)}</div>
      <div>Stage</div><div>${esc(card.stage)}</div>
      <div>Date</div><div>${esc(card.date || '—')}</div>
      <div>Description</div><div>${esc(card.description || '—')}</div>
      <div>Priority</div><div>${esc(card.priority)}</div>
      <div>Assignee</div><div>${esc(card.assignee || '—')}</div>
      <div>Path</div><div>${esc(card.workspace_path || '—')}</div>
    </div>
    ${card.summary ? `<div class="overview-summary"><span>Summary</span><p>${esc(card.summary)}</p></div>` : ''}`;
  } else if (Array.isArray(section.data)) {
    body = section.data.length ? `<pre>${esc(JSON.stringify(section.data, null, 2))}</pre>` : '<div class="card-summary">Empty</div>';
  } else {
    body = `<pre>${esc(JSON.stringify(section.data || {}, null, 2))}</pre>`;
  }
  return `<section class="section tab-panel ${keyClass} ${section.kind === 'markdown' ? 'markdown' : ''}" data-tab-panel="${esc(section.key)}">${body}</section>`;
}

async function loadExplorerDirectory(cardId, path = '', target = null, depth = 0) {
  const container = target || $('fileExplorer');
  container.innerHTML = '<div class="column-loading"><span></span> Loading files...</div>';
  try {
    const params = new URLSearchParams({ path, include_hidden: state.fileExplorerShowAll ? 'true' : 'false' });
    const data = await api(`/api/cards/${encodeURIComponent(cardId)}/files/list?${params.toString()}`);
    const children = data.children || [];
    container.innerHTML = children.length
      ? children.map((node) => explorerNodeHtml(node, depth)).join('')
      : '<div class="empty-column-note">Empty directory</div>';
    bindExplorerRows(cardId, container, depth);
  } catch (err) {
    container.innerHTML = `<div class="error">${esc(err.message || err)}</div>`;
  }
}

function bindExplorerRows(cardId, rootNode = document, depth = 0) {
  rootNode.querySelectorAll('.explorer-row').forEach((row) => {
    row.addEventListener('click', async () => {
      document.querySelectorAll('.explorer-row.selected').forEach((node) => node.classList.remove('selected'));
      row.classList.add('selected');
      const path = row.dataset.filePath || '';
      if (row.dataset.nodeType === 'directory') {
        const children = [...document.querySelectorAll('.explorer-children')].find((node) => node.dataset.childrenFor === path);
        const expanded = row.classList.toggle('expanded');
        row.querySelector('.explorer-caret').textContent = expanded ? '▾' : '▸';
        if (!children) return;
        if (!expanded) {
          children.innerHTML = '';
          return;
        }
        await loadExplorerDirectory(cardId, path, children, depth + 1);
        return;
      }
      const preview = $('filePreview');
      const previewPath = $('filePreviewPath');
      previewPath.textContent = path;
      preview.textContent = 'Loading...';
      const content = await api(`/api/cards/${encodeURIComponent(cardId)}/files/content?path=${encodeURIComponent(path)}`);
      preview.textContent = content.content || '';
    });
  });
}

function initFilesExplorer(cardId) {
  const explorer = $('fileExplorer');
  if (!explorer) return;
  state.fileExplorerShowAll = false;
  const showAllToggle = $('showAllFilesToggle');
  if (showAllToggle) {
    showAllToggle.checked = state.fileExplorerShowAll;
    showAllToggle.addEventListener('change', () => {
      state.fileExplorerShowAll = showAllToggle.checked;
      loadExplorerDirectory(cardId);
    });
  }
  $('reloadFilesBtn')?.addEventListener('click', () => loadExplorerDirectory(cardId));
  loadExplorerDirectory(cardId);
}

function renderDetail(detail) {
  const sections = detail.sections || [];
  const active = sections[0] && sections[0].key;
  $('detailBody').innerHTML = `
    <div class="detail-tabs">${sections.map((section, index) => `<button class="tab-button ${index === 0 ? 'active' : ''}" type="button" data-tab="${esc(section.key)}">${esc(section.title)}</button>`).join('')}</div>
    <div class="tab-panels">${sections.map(sectionHtml).join('')}</div>
  `;
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.tabPanel === active));
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tab-button').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.tabPanel === button.dataset.tab));
      button.classList.add('active');
    });
  });
  initFilesExplorer(detail.card.id);
}

function openModal() {
  $('detailModal').classList.add('open');
  $('detailModal').setAttribute('aria-hidden', 'false');
  document.body.classList.add('modal-open');
}

function closeModal() {
  $('detailModal').classList.remove('open');
  $('detailModal').setAttribute('aria-hidden', 'true');
  document.body.classList.remove('modal-open');
  state.selected = null;
  if (state.catalog) renderCatalog();
}

function setFullscreen(on) {
  state.fullscreen = on;
  $('detailPanel').classList.toggle('fullscreen', on);
  $('fullscreenBtn').textContent = on ? 'Exit Fullscreen' : 'Fullscreen';
}

async function loadDetail(cardId) {
  state.selected = cardId;
  renderCatalog();
  openModal();
  $('detailTitle').textContent = 'Loading...';
  $('detailPath').textContent = cardId;
  $('detailBody').innerHTML = '<div class="section"><h3>Loading</h3><div class="card-summary">Fetching card detail...</div></div>';
  const detail = await api(`/api/cards/${encodeURIComponent(cardId)}`);
  const card = detail.card;
  $('detailTitle').textContent = card.title;
  $('detailPath').textContent = card.workspace_path;
  renderDetail(detail);
}

async function loadColumn(key, offset = 0) {
  const column = columnState(key);
  if (!column || column.loading) return;
  updateColumn(key, { loading: true, error: null });
  renderCatalog();
  try {
    const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
    if ($('ensureCards').checked) params.set('ensure', 'true');
    const data = await api(`/api/columns/${encodeURIComponent(key)}?${params.toString()}`);
    const existing = offset ? (column.cards || []) : [];
    state.catalog.root = data.root || state.catalog.root;
    updateColumn(key, {
      title: data.title || column.title,
      cards: existing.concat(data.cards || []),
      has_more: Boolean(data.has_more),
      next_offset: data.next_offset || existing.length + (data.cards || []).length,
      loading: false,
      loaded: true,
    });
  } catch (err) {
    updateColumn(key, { loading: false, loaded: true, error: err.message || String(err) });
  }
  renderCatalog();
}

async function loadTasks() {
  try {
    const params = new URLSearchParams();
    const data = await api(`/api/tasks?${params.toString()}`);
    state.catalog = {
      root: data.root || '',
      columns: (data.columns || TASK_COLUMN_DEFS).map((column) => ({
        ...column,
        cards: column.cards || [],
        loading: false,
        loaded: true,
        error: null,
        has_more: false,
        next_offset: (column.cards || []).length,
      })),
    };
  } catch (err) {
    state.catalog = emptyCatalog();
    state.catalog.columns[0].error = err.message || String(err);
  }
  renderCatalog();
}

async function refresh() {
  state.selected = null;
  state.catalog = emptyCatalog();
  renderCatalog();
  if (state.activePage === 'tasks') {
    await loadTasks();
    return;
  }
  COLUMN_DEFS.forEach((column) => loadColumn(column.key, 0));
}

$('refreshBtn').addEventListener('click', refresh);
$('settingsBtn').addEventListener('click', openSettings);
$('ensureCards').addEventListener('change', refresh);
document.querySelectorAll('[data-page-tab]').forEach((button) => {
  button.addEventListener('click', () => setActivePage(button.dataset.pageTab || 'projects'));
});
$('closeDetailBtn').addEventListener('click', closeModal);
$('fullscreenBtn').addEventListener('click', () => setFullscreen(!state.fullscreen));
document.querySelectorAll('[data-close-modal]').forEach((node) => node.addEventListener('click', closeModal));
$('closeSettingsBtn').addEventListener('click', closeSettings);
document.querySelectorAll('[data-close-settings]').forEach((node) => node.addEventListener('click', closeSettings));
$('backendSelect').addEventListener('change', () => {
  fillBackendForm(selectedBackendFromForm());
  setBackendStatus('Select Use for session to switch to this backend.');
});
$('useBackendBtn').addEventListener('click', () => useBackend($('backendSelect').value));
$('useCurrentBackendBtn').addEventListener('click', () => {
  useBackend('current');
  setBackendStatus('Using this site as the backend for this session.');
});
$('saveBackendBtn').addEventListener('click', saveBackendFromForm);
$('removeBackendBtn').addEventListener('click', removeSelectedBackend);
$('testBackendBtn').addEventListener('click', testBackendFromForm);
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && $('detailModal').classList.contains('open')) closeModal();
  if (event.key === 'Escape' && $('settingsModal').classList.contains('open')) closeSettings();
});
window.addEventListener('resize', () => applyBoardTemplate());
initAuthControls();
refresh();
