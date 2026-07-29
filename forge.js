(() => {
  'use strict';

  const state = {
    entries: [],
    components: [],
    discoveryCategory: '',
    discoveryFamily: '',
    discoveryId: '',
    componentCategory: '',
    componentFamily: '',
    componentSlot: '',
    componentId: '',
  };
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));

  function uniqueRows(rows, idKey, labelKey) {
    return [...new Map(rows.map((row) => [row[idKey], row[labelKey]])).entries()]
      .sort((a, b) => a[1].localeCompare(b[1]));
  }

  function option(value, label, selected = false) {
    return `<option value="${escapeHtml(value)}"${selected ? ' selected' : ''}>${escapeHtml(label)}</option>`;
  }

  function componentMatches(component, filters = state) {
    return (!filters.componentCategory || component.category_id === filters.componentCategory)
      && (!filters.componentFamily || component.family_id === filters.componentFamily)
      && (!filters.componentSlot || component.slot_id === filters.componentSlot);
  }

  function discoveryMatches(entry, filters = state) {
    return (!filters.discoveryCategory || entry.category_id === filters.discoveryCategory)
      && (!filters.discoveryFamily || entry.family_id === filters.discoveryFamily);
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {componentMatches, discoveryMatches, uniqueRows};
  }
  if (typeof document === 'undefined') return;

  function setDiscoveryPreview(entry) {
    const image = $('#forgeDiscoveryImage');
    if (!entry) {
      image.hidden = true;
      image.removeAttribute('src');
      $('#forgeDiscoveryClass').textContent = 'Unavailable';
      $('#forgeDiscoveryClass').classList.add('synthetic');
      $('#forgeDiscoveryFamilyName').textContent = 'Wonder Forge discovery';
      $('#forgeDiscoveryName').textContent = 'No representative form found';
      $('#forgeDiscoveryTraits').innerHTML = '';
      $('#forgeDiscoveryEvidence').textContent = 'Choose another collection or family.';
      return;
    }
    image.src = entry.image_url;
    image.alt = `${entry.family_display} — ${entry.form_name} representative hologram`;
    image.hidden = false;
    $('#forgeDiscoveryClass').textContent = entry.record_eligible
      ? 'Approved representative'
      : 'Gallery-only representative';
    $('#forgeDiscoveryClass').classList.toggle('synthetic', !entry.record_eligible);
    $('#forgeDiscoveryFamilyName').textContent = `${entry.category_display} · ${entry.family_display}`;
    $('#forgeDiscoveryName').textContent = entry.form_name;
    $('#forgeDiscoveryTraits').innerHTML = [
      entry.category_display,
      entry.family_display,
      entry.size_class,
      entry.ringless ? 'Ringless hologram' : '',
    ].filter(Boolean).map((label) => `<span>${escapeHtml(label)}</span>`).join('');
    $('#forgeDiscoveryEvidence').textContent = entry.record_eligible
      ? entry.display_label
      : `${entry.display_label} Gallery-only; this form is not assigned to Database records.`;
  }

  function syncDiscoveryFormSelect() {
    const matches = state.entries.filter((entry) => discoveryMatches(entry));
    if (!matches.some((entry) => entry.id === state.discoveryId)) {
      state.discoveryId = matches[0]?.id || '';
    }
    $('#forgeDiscoveryForm').innerHTML = matches.map((entry) => (
      option(entry.id, entry.form_name, entry.id === state.discoveryId)
    )).join('');
    $('#forgeDiscoveryForm').value = state.discoveryId;
    const selected = matches.find((entry) => entry.id === state.discoveryId);
    const eligibleCount = matches.filter((entry) => entry.record_eligible).length;
    $('#forgeDiscoveryStatus').textContent = matches.length
      ? `${matches.length} representative ${matches.length === 1 ? 'form' : 'forms'} available in this family · ${eligibleCount} eligible for evidence-safe Database matching.`
      : 'No representative form is available for this selection.';
    setDiscoveryPreview(selected);
  }

  function syncDiscoveryFamilySelect() {
    const rows = state.entries.filter((entry) => entry.category_id === state.discoveryCategory);
    const families = uniqueRows(rows, 'family_id', 'family_display');
    if (!families.some(([id]) => id === state.discoveryFamily)) {
      state.discoveryFamily = families[0]?.[0] || '';
    }
    $('#forgeDiscoveryFamily').innerHTML = families.map(([id, label]) => (
      option(id, label, id === state.discoveryFamily)
    )).join('');
    $('#forgeDiscoveryFamily').value = state.discoveryFamily;
    state.discoveryId = '';
    syncDiscoveryFormSelect();
  }

  function setDiscoveryCategory(categoryId) {
    state.discoveryCategory = categoryId;
    state.discoveryFamily = '';
    state.discoveryId = '';
    $('#forgeDiscoveryCategory').value = categoryId;
    syncDiscoveryFamilySelect();
  }

  function randomizeDiscovery() {
    const matches = state.entries.filter((entry) => discoveryMatches(entry));
    if (!matches.length) return;
    const entry = matches[Math.floor(Math.random() * matches.length)];
    state.discoveryId = entry.id;
    $('#forgeDiscoveryForm').value = entry.id;
    setDiscoveryPreview(entry);
    window.WonderAnalytics?.track('forge_discovery_randomized', {
      category: entry.category_id,
      family: entry.family_id,
      record_eligible: entry.record_eligible,
    });
  }

  function initializeDiscoveryProjector() {
    const categories = uniqueRows(state.entries, 'category_id', 'category_display');
    $('#forgeDiscoveryCategory').innerHTML = categories.map(([id, label]) => option(id, label)).join('');
    $('#forgeDiscoveryCategory').addEventListener('change', (event) => setDiscoveryCategory(event.target.value));
    $('#forgeDiscoveryFamily').addEventListener('change', (event) => {
      state.discoveryFamily = event.target.value;
      state.discoveryId = '';
      syncDiscoveryFormSelect();
    });
    $('#forgeDiscoveryForm').addEventListener('change', (event) => {
      state.discoveryId = event.target.value;
      setDiscoveryPreview(state.entries.find((entry) => entry.id === state.discoveryId));
    });
    $('#forgeDiscoveryRandomize').addEventListener('click', randomizeDiscovery);
    setDiscoveryCategory(categories.find(([id]) => id === 'fauna')?.[0] || categories[0]?.[0] || '');
  }

  function setComponentPreview(component) {
    const image = $('#forgeBuilderImage');
    if (!component) {
      image.hidden = true;
      image.removeAttribute('src');
      $('#forgeBuilderClass').textContent = 'Unavailable';
      $('#forgeBuilderFamilyName').textContent = 'Wonder Forge';
      $('#forgeBuilderName').textContent = 'No compatible component found';
      $('#forgeBuilderTraits').innerHTML = '';
      $('#forgeBuilderEvidence').textContent = 'Choose another available component.';
      return;
    }
    image.src = component.image_url;
    image.alt = `${component.family_display} ${component.component_name} component preview`;
    image.hidden = false;
    $('#forgeBuilderClass').textContent = 'Component preview';
    $('#forgeBuilderFamilyName').textContent = component.family_display;
    $('#forgeBuilderName').textContent = component.component_name;
    $('#forgeBuilderTraits').innerHTML = [
      component.category_display,
      component.slot_display,
    ].map((label) => `<span>${escapeHtml(label)}</span>`).join('');
    $('#forgeBuilderEvidence').textContent = component.display_label;
  }

  function syncComponentSelect() {
    const matches = state.components.filter((component) => componentMatches(component));
    if (!matches.some((component) => component.id === state.componentId)) {
      state.componentId = matches[0]?.id || '';
    }
    $('#forgeBuilderComponent').innerHTML = matches.map((component) => (
      option(component.id, component.component_name, component.id === state.componentId)
    )).join('');
    $('#forgeBuilderComponent').value = state.componentId;
    $('#forgeBuilderStatus').textContent = matches.length
      ? `${matches.length} compatible ${matches.length === 1 ? 'component' : 'components'} available in this slot.`
      : 'No component preview is available for this selection.';
    setComponentPreview(matches.find((component) => component.id === state.componentId));
  }

  function syncSlotSelect() {
    const rows = state.components.filter((component) => (
      component.category_id === state.componentCategory
      && component.family_id === state.componentFamily
    ));
    const slots = uniqueRows(rows, 'slot_id', 'slot_display');
    if (!slots.some(([id]) => id === state.componentSlot)) state.componentSlot = slots[0]?.[0] || '';
    $('#forgeBuilderSlot').innerHTML = slots.map(([id, label]) => option(id, label, id === state.componentSlot)).join('');
    $('#forgeBuilderSlot').value = state.componentSlot;
    syncComponentSelect();
  }

  function syncFamilySelect() {
    const rows = state.components.filter((component) => component.category_id === state.componentCategory);
    const families = uniqueRows(rows, 'family_id', 'family_display');
    if (!families.some(([id]) => id === state.componentFamily)) state.componentFamily = families[0]?.[0] || '';
    $('#forgeBuilderFamily').innerHTML = families.map(([id, label]) => option(id, label, id === state.componentFamily)).join('');
    $('#forgeBuilderFamily').value = state.componentFamily;
    syncSlotSelect();
  }

  function setComponentCategory(categoryId) {
    state.componentCategory = categoryId;
    state.componentFamily = '';
    state.componentSlot = '';
    state.componentId = '';
    $('#forgeBuilderCategory').value = categoryId;
    syncFamilySelect();
  }

  function randomizeComponent() {
    const matches = state.components.filter((component) => componentMatches(component));
    if (!matches.length) return;
    const component = matches[Math.floor(Math.random() * matches.length)];
    state.componentId = component.id;
    $('#forgeBuilderComponent').value = component.id;
    setComponentPreview(component);
    window.WonderAnalytics?.track('forge_component_randomized', {
      category: component.category_id,
      family: component.family_id,
      slot: component.slot_id,
    });
  }

  function initializeComponentBuilder() {
    const categories = uniqueRows(state.components, 'category_id', 'category_display');
    $('#forgeBuilderCategory').innerHTML = categories.map(([id, label]) => option(id, label)).join('');
    $('#forgeBuilderCategory').addEventListener('change', (event) => setComponentCategory(event.target.value));
    $('#forgeBuilderFamily').addEventListener('change', (event) => {
      state.componentFamily = event.target.value;
      state.componentSlot = '';
      state.componentId = '';
      syncSlotSelect();
    });
    $('#forgeBuilderSlot').addEventListener('change', (event) => {
      state.componentSlot = event.target.value;
      state.componentId = '';
      syncComponentSelect();
    });
    $('#forgeBuilderComponent').addEventListener('change', (event) => {
      state.componentId = event.target.value;
      setComponentPreview(state.components.find((component) => component.id === state.componentId));
    });
    $('#forgeRandomize').addEventListener('click', randomizeComponent);
    setComponentCategory(categories.find(([id]) => id === 'starship-parts')?.[0] || categories[0]?.[0] || '');
  }

  function renderGallery() {
    const query = $('#forgeSearch').value.trim().toLowerCase();
    const selectedCategory = $('#forgeCategory').value;
    const selectedFamily = $('#forgeFamily').value;
    const entries = state.entries.filter((entry) => {
      const text = `${entry.category_display} ${entry.family_display} ${entry.form_name}`.toLowerCase();
      return (!query || text.includes(query))
        && (!selectedCategory || entry.category_id === selectedCategory)
        && (!selectedFamily || entry.family_id === selectedFamily);
    });

    $('#forgeCount').textContent = `${entries.length.toLocaleString()} of ${state.entries.length.toLocaleString()} representative holograms`;
    $('#forgeGrid').innerHTML = entries.length ? entries.map((entry) => (
      `<article class="forge-card">
        <div class="forge-image">
          <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(`${entry.family_display} — ${entry.form_name} representative`)}" loading="lazy">
          <span class="forge-class">Representative</span>
        </div>
        <div class="forge-copy">
          <span class="forge-family">${escapeHtml(entry.category_display)} · ${escapeHtml(entry.family_display)}</span>
          <h2>${escapeHtml(entry.form_name)}</h2>
          <p>Evidence-labeled Wonder Forge art for this catalog family.</p>
          <p class="forge-disclaimer">${escapeHtml(entry.display_label)}</p>
        </div>
      </article>`
    )).join('') : '<div class="forge-empty surface">No representative holograms match these filters.</div>';
  }

  function syncGalleryFamilies() {
    const category = $('#forgeCategory').value;
    const rows = state.entries.filter((entry) => !category || entry.category_id === category);
    const families = uniqueRows(rows, 'family_id', 'family_display');
    const current = $('#forgeFamily').value;
    $('#forgeFamily').innerHTML = '<option value="">All families</option>' + families.map(([id, label]) => option(id, label, id === current)).join('');
    if (!families.some(([id]) => id === current)) $('#forgeFamily').value = '';
    renderGallery();
  }

  async function load() {
    try {
      const [catalogResponse, componentResponse] = await Promise.all([
        fetch('assets/forge/forge-catalog.json?v=1.22.0'),
        fetch('assets/forge/forge-components.json?v=1.20.1'),
      ]);
      const [catalog, components] = await Promise.all([
        catalogResponse.json(),
        componentResponse.json(),
      ]);
      if (!catalogResponse.ok || !componentResponse.ok) throw new Error('Wonder Forge catalog request failed.');
      state.entries = Array.isArray(catalog.entries) ? catalog.entries : [];
      state.components = Array.isArray(components.entries) ? components.entries : [];

      const categories = uniqueRows(state.entries, 'category_id', 'category_display');
      $('#forgeCategory').innerHTML = '<option value="">All collections</option>' + categories.map(([id, label]) => option(id, label)).join('');
      $('#forgeTotal').textContent = state.entries.length.toLocaleString();
      $('#forgeComponents').textContent = state.components.length.toLocaleString();
      $('#forgeCollections').textContent = categories.length.toLocaleString();
      $('#forgeFamilies').textContent = uniqueRows(state.entries, 'family_id', 'family_display').length.toLocaleString();
      initializeDiscoveryProjector();
      initializeComponentBuilder();
      syncGalleryFamilies();
      window.WonderAnalytics?.track('forge_gallery_view', {
        entry_count: state.entries.length,
        component_count: state.components.length,
      });
    } catch (error) {
      $('#forgeGrid').innerHTML = `<div class="forge-empty surface">${escapeHtml(error.message)}</div>`;
      $('#forgeCount').textContent = 'Wonder Forge is temporarily unavailable.';
      $('#forgeDiscoveryStatus').textContent = 'The representative discovery catalog is temporarily unavailable.';
      $('#forgeBuilderStatus').textContent = 'The Forge component catalog is temporarily unavailable.';
      setDiscoveryPreview(null);
      setComponentPreview(null);
    }
  }

  $('#forgeSearch').addEventListener('input', renderGallery);
  $('#forgeCategory').addEventListener('change', syncGalleryFamilies);
  $('#forgeFamily').addEventListener('change', renderGallery);
  load();
})();
