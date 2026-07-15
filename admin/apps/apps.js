(() => {
  'use strict';

  const API = '/api';
  const state = {key:'', actor:'PJ', apps:[], maxUploadBytes:0};
  const TEST_GUIDES = {
    'importer-beta': {
      title: 'Importer beta test brief',
      intro: 'Run the app normally—not as administrator. The goal is to confirm safe save detection, correct normalized counts, and a valid WCCP export without sharing a raw save.',
      steps: [
        'Close No Man’s Sky and wait for Steam or Xbox / Game Pass cloud activity to finish.',
        'Create a private download above, compare its SHA-256 with the vault, then extract the inner build ZIP to a normal folder.',
        'Run WonderCodexImporter.exe normally. Do not use Run as administrator and do not add antivirus exclusions.',
        'Scan saves. Confirm the expected platform accounts and character slots are separated and named correctly.',
        'Select one agreed character, open Advanced read-only revision details, then analyze the character.',
        'Compare discovery, fauna, flora, mineral, pet, exact-match, and generation-record totals with a known result when available.',
        'Review Contribution, choose the real original platform/cross-save provenance, and export the WCCP v0.1 ZIP. Do not use Legacy direct review unless PJ specifically asks.',
        'Optionally export the normalized Pegasus beta JSON only when that collection section is part of the test.',
      ],
      screenshots: [
        'App header/version and READ-ONLY SAVE ACCESS badge.',
        'Detected account and character cards after Scan saves.',
        'Advanced read-only revision details for the selected slot.',
        'Normalized Preview totals after Analyze character.',
        'Contribution panel showing provenance, record totals, and WCCP ready/export result.',
        'Every warning or error with its full exact message.',
      ],
      files: [
        'The exported WC-Contribution… WCCP ZIP.',
        'The screenshots listed above.',
        'This downloaded text report, completed with platform, character, counts, and result.',
        'Optional normalized Pegasus beta JSON if PJ requested that test.',
      ],
      stop: [
        'Never send a raw NMS save, WGS container, st_* folder, AppData path, Microsoft/Steam account ID, or administrator key.',
        'If Defender reports malware—not merely an unknown-publisher warning—stop and capture the exact alert. Do not bypass it.',
        'If counts are zero or materially wrong, do not submit or approve the package; preserve screenshots and report the mismatch.',
      ],
      report: [
        'Tester name:',
        'Importer version:',
        'Windows version:',
        'Local save source: Steam / Xbox-Game Pass PC',
        'Original play platform:',
        'Official cross-save used: Yes / No',
        'Accounts detected:',
        'Character tested:',
        'Discoveries / Fauna / Flora / Minerals / Pets / Exact matches:',
        'Counts match expected result: Yes / No / Unknown',
        'WCCP exported and self-validated: Yes / No',
        'Optional Pegasus JSON exported: Yes / No / Not tested',
        'Warnings or errors:',
        'Overall result: Pass / Needs review',
      ],
    },
    'pegasus-transit': {
      title: 'Pegasus Transit operator test brief',
      intro: 'PJ and Boots only. Use the exact selected character and a catalog .wctransit ticket. A failure is a stop condition: preserve the automatic backups before reopening the game.',
      steps: [
        'Save the selected character while flying in open space. Fully close No Man’s Sky.',
        'Create a private download above, compare SHA-256, extract the ZIP, and run WonderCodexPegasusTransitAdmin.exe normally—not as administrator.',
        'Download the chosen catalog .wctransit ticket from its Wonder Codex record while logged in as an admin.',
        'Authorize with your own named operator key, scan saves, and select the exact intended character.',
        'Load the ticket and preview the route. Confirm character, current location, WC record, galaxy, and twelve glyphs before continuing.',
        'Capture the Transit Preview screenshot, complete every departure confirmation, and engage only after preflight passes.',
        'Capture LOCAL WRITE VERIFIED / SUCCESS and the backup/evidence filenames before starting the platform handoff. The Windows username portion of a path may be redacted.',
        'After arrival, confirm the displayed galaxy and system match the ticket before taking specimen screenshots.',
      ],
      platform: {
        'Xbox / Game Pass handoff': [
          'Before Pegasus: fully quit NMS on Xbox, remove Quick Resume, open the PC game only to the main menu to hydrate the latest console save, then exit PC NMS completely.',
          'After LOCAL WRITE VERIFIED: never open Xbox first. Open PC NMS only to the main menu and choose the save’s ? prompt to upload the newer local revision.',
          'Exit PC NMS completely and allow several minutes. Game Pass may remain at Syncing 0%; that display alone did not prevent the validated v0.3.0 trip.',
          'Close the PC Xbox/Game Pass app, then launch Xbox. Proceed only if Xbox explicitly identifies the new cloud revision as the latest data. Otherwise cancel and preserve evidence.',
        ],
        'Steam first-validation lane': [
          'Wait for Steam Cloud to report Up to date before closing NMS and starting Pegasus.',
          'Preserve a complete private copy of the applicable st_* folder immediately before the transit.',
          'After SUCCESS, reopen NMS and verify the destination. If Steam shows any cloud conflict, stop and screenshot it before choosing either copy.',
          'After a successful arrival and clean exit, preserve the complete after-transit st_* folder as the matched pair.',
        ],
      },
      screenshots: [
        'Transit Preview before Engage, with operator key hidden.',
        'SUCCESS / LOCAL WRITE VERIFIED and both backup/evidence filenames; redact the Windows username if desired.',
        'Xbox: the ? local-upload prompt and the latest-cloud-data prompt.',
        'Steam: any cloud status or conflict prompt encountered.',
        'Arrival proof showing destination galaxy and system.',
        'Every unexpected warning or failure with its full exact message.',
      ],
      files: [
        'The exact .wctransit ticket used.',
        'All screenshots listed above.',
        'Xbox: the automatic BEFORE and AFTER-LOCAL-WRITE Pegasus evidence ZIPs.',
        'Steam first trip: complete before/after st_* matched pair, shared privately only.',
        'This downloaded text report, completed with route, platform, prompts, and result.',
      ],
      stop: [
        'Never send an administrator key or publish raw saves/evidence to Discord, GitHub, or the public site.',
        'On any Pegasus failure, unexpected cloud conflict, wrong character, changed source hash, or missing newer-cloud confirmation: stop. Do not reopen gameplay; preserve backups for review.',
        'Do not restore, rename, or delete the automatic evidence ZIPs until PJ and Nova complete the review.',
      ],
      report: [
        'Operator:',
        'Pegasus version:',
        'Platform: Xbox WGS / Steam',
        'Character:',
        'WC record:',
        'Target galaxy / system / glyphs:',
        'Transit Preview matched ticket: Yes / No',
        'LOCAL WRITE VERIFIED: Yes / No',
        'Backup/evidence filenames captured: Yes / No',
        'Xbox ? prompt appeared: Yes / No / N/A',
        'Xbox identified latest cloud data: Yes / No / N/A',
        'Game Pass displayed Syncing 0%: Yes / No / N/A',
        'Steam cloud conflict appeared: Yes / No / N/A',
        'Arrival galaxy/system matched: Yes / No',
        'Evidence files included:',
        'Warnings or errors:',
        'Overall result: Pass / Stop and review',
      ],
    },
  };
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const formatBytes = (value) => {
    const bytes = Number(value || 0);
    if (!bytes) return '—';
    const units = ['B','KB','MB','GB'];
    const unit = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / (1024 ** unit)).toFixed(unit > 1 ? 1 : 0)} ${units[unit]}`;
  };
  const formatDate = (value) => {
    if (!value) return '—';
    const date = new Date(value);
    return Number.isNaN(date.valueOf()) ? '—' : date.toLocaleString();
  };
  const headers = () => ({'X-Admin-Key':state.key,'X-Admin-Actor':state.actor,'Accept':'application/json'});

  function toast(message, error = false) {
    const element = $('#toast');
    element.textContent = message;
    element.className = `toast${error ? ' error' : ''}`;
    element.hidden = false;
    clearTimeout(toast.timer);
    toast.timer = setTimeout(() => element.hidden = true, 4800);
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
    state.apps = [];
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
      const data = await api('/admin/apps');
      sessionStorage.setItem('wc_admin_key', state.key);
      sessionStorage.setItem('wc_admin_actor', state.actor);
      $('#loginPanel').hidden = true;
      $('#dashboard').hidden = false;
      $('#lockButton').hidden = false;
      $('#connectionBadge').textContent = `${data.operator} connected`;
      $('#connectionBadge').className = 'connection-badge online';
      applyData(data);
    } catch (error) {
      state.key = '';
      $('#loginError').textContent = error.message;
      $('#loginError').hidden = false;
    }
  }

  function applyData(data) {
    state.apps = data.items || [];
    state.maxUploadBytes = Number(data.max_upload_bytes || 0);
    $('#storageBadge').textContent = data.storage_ready ? 'Private storage online' : 'Storage setup required';
    $('#storageBadge').className = `status-pill ${data.storage_ready ? 'ready' : 'warning'}`;
    $('#expiryNote').textContent = data.storage_ready ? `Download links expire after ${Math.round((data.download_expires_seconds || 600) / 60)} minutes.` : 'Configure the existing Spaces credentials on the API service.';
    renderApps();
  }

  async function refreshApps() {
    try { applyData(await api('/admin/apps')); }
    catch (error) { showAlert(error.message); }
  }

  function showAlert(message) {
    $('#appsAlert').textContent = message;
    $('#appsAlert').hidden = !message;
  }

  const listMarkup = (items, ordered = false) => {
    const tag = ordered ? 'ol' : 'ul';
    return `<${tag}>${(items || []).map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</${tag}>`;
  };

  function testSheetMarkup(slug) {
    const guide = TEST_GUIDES[slug];
    if (!guide) return '';
    const platform = guide.platform ? `<div class="test-platforms">${Object.entries(guide.platform).map(([title, items]) => `<section><h4>${escapeHtml(title)}</h4>${listMarkup(items, true)}</section>`).join('')}</div>` : '';
    return `<details class="test-sheet">
      <summary><span><b>Testing brief</b><small>Steps, screenshots, and return package</small></span><i>Open</i></summary>
      <div class="test-sheet-body"><div class="test-sheet-intro"><h3>${escapeHtml(guide.title)}</h3><p>${escapeHtml(guide.intro)}</p></div>
        <section class="test-section"><h4>Test steps</h4>${listMarkup(guide.steps, true)}</section>
        ${platform}
        <div class="test-return-grid"><section class="test-section"><h4>Screenshots to capture</h4>${listMarkup(guide.screenshots)}</section><section class="test-section"><h4>Return to PJ</h4>${listMarkup(guide.files)}</section></div>
        <section class="test-stop"><h4>Privacy and stop rules</h4>${listMarkup(guide.stop)}</section>
        <div class="test-guide-actions"><button class="small-button" type="button" data-copy-guide="${escapeHtml(slug)}">Copy checklist</button><button class="small-button" type="button" data-download-guide="${escapeHtml(slug)}">Download test report (.txt)</button><span>Boots can send the private return bundle to PJ; PJ can upload it into the current Wonder Codex work chat.</span></div>
      </div>
    </details>`;
  }

  function renderApps() {
    showAlert('');
    $('#appsGrid').innerHTML = state.apps.map((app) => {
      const release = app.release;
      const restricted = app.slug === 'pegasus-transit';
      const releaseMarkup = release ? `
        <div class="release-panel">
          <div class="release-top"><strong>v${escapeHtml(release.version || 'unlabeled')}</strong><span class="status-pill ready">Available</span></div>
          <div class="release-meta"><span>${escapeHtml(release.filename || 'Private ZIP')}</span><span>${formatBytes(release.size_bytes)} • ${escapeHtml(formatDate(release.uploaded_at))}</span></div>
          <div class="hash-row"><code title="${escapeHtml(release.sha256)}">${escapeHtml(release.sha256 || 'SHA-256 unavailable')}</code><button class="copy-hash" type="button" data-copy-hash="${escapeHtml(app.slug)}">Copy</button></div>
          <button class="button primary download-button" type="button" data-download="${escapeHtml(app.slug)}">Create private download</button>
        </div>` : `<div class="release-panel release-empty"><strong>No build installed</strong><span>Upload the inner Actions build ZIP below. It must contain ${escapeHtml(app.slug === 'importer-beta' ? 'WonderCodexImporter.exe' : 'WonderCodexPegasusTransitAdmin.exe')} directly.</span></div>`;
      return `<article class="app-card${restricted ? ' restricted' : ''}" data-app="${escapeHtml(app.slug)}">
        <div class="app-card-head"><span class="app-symbol">${restricted ? '⌁' : '◇'}</span><span class="channel-pill">${escapeHtml(app.channel)}</span></div>
        <h2>${escapeHtml(app.title)}</h2><p class="app-summary">${escapeHtml(app.summary)}</p><div class="app-safety">${escapeHtml(app.safety_note)}</div>
        ${releaseMarkup}
        ${testSheetMarkup(app.slug)}
        <div class="upload-panel"><h3>${release ? 'Replace current build' : 'Install a build'}</h3><div class="upload-grid"><label>Version<input data-version="${escapeHtml(app.slug)}" value="${escapeHtml(release?.version || app.suggested_version)}" maxlength="40"></label><label>Inner build ZIP<input data-file="${escapeHtml(app.slug)}" type="file" accept=".zip,application/zip"></label></div><p class="upload-note">Maximum ${formatBytes(state.maxUploadBytes)}. The server checks the ZIP, expected executable, CRC, and SHA-256 before replacing the current release.</p><div class="upload-progress" aria-hidden="true"><span data-progress="${escapeHtml(app.slug)}"></span></div><div class="upload-actions"><button class="button secondary" type="button" data-upload="${escapeHtml(app.slug)}">Upload reviewed build</button><span class="upload-status" data-upload-status="${escapeHtml(app.slug)}"></span></div></div>
      </article>`;
    }).join('') || '<div class="app-loading">No private applications are registered.</div>';

    document.querySelectorAll('[data-download]').forEach((button) => button.addEventListener('click', () => downloadApp(button.dataset.download, button)));
    document.querySelectorAll('[data-upload]').forEach((button) => button.addEventListener('click', () => uploadApp(button.dataset.upload, button)));
    document.querySelectorAll('[data-copy-hash]').forEach((button) => button.addEventListener('click', () => copyHash(button.dataset.copyHash)));
    document.querySelectorAll('[data-copy-guide]').forEach((button) => button.addEventListener('click', () => copyGuide(button.dataset.copyGuide)));
    document.querySelectorAll('[data-download-guide]').forEach((button) => button.addEventListener('click', () => downloadGuide(button.dataset.downloadGuide)));
  }

  function guideText(slug) {
    const guide = TEST_GUIDES[slug];
    if (!guide) return '';
    const lines = [`WONDER CODEX — ${guide.title.toUpperCase()}`, '', guide.intro, '', 'TEST STEPS'];
    guide.steps.forEach((item, index) => lines.push(`${index + 1}. ${item}`));
    if (guide.platform) Object.entries(guide.platform).forEach(([title, items]) => { lines.push('', title.toUpperCase()); items.forEach((item, index) => lines.push(`${index + 1}. ${item}`)); });
    lines.push('', 'SCREENSHOTS TO CAPTURE', ...guide.screenshots.map((item) => `- [ ] ${item}`));
    lines.push('', 'RETURN TO PJ', ...guide.files.map((item) => `- [ ] ${item}`));
    lines.push('', 'PRIVACY AND STOP RULES', ...guide.stop.map((item) => `- ${item}`));
    lines.push('', 'TEST REPORT', ...guide.report, '', 'Return privately to PJ. PJ can upload the package into the current Wonder Codex work chat.');
    return lines.join('\r\n');
  }

  async function copyGuide(slug) {
    await navigator.clipboard.writeText(guideText(slug));
    toast('Testing checklist copied.');
  }

  function downloadGuide(slug) {
    const guide = TEST_GUIDES[slug];
    if (!guide) return;
    const blob = new Blob([guideText(slug)], {type:'text/plain;charset=utf-8'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = slug === 'importer-beta' ? 'WonderCodex-Importer-Beta-Test-Report.txt' : 'Pegasus-Transit-Operator-Test-Report.txt';
    link.click();
    setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    toast('Test report downloaded.');
  }

  async function copyHash(slug) {
    const hash = state.apps.find((app) => app.slug === slug)?.release?.sha256;
    if (!hash) return;
    await navigator.clipboard.writeText(hash);
    toast('SHA-256 copied.');
  }

  async function downloadApp(slug, button) {
    const original = button.textContent;
    button.disabled = true;
    button.textContent = 'Preparing secure link…';
    try {
      const data = await api(`/admin/apps/${encodeURIComponent(slug)}/download`, {method:'POST'});
      toast(`Private link ready for ${data.filename}.`);
      window.location.assign(data.download_url);
    } catch (error) {
      toast(error.message, true);
    } finally {
      button.disabled = false;
      button.textContent = original;
    }
  }

  function uploadApp(slug, button) {
    const file = document.querySelector(`[data-file="${slug}"]`)?.files?.[0];
    const version = document.querySelector(`[data-version="${slug}"]`)?.value?.trim();
    const status = document.querySelector(`[data-upload-status="${slug}"]`);
    const progress = document.querySelector(`[data-progress="${slug}"]`);
    if (!version) return toast('Enter the build version first.', true);
    if (!file) return toast('Choose the inner build ZIP first.', true);
    if (state.maxUploadBytes && file.size > state.maxUploadBytes) return toast(`That ZIP exceeds the ${formatBytes(state.maxUploadBytes)} limit.`, true);

    const form = new FormData();
    form.append('version', version);
    form.append('archive', file, file.name);
    const request = new XMLHttpRequest();
    request.open('POST', `${API}/admin/apps/${encodeURIComponent(slug)}/upload`);
    request.setRequestHeader('X-Admin-Key', state.key);
    request.setRequestHeader('X-Admin-Actor', state.actor);
    request.setRequestHeader('Accept', 'application/json');
    button.disabled = true;
    status.textContent = 'Uploading and validating…';
    progress.style.width = '0%';
    request.upload.onprogress = (event) => { if (event.lengthComputable) progress.style.width = `${Math.round((event.loaded / event.total) * 100)}%`; };
    request.onerror = () => finishUpload('The upload connection failed.');
    request.onload = async () => {
      let data = {};
      try { data = JSON.parse(request.responseText || '{}'); } catch {}
      if (request.status < 200 || request.status >= 300) return finishUpload(data.detail || `Upload failed (${request.status}).`);
      progress.style.width = '100%';
      status.textContent = 'Installed.';
      toast(`${data.app?.title || 'Private app'} v${data.release?.version || version} installed.`);
      await refreshApps();
      button.disabled = false;
    };
    request.send(form);

    function finishUpload(message) {
      button.disabled = false;
      status.textContent = message;
      progress.style.width = '0%';
      toast(message, true);
    }
  }

  $('#loginForm').addEventListener('submit', unlock);
  $('#lockButton').addEventListener('click', lock);
  const savedKey = sessionStorage.getItem('wc_admin_key');
  const savedActor = sessionStorage.getItem('wc_admin_actor');
  if (savedActor) $('#actorInput').value = savedActor;
  if (savedKey) { $('#adminKeyInput').value = savedKey; unlock(); }
})();
