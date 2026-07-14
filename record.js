(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
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
    $('#recordImageCaption').textContent = `${archetype.label} • Representative archetype — specimen image pending${note ? ` • ${note}` : ''}`;
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
    $('#recordBadges').innerHTML = badge('Location', data.travel_status) + badge('Projector', data.projector_status) + badge('Image', data.image_status);
    renderImages(data.images || [], data);
    $('#messageId').textContent = data.message_id || 'No Message ID available';
    $('#copyMessage').hidden = !data.message_id;
    $('#dataList').innerHTML = [
      item('Universal Address', data.ua), item('VP0', data.vp0), item('VP1', data.vp1), item('VP2', data.vp2), item('VP3', data.vp3), item('VP4', data.vp4),
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
        ? 'This portal route was decoded automatically from the discovery Universal Address. The decoding method is confirmed; this individual find still welcomes a community revisit.'
        : 'This record needs a valid Universal Address or reviewed galaxy and portal evidence before travel directions can be displayed.';
    $('#locationFacts').hidden = !travelReady;
    if (travelReady) {
      const routeSource = verified ? 'Community verified' : derived ? 'Decoded from UA' : 'Catalog supplied';
      $('#locationFacts').innerHTML = `<div><span>Galaxy number</span><strong>${data.galaxy_number}</strong></div><div><span>Galaxy name</span><strong>${escapeHtml(data.galaxy_name || 'Not supplied')}</strong></div><div><span>Route source</span><strong>${escapeHtml(routeSource)}</strong></div><div><span>RealityIndex</span><strong>${data.reality_index ?? '—'}</strong></div>`;
      WCGlyphs.render('#glyphRow', data.portal_glyphs);
      $('#glyphCode').textContent = data.portal_glyphs;
      $('#copyGlyphs').hidden = false;
    } else {
      WCGlyphs.render('#glyphRow', '');
      $('#glyphCode').textContent = '';
      $('#copyGlyphs').hidden = true;
    }
    $('#imageLink').href = `contribute.html?mode=image&record=${data.id}`;
    $('#verifyLink').href = `contribute.html?mode=verify&record=${data.id}`;
    $('#recordLayout').hidden = false;
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

  $('#copyMessage').addEventListener('click', async () => { if (record?.message_id) { await navigator.clipboard.writeText(record.message_id); toast('Message ID copied.'); } });
  $('#copyGlyphs').addEventListener('click', async () => { if (record?.portal_glyphs) { await WCGlyphs.copy(record.portal_glyphs); toast('Portal glyph code copied.'); } });
  load();
})();
