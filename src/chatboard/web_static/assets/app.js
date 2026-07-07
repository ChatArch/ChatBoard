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
  return `<article class="card${active}" data-card-id="${esc(card.id)}">
    <div class="card-title">${esc(card.title)}</div>
    ${card.summary ? `<div class="card-summary">${esc(card.summary)}</div>` : ''}
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
      <div class="card-list">${(column.cards || []).map(cardHtml).join('') || '<div class="empty-column-note">No cards yet</div>'}</div>
    </section>
  `).join('');
  document.querySelectorAll('.card').forEach((node) => {
    node.addEventListener('click', () => loadDetail(node.dataset.cardId));
  });
}

function sectionHtml(section) {
  let body = '';
  const keyClass = esc(section.key || 'section');
  if (section.kind === 'markdown') {
    body = section.data ? `<pre>${esc(section.data)}</pre>` : '<div class="card-summary">Empty</div>';
  } else if (section.kind === 'fields') {
    const card = section.data || {};
    body = `<div class="kv">
      <div>ID</div><div>${esc(card.id)}</div>
      <div>Area</div><div>${esc(card.area)}</div>
      <div>Stage</div><div>${esc(card.stage)}</div>
      <div>Priority</div><div>${esc(card.priority)}</div>
      <div>Assignee</div><div>${esc(card.assignee || '—')}</div>
      <div>Updated</div><div>${esc(card.timestamps && card.timestamps.updated_at || '—')}</div>
    </div>`;
  } else if (Array.isArray(section.data)) {
    body = section.data.length ? `<pre>${esc(JSON.stringify(section.data, null, 2))}</pre>` : '<div class="card-summary">Empty</div>';
  } else {
    body = `<pre>${esc(JSON.stringify(section.data || {}, null, 2))}</pre>`;
  }
  return `<section class="section ${keyClass} ${section.kind === 'markdown' ? 'markdown' : ''}"><h3>${esc(section.title)}</h3>${body}</section>`;
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
  $('detailBody').innerHTML = (detail.sections || []).map(sectionHtml).join('');
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
