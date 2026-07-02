// static/js/clients.js — Client engagement workspace panel.
//
// The operator-facing surface for the CM delivery layer (routes/client_routes.py):
// portfolio triage (stuck-first, soonest ritual due), client detail (stakeholders,
// transcripts), stakeholder detail (ITM / TRI / rituals / comms frames), and
// transcript -> methodology-artifact synthesis.
//
// Follows the dynamic-pane pattern (notes.js): pane built fresh on open, removed
// on close; makeWindowDraggable for drag/resize/fullscreen/dock; own Esc handler;
// mobile bottom-sheet takeover with inline style belt-and-braces.

import uiModule from './ui.js';
import spinnerModule from './spinner.js';
import { makeWindowDraggable } from './windowDrag.js';
import { snapModalToZone } from './tileManager.js';

const API_BASE = window.location.origin;

// ── Module state ───────────────────────────────────────────────────────────
let _open = false;
let _pane = null;
let _backdrop = null;
let _keydownHandler = null;
// View stack: [{view:'portfolio'}] | {view:'client', clientId} |
// {view:'stakeholder', clientId, stakeholderId} | {view:'artifact', title, content}
let _nav = [{ view: 'portfolio' }];
let _methodology = null; // cached GET /api/clients/methodology

const ARTIFACT_KINDS = [
  ['session_summary', 'Session summary + actions'],
  ['comms_draft', 'Stakeholder comms draft'],
  ['journey_update', 'Journey update'],
  ['risk_log', 'Risk / resistance log'],
  ['itm_update', 'Proposed ITM update'],
  ['tri_assessment', 'Proposed TRI assessment'],
];

const ITM_FIELDS = [
  ['current_identity', 'Current identity', 'How they derive value and indispensability today'],
  ['target_identity', 'Target identity', 'The more-valuable identity to land — in their own words'],
  ['expected_loss', 'Expected loss', 'The precise psychological loss (the hardest, most important cell)'],
  ['target_gain', 'Target gain', 'What they gain that they actually want'],
  ['bridging_rituals', 'Bridging rituals', 'Concrete identity-affirming moments that make it feel real'],
];

const STAGES = ['unknown', 'stuck', 'moving', 'landing', 'landed'];

// ── Helpers ────────────────────────────────────────────────────────────────
function _esc(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// Local copy by convention — there is deliberately no shared export
// (see documentLibrary.js:286).
function _relTime(isoString) {
  if (!isoString) return '';
  // Server timestamps are naive UTC (no 'Z'/offset); parse them as UTC or
  // they render hours in the future on any non-UTC machine.
  let s = String(isoString);
  if (!/([+-]\d\d:?\d\d|Z)$/i.test(s)) s += 'Z';
  const now = Date.now();
  const then = new Date(s).getTime();
  if (Number.isNaN(then)) return '';
  const diffS = Math.floor((now - then) / 1000);
  if (diffS < -60) {
    // future (ritual due dates)
    const inM = Math.floor(-diffS / 60);
    if (inM < 60) return 'in ' + inM + 'm';
    const inH = Math.floor(inM / 60);
    if (inH < 24) return 'in ' + inH + 'h';
    return 'in ' + Math.floor(inH / 24) + 'd';
  }
  if (diffS < 60) return 'just now';
  const diffM = Math.floor(diffS / 60);
  if (diffM < 60) return diffM + 'm ago';
  const diffH = Math.floor(diffM / 60);
  if (diffH < 24) return diffH + 'h ago';
  const diffD = Math.floor(diffH / 24);
  if (diffD === 1) return 'yesterday';
  if (diffD < 14) return diffD + 'd ago';
  const diffW = Math.floor(diffD / 7);
  if (diffW < 8) return diffW + 'w ago';
  return new Date(isoString).toLocaleDateString();
}

async function _api(path, opts = {}) {
  const res = await fetch(`${API_BASE}/api/clients${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    let detail = '';
    try { detail = (await res.json()).detail || ''; } catch { /* ignore */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

function _triStageFromTotal(total) {
  // Mirror of src/methodology.py bands (server value is authoritative).
  if (total == null || total === '') return null;
  const t = Number(total);
  if (Number.isNaN(t)) return null;
  if (t >= 35) return 'landed';
  if (t >= 28) return 'landing';
  if (t >= 19) return 'moving';
  return 'stuck';
}

function _stageChip(stage) {
  const s = (stage || 'unknown').toLowerCase();
  return `<span class="clients-stage-chip clients-stage-${_esc(s)}">${_esc(s)}</span>`;
}

function _body() {
  return _pane ? _pane.querySelector('.clients-pane-body') : null;
}

function _setLoading(container, label) {
  if (!container) return;
  container.innerHTML = '';
  container.appendChild(spinnerModule.createLoadingRow(label || 'Loading…'));
}

function _emptyHTML(text, kind) {
  const icon = uiModule.emptyStateIcon ? uiModule.emptyStateIcon(kind || 'smiley') : '';
  return `<div class="clients-empty">${_esc(text)} <span style="vertical-align:-3px;margin-left:6px;">${icon}</span></div>`;
}

async function _loadMethodology() {
  if (_methodology) return _methodology;
  try { _methodology = await _api('/methodology'); } catch { _methodology = null; }
  return _methodology;
}

// ── Navigation ─────────────────────────────────────────────────────────────
function _navTo(entry) {
  _nav.push(entry);
  _renderView();
}

function _navBack() {
  if (_nav.length > 1) {
    _nav.pop();
    _renderView();
  }
}

function _navReset() {
  _nav = [{ view: 'portfolio' }];
  _renderView();
}

function _renderView() {
  if (!_pane) return;
  const top = _nav[_nav.length - 1];
  const backBtn = _pane.querySelector('#clients-back-btn');
  if (backBtn) backBtn.style.display = _nav.length > 1 ? '' : 'none';
  const titleEl = _pane.querySelector('#clients-pane-title-text');
  if (titleEl) {
    titleEl.textContent =
      top.view === 'portfolio' ? 'Clients' :
      top.view === 'client' ? (top.clientName || 'Client') :
      top.view === 'stakeholder' ? (top.stakeholderName || 'Stakeholder') :
      top.view === 'settings' ? 'Notion settings' :
      top.title || 'Artifact';
  }
  if (top.view === 'portfolio') _renderPortfolio();
  else if (top.view === 'client') _renderClient(top);
  else if (top.view === 'stakeholder') _renderStakeholder(top);
  else if (top.view === 'artifact') _renderArtifact(top);
  else if (top.view === 'settings') _renderSettings();
}

// ── View: portfolio (home) ─────────────────────────────────────────────────
async function _renderPortfolio() {
  const body = _body();
  if (!body) return;
  _setLoading(body, 'Loading portfolio…');
  let summary, portfolio, clients;
  try {
    [summary, portfolio, clients] = await Promise.all([
      _api('/portfolio/summary'),
      _api('/portfolio'),
      _api(''),
    ]);
  } catch (e) {
    body.innerHTML = '<div class="clients-empty">Failed to load</div>';
    return;
  }
  const rows = portfolio.portfolio || [];
  const clientList = clients.clients || [];
  const byStage = summary.by_stage || {};

  const chips = STAGES.filter(s => s !== 'unknown').map(s =>
    `<span class="clients-sum-chip">${_stageChip(s)}<b>${byStage[s] || 0}</b></span>`
  ).join('');

  let triageHTML;
  if (rows.length === 0) {
    triageHTML = _emptyHTML('No stakeholders yet — create a client below, or ask the agent to set one up', 'smiley');
  } else {
    triageHTML = `
      <table class="clients-table">
        <thead><tr>
          <th>Stakeholder</th><th>Client</th><th>Role</th><th>Archetype</th>
          <th>Stage</th><th>Next ritual</th><th></th>
        </tr></thead>
        <tbody>
          ${rows.map(r => `
            <tr class="clients-row" data-cid="${_esc(r.client_id)}" data-sid="${_esc(r.stakeholder_id)}" data-sname="${_esc(r.name)}">
              <td>${_esc(r.name)}</td>
              <td class="clients-dim">${_esc(r.client_name || '')}</td>
              <td class="clients-dim">${_esc(r.role || '')}</td>
              <td class="clients-dim">${_esc(r.archetype || '—')}</td>
              <td>${_stageChip(r.transition_stage)}</td>
              <td class="clients-dim">${r.next_ritual_due ? _esc(_relTime(r.next_ritual_due)) : '—'}</td>
              <td>${r.open_loss_flag ? '<span class="clients-loss-flag" title="Expected-loss diagnosis pending peer review">loss?</span>' : ''}</td>
            </tr>`).join('')}
        </tbody>
      </table>`;
  }

  const clientCards = clientList.map(c => `
    <div class="clients-card clients-client-card" data-cid="${_esc(c.id)}" data-cname="${_esc(c.name)}">
      <div class="clients-card-title">${_esc(c.name)}</div>
      <div class="clients-card-sub">${_esc(c.sector || '')}${c.sector && c.sponsor ? ' · ' : ''}${_esc(c.sponsor || '')}</div>
      <div class="clients-card-foot">
        <span class="clients-policy-chip" title="Model policy for sensitive synthesis">${_esc(c.model_policy || 'local-sensitive')}</span>
        <span class="clients-dim">${_esc(c.status || 'active')}</span>
      </div>
    </div>`).join('');

  body.innerHTML = `
    <div class="clients-summary-bar">
      <span class="clients-sum-chip"><span class="clients-dim">clients</span><b>${summary.clients || 0}</b></span>
      <span class="clients-sum-chip"><span class="clients-dim">stakeholders</span><b>${summary.stakeholders || 0}</b></span>
      ${chips}
      ${summary.open_loss ? `<span class="clients-sum-chip"><span class="clients-loss-flag">loss?</span><b>${summary.open_loss}</b></span>` : ''}
    </div>
    <div class="clients-section-label">Portfolio — who needs the next hour <span class="clients-dim">(stuck first, soonest ritual due)</span></div>
    <div class="clients-triage">${triageHTML}</div>
    <div class="clients-section-label" style="display:flex;align-items:center;">Engagements
      <span style="flex:1"></span>
      <button id="clients-new-btn" class="memory-toolbar-btn">+ New client</button>
    </div>
    <div id="clients-new-form" class="clients-form clients-card" style="display:none;">
      <input id="clients-new-name" class="memory-search-input" placeholder="Client name (required)" style="margin-top:0;" />
      <div class="clients-form-row">
        <input id="clients-new-sector" class="memory-search-input" placeholder="Sector (e.g. pharma)" style="margin-top:0;" />
        <input id="clients-new-sponsor" class="memory-search-input" placeholder="Sponsor" style="margin-top:0;" />
      </div>
      <div class="clients-form-actions">
        <button id="clients-new-cancel" class="confirm-btn confirm-btn-secondary">Cancel</button>
        <button id="clients-new-save" class="confirm-btn confirm-btn-primary">Create</button>
      </div>
    </div>
    <div class="clients-card-grid">${clientCards || _emptyHTML('No clients yet', 'neutral')}</div>
  `;

  // Wiring
  body.querySelectorAll('.clients-row').forEach(tr => {
    tr.addEventListener('click', () => {
      _navTo({ view: 'stakeholder', clientId: tr.dataset.cid, stakeholderId: tr.dataset.sid, stakeholderName: tr.dataset.sname });
    });
  });
  body.querySelectorAll('.clients-client-card').forEach(card => {
    card.addEventListener('click', () => {
      _navTo({ view: 'client', clientId: card.dataset.cid, clientName: card.dataset.cname });
    });
  });
  const newBtn = body.querySelector('#clients-new-btn');
  const newForm = body.querySelector('#clients-new-form');
  if (newBtn && newForm) {
    newBtn.addEventListener('click', () => {
      newForm.style.display = newForm.style.display === 'none' ? '' : 'none';
      newForm.querySelector('#clients-new-name')?.focus();
    });
    newForm.querySelector('#clients-new-cancel')?.addEventListener('click', () => { newForm.style.display = 'none'; });
    newForm.querySelector('#clients-new-save')?.addEventListener('click', async () => {
      const name = newForm.querySelector('#clients-new-name')?.value?.trim();
      if (!name) { uiModule.showError('Client name is required'); return; }
      try {
        await _api('', { method: 'POST', body: JSON.stringify({
          name,
          sector: newForm.querySelector('#clients-new-sector')?.value?.trim() || null,
          sponsor: newForm.querySelector('#clients-new-sponsor')?.value?.trim() || null,
        }) });
        uiModule.showToast('Client created');
        _renderPortfolio();
      } catch (e) { uiModule.showError(e.message || 'Failed to create client'); }
    });
  }
}

// ── View: client detail ────────────────────────────────────────────────────
async function _renderClient(navEntry) {
  const body = _body();
  if (!body) return;
  _setLoading(body, 'Loading client…');
  let client, stakeholders, transcripts;
  try {
    [client, stakeholders, transcripts] = await Promise.all([
      _api(`/${navEntry.clientId}`),
      _api(`/${navEntry.clientId}/stakeholders`),
      _api(`/${navEntry.clientId}/transcripts`),
    ]);
  } catch (e) {
    body.innerHTML = '<div class="clients-empty">Failed to load</div>';
    return;
  }
  navEntry.clientName = client.name;
  _renderView.titleOnly = true;
  const skRows = stakeholders.stakeholders || [];
  const trRows = transcripts.transcripts || [];
  const meth = await _loadMethodology();
  const archetypes = (meth && meth.archetypes) || ['Responsiveness Gatekeeper', 'High-Capacity Executor', 'Authority Expert'];

  body.innerHTML = `
    <div class="clients-detail-head">
      <div>
        <div class="clients-detail-title">${_esc(client.name)}</div>
        <div class="clients-dim">${_esc(client.sector || '')}${client.sector && client.sponsor ? ' · sponsor: ' : (client.sponsor ? 'sponsor: ' : '')}${_esc(client.sponsor || '')}</div>
      </div>
      <span style="flex:1"></span>
      <span class="clients-policy-chip" title="Model policy for sensitive synthesis">${_esc(client.model_policy || 'local-sensitive')}</span>
      <button id="clients-del-client" class="memory-toolbar-btn danger" title="Delete this client and everything in it">Delete</button>
    </div>

    <div class="clients-section-label" style="display:flex;align-items:center;">Stakeholders
      <span style="flex:1"></span>
      <button id="clients-add-sk-btn" class="memory-toolbar-btn">+ Add stakeholder</button>
    </div>
    <div id="clients-add-sk-form" class="clients-form clients-card" style="display:none;">
      <div class="clients-form-row">
        <input id="clients-sk-name" class="memory-search-input" placeholder="Name (required)" style="margin-top:0;" />
        <input id="clients-sk-role" class="memory-search-input" placeholder="Role" style="margin-top:0;" />
      </div>
      <select id="clients-sk-arch" class="settings-select">
        <option value="">Archetype — not yet mapped</option>
        ${archetypes.map(a => `<option value="${_esc(a)}">${_esc(a)}</option>`).join('')}
      </select>
      <div class="clients-form-actions">
        <button id="clients-sk-cancel" class="confirm-btn confirm-btn-secondary">Cancel</button>
        <button id="clients-sk-save" class="confirm-btn confirm-btn-primary">Add</button>
      </div>
    </div>
    <div class="clients-card-grid">
      ${skRows.length ? skRows.map(s => `
        <div class="clients-card clients-sk-card" data-sid="${_esc(s.id)}" data-sname="${_esc(s.name)}">
          <div class="clients-card-title">${_esc(s.name)}</div>
          <div class="clients-card-sub">${_esc(s.role || '')}</div>
          <div class="clients-card-foot">${_stageChip(s.transition_stage)}<span class="clients-dim">${_esc(s.archetype || 'unmapped')}</span></div>
        </div>`).join('') : _emptyHTML('No stakeholders yet', 'neutral')}
    </div>

    <div class="clients-section-label" style="display:flex;align-items:center;">Meeting transcripts
      <span style="flex:1"></span>
      <button id="clients-notion-tr-btn" class="memory-toolbar-btn" title="Pull a transcript from a Notion page">From Notion</button>
      <button id="clients-add-tr-btn" class="memory-toolbar-btn" style="margin-left:6px;">+ Add transcript</button>
    </div>
    <div id="clients-add-tr-form" class="clients-form clients-card" style="display:none;">
      <div class="clients-form-row">
        <input id="clients-tr-title" class="memory-search-input" placeholder="Title (e.g. 'S1 — Tech Learning, June 22')" style="margin-top:0;" />
        <select id="clients-tr-sk" class="settings-select">
          <option value="">Stakeholder (optional)</option>
          ${skRows.map(s => `<option value="${_esc(s.id)}">${_esc(s.name)}</option>`).join('')}
        </select>
      </div>
      <textarea id="clients-tr-content" class="clients-textarea" rows="6" placeholder="Paste the transcript…"></textarea>
      <div class="clients-form-actions">
        <button id="clients-tr-cancel" class="confirm-btn confirm-btn-secondary">Cancel</button>
        <button id="clients-tr-save" class="confirm-btn confirm-btn-primary">Save transcript</button>
      </div>
    </div>
    <div class="clients-tr-list">
      ${trRows.length ? trRows.map(t => `
        <div class="clients-card clients-tr-row" data-tid="${_esc(t.id)}">
          <div class="clients-tr-main">
            <div class="clients-card-title">${_esc(t.title || 'Untitled transcript')}</div>
            <div class="clients-dim">${_esc(t.source || '')} · ${_esc(_relTime(t.created_at))}${t.stakeholder_id ? ' · ' + _esc((skRows.find(s => s.id === t.stakeholder_id) || {}).name || '') : ''}</div>
          </div>
          <select class="settings-select clients-artifact-select" title="Artifact to synthesize">
            ${ARTIFACT_KINDS.map(([k, label]) => `<option value="${_esc(k)}">${_esc(label)}</option>`).join('')}
          </select>
          <button class="confirm-btn confirm-btn-primary clients-synth-btn">Synthesize</button>
          <button class="doc-action-icon-btn clients-tr-del" title="Delete transcript">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M3 6h18"/><path d="M8 6V4h8v2"/><path d="M19 6l-1 14H6L5 6"/></svg>
          </button>
        </div>`).join('') : _emptyHTML('No transcripts yet — paste one to synthesize deliverables', 'neutral')}
    </div>
  `;

  // Wiring
  body.querySelector('#clients-del-client')?.addEventListener('click', async () => {
    const ok = await uiModule.styledConfirm(
      `Delete client "${client.name}" and ALL its stakeholders, ITM/TRI records, rituals, and transcripts?`,
      { confirmText: 'Delete client', danger: true });
    if (!ok) return;
    try {
      await _api(`/${client.id}`, { method: 'DELETE' });
      uiModule.showToast('Client deleted');
      _navReset();
    } catch (e) { uiModule.showError(e.message || 'Failed to delete'); }
  });

  body.querySelectorAll('.clients-sk-card').forEach(card => {
    card.addEventListener('click', () => {
      _navTo({ view: 'stakeholder', clientId: client.id, stakeholderId: card.dataset.sid, stakeholderName: card.dataset.sname });
    });
  });

  const skBtn = body.querySelector('#clients-add-sk-btn');
  const skForm = body.querySelector('#clients-add-sk-form');
  if (skBtn && skForm) {
    skBtn.addEventListener('click', () => {
      skForm.style.display = skForm.style.display === 'none' ? '' : 'none';
      skForm.querySelector('#clients-sk-name')?.focus();
    });
    skForm.querySelector('#clients-sk-cancel')?.addEventListener('click', () => { skForm.style.display = 'none'; });
    skForm.querySelector('#clients-sk-save')?.addEventListener('click', async () => {
      const name = skForm.querySelector('#clients-sk-name')?.value?.trim();
      if (!name) { uiModule.showError('Stakeholder name is required'); return; }
      try {
        await _api(`/${client.id}/stakeholders`, { method: 'POST', body: JSON.stringify({
          name,
          role: skForm.querySelector('#clients-sk-role')?.value?.trim() || null,
          archetype: skForm.querySelector('#clients-sk-arch')?.value || null,
        }) });
        uiModule.showToast('Stakeholder added');
        _renderClient(navEntry);
      } catch (e) { uiModule.showError(e.message || 'Failed to add stakeholder'); }
    });
  }

  body.querySelector('#clients-notion-tr-btn')?.addEventListener('click', async () => {
    const page = await uiModule.styledPrompt('Notion page URL (the meeting transcript):',
      { title: 'From Notion', confirmText: 'Pull', maxLength: 400 });
    if (page === null || !page.trim()) return;
    try {
      const t = await _api(`/${client.id}/transcripts/notion`, {
        method: 'POST', body: JSON.stringify({ page: page.trim() }),
      });
      uiModule.showToast(t.updated ? 'Transcript refreshed from Notion' : 'Transcript pulled from Notion');
      _renderClient(navEntry);
    } catch (e) {
      uiModule.showError(e.message || 'Notion pull failed');
    }
  });

  const trBtn = body.querySelector('#clients-add-tr-btn');
  const trForm = body.querySelector('#clients-add-tr-form');
  if (trBtn && trForm) {
    trBtn.addEventListener('click', () => {
      trForm.style.display = trForm.style.display === 'none' ? '' : 'none';
      trForm.querySelector('#clients-tr-title')?.focus();
    });
    trForm.querySelector('#clients-tr-cancel')?.addEventListener('click', () => { trForm.style.display = 'none'; });
    trForm.querySelector('#clients-tr-save')?.addEventListener('click', async () => {
      const content = trForm.querySelector('#clients-tr-content')?.value?.trim();
      if (!content) { uiModule.showError('Transcript text is required'); return; }
      try {
        await _api(`/${client.id}/transcripts`, { method: 'POST', body: JSON.stringify({
          title: trForm.querySelector('#clients-tr-title')?.value?.trim() || null,
          content,
          source: 'manual',
          stakeholder_id: trForm.querySelector('#clients-tr-sk')?.value || null,
        }) });
        uiModule.showToast('Transcript saved');
        _renderClient(navEntry);
      } catch (e) { uiModule.showError(e.message || 'Failed to save transcript'); }
    });
  }

  body.querySelectorAll('.clients-tr-row').forEach(row => {
    const tid = row.dataset.tid;
    row.querySelector('.clients-synth-btn')?.addEventListener('click', async (ev) => {
      const btn = ev.currentTarget;
      const kind = row.querySelector('.clients-artifact-select')?.value || 'session_summary';
      const kindLabel = (ARTIFACT_KINDS.find(([k]) => k === kind) || [])[1] || kind;
      btn.disabled = true;
      const prev = btn.textContent;
      btn.textContent = 'Synthesizing…';
      try {
        const out = await _api(`/transcripts/${tid}/synthesize`, { method: 'POST', body: JSON.stringify({ artifact_kind: kind }) });
        _navTo({ view: 'artifact', title: kindLabel, content: out.content || '' });
      } catch (e) {
        uiModule.showError(e.message || 'Synthesis failed — is a model endpoint configured?');
      } finally {
        btn.disabled = false;
        btn.textContent = prev;
      }
    });
    row.querySelector('.clients-tr-del')?.addEventListener('click', async () => {
      const ok = await uiModule.styledConfirm('Delete this transcript?', { confirmText: 'Delete', danger: true });
      if (!ok) return;
      try {
        await _api(`/transcripts/${tid}`, { method: 'DELETE' });
        uiModule.showToast('Transcript deleted');
        _renderClient(navEntry);
      } catch (e) { uiModule.showError(e.message || 'Failed to delete'); }
    });
  });
}

// ── View: stakeholder detail (ITM / TRI / rituals / frames) ────────────────
async function _renderStakeholder(navEntry) {
  const body = _body();
  if (!body) return;
  _setLoading(body, 'Loading stakeholder…');
  const sid = navEntry.stakeholderId;
  let stakeholders, itm, tri, rituals, frames;
  try {
    [stakeholders, itm, tri, rituals, frames] = await Promise.all([
      _api(`/${navEntry.clientId}/stakeholders`),
      _api(`/stakeholders/${sid}/itm`),
      _api(`/stakeholders/${sid}/tri`),
      _api(`/stakeholders/${sid}/rituals`),
      _api(`/stakeholders/${sid}/frames`),
    ]);
  } catch (e) {
    body.innerHTML = '<div class="clients-empty">Failed to load</div>';
    return;
  }
  const sk = (stakeholders.stakeholders || []).find(s => s.id === sid) || {};
  navEntry.stakeholderName = sk.name || navEntry.stakeholderName;
  const scorecards = (tri.scorecards || []).slice().reverse(); // newest first
  const ritualRows = rituals.rituals || [];
  const meth = await _loadMethodology();
  const archetypes = (meth && meth.archetypes) || [];

  body.innerHTML = `
    <div class="clients-detail-head">
      <div>
        <div class="clients-detail-title">${_esc(sk.name || '')}</div>
        <div class="clients-dim">${_esc(sk.role || '')}</div>
      </div>
      <span style="flex:1"></span>
      ${_stageChip(sk.transition_stage)}
      <select id="clients-sk-arch-edit" class="settings-select" title="Archetype (a hypothesis — confirm against listening data)">
        <option value="">not yet mapped</option>
        ${archetypes.map(a => `<option value="${_esc(a)}" ${sk.archetype === a ? 'selected' : ''}>${_esc(a)}</option>`).join('')}
      </select>
    </div>

    <div class="clients-section-label">Identity Transition Map</div>
    <div class="clients-card clients-form">
      ${ITM_FIELDS.map(([key, label, hint]) => `
        <label class="clients-field-label">${_esc(label)} <span class="clients-dim">— ${_esc(hint)}</span></label>
        <textarea class="clients-textarea clients-itm-field" data-field="${_esc(key)}" rows="2">${_esc(itm[key] || '')}</textarea>
      `).join('')}
      <label class="clients-check-row">
        <input type="checkbox" id="clients-itm-loss-flag" ${itm.open_loss_flag ? 'checked' : ''} />
        Loss diagnosis pending peer review
      </label>
      <div class="clients-form-actions">
        <span class="clients-dim" style="margin-right:auto;">${itm.last_reviewed ? 'Last reviewed ' + _esc(_relTime(itm.last_reviewed)) : 'Not yet filled'}</span>
        <button id="clients-itm-save" class="confirm-btn confirm-btn-primary">Save ITM</button>
      </div>
    </div>

    <div class="clients-section-label">Readiness (TRI)</div>
    <div class="clients-card clients-form">
      <div class="clients-form-row" style="align-items:center;">
        <select id="clients-tri-cycle" class="settings-select" style="max-width:120px;">
          ${['Day 0', 'Day 30', 'Day 60', 'Day 90'].map(c => `<option>${c}</option>`).join('')}
        </select>
        <input id="clients-tri-total" class="memory-search-input" type="number" min="10" max="40" placeholder="Total (10–40)" style="margin-top:0;max-width:130px;" />
        <span id="clients-tri-derived" class="clients-dim"></span>
        <span style="flex:1"></span>
        <button id="clients-tri-save" class="confirm-btn confirm-btn-primary">Record</button>
      </div>
      ${scorecards.length ? `
        <table class="clients-table" style="margin-top:8px;">
          <thead><tr><th>Cycle</th><th>Total</th><th>Stage</th><th>Direction</th><th>When</th></tr></thead>
          <tbody>${scorecards.map(t => `
            <tr>
              <td>${_esc(t.cycle || '—')}</td>
              <td>${t.total != null ? _esc(t.total) : '—'}</td>
              <td>${_stageChip(t.stage)}</td>
              <td class="clients-dim">${_esc(t.direction || '—')}</td>
              <td class="clients-dim">${_esc(_relTime(t.administered_at || t.created_at))}</td>
            </tr>`).join('')}</tbody>
        </table>` : `<div class="clients-dim" style="padding:6px 2px;">No scorecards yet — record the Day 0 baseline.</div>`}
    </div>

    <div class="clients-section-label">Bridging rituals</div>
    <div class="clients-card clients-form">
      <div class="clients-form-row">
        <input id="clients-ritual-name" class="memory-search-input" placeholder="Design a ritual (e.g. 'first artefact in her voice — sent personally')" style="margin-top:0;" />
        <button id="clients-ritual-add" class="confirm-btn confirm-btn-primary">Add</button>
      </div>
      ${ritualRows.length ? ritualRows.map(r => `
        <div class="clients-ritual-row" data-rid="${_esc(r.id)}">
          <span class="clients-ritual-status">${r.completed_at
            ? '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--green)" stroke-width="2.5" stroke-linecap="round"><path d="M20 6 9 17l-5-5"/></svg>'
            : '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" opacity="0.4"><circle cx="12" cy="12" r="9"/></svg>'}</span>
          <span class="clients-ritual-name ${r.completed_at ? 'clients-ritual-done' : ''}">${_esc(r.name)}</span>
          <span class="clients-dim">${r.scheduled_at ? _esc(_relTime(r.scheduled_at)) : ''}</span>
          ${!r.completed_at ? '<button class="memory-toolbar-btn clients-ritual-complete">Mark complete</button>' : `<span class="clients-dim">${r.acknowledged ? 'acknowledged' : 'completed'}</span>`}
        </div>`).join('') : `<div class="clients-dim" style="padding:6px 2px;">No rituals designed yet.</div>`}
    </div>

    <div class="clients-section-label">Comms guidance <span class="clients-dim">(archetype × stage — adapt to their voice, never send verbatim)</span></div>
    <div class="clients-card clients-form">
      ${frames.frames && frames.frames.length ? `
        <div class="clients-frames-row">
          ${frames.frames.map(f => `<span class="clients-frame-chip" title="${_esc(f.stage_group)}">${_esc(f.id)} · ${_esc(f.title)}</span>`).join('')}
        </div>` : '<div class="clients-dim">No frames — set an archetype and record a TRI first.</div>'}
      ${frames.avoid && frames.avoid.length ? `
        <div class="clients-dim" style="margin-top:6px;">Never use: ${frames.avoid.map(a => _esc(a)).join(' · ')}</div>` : ''}
    </div>
  `;

  // Wiring
  body.querySelector('#clients-sk-arch-edit')?.addEventListener('change', async (ev) => {
    try {
      await _api(`/stakeholders/${sid}`, { method: 'PUT', body: JSON.stringify({ archetype: ev.target.value || null }) });
      uiModule.showToast('Archetype updated');
      _renderStakeholder(navEntry);
    } catch (e) { uiModule.showError(e.message || 'Failed to update'); }
  });

  body.querySelector('#clients-itm-save')?.addEventListener('click', async () => {
    const payload = {};
    body.querySelectorAll('.clients-itm-field').forEach(t => { payload[t.dataset.field] = t.value; });
    payload.open_loss_flag = !!body.querySelector('#clients-itm-loss-flag')?.checked;
    try {
      await _api(`/stakeholders/${sid}/itm`, { method: 'PUT', body: JSON.stringify(payload) });
      uiModule.showToast('ITM saved');
      _renderStakeholder(navEntry);
    } catch (e) { uiModule.showError(e.message || 'Failed to save ITM'); }
  });

  const triTotal = body.querySelector('#clients-tri-total');
  const triDerived = body.querySelector('#clients-tri-derived');
  triTotal?.addEventListener('input', () => {
    const stage = _triStageFromTotal(triTotal.value);
    triDerived.innerHTML = stage ? '→ ' + _stageChip(stage) : '';
  });
  body.querySelector('#clients-tri-save')?.addEventListener('click', async () => {
    const total = Number(triTotal?.value);
    if (!total || total < 10 || total > 40) { uiModule.showError('TRI total must be 10–40'); return; }
    try {
      await _api(`/stakeholders/${sid}/tri`, { method: 'POST', body: JSON.stringify({
        cycle: body.querySelector('#clients-tri-cycle')?.value || null,
        total,
        tri_version: 'v1.2',
      }) });
      uiModule.showToast('TRI recorded');
      _renderStakeholder(navEntry);
    } catch (e) { uiModule.showError(e.message || 'Failed to record TRI'); }
  });

  body.querySelector('#clients-ritual-add')?.addEventListener('click', async () => {
    const name = body.querySelector('#clients-ritual-name')?.value?.trim();
    if (!name) { uiModule.showError('Describe the ritual first'); return; }
    try {
      await _api(`/stakeholders/${sid}/rituals`, { method: 'POST', body: JSON.stringify({ name }) });
      uiModule.showToast('Ritual added');
      _renderStakeholder(navEntry);
    } catch (e) { uiModule.showError(e.message || 'Failed to add ritual'); }
  });

  body.querySelectorAll('.clients-ritual-complete').forEach(btn => {
    btn.addEventListener('click', async (ev) => {
      const rid = ev.currentTarget.closest('.clients-ritual-row')?.dataset.rid;
      if (!rid) return;
      try {
        await _api(`/rituals/${rid}/complete`, { method: 'POST', body: JSON.stringify({ acknowledged: true }) });
        uiModule.showToast('Ritual completed');
        _renderStakeholder(navEntry);
      } catch (e) { uiModule.showError(e.message || 'Failed to complete'); }
    });
  });
}

// ── View: synthesized artifact ─────────────────────────────────────────────
function _renderArtifact(navEntry) {
  const body = _body();
  if (!body) return;
  body.innerHTML = `
    <div class="clients-detail-head">
      <div class="clients-detail-title">${_esc(navEntry.title || 'Artifact')}</div>
      <span style="flex:1"></span>
      <button id="clients-artifact-push" class="confirm-btn confirm-btn-secondary">Push to Notion</button>
      <button id="clients-artifact-copy" class="confirm-btn confirm-btn-primary">Copy</button>
    </div>
    <pre class="clients-artifact-pre">${_esc(navEntry.content || '(empty)')}</pre>
  `;
  body.querySelector('#clients-artifact-copy')?.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(navEntry.content || '');
      uiModule.showToast('Copied to clipboard');
    } catch {
      uiModule.showError('Copy failed — select the text manually');
    }
  });
  body.querySelector('#clients-artifact-push')?.addEventListener('click', async (ev) => {
    const btn = ev.currentTarget;
    const doPush = async (parent) => _api('/notion/push', {
      method: 'POST',
      body: JSON.stringify({ title: navEntry.title || 'Artifact', content: navEntry.content || '', parent: parent || null }),
    });
    btn.disabled = true;
    const prev = btn.textContent;
    btn.textContent = 'Pushing…';
    try {
      let out;
      try {
        out = await doPush(null);
      } catch (e) {
        // No default parent configured — ask for one inline, then retry.
        if (/parent page/i.test(e.message || '')) {
          const parent = await uiModule.styledPrompt('Notion parent page URL (where the artifact page is created):',
            { title: 'Push to Notion', confirmText: 'Push', maxLength: 400 });
          if (parent === null) return;
          out = await doPush(parent);
        } else {
          throw e;
        }
      }
      uiModule.showToast('Pushed to Notion');
      if (out && out.url) {
        try { window.open(out.url, '_blank', 'noopener'); } catch { /* popup blocked — fine */ }
      }
    } catch (e) {
      uiModule.showError(e.message || 'Push failed');
    } finally {
      btn.disabled = false;
      btn.textContent = prev;
    }
  });
}

// ── View: Notion settings ───────────────────────────────────────────────────
async function _renderSettings() {
  const body = _body();
  if (!body) return;
  _setLoading(body, 'Loading settings…');
  let cfg = { configured: false, parent: null };
  try { cfg = await _api('/notion/config'); } catch { /* show defaults */ }
  body.innerHTML = `
    <div class="clients-section-label">Notion connection</div>
    <div class="clients-card clients-form">
      <div class="clients-dim" style="font-size:12px;">
        ${cfg.configured
          ? 'Connected — transcripts can be pulled from Notion pages and artifacts pushed back.'
          : 'Not connected. Create an internal integration at notion.so/my-integrations, share your CM pages with it (Share → Add connections), and paste its secret below.'}
      </div>
      <label class="clients-field-label">Integration token <span class="clients-dim">— stored encrypted, never shown again</span></label>
      <input id="clients-notion-token" class="memory-search-input" type="password"
             placeholder="${cfg.configured ? 'Configured — paste a new token to replace' : 'ntn_… / secret_…'}" style="margin-top:0;" />
      <label class="clients-field-label">Default parent page <span class="clients-dim">— where pushed artifacts are created</span></label>
      <input id="clients-notion-parent" class="memory-search-input"
             placeholder="https://www.notion.so/Your-Page-…" value="${_esc(cfg.parent || '')}" style="margin-top:0;" />
      <div class="clients-form-actions">
        <button id="clients-notion-save" class="confirm-btn confirm-btn-primary">Save</button>
      </div>
    </div>
  `;
  body.querySelector('#clients-notion-save')?.addEventListener('click', async () => {
    const token = body.querySelector('#clients-notion-token')?.value?.trim();
    const parent = body.querySelector('#clients-notion-parent')?.value?.trim();
    try {
      const out = await _api('/notion/config', {
        method: 'POST',
        body: JSON.stringify({ token: token || null, parent: parent != null ? parent : null }),
      });
      uiModule.showToast(out.configured ? 'Notion connected' : 'Saved');
      _navBack();
    } catch (e) {
      uiModule.showError(e.message || 'Failed to save');
    }
  });
}

// ── Panel lifecycle ────────────────────────────────────────────────────────
function _fullscreenSafeRect() {
  const pad = 8;
  return { left: pad, top: pad, width: window.innerWidth - pad * 2, height: window.innerHeight - pad * 2 };
}

function openPanel() {
  if (_open) return;
  _open = true;
  _nav = [{ view: 'portfolio' }];
  document.body.classList.add('clients-view');

  const pane = document.createElement('div');
  pane.id = 'clients-pane';
  pane.className = 'clients-pane';
  pane.innerHTML = `
    <div class="clients-pane-header">
      <button id="clients-back-btn" class="doc-action-icon-btn" title="Back" style="display:none;">
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M15 18l-6-6 6-6"/></svg>
      </button>
      <h4 class="clients-pane-title">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px;vertical-align:-2px;"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/></svg><span id="clients-pane-title-text">Clients</span>
      </h4>
      <span style="flex:1"></span>
      <button id="clients-settings-btn" class="doc-action-icon-btn" title="Notion settings">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M2 12h3M19 12h3M4.9 19.1 7 17M17 7l2.1-2.1"/></svg>
      </button>
      <button id="clients-refresh-btn" class="doc-action-icon-btn" title="Refresh">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12a9 9 0 1 1-2.64-6.36"/><path d="M21 3v6h-6"/></svg>
      </button>
      <button id="clients-close-btn" class="close-btn" data-action="close" title="Close">×</button>
    </div>
    <div class="clients-pane-body"></div>
  `;

  const backdrop = document.createElement('div');
  backdrop.className = 'clients-pane-backdrop';
  backdrop.id = 'clients-pane-backdrop';
  backdrop.addEventListener('click', (ev) => { if (ev.target === backdrop) closePanel(); });
  backdrop.appendChild(pane);
  document.body.appendChild(backdrop);
  _pane = pane;
  _backdrop = backdrop;

  // Mobile bottom-sheet takeover — inline belt-and-braces (see notes.js:1149).
  if (window.innerWidth <= 768) {
    Object.assign(pane.style, {
      position: 'fixed', inset: '0', width: '100%', maxWidth: '100%',
      height: '100dvh', maxHeight: '100dvh', zIndex: '170',
      borderRadius: '14px 14px 0 0', borderBottom: 'none',
    });
  }

  // Drag / resize / fullscreen / dock behavior.
  const header = pane.querySelector('.clients-pane-header');
  makeWindowDraggable(pane, {
    content: pane,
    header,
    fsClass: 'clients-window-fullscreen',
    skipSelector: 'button, input, select, textarea, label',
    enableDock: true,
    enableLeftDock: true,
    onEnterFullscreen: () => {
      pane.classList.add('clients-window-fullscreen');
      snapModalToZone(pane, { name: 'fullscreen', rect: _fullscreenSafeRect() });
    },
    onExitFullscreen: () => { pane.classList.remove('clients-window-fullscreen'); },
  });

  // Header buttons.
  pane.querySelector('#clients-close-btn')?.addEventListener('click', () => closePanel());
  pane.querySelector('#clients-back-btn')?.addEventListener('click', () => _navBack());
  pane.querySelector('#clients-refresh-btn')?.addEventListener('click', () => _renderView());
  pane.querySelector('#clients-settings-btn')?.addEventListener('click', () => {
    const top = _nav[_nav.length - 1];
    if (top.view !== 'settings') _navTo({ view: 'settings' });
  });

  // Esc: back first, then close. Own handler, removed on close (notes.js pattern).
  _keydownHandler = (e) => {
    if (e.key !== 'Escape') return;
    const t = e.target;
    if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.isContentEditable)) return;
    e.stopImmediatePropagation();
    e.preventDefault();
    if (_nav.length > 1) _navBack();
    else closePanel();
  };
  document.addEventListener('keydown', _keydownHandler, true);

  _renderView();
}

function closePanel() {
  if (!_open) return;
  _open = false;
  document.body.classList.remove('clients-view');
  if (_keydownHandler) {
    document.removeEventListener('keydown', _keydownHandler, true);
    _keydownHandler = null;
  }
  const bd = _backdrop;
  _pane = null;
  _backdrop = null;
  if (bd) {
    bd.remove();
  }
  // Restore the sidebar if the /clients route opener collapsed it.
  try { window._restoreSidebarIfRouteCollapsed && window._restoreSidebarIfRouteCollapsed(); } catch { /* ignore */ }
}

function togglePanel() {
  if (_open) closePanel();
  else openPanel();
}

function isPanelOpen() {
  return _open;
}

// Live refresh when the agent mutates client data (producer in chat.js).
window.addEventListener('clients-refresh', () => {
  if (_open) _renderView();
});

// Sync open flag if the pane is dismissed by mobile swipe (ui.js:1065).
window.addEventListener('modal-dismissed', (e) => {
  if (e.detail && (e.detail.id === 'clients-pane' || e.detail.id === 'clients-pane-backdrop')) {
    _open = false;
    document.body.classList.remove('clients-view');
  }
});

const clientsModule = { openPanel, closePanel, togglePanel, isPanelOpen };
export default clientsModule;
window.clientsModule = clientsModule;
