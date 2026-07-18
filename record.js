(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  let record = null;

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

  function configurePegasusTransit(data) {
    const button = $('#pegasusTransit');
    const authorized = Boolean(sessionStorage.getItem('wc_admin_key') && sessionStorage.getItem('wc_admin_actor'));
    const ready = Boolean(data.has_travel_address && data.galaxy_number && data.portal_glyphs);
    button.disabled = !(authorized && ready);
    button.textContent = authorized
      ? ready ? 'PEGASUS TRANSIT — Download admin route' : 'PEGASUS TRANSIT — Route unavailable'
      : 'PEGASUS TRANSIT — Authorized operators only';
  }

  function downloadPegasusTicket() {
    if (!record?.has_travel_address) return;
    const ticket = {
      format: 'wonder-codex-transit/0.1',
      wc_record_id: record.wc_id,
      galaxy_number: record.galaxy_number,
      galaxy_name: record.galaxy_name || '',
      portal_glyphs: record.portal_glyphs,
      universal_address: record.ua_normalized ? `0x${record.ua_normalized}` : record.ua || '',
      generated_utc: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(ticket, null, 2)], {type:'application/vnd.wonder-codex.transit+json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${record.wc_id}.wctransit`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    window.WonderAnalytics?.track('transit_ticket_download', {entity_type:'discovery', entity_id:record.wc_id, download_type:'wctransit'});
    toast('Pegasus Transit route downloaded.');
  }

  function renderFaunaIdentity(data) {
    const element = $('#recordIdentity');
    if (!data.fauna_family_label) {
      element.hidden = true;
      element.innerHTML = '';
      return;
    }
    const exact = data.fauna_identity_source === 'exact_pet_match';
    const evidenceCount = Number(data.fauna_family_evidence_count || 0);
    const evidence = exact
      ? 'Exact companion match'
      : `Confirmed family mapping${evidenceCount ? ` · supported by ${number(evidenceCount)} exact match${evidenceCount === 1 ? '' : 'es'}` : ''}`;
    element.classList.toggle('exact', exact);
    element.classList.toggle('inferred', !exact);
    element.innerHTML = `<p class="kicker">FAUNA IDENTITY</p>
      <div class="fauna-identity-heading"><strong>${escapeHtml(data.fauna_family_label)} family</strong><span class="fauna-behavior">${exact && data.fauna_behavior ? `Behavior: ${escapeHtml(data.fauna_behavior)}` : 'Behavior not inferred'}</span></div>
      <p>${escapeHtml(evidence)} · Technical family ID <code>${escapeHtml(data.fauna_family_id)}</code></p>`;
    element.hidden = false;
  }


  function showArchetype(data, note = '') {
    const archetype = WCArchetypes.resolve(data);
    const gallery = $('#recordGallery');
    const frame = gallery.querySelector('.record-primary-image');
    const primary = $('#recordPrimaryImage');
    frame.classList.add('is-archetype');
    primary.onerror = () => {
      primary.onerror = null;
      primary.removeAttribute('src');
      $('#recordImageCaption').textContent = 'The representative archetype could not be loaded. Please report this record ID to an administrator.';
    };
    primary.src = archetype.url;
    primary.alt = archetype.alt;
    $('#recordImageCaption').textContent = `${archetype.label} • Representative archetype — not this exact specimen${note ? ` • ${note}` : ''}`;
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
      gallery.querySelector('.record-primary-image').classList.remove('is-archetype');
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
    document.title = `${data.wc_id} — ${data.display_name} | Wonder Codex`;
    $('#recordHero').innerHTML = `${escapeHtml(data.wc_id)} <span>published record.</span>`;
    $('#recordIntro').textContent = 'Projector data, attribution, verification status, and travel information for this Wonder Codex discovery.';
    $('#wcId').textContent = data.wc_id;
    $('#recordName').textContent = data.display_name;
    $('#recordType').textContent = data.discovery_type === 'Animal' ? 'Fauna' : data.discovery_type;
    $('#recordAttribution').textContent = `Contributed by ${data.contributor || data.owner || 'Unknown explorer'}${data.save_name ? ` • ${data.save_name}` : ''}`;
    renderFaunaIdentity(data);
    $('#recordBadges').innerHTML = badge('Location', data.travel_status) + badge('Projector', data.projector_status) + badge('Image', data.image_status);
    renderImages(data.images || [], data);
    $('#messageId').textContent = data.message_id || 'No Wonder Projector Message ID available';
    $('#copyMessage').hidden = !data.message_id;
    const identityData = data.fauna_family_label ? [
      item('Fauna family', data.fauna_family_label, false),
      item('Behavior', data.fauna_identity_source === 'exact_pet_match' ? data.fauna_behavior || 'Not recorded' : 'Not inferred', false),
      item('Identity evidence', data.fauna_identity_label, false),
    ] : [];
    $('#dataList').innerHTML = [
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
    $('#evidenceLink').href = `contribute.html?mode=evidence&record=${data.id}`;
    configurePegasusTransit(data);
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
  $('#pegasusTransit').addEventListener('click', downloadPegasusTicket);
  load();
})();
