(() => {
  'use strict';

  const API = '/api';
  const state = {items: [], total: 0, offset: 0, limit: 48, loading: false, lane: 'wonders'};
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  const isAssetLane = () => state.lane !== 'wonders';
  const pluralAsset = (type) => ({Starship:'starships',Freighter:'freighters',Frigate:'frigates',Multitool:'multi-tools'})[type] || 'assets';

  function typeLabel(type) {
    return ({Animal:'Fauna', Flora:'Flora', Mineral:'Mineral', Multitool:'Multi-tool'})[type] || type || 'Other';
  }

  function locationMarkup(item) {
    item = WCLocation.enrich(item);
    if (item.has_travel_address) {
      const galaxy = `${item.galaxy_number}${item.galaxy_name ? ` — ${escapeHtml(item.galaxy_name)}` : ''}`;
      const source = item.has_location ? 'Community verified' : item.travel_status === 'derived' ? 'Automatically derived route' : 'Catalog route';
      return `<div class="location-mini ${escapeHtml(item.travel_status)}"><strong>Galaxy ${galaxy}</strong><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(item.portal_glyphs,{compact:true})}</div><p>${escapeHtml(source)}</p></div>`;
    }
    const label = item.location_status === 'pending' ? 'Location awaiting review' : item.location_status === 'disputed' ? 'Location disputed' : 'Location verification needed';
    return `<div class="location-mini"><strong>${escapeHtml(label)}</strong><p>Contributors can submit galaxy and glyph evidence.</p></div>`;
  }

  function assetLocationMarkup(item) {
    if (item.has_location) {
      const galaxy = `${item.galaxy_number}${item.galaxy_name ? ` — ${escapeHtml(item.galaxy_name)}` : ''}`;
      return `<div class="location-mini verified"><strong>Verified acquisition sighting · Galaxy ${galaxy}</strong><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(item.portal_glyphs,{compact:true})}</div><p>This sighting is separate from the procedural specimen identity.</p></div>`;
    }
    const pending = item.location_status === 'pending';
    return `<div class="location-mini ${pending ? 'pending' : ''}"><strong>${pending ? 'Acquisition sighting under review' : 'Acquisition location not established'}</strong><p>The owned specimen is cataloged; a public acquisition route still needs evidence.</p></div>`;
  }

  function wonderIdentityMarkup(item) {
    if (!item.wonder_family_label && !item.fauna_family_label) return '';
    const exact = item.fauna_identity_source === 'exact_pet_match';
    const behavior = exact && item.fauna_behavior ? `Behavior: ${item.fauna_behavior}` : 'Behavior not inferred';
    const evidenceCount = Number(item.fauna_family_evidence_count || 0);
    const family = item.wonder_family_label || `${item.fauna_family_label} family`;
    const individual = item.wonder_individual_name_status === 'captured'
      ? `Named specimen: ${item.wonder_individual_name}`
      : `Individual signal ${item.wonder_individual_reference || 'encoded'}`;
    const evidence = exact
      ? `Exact companion match${evidenceCount ? ` · ${number(evidenceCount)} supporting match${evidenceCount === 1 ? '' : 'es'}` : ''}`
      : item.wonder_family_source === 'confirmed_vp1_mapping'
        ? `Confirmed VP1 family mapping${evidenceCount ? ` · ${number(evidenceCount)} exact match${evidenceCount === 1 ? '' : 'es'}` : ''}`
        : 'VP1 visual-family signal · VP0 individual/name signal';
    const descriptorCount = Number(item.descriptor_token_count || 0);
    const categories = Array.isArray(item.descriptor_visual_categories) ? item.descriptor_visual_categories : [];
    const descriptorEvidence = exact && descriptorCount
      ? `<small class="descriptor-evidence">${number(descriptorCount)} observed appearance signal${descriptorCount === 1 ? '' : 's'}${categories.length ? ` · research hints: ${escapeHtml(categories.join(', '))}` : ''}</small>`
      : '';
    return `<div class="fauna-identity card-identity ${exact ? 'exact' : 'inferred'}"><div class="fauna-identity-heading"><span class="fauna-family-badge">${escapeHtml(family)}</span><span class="fauna-behavior">${escapeHtml(exact ? behavior : individual)}</span></div><small>${escapeHtml(evidence)}</small>${descriptorEvidence}</div>`;
  }

  function imageMarkup(item, name) {
    const archetype = WCArchetypes.resolve(item);
    const representativeLabel = item.archetype_label || archetype.label;
    const approvedUrl = String(item.primary_image_url || '').trim();
    const isArchetype = !approvedUrl;
    const assetLabel = item.asset_type ? 'Illustrative reconstruction — not an image of this exact specimen.' : `${representativeLabel} · Representative archetype — not this exact specimen.`;
    return `<div class="wonder-card-image ${isArchetype ? 'is-archetype' : 'is-approved'}">
      <img src="${escapeHtml(approvedUrl || archetype.url)}" alt="${escapeHtml(isArchetype ? archetype.alt : name)}" loading="lazy" data-archetype-fallback="${escapeHtml(archetype.url)}" data-archetype-alt="${escapeHtml(archetype.alt)}">
      <div class="archetype-label"${isArchetype ? '' : ' hidden'}><span>${item.asset_type ? 'Illustrative archetype' : 'Representative archetype'}</span><small>${escapeHtml(assetLabel)}</small></div>
    </div>`;
  }

  function bindImageFallbacks() {
    document.querySelectorAll('#catalogGrid .wonder-card-image img[data-archetype-fallback]').forEach((image) => {
      image.addEventListener('error', function useArchetypeFallback() {
        image.removeEventListener('error', useArchetypeFallback);
        image.src = image.dataset.archetypeFallback;
        image.alt = image.dataset.archetypeAlt;
        const frame = image.closest('.wonder-card-image');
        frame?.classList.remove('is-approved'); frame?.classList.add('is-archetype');
        const label = frame?.querySelector('.archetype-label'); if (label) label.hidden = false;
      });
    });
  }

  function wonderCard(item) {
    item = WCLocation.enrich(item);
    return `<article class="wonder-card">${imageMarkup(item, item.display_name)}
      <div class="wonder-card-top"><span class="wc-id">${escapeHtml(item.wc_id)}</span><span class="type-chip">${escapeHtml(typeLabel(item.discovery_type))}</span></div>
      <h2>${escapeHtml(item.display_name)}</h2><p>Contributed by ${escapeHtml(item.contributor || item.owner || 'Unknown explorer')}</p>
      ${wonderIdentityMarkup(item)}
      <div class="card-badges"><span class="status-chip ${escapeHtml(item.travel_status)}">Location ${escapeHtml(item.travel_status)}</span><span class="status-chip ${item.image_status === 'available' ? 'verified' : 'needed'}">Image ${escapeHtml(item.image_status)}</span><span class="status-chip ${item.projector_status === 'verified' ? 'verified' : ''}">Projector ${escapeHtml(item.projector_status.replaceAll('_',' '))}</span></div>
      ${locationMarkup(item)}
      <div class="wonder-card-actions"><a class="mini-link primary" href="record.html?id=${item.id}">View record</a><a class="mini-link" href="contribute.html?mode=image&record=${item.id}">Add image</a><a class="mini-link" href="contribute.html?mode=verify&record=${item.id}">Verify</a></div>
    </article>`;
  }

  function assetIdentityMarkup(item) {
    const className = item.class_label || item.class || 'Class under review';
    const source = (item.source_role || 'unknown').replaceAll('_', ' ');
    const classNote = item.native_class_known ? 'native class confirmed' : 'current class; native spawn class unknown';
    return `<div class="asset-identity card-identity"><div class="asset-identity-heading"><span class="asset-class-badge">${escapeHtml(className)}</span><span>${escapeHtml(source)}</span></div><small>${escapeHtml(classNote)} · Identity: ${escapeHtml(item.identity_basis || 'normalized asset key')} · ${escapeHtml(item.confidence || 'Beta extracted')}</small></div>`;
  }

  function assetCard(item) {
    return `<article class="wonder-card asset-card">${imageMarkup(item, item.display_name)}
      <div class="wonder-card-top"><span class="wc-id">${escapeHtml(item.wc_id)}</span><span class="type-chip">${escapeHtml(typeLabel(item.asset_type))}</span></div>
      <h2>${escapeHtml(item.display_name)}</h2><p>Contributed by ${escapeHtml(item.contributor || 'Anonymous explorer')}</p>
      ${assetIdentityMarkup(item)}
      <div class="card-badges"><span class="status-chip ${item.location_status === 'verified' ? 'verified' : 'unverified'}">Acquisition ${escapeHtml(item.location_status)}</span><span class="status-chip ${item.image_status === 'available' ? 'verified' : 'needed'}">Image ${escapeHtml(item.image_status)}</span>${item.modified_or_special_signal ? '<span class="status-chip pending">Special signal · review</span>' : ''}</div>
      ${assetLocationMarkup(item)}
      <div class="wonder-card-actions"><a class="mini-link primary" href="asset.html?id=${item.id}">View specimen</a></div>
    </article>`;
  }

  function queryString(reset) {
    const params = new URLSearchParams();
    const q = $('#catalogSearch').value.trim(); const location = $('#locationFilter').value; const image = $('#imageFilter').value;
    if (q) params.set('q', q);
    if (isAssetLane()) params.set('asset_type', state.lane);
    else {
      const type = $('#typeFilter').value; const family = $('#familyFilter').value;
      if (type) params.set('discovery_type', type); if (family) params.set('fauna_family', family);
    }
    if (location) params.set('location_status', location); if (image) params.set('image_status', image);
    params.set('limit', state.limit); params.set('offset', reset ? 0 : state.offset);
    return params.toString();
  }

  async function loadFamilies() {
    const select = $('#familyFilter');
    try {
      const response = await fetch(`${API}/fauna-families`); const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      select.innerHTML = '<option value="">All families</option>' + (data.items || []).map((family) => `<option value="${escapeHtml(family.id)}">${escapeHtml(family.label)} (${number(family.record_count)})</option>`).join('');
    } catch { select.innerHTML = '<option value="">Family filter unavailable</option>'; select.disabled = true; }
  }

  async function loadLaneCounts() {
    try {
      const response = await fetch(`${API}/asset-types`); const data = await response.json(); if (!response.ok) return;
      (data.items || []).forEach((item) => { const node = document.querySelector(`[data-asset-count="${CSS.escape(item.id)}"]`); if (node) node.textContent = number(item.count); });
    } catch {}
  }

  function updateLaneUi() {
    $$('.catalog-lane').forEach((button) => { const active = button.dataset.catalogLane === state.lane; button.classList.toggle('active', active); button.setAttribute('aria-selected', active ? 'true' : 'false'); });
    const assets = isAssetLane(); $('#typeFilterField').hidden = assets; $('#familyFilterField').hidden = assets;
    $('#catalogSearch').placeholder = assets ? `WC ID, name, class, contributor…` : 'WC ID, fauna family, contributor, galaxy…';
    $('#catalogContext').textContent = assets ? 'A procedural specimen and its acquisition location are reviewed as separate evidence.' : 'Automatically derived routes are labeled separately from community-verified locations.';
  }

  async function load(reset = true) {
    if (state.loading) return;
    state.loading = true; $('#loadMore').disabled = true;
    if (reset) { state.offset = 0; state.items = []; $('#catalogGrid').innerHTML = '<div class="loading-state surface">Searching the Wonder Database…</div>'; }
    try {
      const endpoint = isAssetLane() ? 'assets' : 'discoveries';
      const response = await fetch(`${API}/${endpoint}?${queryString(reset)}`); const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      state.total = data.total || 0; state.items = reset ? (data.items || []) : state.items.concat(data.items || []); state.offset = state.items.length;
      render(); $('#loadMore').hidden = !data.has_more;
      if (reset && window.WonderAnalytics) {
        const q = $('#catalogSearch').value.trim();
        WonderAnalytics.track('catalog_filter', {
          catalog_lane: state.lane,
          discovery_type: isAssetLane() ? '' : $('#typeFilter').value,
          fauna_family: isAssetLane() ? '' : $('#familyFilter').value,
          location_status: $('#locationFilter').value,
          image_status: $('#imageFilter').value,
          query_kind: WonderAnalytics.queryKind(q),
          query_length: q.length,
          has_query: Boolean(q),
          result_count: state.total,
        });
      }
    } catch (error) {
      $('#catalogGrid').innerHTML = `<div class="empty-catalog surface"><strong>Catalog unavailable</strong><p>${escapeHtml(error.message)}</p></div>`;
      $('#catalogCount').textContent = 'Unable to load records.'; $('#loadMore').hidden = true;
    } finally { state.loading = false; $('#loadMore').disabled = false; }
  }

  function render() {
    const label = isAssetLane() ? pluralAsset(state.lane) : `record${state.total === 1 ? '' : 's'}`;
    $('#catalogCount').textContent = `${number(state.total)} ${label} found`;
    $('#catalogGrid').innerHTML = state.items.length ? state.items.map(isAssetLane() ? assetCard : wonderCard).join('') : isAssetLane()
      ? `<div class="empty-catalog asset-empty surface"><img src="${escapeHtml(WCArchetypes.resolve({asset_type:state.lane}).url)}" alt=""><strong>No published ${escapeHtml(pluralAsset(state.lane))} yet.</strong><p>The review lane and its illustrative archetype are ready for the first approved specimen.</p></div>`
      : '<div class="empty-catalog surface"><strong>No records match these filters.</strong><p>Try a broader search or help verify a location.</p></div>';
    bindImageFallbacks();
  }

  let timer;
  $('#catalogSearch').addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(() => load(true), 300); });
  $('#typeFilter').addEventListener('change', () => { if ($('#typeFilter').value && $('#typeFilter').value !== 'Animal') $('#familyFilter').value = ''; load(true); });
  ['#familyFilter','#locationFilter','#imageFilter'].forEach((selector) => $(selector).addEventListener('change', () => load(true)));
  $$('.catalog-lane').forEach((button) => button.addEventListener('click', () => { state.lane = button.dataset.catalogLane; updateLaneUi(); load(true); }));
  $('#loadMore').addEventListener('click', () => load(false));
  updateLaneUi(); loadFamilies(); loadLaneCounts(); load(true);
})();
