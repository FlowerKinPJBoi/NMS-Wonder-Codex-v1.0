(() => {
  'use strict';

  const API = '/api';
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  const canvas = $('#mapCanvas');
  const stage = $('#mapStage');
  const context = canvas.getContext('2d');
  const state = {
    points: [], clusters: [], hotspots: [], loading: false, request: 0,
    centerX: 0, centerZ: 0, scale: .16, minScale: .08, maxScale: 5,
    width: 0, height: 0, dpr: 1, drag: null, selected: null,
    controller: null, drawFrame: 0, zoomLabel: '',
  };

  function populateGalaxies() {
    const select = $('#galaxyFilter');
    select.innerHTML = WCLocation.galaxyNames.slice(1).map((name, index) => `<option value="${index + 1}">${index + 1} — ${escapeHtml(name)}</option>`).join('');
  }

  async function populateFamilies() {
    try {
      const response = await fetch(`${API}/fauna-families`, {headers:{Accept:'application/json'}});
      if (!response.ok) throw new Error(`Status ${response.status}`);
      const data = await response.json();
      $('#familyFilter').innerHTML = '<option value="">All families</option>' + (data.items || []).map((family) => `<option value="${escapeHtml(family.id)}">${escapeHtml(family.label)} (${number(family.record_count)})</option>`).join('');
      applyUrlState();
    } catch {
      $('#familyFilter').innerHTML = '<option value="">Family list unavailable</option>';
    }
  }

  function applyUrlState() {
    const params = new URLSearchParams(location.search);
    const values = {
      galaxyFilter: params.get('galaxy'), laneFilter: params.get('lane'),
      typeFilter: params.get('type'), familyFilter: params.get('family'),
      qualityFilter: params.get('quality'), mapSearch: params.get('q'), displayMode: params.get('display'),
    };
    Object.entries(values).forEach(([id, value]) => {
      const field = document.getElementById(id);
      if (field && value && [...field.options || []].some((option) => option.value === value)) field.value = value;
      else if (field && value && field.tagName === 'INPUT') field.value = value;
    });
    updateFilterAvailability();
  }

  function updateUrl() {
    const params = new URLSearchParams();
    const entries = [
      ['galaxy', $('#galaxyFilter').value], ['lane', $('#laneFilter').value],
      ['type', $('#typeFilter').value], ['family', $('#familyFilter').value],
      ['quality', $('#qualityFilter').value], ['q', $('#mapSearch').value.trim()],
      ['display', $('#displayMode').value],
    ];
    const defaults = {lane:'wonders', quality:'all', display:'clusters'};
    entries.forEach(([key, value]) => { if (value && value !== defaults[key]) params.set(key, value); });
    history.replaceState(null, '', `${location.pathname}${params.size ? `?${params}` : ''}`);
  }

  function updateFilterAvailability() {
    const lane = $('#laneFilter').value;
    const assetOnly = ['Starship','Freighter','Frigate','Multitool'].includes(lane);
    const mixed = lane === 'all';
    $('#typeFilter').disabled = assetOnly || mixed;
    $('#familyFilter').disabled = assetOnly || mixed;
    if (assetOnly || mixed) { $('#typeFilter').value = ''; $('#familyFilter').value = ''; }
    $('#typeFilterField').classList.toggle('field-disabled', assetOnly || mixed);
    $('#familyFilterField').classList.toggle('field-disabled', assetOnly || mixed);
    if (assetOnly) { $('#qualityFilter').value = 'verified'; $('#qualityFilter').disabled = true; }
    else $('#qualityFilter').disabled = false;
    const familyUnavailable = assetOnly || mixed || ($('#typeFilter').value && $('#typeFilter').value !== 'Animal');
    $('#familyFilter').disabled = familyUnavailable;
    $('#familyFilterField').classList.toggle('field-disabled', familyUnavailable);
  }

  function mapQuery() {
    const params = new URLSearchParams({
      galaxy_number: $('#galaxyFilter').value,
      catalog_lane: $('#laneFilter').value,
      location_quality: $('#qualityFilter').value,
      limit: '5000',
    });
    if ($('#typeFilter').value) params.set('discovery_type', $('#typeFilter').value);
    if ($('#familyFilter').value) params.set('fauna_family', $('#familyFilter').value);
    if ($('#mapSearch').value.trim()) params.set('q', $('#mapSearch').value.trim());
    return params;
  }

  async function loadPoints({reset = true} = {}) {
    const request = ++state.request;
    state.controller?.abort();
    const controller = new AbortController();
    state.controller = controller;
    state.loading = true;
    $('#mapLoading').hidden = false;
    $('#mapEmpty').hidden = true;
    $('#mapCount').textContent = 'Plotting location evidence…';
    updateUrl();
    try {
      const response = await fetch(`${API}/map-points?${mapQuery()}`, {
        headers:{Accept:'application/json'},
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Map request failed (${response.status}).`);
      if (request !== state.request) return;
      state.points = data.items || [];
      state.hotspots = buildHotspots(state.points);
      renderHotspots();
      state.selected = null;
      if (reset) resetView(false);
      $('#mapSelection').className = 'selection-empty';
      $('#mapSelection').innerHTML = '<span class="selection-orbit" aria-hidden="true"></span><strong>Select a point or cluster</strong><p>Coordinates, glyphs, family identity, and catalog links will appear here.</p>';
      const noun = state.points.length === 1 ? 'location-backed record' : 'location-backed records';
      $('#mapCount').textContent = `${number(state.points.length)} ${noun} in Galaxy ${data.galaxy_number} — ${data.galaxy_name}${data.truncated ? ` · showing first ${number(data.returned)}` : ''}`;
      $('#mapEmpty').hidden = state.points.length > 0;
      draw();
      if (window.WonderAnalytics) {
        const q = $('#mapSearch').value.trim();
        WonderAnalytics.track('map_filter', {
          map_galaxy: $('#galaxyFilter').value,
          map_lane: $('#laneFilter').value,
          map_quality: $('#qualityFilter').value,
          discovery_type: $('#typeFilter').value,
          fauna_family: $('#familyFilter').value,
          query_kind: WonderAnalytics.queryKind(q),
          query_length: q.length,
          has_query: Boolean(q),
          result_count: state.points.length,
        });
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      if (request !== state.request) return;
      state.points = [];
      state.hotspots = [];
      $('#mapCount').textContent = error.message;
      $('#mapEmpty').hidden = false;
      $('#mapEmpty').innerHTML = `<strong>Map unavailable</strong><p>${escapeHtml(error.message)}</p>`;
      draw();
    } finally {
      if (request === state.request) { state.loading = false; $('#mapLoading').hidden = true; }
    }
  }

  function resize() {
    const rect = stage.getBoundingClientRect();
    state.dpr = Math.min(window.devicePixelRatio || 1, 2);
    state.width = Math.max(1, Math.round(rect.width));
    state.height = Math.max(1, Math.round(rect.height));
    canvas.width = Math.round(state.width * state.dpr);
    canvas.height = Math.round(state.height * state.dpr);
    canvas.style.width = `${state.width}px`;
    canvas.style.height = `${state.height}px`;
    context.setTransform(state.dpr, 0, 0, state.dpr, 0, 0);
    state.minScale = Math.max(.055, Math.min(state.width, state.height) / 4600);
    if (state.scale < state.minScale) state.scale = state.minScale;
    scheduleDraw();
  }

  function resetView(render = true) {
    state.centerX = 0; state.centerZ = 0;
    state.scale = Math.max(state.minScale, Math.min(state.width, state.height) / 4550);
    if (render) draw();
  }

  function worldToScreen(point) {
    return {x: state.width / 2 + (Number(point.x) - state.centerX) * state.scale, y: state.height / 2 + (Number(point.z) - state.centerZ) * state.scale};
  }

  function createClusters() {
    const bucket = $('#displayMode').value === 'heatmap' ? 58 : 48;
    const groups = new Map();
    state.points.forEach((point) => {
      const screen = worldToScreen(point);
      if (screen.x < -80 || screen.x > state.width + 80 || screen.y < -80 || screen.y > state.height + 80) return;
      const key = `${Math.floor(screen.x / bucket)}:${Math.floor(screen.y / bucket)}`;
      const group = groups.get(key) || {key, points: [], x: 0, y: 0, worldX: 0, worldZ: 0};
      group.points.push(point); group.x += screen.x; group.y += screen.y; group.worldX += Number(point.x); group.worldZ += Number(point.z);
      groups.set(key, group);
    });
    state.clusters = [...groups.values()].map((group) => ({
      ...group, x: group.x / group.points.length, y: group.y / group.points.length,
      worldX: group.worldX / group.points.length, worldZ: group.worldZ / group.points.length,
    }));
    return state.clusters;
  }

  function buildHotspots(points) {
    const cellSize = 320;
    const groups = new Map();
    points.forEach((point) => {
      const key = `${Math.floor(Number(point.x) / cellSize)}:${Math.floor(Number(point.z) / cellSize)}`;
      const group = groups.get(key) || {key, points:[], worldX:0, worldZ:0};
      group.points.push(point);
      group.worldX += Number(point.x);
      group.worldZ += Number(point.z);
      groups.set(key, group);
    });
    return [...groups.values()].map((group) => {
      group.worldX /= group.points.length;
      group.worldZ /= group.points.length;
      group.systems = new Set(group.points.map((point) => `${point.x}:${point.y}:${point.z}`)).size;
      group.verified = group.points.filter((point) => point.travel_status === 'verified').length;
      group.signal = group.points.length >= 25 && group.systems >= 10 ? 'High sample' : group.points.length >= 8 && group.systems >= 4 ? 'Developing' : 'Early signal';
      group.label = dominantLabel(group.points);
      return group;
    }).filter((group) => group.points.length > 1)
      .sort((a,b) => (b.points.length * Math.log2(b.systems + 1)) - (a.points.length * Math.log2(a.systems + 1)));
  }

  function dominantLabel(points) {
    const counts = new Map();
    points.forEach((point) => {
      const label = point.family_label || point.record_type || 'Mixed';
      counts.set(label, (counts.get(label) || 0) + 1);
    });
    return [...counts.entries()].sort((a,b) => b[1] - a[1])[0]?.[0] || 'Mixed';
  }

  function drawBackdrop() {
    const ctx = context;
    ctx.clearRect(0, 0, state.width, state.height);
    const center = worldToScreen({x:0,z:0});
    ctx.save();
    ctx.strokeStyle = 'rgba(109,231,255,.12)'; ctx.lineWidth = 1;
    [512,1024,1536,2048].forEach((radius) => {
      ctx.beginPath(); ctx.arc(center.x, center.y, radius * state.scale, 0, Math.PI * 2); ctx.stroke();
    });
    ctx.strokeStyle = 'rgba(157,140,255,.11)'; ctx.setLineDash([4,7]);
    ctx.beginPath(); ctx.moveTo(center.x, 0); ctx.lineTo(center.x, state.height); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0, center.y); ctx.lineTo(state.width, center.y); ctx.stroke();
    ctx.setLineDash([]);
    const glow = ctx.createRadialGradient(center.x, center.y, 0, center.x, center.y, Math.max(18, 190 * state.scale));
    glow.addColorStop(0, 'rgba(255,215,131,.72)'); glow.addColorStop(.2, 'rgba(255,215,131,.18)'); glow.addColorStop(1, 'rgba(255,215,131,0)');
    ctx.fillStyle = glow; ctx.beginPath(); ctx.arc(center.x, center.y, Math.max(18, 190 * state.scale), 0, Math.PI * 2); ctx.fill();
    ctx.restore();
  }

  function clusterColor(cluster) {
    const type = cluster.points[0]?.record_type;
    return ({Animal:'#6de7ff',Flora:'#72efbd',Mineral:'#ffd783',Starship:'#9d8cff',Freighter:'#ff9fbd',Frigate:'#85b7ff',Multitool:'#ffcb7b'})[type] || '#b6f5ff';
  }

  function drawClusters(clusters) {
    const ctx = context;
    const heatmap = $('#displayMode').value === 'heatmap';
    if (heatmap) {
      ctx.save(); ctx.globalCompositeOperation = 'lighter';
      clusters.forEach((cluster) => {
        const radius = Math.min(88, 20 + Math.sqrt(cluster.points.length) * 9);
        const gradient = ctx.createRadialGradient(cluster.x, cluster.y, 0, cluster.x, cluster.y, radius);
        const color = clusterColor(cluster);
        gradient.addColorStop(0, `${color}A6`); gradient.addColorStop(.28, `${color}4D`); gradient.addColorStop(1, `${color}00`);
        ctx.fillStyle = gradient; ctx.beginPath(); ctx.arc(cluster.x, cluster.y, radius, 0, Math.PI * 2); ctx.fill();
      });
      ctx.restore();
    }
    clusters.forEach((cluster) => {
      const count = cluster.points.length;
      const color = clusterColor(cluster);
      const radius = count === 1 ? 5 : Math.min(25, 9 + Math.log2(count + 1) * 3.1);
      ctx.save();
      ctx.shadowColor = color; ctx.shadowBlur = count === 1 ? 12 : 18;
      ctx.fillStyle = count === 1 ? color : 'rgba(9,16,34,.92)';
      ctx.strokeStyle = color; ctx.lineWidth = count === 1 ? 1 : 2;
      ctx.beginPath(); ctx.arc(cluster.x, cluster.y, radius, 0, Math.PI * 2); ctx.fill(); ctx.stroke();
      ctx.shadowBlur = 0;
      if (count > 1) {
        ctx.fillStyle = '#f6f7ff'; ctx.font = '800 11px Inter, sans-serif'; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(count > 999 ? '999+' : String(count), cluster.x, cluster.y + .5);
      }
      ctx.restore();
      cluster.hitRadius = radius + 8;
    });
  }

  function drawHotspotHalos(hotspots) {
    context.save();
    hotspots.slice(0,8).forEach((hotspot, index) => {
      const screen = worldToScreen({x:hotspot.worldX,z:hotspot.worldZ});
      if (screen.x < -90 || screen.x > state.width + 90 || screen.y < -90 || screen.y > state.height + 90) return;
      const radius = Math.min(70, 24 + Math.sqrt(hotspot.points.length) * 5);
      context.strokeStyle = index === 0 ? 'rgba(255,215,131,.62)' : 'rgba(157,140,255,.38)';
      context.lineWidth = index === 0 ? 2 : 1;
      context.setLineDash([5,7]);
      context.beginPath(); context.arc(screen.x, screen.y, radius, 0, Math.PI * 2); context.stroke();
      context.setLineDash([]);
    });
    context.restore();
  }

  function draw() {
    if (!state.width || !state.height) return;
    drawBackdrop();
    drawHotspotHalos(state.hotspots);
    const clusters = createClusters();
    drawClusters(clusters);
    const zoom = state.scale / state.minScale;
    const label = zoom < 1.35 ? 'Galaxy view' : `${zoom.toFixed(1)}× zoom`;
    if (label !== state.zoomLabel) {
      state.zoomLabel = label;
      $('#zoomReadout').textContent = label;
    }
  }

  function scheduleDraw() {
    if (state.drawFrame) return;
    state.drawFrame = requestAnimationFrame(() => {
      state.drawFrame = 0;
      draw();
    });
  }

  function renderHotspots() {
    const ranked = state.hotspots.slice(0,5);
    $('#hotspotBasis').textContent = 'Fixed 320-coordinate cells · current filters · catalog concentration only.';
    $('#hotspotList').innerHTML = ranked.length ? ranked.map((hotspot,index) => {
      const verifiedPercent = Math.round((hotspot.verified / hotspot.points.length) * 100);
      return `<button class="hotspot-item" type="button" data-hotspot="${escapeHtml(hotspot.key)}"><span>${index + 1}</span><span><strong>${escapeHtml(hotspot.label)} hotspot</strong><small>${hotspot.points.length} records · ${hotspot.systems} systems · ${verifiedPercent}% verified · ${escapeHtml(hotspot.signal)}</small></span><span>Focus</span></button>`;
    }).join('') : '<p class="hotspot-empty">No multi-record hotspot signal exists for this filter yet.</p>';
    $('#hotspotList').querySelectorAll('[data-hotspot]').forEach((button) => button.addEventListener('click', () => {
      const hotspot = state.hotspots.find((item) => item.key === button.dataset.hotspot);
      if (hotspot) focusCluster(hotspot);
    }));
  }

  function renderSelection(cluster) {
    state.selected = cluster;
    const systems = new Set(cluster.points.map((point) => `${point.x}:${point.y}:${point.z}`)).size;
    const shown = cluster.points.slice(0,12);
    $('#mapSelection').className = 'selection-list';
    $('#mapSelection').innerHTML = `<div class="selection-summary"><strong>${number(cluster.points.length)} record${cluster.points.length === 1 ? '' : 's'}</strong><span>${systems} SYSTEM${systems === 1 ? '' : 'S'}</span></div>
      ${shown.map((point) => `<a class="selection-card" href="${escapeHtml(point.record_url)}"><header><strong>${escapeHtml(point.wc_id)}</strong><span class="route-state">${escapeHtml(point.travel_status)}</span></header><p>${escapeHtml(point.display_name)}</p><p>${escapeHtml(point.family_label ? `${point.family_label} · ` : '')}${escapeHtml(point.record_type)}</p><small>${escapeHtml(point.portal_glyphs)} · X ${point.x}, Y ${point.y}, Z ${point.z}</small></a>`).join('')}
      ${cluster.points.length > shown.length ? `<p class="selection-more">+ ${number(cluster.points.length - shown.length)} more records in this cluster</p>` : ''}
      ${cluster.points.length > 1 ? '<button id="focusSelection" class="button secondary" type="button">Zoom into this cluster</button>' : ''}`;
    $('#focusSelection')?.addEventListener('click', () => focusCluster(cluster));
  }

  function focusCluster(cluster) {
    state.centerX = cluster.worldX; state.centerZ = cluster.worldZ;
    state.scale = Math.min(state.maxScale, Math.max(state.scale * 2.5, state.minScale * 3));
    draw();
    const selectedKeys = new Set(cluster.points.map((point) => point.key));
    const refreshed = state.clusters.find((item) => item.points.some((point) => selectedKeys.has(point.key)));
    if (refreshed) renderSelection(refreshed);
  }

  function zoomAt(factor, screenX = state.width / 2, screenY = state.height / 2) {
    const beforeX = state.centerX + (screenX - state.width / 2) / state.scale;
    const beforeZ = state.centerZ + (screenY - state.height / 2) / state.scale;
    const next = Math.max(state.minScale, Math.min(state.maxScale, state.scale * factor));
    state.scale = next;
    state.centerX = beforeX - (screenX - state.width / 2) / next;
    state.centerZ = beforeZ - (screenY - state.height / 2) / next;
    scheduleDraw();
  }

  stage.addEventListener('wheel', (event) => {
    event.preventDefault();
    const rect = stage.getBoundingClientRect();
    zoomAt(event.deltaY < 0 ? 1.22 : .82, event.clientX - rect.left, event.clientY - rect.top);
  }, {passive:false});
  stage.addEventListener('pointerdown', (event) => {
    if (event.button !== 0) return;
    state.drag = {x:event.clientX,y:event.clientY,centerX:state.centerX,centerZ:state.centerZ,moved:false};
    stage.setPointerCapture(event.pointerId); stage.classList.add('dragging');
  });
  stage.addEventListener('pointermove', (event) => {
    if (!state.drag) return;
    const dx = event.clientX - state.drag.x, dy = event.clientY - state.drag.y;
    if (Math.abs(dx) + Math.abs(dy) > 4) state.drag.moved = true;
    state.centerX = state.drag.centerX - dx / state.scale; state.centerZ = state.drag.centerZ - dy / state.scale;
    scheduleDraw();
  });
  stage.addEventListener('pointerup', (event) => {
    const drag = state.drag; state.drag = null; stage.classList.remove('dragging');
    if (!drag?.moved) {
      const rect = stage.getBoundingClientRect(), x = event.clientX - rect.left, y = event.clientY - rect.top;
      const hit = state.clusters.filter((cluster) => Math.hypot(cluster.x - x, cluster.y - y) <= cluster.hitRadius).sort((a,b) => Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y))[0];
      if (hit) renderSelection(hit);
    }
  });
  stage.addEventListener('pointercancel', () => { state.drag = null; stage.classList.remove('dragging'); });
  $('#zoomIn').addEventListener('click', () => zoomAt(1.35));
  $('#zoomOut').addEventListener('click', () => zoomAt(.74));
  $('#resetView').addEventListener('click', () => resetView());

  let timer;
  $('#mapFilters').addEventListener('change', (event) => {
    if (event.target.id === 'displayMode') { updateUrl(); scheduleDraw(); return; }
    if (event.target.id === 'laneFilter') updateFilterAvailability();
    if (event.target.id === 'typeFilter') {
      if (event.target.value !== 'Animal') $('#familyFilter').value = '';
      updateFilterAvailability();
    }
    loadPoints();
  });
  $('#mapSearch').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => loadPoints({reset:false}), 280); });
  new ResizeObserver(resize).observe(stage);

  populateGalaxies();
  applyUrlState();
  populateFamilies().finally(() => loadPoints());
})();
