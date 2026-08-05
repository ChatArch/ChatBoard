const COLUMN_DEFS = [
  { key: 'thoughts', title: '想法' },
  { key: 'project', title: '进行中' },
  { key: 'archiving', title: '归档中' },
  { key: 'archive', title: '已归档' },
];
const PAGE_SIZE = 24;
const state = { catalog: null, machines: null, activePage: 'projects', selected: null, fullscreen: false, fileExplorerShowAll: false };

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

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
}

async function initAuthControls() {
  const logoutBtn = $('logoutBtn');
  if (!logoutBtn) return;
  try {
    const auth = await api('/api/auth');
    if (!auth.enabled) return;
    logoutBtn.hidden = false;
    logoutBtn.addEventListener('click', async () => {
      await api('/api/logout', { method: 'POST', body: '{}' });
      window.location.assign('/login');
    });
  } catch (err) {
    logoutBtn.hidden = true;
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
  return {
    root: '',
    columns: COLUMN_DEFS.map((column) => ({
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
  $('summary').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Loaded</span><strong>${esc(loaded)}${complete ? '' : '+'}</strong></div>
      ${columns.map((column) => `<div class="stat-card"><span>${esc(column.title)}</span><strong>${esc((column.cards || []).length)}${column.has_more ? '+' : ''}</strong></div>`).join('')}
      <div class="stat-card"><span>Status</span><strong>${loading ? 'Loading' : 'Ready'}</strong></div>
    </div>
    <div class="tag-strip"><span class="tag-chip muted">Progressive loading: columns render first, cards arrive in pages.</span></div>
    <div class="root-line">${esc(state.catalog?.root || 'Workspace root loading...')}</div>
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
  $('board').innerHTML = columns.map((column) => `
    <section class="column" data-column="${esc(column.key)}">
      <div class="column-head"><span class="column-title">${esc(column.title)}</span><span class="count">${(column.cards || []).length}${column.has_more ? '+' : ''}</span></div>
      ${columnCardsHtml(column)}
    </section>
  `).join('');
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

function statusClass(status) {
  return `status-${String(status || 'unknown').toLowerCase()}`;
}

function renderMachinesSummary() {
  const data = state.machines || {};
  if (data.enabled === false) {
    const message = data.empty_message || 'Machines 页面暂未启用，真实机器清单暂不展示。';
    $('summary').innerHTML = `
      <div class="stats-grid">
        <div class="stat-card"><span>Machines</span><strong>0</strong></div>
        <div class="stat-card"><span>Status</span><strong>暂未启用</strong></div>
      </div>
      <div class="tag-strip"><span class="tag-chip muted">${esc(message)}</span></div>
      <div class="root-line">${esc(data.root || state.catalog?.root || '')}</div>
    `;
    return;
  }
  const summary = data.summary || {};
  const counts = summary.status_counts || {};
  const framework = data.selected_framework || {};
  $('summary').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Machines</span><strong>${esc(summary.total || 0)}</strong></div>
      <div class="stat-card"><span>OK</span><strong>${esc(counts.ok || 0)}</strong></div>
      <div class="stat-card"><span>Warning</span><strong>${esc(counts.warning || 0)}</strong></div>
      <div class="stat-card"><span>Unknown</span><strong>${esc(counts.unknown || 0)}</strong></div>
      <div class="stat-card"><span>Framework</span><strong>${esc(framework.name || 'Beszel')}</strong></div>
    </div>
    <div class="tag-strip">
      <span class="tag-chip muted">Selected machine-status framework: <b>${esc(framework.name || 'Beszel')}</b></span>
      <span class="tag-chip muted">Registered SSH machines first; agent install later.</span>
    </div>
    <div class="root-line">${esc(data.registry_path || 'Machine registry loading...')}</div>
  `;
}

function machineCardHtml(machine) {
  const roles = (machine.roles || []).slice(0, 4).map((role) => `<span class="badge role">${esc(role)}</span>`).join('');
  const aliases = (machine.aliases || []).filter((item) => item !== machine.title).slice(0, 3).join(' · ');
  const tools = machine.tools || {};
  const toolBadges = ['beszel', 'cockpit', 'netdata', 'uptime', 'homepage']
    .filter((key) => tools[key])
    .map((key) => `<span class="badge asset">${esc(key)}</span>`)
    .join('');
  return `<article class="card machine-card" data-machine-id="${esc(machine.id)}">
    <div class="machine-card-top">
      <div class="card-title">${esc(machine.title)}</div>
      <span class="machine-status ${esc(statusClass(machine.status))}">${esc(machine.status || 'unknown')}</span>
    </div>
    <div class="card-date">${esc(machine.zone || machine.group || 'unknown zone')}</div>
    <div class="card-description">${esc(machine.summary || '')}</div>
    <div class="machine-line">${esc(machine.host || 'local')} ${machine.port ? `:${esc(machine.port)}` : ''}</div>
    ${aliases ? `<div class="machine-aliases">${esc(aliases)}</div>` : ''}
    <div class="card-meta">
      ${roles}
      ${toolBadges || '<span class="badge muted">tools pending</span>'}
    </div>
  </article>`;
}

function renderMachines() {
  const data = state.machines || { machines: [], groups: [] };
  const machines = data.machines || [];
  renderMachinesSummary();
  $('emptyColumns').innerHTML = '';
  $('board').className = 'board machines-board';
  if (data.enabled === false) {
    $('board').innerHTML = `<div class="empty-column-note">${esc(data.empty_message || 'Machines 页面暂未启用，真实机器清单暂不展示。')}</div>`;
    return;
  }
  if (!machines.length) {
    $('board').innerHTML = '<div class="empty-column-note">No machines registered yet.</div>';
    return;
  }
  const grouped = {};
  machines.forEach((machine) => {
    const group = machine.group || machine.zone || 'unknown';
    grouped[group] = grouped[group] || [];
    grouped[group].push(machine);
  });
  const groupTitles = Object.fromEntries((data.groups || []).map((group) => [group.key, group.title]));
  $('board').innerHTML = Object.keys(grouped).sort().map((group) => `
    <section class="column machine-group" data-machine-group="${esc(group)}">
      <div class="column-head"><span class="column-title">${esc(groupTitles[group] || group)}</span><span class="count">${grouped[group].length}</span></div>
      <div class="card-list">${grouped[group].map(machineCardHtml).join('')}</div>
    </section>
  `).join('');
  document.querySelectorAll('[data-machine-id]').forEach((node) => {
    node.addEventListener('click', () => loadMachineDetail(node.dataset.machineId));
  });
}

function machineSectionHtml(section) {
  if (section.kind === 'kv') {
    const rows = (section.data || []).map(([key, value]) => `<div>${esc(key)}</div><div>${esc(value ?? '—')}</div>`).join('');
    return `<section class="section tab-panel ${esc(section.key)}" data-tab-panel="${esc(section.key)}"><h3>${esc(section.title)}</h3><div class="kv">${rows}</div></section>`;
  }
  if (section.kind === 'list') {
    const rows = (section.data || []).map((item) => `<li>${esc(item)}</li>`).join('');
    return `<section class="section tab-panel ${esc(section.key)}" data-tab-panel="${esc(section.key)}"><h3>${esc(section.title)}</h3><ul class="machine-list">${rows}</ul></section>`;
  }
  return sectionHtml(section);
}

function renderMachineDetail(detail) {
  const sections = detail.sections || [];
  const active = sections[0] && sections[0].key;
  $('detailBody').innerHTML = `
    <div class="detail-tabs">${sections.map((section, index) => `<button class="tab-button ${index === 0 ? 'active' : ''}" type="button" data-tab="${esc(section.key)}">${esc(section.title)}</button>`).join('')}</div>
    <div class="tab-panels">${sections.map(machineSectionHtml).join('')}</div>
  `;
  document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.tabPanel === active));
  document.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tab-button').forEach((item) => item.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((panel) => panel.classList.toggle('active', panel.dataset.tabPanel === button.dataset.tab));
      button.classList.add('active');
    });
  });
}

async function loadMachines() {
  $('summary').innerHTML = '<div class="column-loading"><span></span> Loading machines...</div>';
  $('board').className = 'board machines-board';
  $('board').innerHTML = '';
  state.machines = await api('/api/machines');
  renderMachines();
}

async function loadMachineDetail(machineId) {
  state.selected = machineId;
  renderMachines();
  openModal();
  $('detailTitle').textContent = 'Loading...';
  $('detailPath').textContent = machineId;
  $('detailBody').innerHTML = '<div class="section"><h3>Loading</h3><div class="card-summary">Fetching machine detail...</div></div>';
  const detail = await api(`/api/machines/${encodeURIComponent(machineId)}`);
  const machine = detail.machine;
  $('detailTitle').textContent = machine.title;
  $('detailPath').textContent = `${machine.host || 'local'}${machine.port ? `:${machine.port}` : ''}`;
  renderMachineDetail(detail);
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
  if (state.activePage === 'machines' && state.machines) renderMachines();
  else if (state.catalog) renderCatalog();
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

async function refresh() {
  state.selected = null;
  if (state.activePage === 'machines') {
    await loadMachines();
    return;
  }
  state.catalog = emptyCatalog();
  renderCatalog();
  COLUMN_DEFS.forEach((column) => loadColumn(column.key, 0));
}

$('refreshBtn').addEventListener('click', refresh);
$('ensureCards').addEventListener('change', refresh);
document.querySelectorAll('[data-page-tab]').forEach((button) => {
  button.addEventListener('click', () => setActivePage(button.dataset.pageTab || 'projects'));
});
$('closeDetailBtn').addEventListener('click', closeModal);
$('fullscreenBtn').addEventListener('click', () => setFullscreen(!state.fullscreen));
document.querySelectorAll('[data-close-modal]').forEach((node) => node.addEventListener('click', closeModal));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && $('detailModal').classList.contains('open')) closeModal();
});
initAuthControls();
refresh();
