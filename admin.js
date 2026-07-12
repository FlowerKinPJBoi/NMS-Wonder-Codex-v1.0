(() => {
  'use strict';

  const API = '/api';
  const state = {
    key: '', actor: 'PJ', mode: 'submissions',
    submissionStatus: 'pending', submissions: [], selectedSubmission: null, submissionDetail: null, recordSection: 'discoveries',
    verificationStatus: 'pending', verifications: [], selectedVerification: null, verificationDetail: null,
    catalogRecords: [], selectedCatalog: null,
    imageStatus: 'pending', images: [], selectedImage: null, imageDetail: null,
  };
  const $ = (selector) => document.querySelector(selector);
  const $$ = (selector) => [...document.querySelectorAll(selector)];
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  const dateTime = (value) => { if (!value) return '—'; const d = new Date(value); return Number.isNaN(d.valueOf()) ? '—' : d.toLocaleString(); };
  const shortDate = (value) => { if (!value) return '—'; const d = new Date(value); return Number.isNaN(d.valueOf()) ? '—' : d.toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'}); };
  const headers = () => ({'X-Admin-Key': state.key, 'Accept':'application/json'});

  function toast(message, error = false) {
    const element = $('#toast');
    element.textContent = message;
    element.className = `toast${error ? ' error' : ''}`;
    element.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.hidden = true, 4500);
  }

  async function api(path, options = {}) {
    const response = await fetch(API + path, {...options, headers:{...headers(), ...(options.headers || {})}});
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function lock() {
    sessionStorage.removeItem('wc_admin_key');
    sessionStorage.removeItem('wc_admin_actor');
    state.key = '';
    $('#dashboard').hidden = true;
    $('#loginPanel').hidden = false;
    $('#lockButton').hidden = true;
    $('#connectionBadge').textContent = 'Locked';
    $('#connectionBadge').className = 'connection-badge';
    $('#adminKeyInput').value = '';
  }

  async function unlock(event) {
    event?.preventDefault();
    state.key = $('#adminKeyInput').value.trim();
    state.actor = $('#actorInput').value.trim() || 'PJ';
    $('#loginError').hidden = true;
    try {
      await api('/admin/summary');
      sessionStorage.setItem('wc_admin_key', state.key);
      sessionStorage.setItem('wc_admin_actor', state.actor);
      $('#loginPanel').hidden = true;
      $('#dashboard').hidden = false;
      $('#lockButton').hidden = false;
      $('#connectionBadge').textContent = 'Admin connected';
      $('#connectionBadge').className = 'connection-badge online';
      await refreshAll();
    } catch (error) {
      state.key = '';
      $('#loginError').textContent = error.message;
      $('#loginError').hidden = false;
    }
  }

  async function loadSummary() {
    const data = await api('/admin/summary');
    const map = {
      sumPending: data.pending_batches,
      sumPendingRecords: data.pending_discoveries,
      sumVerifications: data.pending_verifications,
      sumPublished: data.published_discoveries,
      sumLocations: data.verified_locations,
      sumImages: data.images_needed,
      sumApproved: data.approved_batches,
      sumRejected: data.rejected_batches,
      verificationTabCount: data.pending_verifications,
      imageTabCount: data.pending_images,
    };
    Object.entries(map).forEach(([id, value]) => { const element = document.getElementById(id); if (element) element.textContent = number(value); });
  }

  async function refreshAll() {
    const jobs = [loadSummary(), loadAudit()];
    if (state.mode === 'submissions') jobs.push(loadSubmissions());
    if (state.mode === 'verifications') jobs.push(loadVerifications());
    if (state.mode === 'catalog') jobs.push(loadCatalog());
    if (state.mode === 'images') jobs.push(loadImages());
    await Promise.all(jobs);
    $('#lastRefresh').textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  function setMode(mode) {
    state.mode = mode;
    $$('.admin-mode').forEach((button) => button.classList.toggle('active', button.dataset.mode === mode));
    $$('.admin-mode-panel').forEach((panel) => panel.hidden = panel.dataset.panel !== mode);
    if (mode === 'submissions') loadSubmissions();
    if (mode === 'verifications') loadVerifications();
    if (mode === 'catalog') loadCatalog();
    if (mode === 'images') loadImages();
  }

  // ---------- Data submission review ----------
  async function loadSubmissions() {
    const data = await api(`/admin/submissions?status=${encodeURIComponent(state.submissionStatus)}&limit=200`);
    state.submissions = data.items || [];
    renderSubmissionQueue();
  }

  function renderSubmissionQueue() {
    const query = $('#queueSearch').value.trim().toLowerCase();
    const rows = state.submissions.filter((item) => `${item.contributor} ${item.save_name} ${item.id}`.toLowerCase().includes(query));
    $('#queueEmpty').hidden = rows.length > 0;
    $('#queueList').innerHTML = rows.map((item) => `<button class="queue-item ${state.selectedSubmission === item.id ? 'active' : ''}" data-id="${escapeHtml(item.id)}" type="button"><div class="queue-item-top"><strong>${escapeHtml(item.save_name)}</strong><time>${escapeHtml(shortDate(item.created_at))}</time></div><div class="queue-item-sub">${escapeHtml(item.contributor)}${item.public_attribution ? '' : ' • Private attribution'}${item.platform ? ` • ${escapeHtml(item.platform)}` : ''}</div><div class="queue-counts"><span>${number(item.discovery_count)} discoveries</span><span>${number(item.pet_match_count)} matches</span><span>${number(item.issue_count)} issues</span></div></button>`).join('');
    $$('#queueList .queue-item').forEach((button) => button.addEventListener('click', () => selectSubmission(button.dataset.id)));
  }

  async function selectSubmission(id) {
    state.selectedSubmission = id;
    renderSubmissionQueue();
    $('#reviewPlaceholder').hidden = true;
    $('#reviewContent').hidden = false;
    $('#recordTableWrap').innerHTML = '<div class="review-placeholder"><p>Loading submission…</p></div>';
    try {
      state.submissionDetail = await api(`/admin/submissions/${encodeURIComponent(id)}`);
      renderSubmissionDetail();
    } catch (error) {
      toast(error.message, true);
      clearSubmissionDetail();
    }
  }

  function clearSubmissionDetail() {
    state.selectedSubmission = null;
    state.submissionDetail = null;
    $('#reviewContent').hidden = true;
    $('#reviewPlaceholder').hidden = false;
    renderSubmissionQueue();
  }

  function renderSubmissionDetail() {
    const {batch, counts = {}} = state.submissionDetail;
    $('#detailStatus').textContent = batch.status;
    $('#detailStatus').className = `detail-status ${batch.status}`;
    $('#detailSave').textContent = batch.save_name;
    $('#detailContributor').textContent = `Contributor: ${batch.contributor}${batch.public_attribution ? '' : ' • Private on public site'}${batch.platform ? ` • ${batch.platform}` : ''}`;
    $('#detailDiscoveries').textContent = number(counts.discoveries ?? state.submissionDetail.discoveries?.length);
    $('#detailMatches').textContent = number(counts.pet_matches ?? state.submissionDetail.pet_matches?.length);
    $('#detailIssues').textContent = number(counts.issues ?? state.submissionDetail.issues?.length);
    $('#detailCreated').textContent = shortDate(batch.created_at);
    $('#existingNote').hidden = !batch.reviewer_note;
    $('#existingNote').textContent = batch.reviewer_note ? `Reviewer note: ${batch.reviewer_note}` : '';
    $('#reviewActions').hidden = batch.status !== 'pending';
    $('#actionResult').hidden = true;
    $('#reviewNote').value = '';
    renderSubmissionRecords();
  }

  function currentSubmissionRows() {
    if (!state.submissionDetail || state.recordSection === 'raw') return [];
    return state.submissionDetail[state.recordSection] || [];
  }

  function renderSubmissionRecords() {
    const raw = state.recordSection === 'raw';
    $('#rawPreview').hidden = !raw;
    $('#recordTableWrap').hidden = raw;
    $$('.record-tab').forEach((tab) => tab.classList.toggle('active', tab.dataset.section === state.recordSection));
    if (raw) {
      $('#rawPreview').textContent = JSON.stringify(state.submissionDetail, null, 2);
      $('#previewNote').textContent = 'Complete batch metadata and available preview records.';
      return;
    }
    const query = $('#recordSearch').value.trim().toLowerCase();
    const all = currentSubmissionRows();
    const filtered = all.filter((row) => JSON.stringify(row).toLowerCase().includes(query));
    const shown = filtered.slice(0, 250);
    const columns = [...new Set(shown.flatMap((row) => Object.keys(row)))].slice(0, 14);
    if (!shown.length) {
      $('#recordTableWrap').innerHTML = '<div class="review-placeholder"><p>No preview records match this filter.</p></div>';
      $('#previewNote').textContent = `0 of ${number(all.length)} preview records shown.`;
      return;
    }
    $('#recordTableWrap').innerHTML = `<table class="record-table"><thead><tr>${columns.map((key) => `<th>${escapeHtml(key)}</th>`).join('')}</tr></thead><tbody>${shown.map((row) => `<tr>${columns.map((key) => `<td>${escapeHtml(typeof row[key] === 'object' ? JSON.stringify(row[key]) : row[key])}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    const trunc = state.submissionDetail.truncated_to_500_per_section ? ' The API preview is capped at 500 per section; approval processes the full stored batch.' : '';
    $('#previewNote').textContent = `Showing ${number(shown.length)} of ${number(filtered.length)} filtered preview records.${trunc}`;
  }

  async function reviewSubmission(decision) {
    if (!state.submissionDetail || state.submissionDetail.batch.status !== 'pending') return;
    const note = $('#reviewNote').value.trim();
    const verb = decision === 'approve' ? 'approve and publish' : 'reject';
    if (!confirm(`Are you sure you want to ${verb} “${state.submissionDetail.batch.save_name}”?`)) return;
    const button = decision === 'approve' ? $('#approveButton') : $('#rejectButton');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = decision === 'approve' ? 'Publishing…' : 'Rejecting…';
    try {
      const result = await api(`/admin/submissions/${encodeURIComponent(state.selectedSubmission)}/${decision}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({actor:state.actor, note})});
      $('#actionResult').hidden = false;
      $('#actionResult').className = 'inline-alert success';
      $('#actionResult').textContent = decision === 'approve' ? `Published ${number(result.discoveries_added)} discoveries and ${number(result.pet_matches_added)} pet matches.` : 'Submission rejected and retained in the audit history.';
      toast(decision === 'approve' ? 'Submission approved and published.' : 'Submission rejected.');
      clearSubmissionDetail();
      await Promise.all([loadSummary(), loadSubmissions(), loadAudit()]);
    } catch (error) {
      toast(error.message, true);
      $('#actionResult').hidden = false;
      $('#actionResult').className = 'inline-alert error';
      $('#actionResult').textContent = error.message;
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function exportSubmission() {
    if (!state.submissionDetail) return;
    const blob = new Blob([JSON.stringify(state.submissionDetail, null, 2)], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `${state.submissionDetail.batch.save_name.replace(/[^a-z0-9_-]+/gi,'_')}_${state.submissionDetail.batch.id}.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  // ---------- Location verification review ----------
  async function loadVerifications() {
    const data = await api(`/admin/verifications?status=${encodeURIComponent(state.verificationStatus)}&limit=200`);
    state.verifications = data.items || [];
    renderVerificationQueue();
  }

  function renderVerificationQueue() {
    const query = $('#verificationSearch').value.trim().toLowerCase();
    const rows = state.verifications.filter((item) => `${item.contributor} ${item.wc_id} ${item.display_name} ${item.id}`.toLowerCase().includes(query));
    $('#verificationEmpty').hidden = rows.length > 0;
    $('#verificationList').innerHTML = rows.map((item) => `<button class="queue-item ${state.selectedVerification === item.id ? 'active' : ''}" data-id="${escapeHtml(item.id)}" type="button"><div class="queue-item-top"><strong>${escapeHtml(item.wc_id)}</strong><time>${escapeHtml(shortDate(item.created_at))}</time></div><div class="queue-item-sub">${escapeHtml(item.display_name || 'Unnamed record')} • ${escapeHtml(item.contributor)}${item.public_attribution ? '' : ' • Private attribution'}</div><div class="queue-counts"><span>${item.galaxy_number ? `Galaxy ${item.galaxy_number}` : 'No galaxy'}</span><span>${item.portal_glyphs || 'No glyphs'}</span></div></button>`).join('');
    $$('#verificationList .queue-item').forEach((button) => button.addEventListener('click', () => selectVerification(button.dataset.id)));
  }

  async function selectVerification(id) {
    state.selectedVerification = id;
    renderVerificationQueue();
    $('#verificationPlaceholder').hidden = true;
    $('#verificationContent').hidden = false;
    try {
      state.verificationDetail = await api(`/admin/verifications/${encodeURIComponent(id)}`);
      renderVerificationDetail();
    } catch (error) {
      toast(error.message, true);
      clearVerificationDetail();
    }
  }

  function clearVerificationDetail() {
    state.selectedVerification = null;
    state.verificationDetail = null;
    $('#verificationContent').hidden = true;
    $('#verificationPlaceholder').hidden = false;
    renderVerificationQueue();
  }

  function locationMarkup(data, proposed = false) {
    const galaxyNumber = data.galaxy_number;
    const glyphs = data.portal_glyphs || '';
    const complete = galaxyNumber && glyphs.length === 12;
    const status = proposed ? (complete ? 'pending' : 'unverified') : (data.location_status || 'unverified');
    return `<span class="status-chip ${escapeHtml(status)}">${proposed ? 'Submitted' : 'Catalog'} ${escapeHtml(status)}</span><h3>${galaxyNumber ? `Galaxy ${galaxyNumber}${data.galaxy_name ? ` — ${escapeHtml(data.galaxy_name)}` : ''}` : 'No galaxy supplied'}</h3>${glyphs ? `<div class="portal-glyph-row compact">${WCGlyphs.codeHtml(glyphs,{compact:true})}</div><p class="glyph-code">${escapeHtml(glyphs)}</p>` : '<p>No portal glyphs supplied.</p>'}`;
  }

  function renderVerificationDetail() {
    const {verification, discovery} = state.verificationDetail;
    $('#verificationStatus').textContent = verification.status;
    $('#verificationStatus').className = `detail-status ${verification.status}`;
    $('#verificationWcId').textContent = discovery.wc_id;
    $('#verificationName').textContent = discovery.display_name;
    $('#verificationContributor').textContent = `Evidence from ${verification.contributor}${verification.public_attribution ? '' : ' • Private on public site'} • submitted ${dateTime(verification.created_at)}`;
    $('#verificationPublicLink').href = `record.html?id=${discovery.id}`;
    $('#currentLocation').innerHTML = locationMarkup(discovery, false);
    $('#proposedLocation').innerHTML = locationMarkup(verification, true);
    const checks = [
      ['Reached system', verification.reached_system],
      ['Discovery present', verification.discovery_present],
      ['Projector confirmed', verification.projector_confirmed],
    ];
    $('#verificationChecks').innerHTML = checks.map(([label, yes]) => `<div class="verification-check ${yes ? 'yes' : 'no'}"><strong>${yes ? '✓' : '×'} ${escapeHtml(label)}</strong><span>${yes ? 'Contributor marked confirmed' : 'Not confirmed in this submission'}</span></div>`).join('');
    $('#verificationNotes').hidden = !verification.notes;
    $('#verificationNotes').textContent = verification.notes ? `Contributor notes: ${verification.notes}` : '';
    $('#verificationActions').hidden = verification.status !== 'pending';
    $('#verificationReviewNote').value = '';
    $('#applyLocation').checked = true;
    $('#verificationResult').hidden = true;
  }

  async function reviewVerification(decision) {
    const detail = state.verificationDetail;
    if (!detail || detail.verification.status !== 'pending') return;
    const verb = decision === 'approve' ? 'approve this verification' : 'reject this verification';
    if (!confirm(`Are you sure you want to ${verb} for ${detail.discovery.wc_id}?`)) return;
    const button = decision === 'approve' ? $('#approveVerification') : $('#rejectVerification');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = decision === 'approve' ? 'Approving…' : 'Rejecting…';
    try {
      const result = await api(`/admin/verifications/${encodeURIComponent(state.selectedVerification)}/${decision}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({actor:state.actor, note:$('#verificationReviewNote').value.trim(), apply_location:$('#applyLocation').checked})});
      $('#verificationResult').hidden = false;
      $('#verificationResult').className = 'inline-alert success';
      $('#verificationResult').textContent = decision === 'approve' ? `Verification approved.${result.location_applied ? ' Galaxy and glyphs were applied to the catalog.' : ' Catalog location was not changed.'}` : 'Verification rejected and retained in audit history.';
      toast(decision === 'approve' ? 'Verification approved.' : 'Verification rejected.');
      clearVerificationDetail();
      await Promise.all([loadSummary(), loadVerifications(), loadAudit()]);
    } catch (error) {
      $('#verificationResult').hidden = false;
      $('#verificationResult').className = 'inline-alert error';
      $('#verificationResult').textContent = error.message;
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  // ---------- Catalog editor ----------
  async function loadCatalog() {
    const query = $('#catalogAdminSearch').value.trim();
    const data = await api(`/admin/discoveries?q=${encodeURIComponent(query)}&limit=100`);
    state.catalogRecords = data.items || [];
    renderCatalogList();
  }

  function renderCatalogList() {
    $('#catalogAdminEmpty').hidden = state.catalogRecords.length > 0;
    $('#catalogAdminList').innerHTML = state.catalogRecords.map((item) => `<button class="queue-item ${state.selectedCatalog?.id === item.id ? 'active' : ''}" data-id="${item.id}" type="button"><div class="queue-item-top"><strong>${escapeHtml(item.wc_id)}</strong><span class="status-chip ${escapeHtml(item.location_status)}">${escapeHtml(item.location_status)}</span></div><div class="queue-item-sub">${escapeHtml(item.display_name)}</div><div class="queue-counts"><span>${escapeHtml(item.discovery_type)}</span><span>Image ${escapeHtml(item.image_status)}</span></div></button>`).join('');
    $$('#catalogAdminList .queue-item').forEach((button) => button.addEventListener('click', () => selectCatalog(Number(button.dataset.id))));
  }

  async function selectCatalog(id) {
    try {
      state.selectedCatalog = await api(`/admin/discoveries/${id}`);
      renderCatalogList();
      renderCatalogForm();
    } catch (error) { toast(error.message, true); }
  }

  function renderCatalogForm() {
    const record = state.selectedCatalog;
    $('#catalogPlaceholder').hidden = true;
    $('#catalogForm').hidden = false;
    $('#catalogWcId').textContent = record.wc_id;
    $('#catalogRecordName').textContent = record.display_name;
    $('#catalogRecordData').textContent = `${record.discovery_type} • ${record.ua} • contributor ${record.contributor}${record.public_attribution ? '' : ' (private on public site)'}`;
    $('#catalogPublicLink').href = `record.html?id=${record.id}`;
    $('#catalogDisplayName').value = record.custom_display_name || '';
    $('#catalogGalaxyNumber').value = record.galaxy_number || '';
    $('#catalogGalaxyName').value = record.galaxy_name || '';
    $('#catalogGlyphs').value = record.portal_glyphs || '';
    $('#catalogGlyphs').dispatchEvent(new Event('input'));
    $('#catalogLocationStatus').value = record.location_status;
    $('#catalogProjectorStatus').value = record.projector_status;
    $('#catalogImageStatus').value = record.image_status;
    $('#catalogNote').value = record.catalog_note || '';
    $('#catalogSaveResult').hidden = true;
  }

  async function saveCatalog(event) {
    event.preventDefault();
    if (!state.selectedCatalog) return;
    const payload = {
      actor: state.actor,
      display_name: $('#catalogDisplayName').value.trim(),
      galaxy_number: $('#catalogGalaxyNumber').value ? Number($('#catalogGalaxyNumber').value) : null,
      galaxy_name: $('#catalogGalaxyName').value.trim(),
      portal_glyphs: WCGlyphs.normalize($('#catalogGlyphs').value),
      location_status: $('#catalogLocationStatus').value,
      projector_status: $('#catalogProjectorStatus').value,
      image_status: $('#catalogImageStatus').value,
      catalog_note: $('#catalogNote').value.trim(),
    };
    const button = $('#saveCatalog');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Saving…';
    try {
      const result = await api(`/admin/discoveries/${state.selectedCatalog.id}`, {method:'PATCH', headers:{'Content-Type':'application/json'}, body:JSON.stringify(payload)});
      state.selectedCatalog = result.discovery;
      $('#catalogSaveResult').hidden = false;
      $('#catalogSaveResult').className = 'inline-alert success';
      $('#catalogSaveResult').textContent = 'Catalog record updated and logged.';
      toast(`${result.discovery.wc_id} updated.`);
      await Promise.all([loadSummary(), loadCatalog(), loadAudit()]);
      renderCatalogForm();
    } catch (error) {
      $('#catalogSaveResult').hidden = false;
      $('#catalogSaveResult').className = 'inline-alert error';
      $('#catalogSaveResult').textContent = error.message;
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }


  // ---------- Image review ----------
  async function loadImages() {
    const data = await api(`/admin/images?status=${encodeURIComponent(state.imageStatus)}&limit=200`);
    state.images = data.items || [];
    renderImageQueue();
  }

  function renderImageQueue() {
    const query = $('#imageSearch').value.trim().toLowerCase();
    const rows = state.images.filter((item) => `${item.contributor} ${item.wc_id} ${item.display_name} ${item.image_role}`.toLowerCase().includes(query));
    $('#imageEmpty').hidden = rows.length > 0;
    $('#imageList').innerHTML = rows.map((item) => `<button class="queue-item ${state.selectedImage === item.id ? 'active' : ''}" data-id="${escapeHtml(item.id)}" type="button"><div class="queue-item-top"><strong>${escapeHtml(item.wc_id)}</strong><time>${escapeHtml(shortDate(item.created_at))}</time></div><div class="queue-item-sub">${escapeHtml(item.display_name || 'Unnamed record')} • ${escapeHtml(item.contributor)}${item.public_attribution ? '' : ' • Private attribution'}</div><div class="queue-counts"><span>${escapeHtml(item.image_role.replaceAll('_',' '))}</span><span>${number(item.width)}×${number(item.height)}</span></div></button>`).join('');
    $$('#imageList .queue-item').forEach((button) => button.addEventListener('click', () => selectImage(button.dataset.id)));
  }

  async function selectImage(id) {
    state.selectedImage = id;
    renderImageQueue();
    $('#imagePlaceholder').hidden = true;
    $('#imageContent').hidden = false;
    try {
      state.imageDetail = await api(`/admin/images/${encodeURIComponent(id)}`);
      renderImageDetail();
    } catch (error) {
      toast(error.message, true);
      clearImageDetail();
    }
  }

  function clearImageDetail() {
    state.selectedImage = null;
    state.imageDetail = null;
    $('#imageContent').hidden = true;
    $('#imagePlaceholder').hidden = false;
  }

  function renderImageDetail() {
    const {image, discovery} = state.imageDetail;
    $('#imageStatus').textContent = image.status;
    $('#imageStatus').className = `detail-status ${image.status}`;
    $('#imageWcId').textContent = discovery.wc_id;
    $('#imageName').textContent = discovery.display_name;
    $('#imageContributorLine').textContent = `Image from ${image.contributor}${image.public_attribution ? '' : ' • Private on public site'} • submitted ${dateTime(image.created_at)}`;
    $('#imagePublicLink').href = `record.html?id=${discovery.id}`;
    $('#adminImage').src = image.preview_url;
    $('#adminImage').alt = `${discovery.wc_id} submitted by ${image.contributor}`;
    $('#imageMetadata').innerHTML = `<div><strong>${number(image.width)}×${number(image.height)}</strong><span>Dimensions</span></div><div><strong>${(image.size_bytes/1024/1024).toFixed(2)} MB</strong><span>Stored size</span></div><div><strong>${escapeHtml(image.image_role.replaceAll('_',' '))}</strong><span>Requested role</span></div><div><strong>${escapeHtml(image.original_filename)}</strong><span>Original file</span></div>`;
    $('#imageCaptionReview').hidden = !image.caption;
    $('#imageCaptionReview').textContent = image.caption ? `Contributor caption: ${image.caption}` : '';
    $('#imageActions').hidden = image.status !== 'pending';
    $('#imageReviewNote').value = '';
    $('#imageApprovalRole').value = image.image_role === 'primary_catalog' ? 'primary' : 'alternate';
    $('#imageReviewResult').hidden = true;
  }

  async function reviewImage(decision) {
    const detail = state.imageDetail;
    if (!detail || detail.image.status !== 'pending') return;
    if (!confirm(`${decision === 'approve' ? 'Publish' : 'Reject'} this image for ${detail.discovery.wc_id}?`)) return;
    const button = decision === 'approve' ? $('#approveImage') : $('#rejectImage');
    const original = button.textContent;
    button.disabled = true;
    button.textContent = decision === 'approve' ? 'Publishing…' : 'Rejecting…';
    try {
      const result = await api(`/admin/images/${encodeURIComponent(state.selectedImage)}/${decision}`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({actor:state.actor, note:$('#imageReviewNote').value.trim(), approval_role:$('#imageApprovalRole').value})});
      $('#imageReviewResult').hidden = false;
      $('#imageReviewResult').className = 'inline-alert success';
      $('#imageReviewResult').textContent = decision === 'approve' ? `Image published${result.is_primary ? ' as the primary catalog image' : ' as an alternate image'}.` : 'Image rejected and its private object removed.';
      toast(decision === 'approve' ? 'Image published.' : 'Image rejected.');
      clearImageDetail();
      await Promise.all([loadSummary(), loadImages(), loadAudit()]);
    } catch (error) {
      $('#imageReviewResult').hidden = false;
      $('#imageReviewResult').className = 'inline-alert error';
      $('#imageReviewResult').textContent = error.message;
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  // ---------- Audit ----------
  async function loadAudit() {
    try {
      const data = await api('/admin/audit?limit=40');
      const rows = data.items || [];
      const symbol = (event) => event.includes('approved') ? '✓' : event.includes('rejected') ? '×' : event.includes('updated') ? '✎' : '•';
      $('#auditList').innerHTML = rows.length ? rows.map((item) => `<div class="audit-item"><span class="audit-symbol">${symbol(item.event_type)}</span><div><strong>${escapeHtml(item.event_type.replaceAll('_',' '))}</strong><small>${escapeHtml(item.actor)} • ${escapeHtml(item.detail?.wc_id || item.batch_id || 'No record')}</small></div><time>${escapeHtml(dateTime(item.created_at))}</time></div>`).join('') : '<div class="empty-state"><p>No review events yet.</p></div>';
    } catch (error) {
      $('#auditList').innerHTML = `<div class="inline-alert error">${escapeHtml(error.message)}</div>`;
    }
  }

  // ---------- Events ----------
  $('#loginForm').addEventListener('submit', unlock);
  $('#lockButton').addEventListener('click', lock);
  $('#refreshButton').addEventListener('click', refreshAll);
  $('#refreshAudit').addEventListener('click', loadAudit);
  $$('.admin-mode').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode)));

  $('#queueSearch').addEventListener('input', renderSubmissionQueue);
  $('#recordSearch').addEventListener('input', renderSubmissionRecords);
  $('#approveButton').addEventListener('click', () => reviewSubmission('approve'));
  $('#rejectButton').addEventListener('click', () => reviewSubmission('reject'));
  $('#exportButton').addEventListener('click', exportSubmission);
  $('#copyIdButton').addEventListener('click', async () => { if (state.selectedSubmission) { await navigator.clipboard.writeText(state.selectedSubmission); toast('Submission ID copied.'); } });
  $$('.status-tab').forEach((tab) => tab.addEventListener('click', async () => { state.submissionStatus = tab.dataset.status; $$('.status-tab').forEach((item) => item.classList.toggle('active', item === tab)); clearSubmissionDetail(); await loadSubmissions(); }));
  $$('.record-tab').forEach((tab) => tab.addEventListener('click', () => { state.recordSection = tab.dataset.section; renderSubmissionRecords(); }));

  $('#verificationSearch').addEventListener('input', renderVerificationQueue);
  $$('.verification-status-tab').forEach((tab) => tab.addEventListener('click', async () => { state.verificationStatus = tab.dataset.status; $$('.verification-status-tab').forEach((item) => item.classList.toggle('active', item === tab)); clearVerificationDetail(); await loadVerifications(); }));
  $('#approveVerification').addEventListener('click', () => reviewVerification('approve'));
  $('#rejectVerification').addEventListener('click', () => reviewVerification('reject'));

  let catalogTimer;
  $('#catalogAdminSearch').addEventListener('input', () => { clearTimeout(catalogTimer); catalogTimer = setTimeout(loadCatalog, 300); });
  $('#catalogForm').addEventListener('submit', saveCatalog);
  $('#imageSearch').addEventListener('input', renderImageQueue);
  $$('.image-status-tab').forEach((tab) => tab.addEventListener('click', async () => { state.imageStatus = tab.dataset.status; $$('.image-status-tab').forEach((item) => item.classList.toggle('active', item === tab)); clearImageDetail(); await loadImages(); }));
  $('#approveImage').addEventListener('click', () => reviewImage('approve'));
  $('#rejectImage').addEventListener('click', () => reviewImage('reject'));
  WCGlyphs.bindInput('#catalogGlyphs','#catalogGlyphPreview','#catalogGlyphStatus');

  const savedKey = sessionStorage.getItem('wc_admin_key');
  const savedActor = sessionStorage.getItem('wc_admin_actor');
  if (savedActor) $('#actorInput').value = savedActor;
  if (savedKey) { $('#adminKeyInput').value = savedKey; unlock(); }
})();
