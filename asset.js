(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const id = Number(new URLSearchParams(location.search).get('id'));
  const fact = (label, value, code = false) => `<div class="data-item"><span>${escapeHtml(label)}</span><${code ? 'code' : 'strong'}>${escapeHtml(value || '—')}</${code ? 'code' : 'strong'}></div>`;

  function render(item) {
    const art = WCArchetypes.resolve(item); const image = item.primary_image_url || art.url; const archetype = !item.primary_image_url;
    document.title = `${item.wc_id} | Wonder Codex`; $('#assetTitle').innerHTML = `${escapeHtml(item.wc_id)} <span>published specimen.</span>`;
    $('#assetSubtitle').textContent = 'Normalized procedural identity, source provenance, review state, and acquisition evidence.';
    $('#assetGallery').innerHTML = `<div class="record-primary-image ${archetype ? 'is-archetype' : ''}"><img src="${escapeHtml(image)}" alt="${escapeHtml(archetype ? art.alt : item.display_name)}"><div class="record-image-caption">${archetype ? 'Illustrative reconstruction — not an image of this exact specimen.' : 'Approved specimen image'}</div></div>`;
    $('#assetIllustrationNote').hidden = !archetype;
    $('#assetWcId').textContent = item.wc_id; $('#assetName').textContent = item.display_name; $('#assetContributor').textContent = `Contributed by ${item.contributor || 'Anonymous explorer'}`; $('#assetType').textContent = item.asset_type === 'Multitool' ? 'Multi-tool' : item.asset_type;
    $('#assetBadges').innerHTML = `<span class="status-chip ${item.location_status === 'verified' ? 'verified' : 'unverified'}">Acquisition ${escapeHtml(item.location_status)}</span><span class="status-chip ${item.image_status === 'available' ? 'verified' : 'needed'}">Image ${escapeHtml(item.image_status)}</span>${item.modified_or_special_signal ? '<span class="status-chip pending">Special signal under review</span>' : ''}`;
    $('#assetFacts').innerHTML = [fact('Asset type', item.asset_type), fact('Class', item.class), fact('Source role', (item.source_role || '').replaceAll('_',' ')), fact('Source collection', item.source_collection), fact('Source ordinal', item.source_ordinal === null ? '—' : item.source_ordinal), fact('Identity basis', item.identity_basis), fact('Confidence', item.confidence), fact('Procedural seed', item.seed, true), fact('Resource filename', item.resource_filename, true), fact('Delivery eligibility', item.delivery_eligibility), fact('Delivery evidence', item.delivery_evidence_status), fact('Platform provenance', item.platform)].join('');
    if (item.has_location) $('#assetLocation').innerHTML = `<p class="kicker">VERIFIED ACQUISITION SIGHTING</p><h2>Galaxy ${escapeHtml(item.galaxy_number)}${item.galaxy_name ? ` — ${escapeHtml(item.galaxy_name)}` : ''}</h2><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(item.portal_glyphs,{compact:true})}</div><p class="glyph-code">${escapeHtml(item.portal_glyphs)}</p>`;
    else $('#assetLocation').innerHTML = `<p class="kicker">ACQUISITION EVIDENCE</p><h2>Location not established</h2><p>This specimen was normalized from owned-save data. A repeatable public acquisition route has not yet been verified.</p>`;
    $('#assetLayout').hidden = false;
  }

  if (!Number.isInteger(id) || id < 1) { $('#assetError').textContent = 'This asset record link is invalid.'; $('#assetError').hidden = false; return; }
  fetch(`/api/assets/${id}`).then(async (response) => { const data = await response.json(); if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`); render(data); }).catch((error) => { $('#assetError').textContent = error.message; $('#assetError').hidden = false; });
})();
