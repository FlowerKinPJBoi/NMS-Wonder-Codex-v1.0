(() => {
  'use strict';

  const API = '/api';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const state = {imageRecord: null, verifyRecord: null};

  function setMode(mode) {
    const valid = ['save','image','verify','research'];
    const selected = valid.includes(mode) ? mode : 'save';
    $$('.contribution-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.mode === selected));
    $$('[data-section]').forEach((section) => section.hidden = section.dataset.section !== selected);
    const url = new URL(location.href);
    url.searchParams.set('mode', selected);
    history.replaceState({}, '', url);
  }

  function locationPanel(record) {
    if (record?.has_location) {
      return `<div class="location-panel verified"><span class="status-chip verified">Verified location</span><h3>Galaxy ${record.galaxy_number}${record.galaxy_name ? ` — ${escapeHtml(record.galaxy_name)}` : ''}</h3><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(record.portal_glyphs,{compact:true})}</div><p class="glyph-code">${escapeHtml(record.portal_glyphs)}</p></div>`;
    }
    return `<div class="location-panel"><span class="status-chip ${escapeHtml(record?.location_status || 'unverified')}">Location ${escapeHtml(record?.location_status || 'unverified')}</span><h3>No reviewed travel address yet</h3><p>You may submit a proposed galaxy and glyph code with your evidence.</p></div>`;
  }

  function selectedMarkup(record) {
    return `<span class="wc-id">${escapeHtml(record.wc_id)}</span><h3>${escapeHtml(record.display_name)}</h3><p>${escapeHtml(record.discovery_type)} • Contributor ${escapeHtml(record.contributor || 'Unknown')}</p>${locationPanel(record)}`;
  }

  function optionMarkup(record, active) {
    return `<button class="record-option ${active ? 'active' : ''}" type="button" data-id="${record.id}"><strong>${escapeHtml(record.wc_id)} — ${escapeHtml(record.display_name)}</strong><small>${escapeHtml(record.discovery_type)} • ${escapeHtml(record.contributor || record.owner || 'Unknown')}</small></button>`;
  }

  function makeRecordSearch(inputSelector, resultsSelector, mode) {
    const input = $(inputSelector);
    const results = $(resultsSelector);
    let timer;
    async function search() {
      const q = input.value.trim();
      if (!q) { results.innerHTML = ''; return; }
      results.innerHTML = '<div class="notice">Searching catalog…</div>';
      try {
        const response = await fetch(`${API}/discoveries?q=${encodeURIComponent(q)}&limit=12`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        const current = mode === 'image' ? state.imageRecord : state.verifyRecord;
        results.innerHTML = data.items?.length ? data.items.map((record) => optionMarkup(record, current?.id === record.id)).join('') : '<div class="notice">No published records found.</div>';
        results.querySelectorAll('.record-option').forEach((button) => button.addEventListener('click', () => selectRecord(mode, Number(button.dataset.id))));
      } catch (error) {
        results.innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
      }
    }
    input.addEventListener('input', () => { clearTimeout(timer); timer = setTimeout(search, 280); });
    return search;
  }

  async function fetchRecord(id) {
    const response = await fetch(`${API}/discoveries/${id}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function selectRecord(mode, id) {
    try {
      const record = await fetchRecord(id);
      if (mode === 'image') {
        state.imageRecord = record;
        $('#imageSelected').innerHTML = selectedMarkup(record);
        $('#imageSelected').hidden = false;
        $('#imageRecordResults').innerHTML = '';
        $('#imageRecordSearch').value = `${record.wc_id} — ${record.display_name}`;
        $('#submitImage').disabled = false;
      } else {
        state.verifyRecord = record;
        $('#verifySelected').innerHTML = selectedMarkup(record);
        $('#verifySelected').hidden = false;
        $('#verifyRecordResults').innerHTML = '';
        $('#verifyRecordSearch').value = `${record.wc_id} — ${record.display_name}`;
        $('#verifyTravelPanel').innerHTML = locationPanel(record);
        if (record.has_location) {
          $('#verifyGalaxyNumber').value = record.galaxy_number || '';
          $('#verifyGalaxyName').value = record.galaxy_name || '';
          $('#verifyGlyphs').value = record.portal_glyphs || '';
          $('#verifyGlyphs').dispatchEvent(new Event('input'));
        }
        $('#submitVerification').disabled = false;
      }
    } catch (error) {
      const result = mode === 'image' ? $('#imageSelected') : $('#verificationResult');
      result.textContent = error.message;
      result.className = 'notice error';
      result.hidden = false;
    }
  }

  function previewImage() {
    const file = $('#imageFile').files[0];
    const preview = $('#imagePreview');
    if (!file) { preview.innerHTML = '<span>No screenshot selected.</span>'; return; }
    if (!file.type.startsWith('image/')) { preview.innerHTML = '<span>Please choose a PNG, JPEG, or WebP image.</span>'; return; }
    const url = URL.createObjectURL(file);
    preview.innerHTML = `<img src="${url}" alt="Local screenshot preview">`;
    const image = preview.querySelector('img');
    image.addEventListener('load', () => URL.revokeObjectURL(url), {once:true});
  }


  async function submitImage(event) {
    event.preventDefault();
    const result = $('#imageResult');
    result.hidden = false;
    result.className = 'notice';
    if (!state.imageRecord) { result.textContent = 'Select a Wonder record first.'; result.classList.add('error'); return; }
    const contributor = $('#imageContributor').value.trim();
    const file = $('#imageFile').files[0];
    if (!contributor) { result.textContent = 'Enter your contributor name.'; result.classList.add('error'); return; }
    if (!file) { result.textContent = 'Choose a screenshot file.'; result.classList.add('error'); return; }
    if (!$('#imagePermission').checked) { result.textContent = 'Confirm that Wonder Codex may display the image with attribution.'; result.classList.add('error'); return; }

    const form = new FormData();
    form.append('discovery_id', state.imageRecord.id);
    form.append('contributor', contributor);
    form.append('image_role', $('#imageRole').value);
    form.append('caption', $('#imageCaption').value.trim());
    form.append('permission_confirmed', 'true');
    form.append('public_attribution', String(!$('#imagePrivateAttribution').checked));
    form.append('website', $('#imageWebsite').value);
    form.append('image', file, file.name);

    const button = $('#submitImage');
    button.disabled = true;
    button.textContent = 'Uploading privately…';
    result.textContent = 'Preparing the screenshot and placing it in the Admin Images queue…';
    try {
      const response = await fetch(`${API}/images`, {method:'POST', body:form});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      result.className = 'notice success';
      result.innerHTML = `<strong>Image received!</strong><br>${escapeHtml(data.wc_id)} is now in the Admin Images queue.<br>${data.public_attribution ? 'Public attribution selected.' : 'Your public attribution will be Anonymous Contributor.'}<br>Reference: <code>${escapeHtml(data.image_id)}</code>`;
      button.textContent = 'Submitted ✓';
    } catch (error) {
      result.className = 'notice error';
      result.textContent = `Image submission failed: ${error.message}`;
      button.disabled = false;
      button.textContent = 'Submit image for review';
    }
  }

  async function submitVerification(event) {
    event.preventDefault();
    const result = $('#verificationResult');
    result.hidden = false;
    result.className = 'notice';
    if (!state.verifyRecord) { result.textContent = 'Select a Wonder record first.'; result.classList.add('error'); return; }
    const contributor = $('#verifyContributor').value.trim();
    if (!contributor) { result.textContent = 'Enter your contributor name.'; result.classList.add('error'); return; }
    const glyphs = WCGlyphs.normalize($('#verifyGlyphs').value);
    if (glyphs && glyphs.length !== 12) { result.textContent = 'Enter all 12 portal glyph values or leave the glyph field blank.'; result.classList.add('error'); return; }

    const payload = {
      discovery_id: state.verifyRecord.id,
      contributor,
      galaxy_number: $('#verifyGalaxyNumber').value ? Number($('#verifyGalaxyNumber').value) : null,
      galaxy_name: $('#verifyGalaxyName').value.trim(),
      portal_glyphs: glyphs,
      reached_system: $('#verifyReached').checked,
      discovery_present: $('#verifyPresent').checked,
      projector_confirmed: $('#verifyProjector').checked,
      notes: $('#verifyNotes').value.trim(),
      public_attribution: !$('#verifyPrivateAttribution').checked,
      website: $('#verificationWebsite').value,
    };

    const button = $('#submitVerification');
    button.disabled = true;
    button.textContent = 'Submitting verification…';
    result.textContent = 'Sending normalized verification evidence to the review queue…';
    try {
      const response = await fetch(`${API}/verifications`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
      result.className = 'notice success';
      result.innerHTML = `<strong>Verification received!</strong><br>${escapeHtml(data.wc_id)} is now in the Admin Verifications queue.<br>${data.public_attribution ? 'Public attribution selected.' : 'Your public attribution will be Anonymous Contributor.'}<br>Reference: <code>${escapeHtml(data.verification_id)}</code>`;
      button.textContent = 'Submitted ✓';
    } catch (error) {
      result.className = 'notice error';
      result.textContent = `Submission failed: ${error.message}`;
      button.disabled = false;
      button.textContent = 'Submit verification for review';
    }
  }

  $$('.contribution-tab').forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.mode)));
  makeRecordSearch('#imageRecordSearch','#imageRecordResults','image');
  makeRecordSearch('#verifyRecordSearch','#verifyRecordResults','verify');
  $('#imageFile').addEventListener('change', previewImage);
  $('#imageForm').addEventListener('submit', submitImage);
  $('#verificationForm').addEventListener('submit', submitVerification);
  WCGlyphs.bindKeypad('#verifyGlyphs','#verifyGlyphKeypad','#verifyGlyphPreview','#verifyGlyphStatus');
  $('#verifyGlyphLegend').innerHTML = WCGlyphs.values.map((glyph) => WCGlyphs.glyphHtml(glyph)).join('');

  const params = new URLSearchParams(location.search);
  setMode(params.get('mode') || 'save');
  const recordId = params.get('record');
  const mode = params.get('mode');
  if (recordId && /^\d+$/.test(recordId) && (mode === 'image' || mode === 'verify')) selectRecord(mode, Number(recordId));
})();
