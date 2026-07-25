(() => {
  'use strict';

  const state = {
    entries: [],
    builderFamily: '',
    builderSelections: [],
    builderEntry: null,
  };
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const SLOT_LABELS = {
    CAT: ['Body', 'Head', 'Tail', 'Back trait', 'Ears / crest'],
    STRIDER: ['Body', 'Head', 'Tail', 'Additional trait'],
    TREX: ['Body', 'Head', 'Tail', 'Additional trait'],
  };

  function evidenceClass(entry) {
    return entry.record_eligible ? 'verified' : 'synthetic';
  }

  function familyEntries(familyId) {
    return state.entries.filter((entry) => entry.family_id === familyId);
  }

  function option(value, label, selected = false) {
    return `<option value="${escapeHtml(value)}"${selected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
  }

  function unique(values) {
    return [...new Set(values.filter(Boolean))];
  }

  function traitEntries(entries) {
    return entries.filter((entry) => Array.isArray(entry.traits) && entry.traits.length);
  }

  function entriesMatchingPrefix(entries, selections, length = selections.length) {
    return entries.filter((entry) => selections.slice(0, length).every((value, index) => !value || entry.traits[index] === value));
  }

  function slotLabel(familyId, index) {
    return SLOT_LABELS[familyId]?.[index] || `Part ${index + 1}`;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {entriesMatchingPrefix, slotLabel, traitEntries, unique};
  }
  if (typeof document === 'undefined') return;

  function setBuilderPreview(entry) {
    state.builderEntry = entry || null;
    const image = $('#forgeBuilderImage');
    if (!entry) {
      image.hidden = true;
      image.removeAttribute('src');
      $('#forgeBuilderClass').textContent = 'Unavailable';
      $('#forgeBuilderFamilyName').textContent = 'Wonder Forge';
      $('#forgeBuilderName').textContent = 'No compatible render found';
      $('#forgeBuilderTraits').innerHTML = '';
      $('#forgeBuilderEvidence').textContent = 'Choose another available combination.';
      return;
    }

    const verified = entry.record_eligible;
    image.src = entry.image_url;
    image.alt = `${entry.family_display} — ${entry.form_name} Forge hologram`;
    image.hidden = false;
    $('#forgeBuilderClass').textContent = verified ? 'Verified reference' : 'Synthetic variant';
    $('#forgeBuilderClass').classList.toggle('synthetic', !verified);
    $('#forgeBuilderFamilyName').textContent = entry.family_display;
    $('#forgeBuilderName').textContent = entry.form_name;
    $('#forgeBuilderTraits').innerHTML = (entry.traits || []).map((trait) => `<span>${escapeHtml(trait)}</span>`).join('');
    $('#forgeBuilderEvidence').textContent = verified
      ? 'Verified natural reference form · Representative family image — not this exact specimen.'
      : 'Synthetic NMS-parts variant · Natural in-game spawn not yet confirmed.';
  }

  function renderBuilderParts() {
    const entries = familyEntries(state.builderFamily);
    const configurable = traitEntries(entries);
    const container = $('#forgeBuilderParts');

    if (!configurable.length) {
      const selectedId = state.builderSelections[0] || entries[0]?.id || '';
      const selected = entries.find((entry) => entry.id === selectedId) || entries[0];
      state.builderSelections = selected ? [selected.id] : [];
      container.innerHTML = `<label>Complete base form<select data-builder-form>${entries.map((entry) => option(entry.id, entry.form_name, entry.id === selected?.id)).join('')}</select></label>`;
      container.querySelector('[data-builder-form]')?.addEventListener('change', (event) => {
        const next = entries.find((entry) => entry.id === event.target.value);
        state.builderSelections = next ? [next.id] : [];
        setBuilderPreview(next);
      });
      $('#forgeBuilderStatus').textContent = `${entries.length} complete ${entries.length === 1 ? 'form is' : 'forms are'} available for this base. Modular part maps have not yet been certified for this family.`;
      setBuilderPreview(selected);
      return;
    }

    const slotCount = Math.max(...configurable.map((entry) => entry.traits.length));
    const controls = [];
    for (let index = 0; index < slotCount; index += 1) {
      const candidates = entriesMatchingPrefix(configurable, state.builderSelections, index);
      const choices = unique(candidates.map((entry) => entry.traits[index]));
      if (!choices.length) continue;
      if (!choices.includes(state.builderSelections[index])) state.builderSelections[index] = choices[0];
      controls.push(`<label>${escapeHtml(slotLabel(state.builderFamily, index))}<select data-builder-slot="${index}">${choices.map((choice) => option(choice, choice, choice === state.builderSelections[index])).join('')}</select></label>`);
    }
    state.builderSelections = state.builderSelections.slice(0, slotCount);
    container.innerHTML = controls.join('');
    container.querySelectorAll('[data-builder-slot]').forEach((select) => select.addEventListener('change', (event) => {
      const index = Number(event.target.dataset.builderSlot);
      state.builderSelections[index] = event.target.value;
      state.builderSelections.splice(index + 1);
      renderBuilderParts();
    }));

    const matches = entriesMatchingPrefix(configurable, state.builderSelections);
    const selected = matches[0] || configurable[0];
    $('#forgeBuilderStatus').textContent = `${configurable.length} compatible rendered recipes available for this base. Dropdowns only offer parts that lead to a current preview.`;
    setBuilderPreview(selected);
  }

  function setBuilderFamily(familyId, preferredEntry = null) {
    state.builderFamily = familyId;
    const entries = familyEntries(familyId);
    const configurable = traitEntries(entries);
    const selected = preferredEntry && preferredEntry.family_id === familyId
      ? preferredEntry
      : configurable[0] || entries[0];
    state.builderSelections = selected?.traits?.length ? [...selected.traits] : selected ? [selected.id] : [];
    $('#forgeBuilderFamily').value = familyId;
    renderBuilderParts();
  }

  function randomizeBuilder() {
    const family = familyEntries(state.builderFamily);
    const entries = traitEntries(family).length ? traitEntries(family) : family;
    if (!entries.length) return;
    const entry = entries[Math.floor(Math.random() * entries.length)];
    setBuilderFamily(state.builderFamily, entry);
    window.WonderAnalytics?.track('forge_builder_randomized', {
      family: entry.family_id,
      evidence_class: evidenceClass(entry),
    });
  }

  function initializeBuilder(families) {
    const priority = ['TREX', 'TRICERATOPS', 'CAT', 'STRIDER'];
    $('#forgeBuilderFamily').innerHTML = families.map(([id, label]) => {
      const count = familyEntries(id).length;
      return option(id, `${label} · ${count} ${count === 1 ? 'form' : 'forms'}`);
    }).join('');
    const initialFamily = priority.find((id) => families.some(([familyId]) => familyId === id)) || families[0]?.[0] || '';
    if (initialFamily) setBuilderFamily(initialFamily);
    $('#forgeBuilderFamily').addEventListener('change', (event) => setBuilderFamily(event.target.value));
    $('#forgeRandomize').addEventListener('click', randomizeBuilder);
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
      const response = await fetch('assets/forge/forge-catalog.json?v=1.18.1');
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
      initializeBuilder(families);
      render();
      window.WonderAnalytics?.track('forge_gallery_view', {entry_count: state.entries.length});
    } catch (error) {
      $('#forgeGrid').innerHTML = `<div class="forge-empty surface">${escapeHtml(error.message)}</div>`;
      $('#forgeCount').textContent = 'Wonder Forge is temporarily unavailable.';
      $('#forgeBuilderStatus').textContent = 'The Forge recipe catalog is temporarily unavailable.';
      setBuilderPreview(null);
    }
  }

  $('#forgeSearch').addEventListener('input', render);
  $('#forgeClass').addEventListener('change', render);
  $('#forgeFamily').addEventListener('change', render);
  load();
})();
