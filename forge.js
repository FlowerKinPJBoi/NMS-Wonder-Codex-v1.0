(() => {
  'use strict';

  const state = {
    recipes: [],
    representatives: [],
    components: [],
    builderFamily: '',
    builderSelections: [],
  };
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(
    /[&<>"']/g,
    (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]),
  );
  const SLOT_LABELS = {
    CAT: ['Body', 'Head', 'Tail', 'Back trait', 'Ears / crest'],
    STRIDER: ['Body', 'Head', 'Tail', 'Additional trait'],
    TREX: ['Body', 'Head', 'Tail', 'Additional trait'],
  };

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
    return entries.filter((entry) => selections.slice(0, length).every(
      (value, index) => !value || entry.traits[index] === value,
    ));
  }

  function slotLabel(familyId, index) {
    return SLOT_LABELS[familyId]?.[index] || `Part ${index + 1}`;
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = {entriesMatchingPrefix, slotLabel, traitEntries, unique};
  }
  if (typeof document === 'undefined') return;

  function familyEntries(familyId) {
    return state.recipes.filter((entry) => entry.family_id === familyId);
  }

  function setBuilderPreview(entry) {
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
    $('#forgeBuilderTraits').innerHTML = (entry.traits || [])
      .map((trait) => `<span>${escapeHtml(trait)}</span>`)
      .join('');
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
      container.innerHTML = `<label>Complete base form<select data-builder-form>${entries.map(
        (entry) => option(entry.id, entry.form_name, entry.id === selected?.id),
      ).join('')}</select></label>`;
      container.querySelector('[data-builder-form]')?.addEventListener('change', (event) => {
        const next = entries.find((entry) => entry.id === event.target.value);
        state.builderSelections = next ? [next.id] : [];
        setBuilderPreview(next);
      });
      $('#forgeBuilderStatus').textContent = `${entries.length} complete ${entries.length === 1 ? 'form is' : 'forms are'} available for this base. Modular maps have not yet been certified for this family.`;
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
      controls.push(`<label>${escapeHtml(slotLabel(state.builderFamily, index))}<select data-builder-slot="${index}">${choices.map(
        (choice) => option(choice, choice, choice === state.builderSelections[index]),
      ).join('')}</select></label>`);
    }
    state.builderSelections = state.builderSelections.slice(0, slotCount);
    container.innerHTML = controls.join('');
    container.querySelectorAll('[data-builder-slot]').forEach((select) => {
      select.addEventListener('change', (event) => {
        const index = Number(event.target.dataset.builderSlot);
        state.builderSelections[index] = event.target.value;
        state.builderSelections.splice(index + 1);
        renderBuilderParts();
      });
    });
    const selected = entriesMatchingPrefix(configurable, state.builderSelections)[0] || configurable[0];
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
    state.builderSelections = selected?.traits?.length
      ? [...selected.traits]
      : selected ? [selected.id] : [];
    $('#forgeBuilderFamily').value = familyId;
    renderBuilderParts();
  }

  function initializeBuilder() {
    const families = [...new Map(
      state.recipes.map((entry) => [entry.family_id, entry.family_display]),
    ).entries()].sort((a, b) => a[1].localeCompare(b[1]));
    $('#forgeBuilderFamily').innerHTML = families.map(([id, label]) => {
      const count = familyEntries(id).length;
      return option(id, `${label} · ${count} ${count === 1 ? 'form' : 'forms'}`);
    }).join('');
    const priority = ['TREX', 'TRICERATOPS', 'CAT', 'STRIDER'];
    const initial = priority.find((id) => families.some(([familyId]) => familyId === id))
      || families[0]?.[0]
      || '';
    if (initial) setBuilderFamily(initial);
    $('#forgeBuilderFamily').addEventListener('change', (event) => setBuilderFamily(event.target.value));
    $('#forgeRandomize').addEventListener('click', () => {
      const family = familyEntries(state.builderFamily);
      const entries = traitEntries(family).length ? traitEntries(family) : family;
      if (!entries.length) return;
      setBuilderFamily(state.builderFamily, entries[Math.floor(Math.random() * entries.length)]);
    });
  }

  function componentMatches() {
    const category = $('#componentCategory').value;
    const family = $('#componentFamily').value;
    const slot = $('#componentSlot').value;
    return state.components.filter((entry) => (
      (!category || entry.category === category)
      && (!family || entry.family === family)
      && (!slot || entry.slot === slot)
    ));
  }

  function setComponentPreview(entry) {
    const image = $('#componentImage');
    if (!entry) {
      image.hidden = true;
      image.removeAttribute('src');
      $('#componentName').textContent = 'No component available';
      $('#componentPath').textContent = 'Wonder Forge component';
      $('#componentEvidence').textContent = 'Choose another category, family, or slot.';
      return;
    }
    image.src = entry.image_url;
    image.alt = `${entry.name} ${entry.slot} component preview`;
    image.hidden = false;
    $('#componentName').textContent = entry.name;
    $('#componentPath').textContent = `${entry.category_label} · ${entry.family} · ${entry.slot}`;
    $('#componentEvidence').textContent = entry.public_label;
  }

  function renderComponentPartOptions(preferred = '') {
    const matches = componentMatches();
    const part = $('#componentPart');
    part.innerHTML = matches.map((entry) => option(
      entry.id,
      entry.name,
      entry.id === preferred,
    )).join('');
    const selected = matches.find((entry) => entry.id === preferred) || matches[0];
    if (selected) part.value = selected.id;
    $('#componentStatus').textContent = `${matches.length} returned component ${matches.length === 1 ? 'preview' : 'previews'} in this compatibility lane.`;
    setComponentPreview(selected);
  }

  function renderComponentSlots(preferred = '') {
    const category = $('#componentCategory').value;
    const family = $('#componentFamily').value;
    const slots = unique(state.components.filter(
      (entry) => entry.category === category && entry.family === family,
    ).map((entry) => entry.slot)).sort();
    $('#componentSlot').innerHTML = slots.map((slot) => option(slot, slot, slot === preferred)).join('');
    if (slots.length) $('#componentSlot').value = slots.includes(preferred) ? preferred : slots[0];
    renderComponentPartOptions();
  }

  function renderComponentFamilies(preferred = '') {
    const category = $('#componentCategory').value;
    const families = unique(state.components.filter(
      (entry) => entry.category === category,
    ).map((entry) => entry.family)).sort();
    $('#componentFamily').innerHTML = families.map(
      (family) => option(family, family, family === preferred),
    ).join('');
    if (families.length) $('#componentFamily').value = families.includes(preferred) ? preferred : families[0];
    renderComponentSlots();
  }

  function initializeComponents() {
    const categories = [...new Map(
      state.components.map((entry) => [entry.category, entry.category_label]),
    ).entries()].sort((a, b) => a[1].localeCompare(b[1]));
    $('#componentCategory').innerHTML = categories.map(([id, label]) => option(id, label)).join('');
    renderComponentFamilies();
    $('#componentCategory').addEventListener('change', () => renderComponentFamilies());
    $('#componentFamily').addEventListener('change', () => renderComponentSlots());
    $('#componentSlot').addEventListener('change', () => renderComponentPartOptions());
    $('#componentPart').addEventListener('change', (event) => {
      setComponentPreview(componentMatches().find((entry) => entry.id === event.target.value));
    });
    $('#componentRandomize').addEventListener('click', () => {
      const entry = state.components[Math.floor(Math.random() * state.components.length)];
      if (!entry) return;
      $('#componentCategory').value = entry.category;
      renderComponentFamilies(entry.family);
      $('#componentSlot').value = entry.slot;
      renderComponentPartOptions(entry.id);
      window.WonderAnalytics?.track('forge_component_randomized', {
        category: entry.category,
        family: entry.family,
        slot: entry.slot,
      });
    });
  }

  function renderGallery() {
    const query = $('#forgeSearch').value.trim().toLowerCase();
    const category = $('#forgeCategory').value;
    const entries = state.representatives.filter((entry) => {
      const text = `${entry.category_label} ${entry.family_id} ${entry.name}`.toLowerCase();
      return (!query || text.includes(query)) && (!category || entry.category === category);
    });
    $('#forgeCount').textContent = `${entries.length.toLocaleString()} of ${state.representatives.length.toLocaleString()} approved representatives`;
    $('#forgeGrid').innerHTML = entries.length ? entries.map((entry) => (
      `<article class="forge-card verified">
        <div class="forge-image">
          <img src="${escapeHtml(entry.image_url)}" alt="${escapeHtml(`${entry.name} representative hologram`)}" loading="lazy">
          <span class="forge-class">Approved representative</span>
        </div>
        <div class="forge-copy">
          <span class="forge-family">${escapeHtml(entry.category_label)}${entry.family_id ? ` · ${escapeHtml(entry.family_id)}` : ''}</span>
          <h2>${escapeHtml(entry.name)}</h2>
          <p>Returned by Wonder Forge Expedition v0.1.16 and approved for evidence-labeled representative display.</p>
          <p class="forge-disclaimer">${escapeHtml(entry.public_label)}</p>
        </div>
      </article>`
    )).join('') : '<div class="forge-empty surface">No representatives match these filters.</div>';
  }

  async function load() {
    try {
      const [recipeResponse, expeditionResponse] = await Promise.all([
        fetch('assets/forge/forge-catalog.json?v=1.18.1'),
        fetch('assets/expedition/expedition-catalog.json?v=1.20.0'),
      ]);
      const [recipes, expedition] = await Promise.all([
        recipeResponse.json(),
        expeditionResponse.json(),
      ]);
      if (!recipeResponse.ok) throw new Error(`Forge recipe request failed (${recipeResponse.status})`);
      if (!expeditionResponse.ok) throw new Error(`Expedition catalog request failed (${expeditionResponse.status})`);
      state.recipes = Array.isArray(recipes.entries) ? recipes.entries : [];
      state.representatives = Array.isArray(expedition.catalog_entries)
        ? expedition.catalog_entries
        : [];
      state.components = Array.isArray(expedition.component_entries)
        ? expedition.component_entries
        : [];
      const counts = expedition.counts || {};
      $('#forgeTotal').textContent = (
        state.representatives.length + state.components.length
      ).toLocaleString();
      $('#forgeVerified').textContent = state.representatives.length.toLocaleString();
      $('#forgeComponents').textContent = state.components.length.toLocaleString();
      $('#forgeGroups').textContent = Number(counts.compatibility_groups || 0).toLocaleString();
      const categories = [...new Map(
        state.representatives.map((entry) => [entry.category, entry.category_label]),
      ).entries()].sort((a, b) => a[1].localeCompare(b[1]));
      $('#forgeCategory').innerHTML = '<option value="">All categories</option>'
        + categories.map(([id, label]) => option(id, label)).join('');
      initializeBuilder();
      initializeComponents();
      renderGallery();
      window.WonderAnalytics?.track('forge_gallery_view', {
        representative_count: state.representatives.length,
        component_count: state.components.length,
      });
    } catch (error) {
      $('#forgeGrid').innerHTML = `<div class="forge-empty surface">${escapeHtml(error.message)}</div>`;
      $('#forgeCount').textContent = 'Wonder Forge is temporarily unavailable.';
      $('#forgeBuilderStatus').textContent = 'The Forge recipe catalog is temporarily unavailable.';
      $('#componentStatus').textContent = 'The component atlas is temporarily unavailable.';
      setBuilderPreview(null);
      setComponentPreview(null);
    }
  }

  $('#forgeSearch').addEventListener('input', renderGallery);
  $('#forgeCategory').addEventListener('change', renderGallery);
  load();
})();
