(() => {
  'use strict';

  const API = '/api';
  const state = {key: '', actor: 'PJ', days: 7};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  const dateTime = (value) => { const date = new Date(value); return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleString(); };
  const headers = () => ({'X-Admin-Key':state.key,'X-Admin-Actor':state.actor,Accept:'application/json'});

  async function api(path) {
    const response = await fetch(API + path, {headers:headers()});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function toast(message, error = false) {
    const element = $('#toast'); element.textContent = message; element.className = `toast${error ? ' error' : ''}`; element.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { element.hidden = true; }, 4000);
  }

  function lock() {
    sessionStorage.removeItem('wc_admin_key'); sessionStorage.removeItem('wc_admin_actor');
    state.key = ''; $('#dashboard').hidden = true; $('#loginPanel').hidden = false; $('#lockButton').hidden = true;
    $('#connectionBadge').textContent = 'Locked'; $('#connectionBadge').className = 'connection-badge'; $('#adminKeyInput').value = '';
  }

  async function unlock(event) {
    event?.preventDefault();
    state.key = $('#adminKeyInput').value.trim(); state.actor = $('#actorInput').value.trim() || 'PJ'; $('#loginError').hidden = true;
    try {
      const data = await api(`/owner/analytics/summary?days=${state.days}`);
      sessionStorage.setItem('wc_admin_key', state.key); sessionStorage.setItem('wc_admin_actor', state.actor);
      $('#loginPanel').hidden = true; $('#dashboard').hidden = false; $('#lockButton').hidden = false;
      $('#connectionBadge').textContent = 'Owner connected'; $('#connectionBadge').className = 'connection-badge online'; render(data);
    } catch (error) {
      state.key = ''; $('#loginError').textContent = error.message; $('#loginError').hidden = false;
    }
  }

  function metricRows(items, empty = 'No signal in this range yet.') {
    if (!items?.length) return `<div class="metric-empty">${escapeHtml(empty)}</div>`;
    return items.map((item) => `<div class="metric-row"><span title="${escapeHtml(item.label)}">${escapeHtml(item.label.replaceAll('_',' '))}</span><strong>${number(item.count)}</strong></div>`).join('');
  }

  function renderChart(series) {
    const target = $('#trafficChart');
    if (!series?.length) { target.innerHTML = '<div class="metric-empty">Analytics collection has started. The first traffic bars will appear here.</div>'; return; }
    const max = Math.max(1, ...series.flatMap((item) => [item.page_views, item.sessions]));
    target.innerHTML = series.map((item) => {
      const label = new Date(`${item.day}T12:00:00Z`).toLocaleDateString(undefined,{month:'short',day:'numeric'});
      const viewsHeight = Math.max(2, Math.round(item.page_views / max * 190));
      const sessionsHeight = Math.max(2, Math.round(item.sessions / max * 190));
      return `<div class="chart-day"><div class="chart-bars"><span class="chart-bar views" style="height:${viewsHeight}px" title="${number(item.page_views)} page views"></span><span class="chart-bar sessions" style="height:${sessionsHeight}px" title="${number(item.sessions)} visits"></span></div><small>${escapeHtml(label)}</small></div>`;
    }).join('');
  }

  const filterLabels = {
    catalog_lane:'Catalog lanes', discovery_type:'Discovery types', fauna_family:'Fauna families', location_status:'Location status',
    image_status:'Image status', query_kind:'Search activity', map_galaxy:'Map galaxies', map_lane:'Map lanes', map_quality:'Map quality',
    evidence_type:'Evidence submitted', download_type:'Downloads',
  };

  function renderFilters(filters) {
    const groups = Object.entries(filters || {}).filter(([,items]) => items?.length);
    $('#filterBreakdowns').innerHTML = groups.length ? groups.map(([key,items]) => `<section class="filter-group"><h3>${escapeHtml(filterLabels[key] || key)}</h3><div class="metric-list compact">${metricRows(items)}</div></section>`).join('') : '<div class="metric-empty">Catalog and map filter activity will appear after explorers use them.</div>';
  }

  function renderJourneys(journeys) {
    $('#journeys').innerHTML = journeys?.length ? journeys.map((journey) => {
      const pages = journey.pages?.map((page) => `<span title="${escapeHtml(page.path)}">${escapeHtml(page.title || page.path)}</span>`).join('<i>→</i>') || '<span>No page views recorded</span>';
      const actions = journey.actions?.length ? `<div class="journey-actions">Actions: ${journey.actions.map((action) => `${escapeHtml(action.type.replaceAll('_',' '))}${action.entity ? ` · ${escapeHtml(action.entity)}` : ''}`).join(' · ')}</div>` : '';
      return `<article class="journey"><div class="journey-head"><strong>${escapeHtml(journey.label)}</strong><span>${escapeHtml(journey.device)} · ${escapeHtml(journey.browser)} · ${escapeHtml(dateTime(journey.last_seen_at))}</span></div><div class="journey-path">${pages}</div>${actions}</article>`;
    }).join('') : '<div class="metric-empty">Recent anonymous journeys will appear here.</div>';
  }

  function render(data) {
    $('#pageViews').textContent = number(data.totals.page_views); $('#sessions').textContent = number(data.totals.sessions);
    $('#pagesPerSession').textContent = Number(data.totals.pages_per_session || 0).toLocaleString(undefined,{maximumFractionDigits:2});
    $('#liveSessions').textContent = number(data.totals.live_sessions); $('#customEvents').textContent = number(data.totals.custom_events);
    $('#rangeLabel').textContent = data.range.label; renderChart(data.series);
    $('#topPages').innerHTML = metricRows(data.top_pages); $('#topReferrers').innerHTML = metricRows(data.top_referrers);
    $('#devices').innerHTML = metricRows(data.devices); $('#browsers').innerHTML = metricRows(data.browsers); $('#operatingSystems').innerHTML = metricRows(data.operating_systems);
    $('#topEvents').innerHTML = metricRows(data.top_events); $('#topEntities').innerHTML = metricRows(data.top_entities);
    renderFilters(data.filters); renderJourneys(data.journeys); $('#lastRefresh').textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  async function refresh() {
    $('#refreshButton').disabled = true;
    try { render(await api(`/owner/analytics/summary?days=${state.days}`)); }
    catch (error) { toast(error.message, true); if (["Invalid operator credentials.","Owner analytics access required."].includes(error.message)) lock(); }
    finally { $('#refreshButton').disabled = false; }
  }

  $('#loginForm').addEventListener('submit', unlock); $('#lockButton').addEventListener('click', lock); $('#refreshButton').addEventListener('click', refresh);
  $$('.range-tabs button').forEach((button) => button.addEventListener('click', () => {
    state.days = Number(button.dataset.days); $$('.range-tabs button').forEach((item) => item.classList.toggle('active', item === button)); refresh();
  }));

  const savedKey = sessionStorage.getItem('wc_admin_key'); const savedActor = sessionStorage.getItem('wc_admin_actor');
  if (savedActor) $('#actorInput').value = savedActor;
  if (savedKey && savedActor) { state.key = savedKey; state.actor = savedActor; $('#adminKeyInput').value = savedKey; unlock(); }
})();
