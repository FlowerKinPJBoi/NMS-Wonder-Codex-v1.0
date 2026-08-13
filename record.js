(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  let record = null;
  let pegasusDispatch = null;
  let pegasusPollTimer = null;

  function toast(message) {
    const element = $('#toast');
    element.textContent = message;
    element.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.hidden = true, 3000);
  }

  function badge(label, status) {
    return `<span class="status-chip ${escapeHtml(status)}">${escapeHtml(label)} ${escapeHtml(status.replaceAll('_',' '))}</span>`;
  }

  function item(label, value, code = true) {
    const safe = value || '—';
    return `<div class="data-item"><span>${escapeHtml(label)}</span>${code ? `<code>${escapeHtml(safe)}</code>` : `<strong>${escapeHtml(safe)}</strong>`}</div>`;
  }

  function pegasusStatus(message, heading = 'Pegasus Live private alpha.') {
    const panel = $('#pegasusStatus');
    panel.innerHTML = `<strong>${escapeHtml(heading)}</strong><br>${escapeHtml(message)}`;
  }

  function pegasusProfileReady() {
    const profile = window.WCAccount?.profile;
    return Boolean(
      window.WCAccount?.session?.access_token
      && ['admin', 'tester'].includes(profile?.access_tier)
      && profile?.has_nms_friend_code
      && profile?.bot_connect_consent
    );
  }

  function dispatchLabel(status) {
    return ({
      queued: 'Route queued',
      claimed: 'Pegasus acknowledged the route',
      preparing: 'Pegasus is preparing',
      waiting_for_game_exit: 'Waiting for a safe game exit',
      save_written: 'Destination written and verified',
      launching: 'Pegasus is launching',
      boarding: 'Pegasus is ready for boarding',
      completed: 'Transit completed',
      failed: 'Transit stopped safely',
      cancelled: 'Transit cancelled',
      expired: 'Request expired',
    })[status] || 'Dispatch update';
  }

  function renderPegasusDispatch(dispatch) {
    pegasusDispatch = dispatch;
    const button = $('#pegasusTransit');
    const terminal = ['completed', 'failed', 'cancelled', 'expired'].includes(dispatch.status);
    button.disabled = !terminal;
    button.textContent = terminal
      ? 'REQUEST PEGASUS LIVE AGAIN'
      : `PEGASUS LIVE — ${dispatchLabel(dispatch.status)}`;
    pegasusStatus(
      dispatch.message || 'Pegasus is processing this dispatch.',
      `${dispatchLabel(dispatch.status)} · ${dispatch.route.wc_record_id}`,
    );
    if (!terminal) schedulePegasusPoll(dispatch.id);
  }

  function schedulePegasusPoll(dispatchId) {
    clearTimeout(pegasusPollTimer);
    pegasusPollTimer = setTimeout(() => pollPegasusDispatch(dispatchId), 4000);
  }

  async function pegasusResponse(response) {
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Pegasus request failed (${response.status})`);
    return data;
  }

  async function pollPegasusDispatch(dispatchId) {
    const token = window.WCAccount?.session?.access_token;
    if (!token || !dispatchId) return;
    try {
      const data = await pegasusResponse(await fetch(`/api/pegasus/dispatches/${dispatchId}`, {
        headers: {Authorization: `Bearer ${token}`},
      }));
      renderPegasusDispatch(data.dispatch);
    } catch (error) {
      pegasusStatus(error.message, 'Pegasus status unavailable');
      schedulePegasusPoll(dispatchId);
    }
  }

  async function configurePegasusTransit(data) {
    const button = $('#pegasusTransit');
    const ready = Boolean(data.has_travel_address && data.galaxy_number && data.portal_glyphs);
    const account = await window.WCAccount?.ready;
    const profile = window.WCAccount?.profile;
    if (!ready) {
      button.disabled = true;
      button.textContent = 'PEGASUS LIVE — Route unavailable';
      pegasusStatus('This record needs a complete catalog travel address before Pegasus can depart.');
      return;
    }
    if (!account?.enabled || !window.WCAccount?.session) {
      button.disabled = true;
      button.textContent = 'PEGASUS LIVE — Passport sign-in required';
      pegasusStatus('Sign in through Passport to request this private-alpha service.');
      return;
    }
    if (!['admin', 'tester'].includes(profile?.access_tier)) {
      button.disabled = true;
      button.textContent = 'PEGASUS LIVE — Admin or Tester only';
      pegasusStatus('Your Passport is active, but Pegasus Live is currently restricted to Admin and Tester roles.');
      return;
    }
    if (!profile.has_nms_friend_code || !profile.bot_connect_consent) {
      button.disabled = true;
      button.textContent = 'PEGASUS LIVE — Complete Passport setup';
      pegasusStatus('Add your NMS friend code and enable bot-connect consent in Passport before requesting Pegasus.');
      return;
    }
    try {
      const active = await pegasusResponse(await fetch('/api/pegasus/dispatches/active', {
        headers: {Authorization: `Bearer ${window.WCAccount.session.access_token}`},
      }));
      if (active.dispatch) {
        renderPegasusDispatch(active.dispatch);
        return;
      }
    } catch (error) {
      pegasusStatus(error.message, 'Pegasus access check failed');
      button.disabled = true;
      return;
    }
    button.disabled = false;
    button.textContent = 'REQUEST PEGASUS LIVE TRANSIT';
    pegasusStatus(`Ready to dispatch Pegasus to ${data.wc_id}. The catalog route will be verified again before it enters the queue.`);
  }

  async function requestPegasusTransit() {
    if (!record || !pegasusProfileReady()) return;
    const button = $('#pegasusTransit');
    button.disabled = true;
    button.textContent = 'PEGASUS LIVE — Sending route…';
    pegasusStatus('Submitting this route to the private dispatch queue.');
    try {
      const data = await pegasusResponse(await fetch('/api/pegasus/dispatches', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${window.WCAccount.session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({discovery_id: record.id}),
      }));
      renderPegasusDispatch(data.dispatch);
      window.WonderAnalytics?.track('pegasus_live_requested', {
        entity_type: 'discovery',
        entity_id: record.wc_id,
        requester_tier: window.WCAccount.profile.access_tier,
      });
      toast(data.reused ? 'Your active Pegasus dispatch is still in progress.' : 'Pegasus Live dispatch requested.');
    } catch (error) {
      pegasusStatus(error.message, 'Pegasus request stopped');
      button.disabled = false;
      button.textContent = 'REQUEST PEGASUS LIVE TRANSIT';
    }
  }

  function renderWonderIdentity(data) {
    const element = $('#recordIdentity');
    if (!data.wonder_family_label && !data.fauna_family_label) {
      element.hidden = true;
      element.innerHTML = '';
      return;
    }
    if (data.discovery_type === 'Planet') {
      const exactSize = data.planet_size_status === 'exact_joined_giant_base'
        || data.planet_size_status === 'confirmed_gas_giant_family';
      const evidence = data.planet_size_status === 'exact_joined_giant_base'
        ? 'Giant size confirmed by an exact player-base-to-Planet join'
        : data.planet_size_status === 'confirmed_gas_giant_family'
          ? 'Gas Giant family confirmed by VP1'
          : 'VP1 confirms the planet family; standard size remains representative because DiscoveryData has no size field';
      element.classList.toggle('exact', exactSize);
      element.classList.toggle('inferred', !exactSize);
      element.innerHTML = `<p class="kicker">PLANET IDENTITY</p>
        <div class="fauna-identity-heading"><strong>${escapeHtml(data.wonder_family_label)}</strong><span class="fauna-behavior">${escapeHtml(data.planet_size_class || 'Standard')}</span></div>
        <p>${escapeHtml(evidence)} · ${escapeHtml(data.planet_name_label || 'Name evidence under review')}</p>`;
      element.hidden = false;
      return;
    }
    const exact = data.fauna_identity_source === 'exact_pet_match';
    const evidenceCount = Number(data.fauna_family_evidence_count || 0);
    const family = data.wonder_family_label || `${data.fauna_family_label} family`;
    const evidence = exact ? 'Exact companion match'
      : data.wonder_family_source === 'confirmed_vp1_mapping'
        ? `Confirmed family mapping${evidenceCount ? ` · supported by ${number(evidenceCount)} exact match${evidenceCount === 1 ? '' : 'es'}` : ''}`
        : 'VP1 visual-family signal from controlled Wonder Projector research';
    const individual = data.wonder_individual_name_status === 'captured'
      ? `Captured in-game name: ${data.wonder_individual_name}`
      : `Individual/name signal ${data.wonder_individual_reference || 'encoded'} — exact name not decoded yet`;
    const descriptorCount = Number(data.descriptor_token_count || 0);
    const categories = Array.isArray(data.descriptor_visual_categories) ? data.descriptor_visual_categories : [];
    const appearance = exact && descriptorCount
      ? `<p class="descriptor-evidence">${number(descriptorCount)} appearance signal${descriptorCount === 1 ? '' : 's'} observed in the exact paired pet record${categories.length ? ` · token-name research hints: ${escapeHtml(categories.join(', '))}` : ''}. These hints are not yet confirmed body-part mappings.</p>`
      : '';
    element.classList.toggle('exact', exact);
    element.classList.toggle('inferred', !exact);
    element.innerHTML = `<p class="kicker">WONDER IDENTITY</p>
      <div class="fauna-identity-heading"><strong>${escapeHtml(family)}</strong><span class="fauna-behavior">${escapeHtml(individual)}</span></div>
      <p>${escapeHtml(evidence)} · ${escapeHtml(data.wonder_projector_fingerprint_label || 'Projector fingerprint under review')}</p>${appearance}`;
    element.hidden = false;
  }


  function showArchetype(data, note = '') {
    const archetype = WCArchetypes.resolve(data);
    const forgeUrl = String(data.forge_image_url || '').trim();
    const expedition = forgeUrl ? null : window.WCExpedition?.resolve(data);
    const representativeUrl = forgeUrl || String(expedition?.image_url || '');
    const gallery = $('#recordGallery');
    const frame = gallery.querySelector('.record-primary-image');
    const primary = $('#recordPrimaryImage');
    frame.classList.add('is-archetype');
    frame.classList.toggle('is-forge', Boolean(representativeUrl));
    const showStaticArchetype = () => {
      frame.classList.remove('is-forge');
      primary.onerror = () => {
        primary.onerror = null;
        primary.removeAttribute('src');
        $('#recordImageCaption').textContent = 'The representative archetype could not be loaded. Please report this record ID to an administrator.';
      };
      primary.src = archetype.url;
      primary.alt = archetype.alt;
      $('#recordImageCaption').textContent = `${data.archetype_label || archetype.label} • Representative archetype — not this exact specimen${note ? ` • ${note}` : ''}`;
    };
    primary.onerror = () => {
      if (representativeUrl) {
        showStaticArchetype();
        return;
      }
      primary.onerror = null;
      primary.removeAttribute('src');
      $('#recordImageCaption').textContent = 'The representative archetype could not be loaded. Please report this record ID to an administrator.';
    };
    primary.src = representativeUrl || archetype.url;
    primary.alt = representativeUrl ? `${data.planet_biome_family || data.fauna_family_label || expedition?.category_label || 'Wonder'} representative from Wonder Forge` : archetype.alt;
    $('#recordImageCaption').textContent = representativeUrl
      ? `${data.forge_form_name || expedition?.name || data.planet_biome_family || data.fauna_family_label || 'Approved representative'} • Wonder Forge ${forgeUrl ? 'verified natural form' : 'Expedition representative'} • ${data.forge_display_label || expedition?.public_label || 'Representative family image — not this exact specimen.'}${note ? ` • ${note}` : ''}`
      : `${data.archetype_label || archetype.label} • Representative archetype — not this exact specimen${note ? ` • ${note}` : ''}`;
    $('#recordThumbnails').innerHTML = '';
    $('#recordThumbnails').hidden = true;
    gallery.hidden = false;
  }

  function renderImages(images, data) {
    const approved = Array.isArray(images) ? images.filter((image) => image.url) : [];
    const gallery = $('#recordGallery');
    if (!approved.length) { showArchetype(data); return; }
    let active = approved.find((image) => image.is_primary) || approved[0];
    const show = (image) => {
      active = image;
      const primary = $('#recordPrimaryImage');
      gallery.querySelector('.record-primary-image').classList.remove('is-archetype', 'is-forge');
      primary.onerror = () => {
        showArchetype(data, 'approved image temporarily unavailable');
      };
      const deliveryUrl = `${image.url}${image.url.includes('?') ? '&' : '?'}display=140`;
      primary.src = deliveryUrl;
      primary.alt = `${record.wc_id} — ${image.role.replaceAll('_',' ')}`;
      $('#recordImageCaption').textContent = `${image.caption || image.role.replaceAll('_',' ')} • Image by ${image.contributor}`;
      $$('#recordThumbnails .record-thumbnail').forEach((button) => button.classList.toggle('active', button.dataset.id === image.id));
    };
    $('#recordThumbnails').innerHTML = approved.map((image) => `<button class="record-thumbnail" type="button" data-id="${escapeHtml(image.id)}"><img src="${escapeHtml(image.url)}${image.url.includes('?') ? '&' : '?'}display=140" alt="${escapeHtml(image.role.replaceAll('_',' '))}"></button>`).join('');
    $('#recordThumbnails').hidden = false;
    $$('#recordThumbnails .record-thumbnail').forEach((button) => button.addEventListener('click', () => show(approved.find((image) => image.id === button.dataset.id))));
    gallery.hidden = false;
    show(active);
  }

  function render(data) {
    data = WCLocation.enrich(data);
    record = data;
    const expedition = data.forge_image_url ? null : window.WCExpedition?.resolve(data);
    const hasForgeRepresentative = Boolean(data.forge_image_url || expedition);
    document.title = `${data.wc_id} — ${data.display_name} | Wonder Codex`;
    $('#recordHero').innerHTML = `${escapeHtml(data.wc_id)} <span>published record.</span>`;
    $('#recordIntro').textContent = 'Projector data, attribution, verification status, and travel information for this Wonder Codex discovery.';
    $('#wcId').textContent = data.wc_id;
    $('#recordName').textContent = data.display_name;
    $('#recordType').textContent = data.discovery_type === 'Animal' ? 'Fauna' : data.discovery_type;
    $('#recordAttribution').textContent = `Contributed by ${data.contributor || data.owner || 'Unknown explorer'}${data.save_name ? ` • ${data.save_name}` : ''}`;
    renderWonderIdentity(data);
    $('#recordBadges').innerHTML = badge('Location', data.travel_status) + badge('Projector', data.projector_status) + badge('Image', data.image_status)
      + (hasForgeRepresentative && data.image_status !== 'available' ? '<span class="status-chip forge">Forge family representative</span>' : '');
    renderImages(data.images || [], data);
    $('#messageId').textContent = data.message_id || 'No Wonder Projector Message ID available';
    $('#copyMessage').hidden = !data.message_id;
    const planetIdentityData = data.discovery_type === 'Planet' ? [
      item('Planet family', data.planet_biome_family || data.wonder_family_label, false),
      item('Hologram size class', data.planet_size_class || 'Standard', false),
      item('Size evidence', String(data.planet_size_status || 'under_review').replaceAll('_', ' '), false),
      item('Name evidence', data.planet_name_label || 'Under review', false),
    ] : [];
    const identityData = data.wonder_family_label ? [
      item('Visual family', data.wonder_family_label, false),
      item('Individual identity', data.wonder_individual_name || data.wonder_individual_reference || 'Encoded', false),
      item('Identity evidence', data.wonder_projector_fingerprint_label, false),
      ...(hasForgeRepresentative ? [
        item('Forge image basis', `${data.forge_match_label || expedition?.selection_basis || 'Stable catalog identity'} · representative only`, false),
      ] : []),
      ...(data.descriptor_token_count ? [
        item('Appearance signals', `${data.descriptor_token_count} observed`, false),
        item('Visual profile', data.visual_profile_fingerprint || 'Under review', false),
      ] : []),
    ] : [];
    $('#dataList').innerHTML = [
      ...planetIdentityData,
      ...identityData,
      item('Owner', data.owner, false), item('Platform', data.platform, false),
      item('Approved verifications', data.verification_counts?.approved ?? 0, false), item('Pending verifications', data.verification_counts?.pending ?? 0, false),
    ].join('');
    $('#catalogNote').hidden = !data.catalog_note;
    $('#catalogNote').textContent = data.catalog_note || '';

    const verified = data.has_location;
    const travelReady = data.has_travel_address;
    const derived = data.travel_status === 'derived';
    $('#locationPanel').classList.toggle('verified', verified);
    $('#locationPanel').classList.toggle('derived', derived);
    $('#locationTitle').textContent = travelReady
      ? `Galaxy ${data.galaxy_number}${data.galaxy_name ? ` — ${data.galaxy_name}` : ''}`
      : data.location_status === 'pending'
        ? 'Location awaiting review'
        : 'Location not yet available';
    $('#locationCopy').textContent = verified
      ? 'Use this reviewed galaxy and 12-glyph portal address to travel to the system.'
      : derived
        ? 'This portal route was decoded automatically from saved discovery data. The decoding method is confirmed; this individual find still welcomes a community revisit.'
        : 'This record needs reviewed galaxy and portal evidence before travel directions can be displayed.';
    $('#locationFacts').hidden = !travelReady;
    if (travelReady) {
      const routeSource = verified ? 'Community verified' : derived ? 'Decoded automatically' : 'Catalog supplied';
      const routeState = verified ? 'Verified' : derived ? 'Awaiting community revisit' : 'Catalog evidence';
      $('#locationFacts').innerHTML = `<div><span>Galaxy number</span><strong>${data.galaxy_number}</strong></div><div><span>Galaxy name</span><strong>${escapeHtml(data.galaxy_name || 'Not supplied')}</strong></div><div><span>Route source</span><strong>${escapeHtml(routeSource)}</strong></div><div><span>Route status</span><strong>${escapeHtml(routeState)}</strong></div>`;
      WCGlyphs.render('#glyphRow', data.portal_glyphs);
      $('#glyphCode').textContent = data.portal_glyphs;
      $('#copyGlyphs').hidden = false;
    } else {
      WCGlyphs.render('#glyphRow', '');
      $('#glyphCode').textContent = '';
      $('#copyGlyphs').hidden = true;
    }
    $('#evidenceLink').href = `contribute.html?mode=image&record=${data.id}`;
    configurePegasusTransit(data).catch((error) => pegasusStatus(error.message, 'Pegasus access check failed'));
    $('#recordLayout').hidden = false;
    window.WonderAnalytics?.track('record_view', {
      entity_type: 'discovery',
      entity_id: data.wc_id,
      discovery_type: data.discovery_type,
      fauna_family: data.fauna_family_id || '',
      location_status: data.travel_status || data.location_status || '',
      image_status: data.image_status || '',
    });
  }

  async function load() {
    const id = new URLSearchParams(location.search).get('id');
    if (!id || !/^\d+$/.test(id)) {
      $('#recordError').textContent = 'This record link is missing a valid numeric discovery ID.';
      $('#recordError').hidden = false;
      return;
    }
    try {
      const response = await fetch(`/api/discoveries/${id}`);
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      render(data);
    } catch (error) {
      $('#recordError').textContent = error.message;
      $('#recordError').hidden = false;
    }
  }

  $('#copyMessage').addEventListener('click', async () => { if (record?.message_id) { await navigator.clipboard.writeText(record.message_id); toast('Wonder Projector Message ID copied.'); } });
  $('#copyGlyphs').addEventListener('click', async () => { if (record?.portal_glyphs) { await WCGlyphs.copy(record.portal_glyphs); toast('Portal glyph code copied.'); } });
  $('#pegasusTransit').addEventListener('click', requestPegasusTransit);
  window.addEventListener('wc-account-change', () => {
    if (record && !pegasusDispatch) configurePegasusTransit(record).catch(() => {});
  });
  Promise.all([
    Promise.resolve(window.WCExpedition?.load()).catch(() => null),
    Promise.resolve(window.WCAccount?.ready).catch(() => null),
  ])
    .finally(load);
})();
