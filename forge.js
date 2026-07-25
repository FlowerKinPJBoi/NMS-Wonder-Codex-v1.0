(() => {
  'use strict';

  const state = {entries: []};
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function evidenceClass(entry) {
    return entry.record_eligible ? 'verified' : 'synthetic';
  }

  function render() {
    const query = $('#forgeSearch').value.trim().toLowerCase();
    const selectedClass = $('#forgeClass').value;
    const selectedFamily = $('#forgeFamily').value;
    const entries = state.entries.filter((entry) => {
      const text = `${entry.family_display} ${entry.form_name} ${(entry.traits || []).join(' ')}`.toLowerCase();
      return (!query || text.includes(query))
        && (!selectedClass || evidenceClass(entry) === selectedClass)
        && (!selectedFamily || entry.family_id === selectedFamily);
    });

    $('#forgeCount').textContent = `${entries.length.toLocaleString()} of ${state.entries.length.toLocaleString()} hologram forms`;
    $('#forgeGrid').innerHTML = entries.length ? entries.map((entry) => {
      const verified = entry.record_eligible;
      const traits = (entry.traits || []).slice(0, 5);
      const policy = verified
        ? 'Representative family image — not this exact specimen.'
        : 'Synthetic NMS-parts variant — natural in-game spawn not yet confirmed.';
      return `<article class="forge-card ${verified ? 'verified' : 'synthetic'}">
        <div class="forge-image">
          <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(`${entry.family_display} — ${entry.form_name} hologram`)}" loading="lazy">
          <span class="forge-class">${verified ? 'Verified reference' : 'Synthetic variant'}</span>
        </div>
        <div class="forge-copy">
          <span class="forge-family">${escapeHtml(entry.family_display)}</span>
          <h2>${escapeHtml(entry.form_name)}</h2>
          <p>${verified ? 'Natural wild form verified by the returned Forge catalog evidence.' : 'Authentic No Man’s Sky component combination held in the research-only lane.'}</p>
          ${traits.length ? `<div class="forge-traits">${traits.map((trait) => `<span>${escapeHtml(trait)}</span>`).join('')}</div>` : ''}
          <p class="forge-disclaimer">${escapeHtml(policy)}</p>
        </div>
      </article>`;
    }).join('') : '<div class="forge-empty surface">No Forge forms match these filters.</div>';
  }

  async function load() {
    try {
      const response = await fetch('assets/forge/forge-catalog.json?v=1.18.0');
      const catalog = await response.json();
      if (!response.ok) throw new Error(`Forge catalog request failed (${response.status})`);
      state.entries = Array.isArray(catalog.entries) ? catalog.entries : [];
      const families = [...new Map(state.entries.map((entry) => [entry.family_id, entry.family_display])).entries()]
        .sort((a, b) => a[1].localeCompare(b[1]));
      $('#forgeFamily').innerHTML = '<option value="">All families</option>' + families.map(([id, label]) => `<option value="${escapeHtml(id)}">${escapeHtml(label)}</option>`).join('');
      $('#forgeTotal').textContent = Number(catalog.entry_count || state.entries.length).toLocaleString();
      $('#forgeVerified').textContent = Number(catalog.verified_reference_count || 0).toLocaleString();
      $('#forgeSynthetic').textContent = Number(catalog.synthetic_variant_count || 0).toLocaleString();
      $('#forgeFamilies').textContent = families.length.toLocaleString();
      render();
      window.WonderAnalytics?.track('forge_gallery_view', {entry_count: state.entries.length});
    } catch (error) {
      $('#forgeGrid').innerHTML = `<div class="forge-empty surface">${escapeHtml(error.message)}</div>`;
      $('#forgeCount').textContent = 'Wonder Forge is temporarily unavailable.';
    }
  }

  $('#forgeSearch').addEventListener('input', render);
  $('#forgeClass').addEventListener('change', render);
  $('#forgeFamily').addEventListener('change', render);
  load();
})();
