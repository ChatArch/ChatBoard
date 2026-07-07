const state = { catalog: null, selected: null, fullscreen: false };

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

function renderSummary(data) {
  const summary = data.summary || {};
  const areas = summary.areas || {};
  const tags = summary.top_tags || [];
  $('summary').innerHTML = `
    <div class="stats-grid">
      <div class="stat-card"><span>Total</span><strong>${esc(data.total_cards)}</strong></div>
      <div class="stat-card"><span>Project</span><strong>${esc(areas.projects || 0)}</strong></div>
      <div class="stat-card"><span>Discussion</span><strong>${esc(areas.discussion || 0)}</strong></div>
      <div class="stat-card"><span>Archive</span><strong>${esc(areas.archive || 0)}</strong></div>
      <div class="stat-card"><span>PRD</span><strong>${esc(summary.with_prd || 0)}</strong></div>
      <div class="stat-card"><span>Reports</span><strong>${esc(summary.with_reports || 0)}</strong></div>
    </div>
    <div class="tag-strip">${tags.map(([tag, count]) => `<span class="tag-chip">#${esc(tag)} <b>${esc(count)}</b></span>`).join('') || '<span class="tag-chip muted">No tags yet</span>'}</div>
    <div class="root-line">${esc(data.root)}</div>
  `;
}

function archiveColumnCardsHtml(cards = []) {
  if (!cards.length) return '<div class="empty-column-note">No cards yet</div>';
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

function columnCardsHtml(column) {
  const cards = column.cards || [];
  if (column.key === 'archive') return archiveColumnCardsHtml(cards);
  return `<div class="card-list">${cards.map(cardHtml).join('') || '<div class="empty-column-note">No cards yet</div>'}</div>`;
}

function renderCatalog(data) {
  state.catalog = data;
  const columns = data.columns || [];
  const nonEmpty = columns.filter((column) => (column.cards || []).length > 0);
  renderSummary(data);
  $('emptyColumns').innerHTML = '';
  $('board').className = 'board';
  if (nonEmpty.length <= 1) $('board').classList.add('mostly-project');
  $('board').innerHTML = columns.map((column) => `
    <section class="column" data-column="${esc(column.key)}">
      <div class="column-head"><span class="column-title">${esc(column.title)}</span><span class="count">${(column.cards || []).length}</span></div>
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
}

function fileTreeHtml(nodes = []) {
  if (!nodes.length) return '<div class="card-summary">No files</div>';
  return `<ul class="file-tree">${nodes.map((node) => {
    if (node.type === 'directory') {
      return `<li><span class="file-dir">${esc(node.name)}/</span>${fileTreeHtml(node.children || [])}</li>`;
    }
    const action = node.previewable ? `data-file-path="${esc(node.path)}"` : '';
    return `<li><button class="file-node" type="button" ${action}>${esc(node.name)}</button><span class="file-size">${esc(node.size || 0)}b</span></li>`;
  }).join('')}</ul>`;
}

function sectionHtml(section) {
  let body = '';
  const keyClass = esc(section.key || 'section');
  if (section.kind === 'markdown') {
    body = section.data ? `<pre>${esc(section.data)}</pre>` : '<div class="card-summary">Empty</div>';
  } else if (section.kind === 'file_tree') {
    body = `<div class="files-layout"><div>${fileTreeHtml(section.data || [])}</div><pre id="filePreview" class="file-preview">Select a text file to preview.</pre></div>`;
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
  document.querySelectorAll('.file-node[data-file-path]').forEach((button) => {
    button.addEventListener('click', async () => {
      const preview = $('filePreview');
      preview.textContent = 'Loading...';
      const content = await api(`/api/cards/${encodeURIComponent(detail.card.id)}/files/content?path=${encodeURIComponent(button.dataset.filePath)}`);
      preview.textContent = content.content || '';
    });
  });
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
  if (state.catalog) renderCatalog(state.catalog);
}

function setFullscreen(on) {
  state.fullscreen = on;
  $('detailPanel').classList.toggle('fullscreen', on);
  $('fullscreenBtn').textContent = on ? 'Exit Fullscreen' : 'Fullscreen';
}

async function loadDetail(cardId) {
  state.selected = cardId;
  renderCatalog(state.catalog);
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

async function refresh() {
  $('summary').textContent = 'Loading...';
  try {
    const ensure = $('ensureCards').checked ? '?ensure=true' : '';
    const data = await api(`/api/catalog${ensure}`);
    renderCatalog(data);
  } catch (err) {
    $('board').innerHTML = `<div class="error">${esc(err.message || err)}</div>`;
    $('summary').textContent = 'Failed to load catalog';
  }
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
