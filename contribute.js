(() => {
  'use strict';

  const API = '/api';
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const imageSubmissionAccepted = (data) => Boolean(data?.ok && data?.queued && data?.image_id);
  const evidenceRequirements = ({hasRecord, newDiscovery = false, discoveryType = '', image, location, contributor, hasFile, permission, glyphs}) => {
    const missing = [];
    if (!newDiscovery && !hasRecord) missing.push('choose a catalog record from the search results');
    if (newDiscovery && !discoveryType) missing.push('choose the new discovery category');
    if (!image && !location) missing.push('choose Screenshot Find, Location verification, or both');
    if (!contributor) missing.push('enter your contributor name');
    if (image && !hasFile) missing.push('choose a screenshot file');
    if (image && !permission) missing.push('confirm permission to display the screenshot');
    if (location && glyphs && glyphs.length !== 12) missing.push('complete all 12 portal glyphs or clear them');
    return missing;
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = {evidenceRequirements, imageSubmissionAccepted};
  if (typeof document === 'undefined') return;
  const state = {record: null, submitting: false, completed: false, humanInteracted: false};

  function setMode(mode) {
    const aliases = {image: 'evidence', verify: 'evidence'};
    const requested = aliases[mode] || mode;
    const selected = ['save','evidence','research'].includes(requested) ? requested : 'save';
    $$('.contribution-tab').forEach((tab) => {
      const active = tab.dataset.mode === selected;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
    });
    $$('[data-section]').forEach((section) => section.hidden = section.dataset.section !== selected);
    const url = new URL(location.href);
    url.searchParams.set('mode', aliases[mode] ? mode : selected);
    history.replaceState({}, '', url);
  }

  function locationPanel(record) {
    record = WCLocation.enrich(record || {});
    if (record.has_travel_address) {
      const verified = record.has_location;
      const derived = record.travel_status === 'derived';
      const label = verified ? 'Verified location' : derived ? 'Automatically derived route' : 'Catalog route';
      const copy = verified
        ? 'Travel address reviewed and approved.'
        : derived
          ? 'Decoded automatically from saved discovery data. Please revisit and submit confirmation.'
          : 'Travel address is available but not yet verified.';
      return `<div class="location-panel ${verified ? 'verified' : derived ? 'derived' : ''}"><span class="status-chip ${escapeHtml(record.travel_status)}">${escapeHtml(label)}</span><h3>Galaxy ${record.galaxy_number}${record.galaxy_name ? ` — ${escapeHtml(record.galaxy_name)}` : ''}</h3><div class="portal-glyph-row compact">${WCGlyphs.codeHtml(record.portal_glyphs,{compact:true})}</div><p class="glyph-code">${escapeHtml(record.portal_glyphs)}</p><p>${escapeHtml(copy)}</p></div>`;
    }
    return `<div class="location-panel"><span class="status-chip ${escapeHtml(record.travel_status || 'unverified')}">Location ${escapeHtml(record.travel_status || 'unverified')}</span><h3>No travel address available yet</h3><p>You may submit a proposed galaxy and glyph code with your evidence.</p></div>`;
  }

  function selectedMarkup(record) {
    return `<p class="selection-confirmation">✓ Record selected for this submission</p><span class="wc-id">${escapeHtml(record.wc_id)}</span><h3>${escapeHtml(record.display_name)}</h3><p>${escapeHtml(record.discovery_type)} • Contributor ${escapeHtml(record.contributor || 'Unknown')}</p>${locationPanel(record)}`;
  }

  function optionMarkup(record, active) {
    return `<button class="record-option ${active ? 'active' : ''}" type="button" data-id="${record.id}"><strong>${escapeHtml(record.wc_id)} — ${escapeHtml(record.display_name)}</strong><small>${escapeHtml(record.discovery_type)} • ${escapeHtml(record.contributor || record.owner || 'Unknown')}</small></button>`;
  }

  function makeRecordSearch() {
    const input = $('#evidenceRecordSearch');
    const results = $('#evidenceRecordResults');
    let timer;
    async function search() {
      const q = input.value.trim();
      if (!q) { results.innerHTML = ''; return; }
      results.innerHTML = '<div class="notice">Searching catalog…</div>';
      try {
        const response = await fetch(`${API}/discoveries?q=${encodeURIComponent(q)}&limit=12`);
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
        results.innerHTML = data.items?.length
          ? data.items.map((record) => optionMarkup(record, state.record?.id === record.id)).join('')
          : '<div class="notice">No published records found.</div>';
        results.querySelectorAll('.record-option').forEach((button) => button.addEventListener('click', () => selectRecord(Number(button.dataset.id))));
      } catch (error) {
        results.innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
      }
    }
    input.addEventListener('input', () => {
      if (state.record && input.value !== input.dataset.selectedLabel) {
        state.record = null;
        state.completed = false;
        delete input.dataset.recordId;
        delete input.dataset.selectedLabel;
        $('#evidenceSelected').hidden = true;
      }
      updateSubmitState();
      clearTimeout(timer);
      timer = setTimeout(search, 280);
    });
  }

  async function fetchRecord(id) {
    const response = await fetch(`${API}/discoveries/${id}`);
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function selectRecord(id) {
    try {
      const record = WCLocation.enrich(await fetchRecord(id));
      state.record = record;
      state.completed = false;
      $('#evidenceSelected').innerHTML = selectedMarkup(record);
      $('#evidenceSelected').hidden = false;
      $('#evidenceRecordResults').innerHTML = '';
      const selectedLabel = `${record.wc_id} — ${record.display_name}`;
      $('#evidenceRecordSearch').value = selectedLabel;
      $('#evidenceRecordSearch').dataset.recordId = String(record.id);
      $('#evidenceRecordSearch').dataset.selectedLabel = selectedLabel;
      $('#verifyTravelPanel').innerHTML = locationPanel(record);
      if (record.has_travel_address) {
        $('#verifyGalaxyNumber').value = record.galaxy_number || '';
        $('#verifyGalaxyName').value = record.galaxy_name || '';
        $('#verifyGlyphs').value = record.portal_glyphs || '';
      } else {
        $('#verifyGalaxyNumber').value = '';
        $('#verifyGalaxyName').value = '';
        $('#verifyGlyphs').value = '';
      }
      $('#verifyGlyphs').dispatchEvent(new Event('input'));
      updateSubmitState();
    } catch (error) {
      const result = $('#evidenceResult');
      result.textContent = error.message;
      result.className = 'notice error';
      result.hidden = false;
    }
  }

  function selectedEvidence() {
    return {
      image: $('#includeImageEvidence').checked,
      location: $('#includeLocationEvidence').checked,
    };
  }

  function isNewDiscovery() {
    return $('#submissionNew').checked;
  }

  function setSubmissionKind(kind) {
    const isNew = kind === 'new';
    $('#submissionNew').checked = isNew;
    $('#submissionExisting').checked = !isNew;
    $('#newDiscoveryFields').hidden = !isNew;
    $('#existingRecordFields').hidden = isNew;
    $('#includeImageEvidence').checked = isNew || $('#includeImageEvidence').checked;
    $('#includeImageEvidence').disabled = isNew;
    if (isNew) $('#includeLocationEvidence').checked = false;
    toggleEvidencePanels();
  }

  function updateSubmitState() {
    const selected = selectedEvidence();
    const glyphs = WCGlyphs.normalize($('#verifyGlyphs').value);
    const missing = evidenceRequirements({
      hasRecord: Boolean(state.record),
      newDiscovery: isNewDiscovery(),
      discoveryType: $('#newDiscoveryType').value,
      image: selected.image,
      location: selected.location,
      contributor: $('#evidenceContributor').value.trim(),
      hasFile: Boolean($('#imageFile').files[0]),
      permission: $('#imagePermission').checked,
      glyphs,
    });
    const button = $('#submitEvidence');
    const readiness = $('#evidenceReadiness');
    button.disabled = state.submitting || state.completed;
    readiness.classList.toggle('ready', missing.length === 0);
    readiness.textContent = state.submitting
      ? 'Submitting to the private review queue…'
      : state.completed
        ? 'Evidence received. This submission is complete.'
        : missing.length
          ? `Before submitting: ${missing[0]}.`
          : 'Ready to submit for private review.';
  }

  function toggleEvidencePanels() {
    const selected = selectedEvidence();
    $('#imageEvidenceFields').hidden = !selected.image;
    $('#locationEvidenceFields').hidden = !selected.location;
    $('#imageEvidenceGuide').hidden = !selected.image;
    $('#locationEvidenceGuide').hidden = !selected.location;
    $('#evidenceGuideEmpty').hidden = selected.image || selected.location;
    updateSubmitState();
  }

  function setEvidenceIntent(image, locationEvidence) {
    $('#includeImageEvidence').checked = image;
    $('#includeLocationEvidence').checked = locationEvidence;
    toggleEvidencePanels();
  }

  function previewImage() {
    const file = $('#imageFile').files[0];
    const preview = $('#imagePreview');
    if (!file) { preview.innerHTML = '<span>No screenshot selected.</span>'; return; }
    if (!file.type.startsWith('image/')) { preview.innerHTML = '<span>Please choose a PNG, JPEG, or WebP image.</span>'; return; }
    const url = URL.createObjectURL(file);
    preview.innerHTML = `<img src="${url}" alt="Local screenshot preview">`;
    preview.querySelector('img').addEventListener('load', () => URL.revokeObjectURL(url), {once:true});
  }

  async function responseData(response) {
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function submitImage(contributor, publicAttribution) {
    const file = $('#imageFile').files[0];
    const form = new FormData();
    form.append('discovery_id', state.record.id);
    form.append('contributor', contributor);
    form.append('image_role', $('#imageRole').value);
    form.append('caption', $('#imageCaption').value.trim());
    form.append('permission_confirmed', 'true');
    form.append('public_attribution', String(publicAttribution));
    form.append('website', state.humanInteracted ? '' : $('#evidenceWebsite').value);
    form.append('image', file, file.name);
    const data = await responseData(await fetch(`${API}/images`, {method:'POST', body:form}));
    if (!imageSubmissionAccepted(data)) {
      throw new Error('The screenshot was not added to the review queue. Please refresh the page and try again.');
    }
    return data;
  }

  async function submitNewDiscovery(contributor, publicAttribution) {
    const file = $('#imageFile').files[0];
    const form = new FormData();
    form.append('contributor', contributor);
    form.append('discovery_type', $('#newDiscoveryType').value);
    form.append('display_name', $('#newDisplayName').value.trim());
    form.append('platform', $('#newPlatform').value);
    if ($('#verifyGalaxyNumber').value) form.append('galaxy_number', $('#verifyGalaxyNumber').value);
    form.append('galaxy_name', $('#verifyGalaxyName').value.trim());
    form.append('portal_glyphs', WCGlyphs.normalize($('#verifyGlyphs').value));
    form.append('notes', $('#imageCaption').value.trim());
    form.append('permission_confirmed', 'true');
    form.append('public_attribution', String(publicAttribution));
    form.append('website', state.humanInteracted ? '' : $('#evidenceWebsite').value);
    form.append('image', file, file.name);
    return responseData(await fetch(`${API}/new-discoveries`, {method:'POST', body:form}));
  }

  async function submitLocation(contributor, publicAttribution) {
    const payload = {
      discovery_id: state.record.id,
      contributor,
      galaxy_number: $('#verifyGalaxyNumber').value ? Number($('#verifyGalaxyNumber').value) : null,
      galaxy_name: $('#verifyGalaxyName').value.trim(),
      portal_glyphs: WCGlyphs.normalize($('#verifyGlyphs').value),
      reached_system: $('#verifyReached').checked,
      discovery_present: $('#verifyPresent').checked,
      projector_confirmed: $('#verifyProjector').checked,
      notes: $('#verifyNotes').value.trim(),
      public_attribution: publicAttribution,
      website: $('#evidenceWebsite').value,
    };
    return responseData(await fetch(`${API}/verifications`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)}));
  }

  async function submitEvidence(event) {
    event.preventDefault();
    const result = $('#evidenceResult');
    result.hidden = false;
    result.className = 'notice';
    const selected = selectedEvidence();
    const isNew = isNewDiscovery();
    if (!isNew && !state.record) { result.textContent = 'Select a Wonder record first.'; result.classList.add('error'); return; }
    if (!selected.image && !selected.location) { result.textContent = 'Choose image evidence, location verification, or both.'; result.classList.add('error'); return; }
    const contributor = $('#evidenceContributor').value.trim();
    if (!contributor) { result.textContent = 'Enter your contributor name.'; result.classList.add('error'); return; }
    if (selected.image && !$('#imageFile').files[0]) { result.textContent = 'Choose a screenshot file for the image evidence.'; result.classList.add('error'); return; }
    if (selected.image && !$('#imagePermission').checked) { result.textContent = 'Confirm that Wonder Codex may display the submitted image after approval.'; result.classList.add('error'); return; }
    const glyphs = WCGlyphs.normalize($('#verifyGlyphs').value);
    if (selected.location && glyphs && glyphs.length !== 12) { result.textContent = 'Enter all 12 portal glyph values or leave the glyph field blank.'; result.classList.add('error'); return; }

    const publicAttribution = !$('#evidencePrivateAttribution').checked;
    const evidenceType = selected.image && selected.location ? 'both' : selected.image ? 'image' : 'location';
    window.WonderAnalytics?.track('contribution_started', {
      entity_type:'discovery', entity_id:isNew ? 'new' : state.record.wc_id, evidence_type:isNew ? 'new_screenshot' : evidenceType,
      public_attribution:publicAttribution,
    });
    const button = $('#submitEvidence');
    state.submitting = true;
    updateSubmitState();
    button.textContent = selected.image && selected.location ? 'Submitting image and location…' : 'Submitting evidence…';
    result.textContent = 'Sending your evidence to the private review queues…';

    const outcomes = [];
    if (isNew) {
      try {
        const data = await submitNewDiscovery(contributor, publicAttribution);
        if (!data?.ok || !data?.queued || !data?.intake_id) throw new Error('The new discovery was not added to the review queue.');
        outcomes.push({kind:'New discovery screenshot', ok:true, reference:data.reference});
      } catch (error) { outcomes.push({kind:'New discovery screenshot', ok:false, error:error.message}); }
    } else if (selected.image) {
      try {
        const data = await submitImage(contributor, publicAttribution);
        outcomes.push({kind:'Image', ok:true, reference:data.image_id});
        $('#includeImageEvidence').checked = false;
        $('#includeImageEvidence').disabled = true;
      } catch (error) { outcomes.push({kind:'Image', ok:false, error:error.message}); }
    }
    if (!isNew && selected.location) {
      try {
        const data = await submitLocation(contributor, publicAttribution);
        outcomes.push({kind:'Location verification', ok:true, reference:data.verification_id});
        $('#includeLocationEvidence').checked = false;
        $('#includeLocationEvidence').disabled = true;
      } catch (error) { outcomes.push({kind:'Location verification', ok:false, error:error.message}); }
    }

    state.submitting = false;
    toggleEvidencePanels();
    const successes = outcomes.filter((item) => item.ok);
    const failures = outcomes.filter((item) => !item.ok);
    state.completed = successes.length > 0 && failures.length === 0;
    const lines = outcomes.map((item) => item.ok
      ? `<li><strong>${escapeHtml(item.kind)} received</strong> — reference <code>${escapeHtml(item.reference)}</code></li>`
      : `<li><strong>${escapeHtml(item.kind)} failed</strong> — ${escapeHtml(item.error)}</li>`).join('');
    result.className = `notice ${failures.length ? (successes.length ? '' : 'error') : 'success'}`.trim();
    result.innerHTML = `<strong>${failures.length ? (successes.length ? 'Part of your evidence was received.' : 'Evidence submission failed.') : 'Evidence received!'}</strong><ul>${lines}</ul>${publicAttribution ? 'Public attribution selected.' : 'Your public attribution will be Anonymous Contributor.'}${successes.length && failures.length ? '<br>The completed item is locked to prevent a duplicate; retry only the remaining evidence.' : ''}`;
    button.textContent = failures.length ? 'Retry remaining evidence' : 'Submitted ✓';
    updateSubmitState();
    if (successes.length) window.WonderAnalytics?.track('contribution_completed', {
      entity_type:'discovery', entity_id:isNew ? 'new' : state.record.wc_id, evidence_type:isNew ? 'new_screenshot' : evidenceType,
      public_attribution:publicAttribution,
    });
  }

  $$('.contribution-tab').forEach((tab) => tab.addEventListener('click', () => setMode(tab.dataset.mode)));
  makeRecordSearch();
  $('#includeImageEvidence').addEventListener('change', toggleEvidencePanels);
  $('#includeLocationEvidence').addEventListener('change', toggleEvidencePanels);
  $$('input[name="submissionKind"]').forEach((input) => input.addEventListener('change', () => setSubmissionKind(input.value)));
  $('#evidenceContributor').addEventListener('input', updateSubmitState);
  $('#imageFile').addEventListener('change', () => { previewImage(); updateSubmitState(); });
  $('#imagePermission').addEventListener('change', updateSubmitState);
  $('#evidenceForm').addEventListener('pointerdown', (event) => {
    if (event.isTrusted) state.humanInteracted = true;
  }, {capture:true});
  $('#evidenceForm').addEventListener('keydown', (event) => {
    if (event.isTrusted) state.humanInteracted = true;
  }, {capture:true});
  $('#evidenceForm').addEventListener('submit', submitEvidence);
  WCGlyphs.bindKeypad('#verifyGlyphs','#verifyGlyphKeypad','#verifyGlyphPreview','#verifyGlyphStatus');
  $('#verifyGlyphLegend').innerHTML = WCGlyphs.values.map((glyph) => WCGlyphs.glyphHtml(glyph)).join('');

  const params = new URLSearchParams(location.search);
  const requestedMode = params.get('mode') || 'save';
  const requestedEvidence = params.get('evidence') || '';
  setMode(requestedMode);
  setEvidenceIntent(
    requestedMode === 'image' || requestedEvidence === 'image' || requestedEvidence === 'both',
    requestedMode === 'verify' || requestedEvidence === 'location' || requestedEvidence === 'both',
  );
  if (['image','verify'].includes(requestedMode) || requestedEvidence) {
    requestAnimationFrame(() => document.querySelector('.contribution-tabs')?.scrollIntoView({block:'start'}));
  }
  const recordId = params.get('record');
  setSubmissionKind(
    (recordId && /^\d+$/.test(recordId)) || requestedMode === 'verify' ? 'existing' : 'new'
  );
  if (recordId && /^\d+$/.test(recordId) && ['evidence','image','verify'].includes(requestedMode)) selectRecord(Number(recordId));
  window.WCAccount?.ready.then(({profile}) => {
    if (!profile) return;
    $('#evidenceContributor').value = profile.contributor_name;
    $('#evidencePrivateAttribution').checked = !profile.public_attribution;
    if (profile.platform) $('#newPlatform').value = profile.platform;
    $('#evidenceContributor').dataset.accountFilled = 'true';
    updateSubmitState();
  }).catch(() => {});
  updateSubmitState();
})();
