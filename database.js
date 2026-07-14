(() => {
  'use strict';

  const API = '/api';
  const state = {items: [], total: 0, offset: 0, limit: 48, loading: false};
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();

  function typeLabel(type) {
    return ({Animal:'Fauna', Flora:'Flora', Mineral:'Mineral'})[type] || type || 'Other';
  }

  function locationMarkup(item) {
    item = WCLocation.enrich(item);
    if (item.has_travel_address) {
      const galaxy = `${item.galaxy_number}${item.galaxy_name ? ` — ${escapeHtml(item.galaxy_name)}` : ''}`;
      const source = item.has_location ? 'Community verified' : item.travel_status === 'derived' ? 'UA-derived route' : 'Catalog route';
      return `<div class="location-mini ${escapeHtml(item.travel_status)}"><strong>Galaxy ${galaxy}</strong><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(item.portal_glyphs,{compact:true})}</div><p>${escapeHtml(source)}</p></div>`;
    }
    const label = item.location_status === 'pending' ? 'Location awaiting review' : item.location_status === 'disputed' ? 'Location disputed' : 'Location verification needed';
    return `<div class="location-mini"><strong>${escapeHtml(label)}</strong><p>Contributors can submit galaxy and glyph evidence.</p></div>`;
  }

  function imageMarkup(item, name) {
    const archetype = WCArchetypes.resolve(item);
    const approvedUrl = String(item.primary_image_url || '').trim();
    const isArchetype = !approvedUrl;
    return `<div class="wonder-card-image ${isArchetype ? 'is-archetype' : 'is-approved'}">
      <img src="${escapeHtml(approvedUrl || archetype.url)}" alt="${escapeHtml(isArchetype ? archetype.alt : name)}" loading="lazy" data-archetype-fallback="${escapeHtml(archetype.url)}" data-archetype-alt="${escapeHtml(archetype.alt)}">
      <div class="archetype-label"${isArchetype ? '' : ' hidden'}><span>Representative archetype</span><small>${escapeHtml(archetype.label)} · specimen image pending</small></div>
    </div>`;
  }

  function bindImageFallbacks() {
    document.querySelectorAll('#catalogGrid .wonder-card-image img[data-archetype-fallback]').forEach((image) => {
      image.addEventListener('error', function useArchetypeFallback() {
        image.removeEventListener('error', useArchetypeFallback);
        image.src = image.dataset.archetypeFallback;
        image.alt = image.dataset.archetypeAlt;
        const frame = image.closest('.wonder-card-image');
        frame?.classList.remove('is-approved');
        frame?.classList.add('is-archetype');
        const label = frame?.querySelector('.archetype-label');
        if (label) label.hidden = false;
      });
    });
  }

  function card(item) {
    item = WCLocation.enrich(item);
    const name = escapeHtml(item.display_name);
    return `<article class="wonder-card">
      ${imageMarkup(item, item.display_name)}
      <div class="wonder-card-top"><span class="wc-id">${escapeHtml(item.wc_id)}</span><span class="type-chip">${escapeHtml(typeLabel(item.discovery_type))}</span></div>
      <h2>${name}</h2>
      <p>Contributed by ${escapeHtml(item.contributor || item.owner || 'Unknown explorer')}</p>
      <div class="card-badges">
        <span class="status-chip ${escapeHtml(item.travel_status)}">Location ${escapeHtml(item.travel_status)}</span>
        <span class="status-chip ${item.image_status === 'available' ? 'verified' : 'needed'}">Image ${escapeHtml(item.image_status)}</span>
        <span class="status-chip ${item.projector_status === 'verified' ? 'verified' : ''}">Projector ${escapeHtml(item.projector_status.replaceAll('_',' '))}</span>
      </div>
      ${locationMarkup(item)}
      <div class="wonder-card-actions">
        <a class="mini-link primary" href="record.html?id=${item.id}">View record</a>
        <a class="mini-link" href="contribute.html?mode=image&record=${item.id}">Add image</a>
        <a class="mini-link" href="contribute.html?mode=verify&record=${item.id}">Verify</a>
      </div>
    </article>`;
  }

  function queryString(reset) {
    const params = new URLSearchParams();
    const q = $('#catalogSearch').value.trim();
    const type = $('#typeFilter').value;
    const location = $('#locationFilter').value;
    const image = $('#imageFilter').value;
    if (q) params.set('q', q);
    if (type) params.set('discovery_type', type);
    if (location) params.set('location_status', location);
    if (image) params.set('image_status', image);
    params.set('limit', state.limit);
    params.set('offset', reset ? 0 : state.offset);
    return params.toString();
  }

  async function load(reset = true) {
    if (state.loading) return;
    state.loading = true;
    $('#loadMore').disabled = true;
    if (reset) {
      state.offset = 0;
      state.items = [];
      $('#catalogGrid').innerHTML = '<div class="loading-state surface">Searching the Wonder Database…</div>';
    }
    try {
      const response = await fetch(`${API}/discoveries?${queryString(reset)}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      state.total = data.total || 0;
      state.items = reset ? (data.items || []) : state.items.concat(data.items || []);
      state.offset = state.items.length;
      render();
      $('#loadMore').hidden = !data.has_more;
    } catch (error) {
      $('#catalogGrid').innerHTML = `<div class="empty-catalog surface"><strong>Catalog unavailable</strong><p>${escapeHtml(error.message)}</p></div>`;
      $('#catalogCount').textContent = 'Unable to load records.';
      $('#loadMore').hidden = true;
    } finally {
      state.loading = false;
      $('#loadMore').disabled = false;
    }
  }

  function render() {
    $('#catalogCount').textContent = `${number(state.total)} record${state.total === 1 ? '' : 's'} found`;
    $('#catalogGrid').innerHTML = state.items.length
      ? state.items.map(card).join('')
      : '<div class="empty-catalog surface"><strong>No records match these filters.</strong><p>Try a broader search or help verify a location.</p></div>';
    bindImageFallbacks();
  }

  let timer;
  $('#catalogSearch').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => load(true), 300); });
  ['#typeFilter','#locationFilter','#imageFilter'].forEach((selector) => $(selector).addEventListener('change', () => load(true)));
  $('#loadMore').addEventListener('click', () => load(false));
  load(true);
})();
