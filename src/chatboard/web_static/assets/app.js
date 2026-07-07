const COLUMN_DEFS = [
  { key: 'project', title: 'Project' },
  { key: 'discussion', title: 'Discussion' },
  { key: 'archive', title: 'Archive' },
  { key: 'discard', title: 'Discard' },
];
const PAGE_SIZE = 24;
const state = { catalog: null, selected: null, fullscreen: false, fileExplorerShowAll: false };

const $ = (id) => document.getElementById(id);
const esc = (value) => String(value ?? '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(`${response.status} ${await response.text()}`);
  return response.json();
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
    ${card.summary ? `<div class="card-summary">${esc(card.summary)}</div>` : ''}
    ${nestedItems}
    <div class="card-meta">
      <span class="badge area">${esc(card.area)}</span>
      <span class="badge stage">${esc(card.stage)}</span>
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
      <div>Priority</div><div>${esc(card.priority)}</div>
      <div>Assignee</div><div>${esc(card.assignee || '—')}</div>
      <div>Path</div><div>${esc(card.workspace_path || '—')}</div>
    </div>`;
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

async function refresh() {
  state.catalog = emptyCatalog();
  renderCatalog();
  COLUMN_DEFS.forEach((column) => loadColumn(column.key, 0));
}

$('refreshBtn').addEventListener('click', refresh);
$('ensureCards').addEventListener('change', refresh);
$('closeDetailBtn').addEventListener('click', closeModal);
$('fullscreenBtn').addEventListener('click', () => setFullscreen(!state.fullscreen));
document.querySelectorAll('[data-close-modal]').forEach((node) => node.addEventListener('click', closeModal));
document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape' && $('detailModal').classList.contains('open')) closeModal();
});
refresh();
