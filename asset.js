(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const id = Number(new URLSearchParams(location.search).get('id'));
  const fact = (label, value, code = false) => `<div class="data-item"><span>${escapeHtml(label)}</span><${code ? 'code' : 'strong'}>${escapeHtml(value || '—')}</${code ? 'code' : 'strong'}></div>`;

  function render(item) {
    const forgeImage = String(item.forge_image_url || '').trim();
    const expedition = item.primary_image_url || forgeImage
      ? null
      : window.WCExpedition?.resolve(item);
    const representativeImage = forgeImage || String(expedition?.image_url || '');
    const image = item.primary_image_url || representativeImage;
    const forgeRepresentative = !item.primary_image_url && Boolean(representativeImage);
    const forgeName = item.forge_form_name || expedition?.name || item.asset_type;
    const forgeLabel = item.forge_display_label || expedition?.public_label
      || 'Evidence-matched Forge reconstruction — verify color and lighting in game.';
    document.title = `${item.wc_id} | Wonder Codex`; $('#assetTitle').innerHTML = `${escapeHtml(item.wc_id)} <span>published specimen.</span>`;
    $('#assetSubtitle').textContent = 'Normalized procedural identity, source provenance, review state, and acquisition evidence.';
    $('#assetGallery').innerHTML = image
      ? `<div class="record-primary-image ${forgeRepresentative ? 'is-forge' : ''}"><img src="${escapeHtml(image)}" alt="${escapeHtml(forgeRepresentative ? `${item.display_name} evidence-matched Forge reconstruction` : item.display_name)}"><div class="record-image-caption">${forgeRepresentative ? `${escapeHtml(forgeName)} • ${escapeHtml(forgeLabel)}` : 'Approved specimen image'}</div></div>`
      : '<div class="record-primary-image is-missing"><div class="record-image-placeholder"><span>Image needed</span><strong>Exact visual not yet matched</strong><small>This asset needs an exact screenshot or an Expedition reconstruction bound to the same procedural identity.</small></div><div class="record-image-caption">No broad asset-type image is substituted</div></div>';
    $('#assetIllustrationNote').hidden = Boolean(item.primary_image_url);
    $('#assetIllustrationNote').textContent = forgeRepresentative
      ? `${item.forge_match_label || 'Stable catalog identity'} • ${forgeLabel}`
      : 'Image needed — no exact screenshot or evidence-matched Forge reconstruction is available yet.';
    const galleryImage = $('#assetGallery img');
    galleryImage?.addEventListener('error', () => {
      $('#assetGallery').innerHTML = '<div class="record-primary-image is-missing"><div class="record-image-placeholder"><span>Image needed</span><strong>Visual temporarily unavailable</strong><small>The image could not be loaded; no broad placeholder has been substituted.</small></div><div class="record-image-caption">Please report this asset record to an administrator</div></div>';
    }, {once: true});
    $('#assetWcId').textContent = item.wc_id; $('#assetName').textContent = item.display_name; $('#assetContributor').textContent = `Contributed by ${item.contributor || 'Anonymous explorer'}`; $('#assetType').textContent = item.asset_type === 'Multitool' ? 'Multi-tool' : item.asset_type;
    $('#assetBadges').innerHTML = `<span class="status-chip ${item.location_status === 'verified' ? 'verified' : 'unverified'}">Acquisition ${escapeHtml(item.location_status)}</span><span class="status-chip ${item.image_status === 'available' ? 'verified' : 'needed'}">Image ${escapeHtml(item.image_status)}</span>${item.modified_or_special_signal ? '<span class="status-chip pending">Special signal under review</span>' : ''}`;
    const classLabel = item.native_class_known ? 'Class' : 'Current class';
    const homeEvidence = (item.home_system_evidence || '').replaceAll('_', ' ');
    $('#assetFacts').innerHTML = [
      fact('Asset type', item.asset_type),
      fact(classLabel, item.class_label || item.class),
      fact('Native spawn class', item.native_class_known ? item.class : 'Not established'),
      fact('Source role', (item.source_role || '').replaceAll('_',' ')),
      fact('Source collection', item.source_collection),
      fact('Source ordinal', item.source_ordinal === null ? '—' : item.source_ordinal),
      fact('Identity basis', item.identity_basis),
      fact('Stable identity fingerprint', item.identity_fingerprint, true),
      fact('Confidence', item.confidence),
      fact('Procedural seed', item.seed, true),
      fact('Seed meaning', item.appearance_seed_location_status === 'not_a_location_claim' ? 'Appearance identity — not a location' : item.appearance_seed_location_status),
      fact('Home-system evidence', homeEvidence),
      fact('Resource filename', item.resource_filename, true),
      fact('Delivery eligibility', item.delivery_eligibility),
      fact('Delivery evidence', item.delivery_evidence_status),
      fact('Platform provenance', item.platform),
    ].join('');
    if (item.has_location) $('#assetLocation').innerHTML = `<p class="kicker">VERIFIED ACQUISITION SIGHTING</p><h2>Galaxy ${escapeHtml(item.galaxy_number)}${item.galaxy_name ? ` — ${escapeHtml(item.galaxy_name)}` : ''}</h2><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(item.portal_glyphs,{compact:true})}</div><p class="glyph-code">${escapeHtml(item.portal_glyphs)}</p>`;
    else $('#assetLocation').innerHTML = `<p class="kicker">ACQUISITION EVIDENCE</p><h2>Location not established</h2><p>This specimen was normalized from owned-save data. A repeatable public acquisition route has not yet been verified.</p>`;
    $('#assetLayout').hidden = false;
    window.WonderAnalytics?.track('asset_view', {
      entity_type: item.asset_type || 'asset', entity_id: item.wc_id,
      catalog_lane: item.asset_type || '', location_status: item.location_status || '', image_status: item.image_status || '',
    });
  }

  if (!Number.isInteger(id) || id < 1) { $('#assetError').textContent = 'This asset record link is invalid.'; $('#assetError').hidden = false; return; }
  Promise.resolve(window.WCExpedition?.load())
    .catch(() => null)
    .finally(() => {
      fetch(`/api/assets/${id}`).then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        render(data);
      }).catch((error) => {
        $('#assetError').textContent = error.message;
        $('#assetError').hidden = false;
      });
    });
})();
