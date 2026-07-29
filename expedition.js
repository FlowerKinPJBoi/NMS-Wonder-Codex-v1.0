(() => {
  'use strict';

  const CATALOG_URL = 'assets/forge/forge-catalog.json?v=1.22.0';
  const state = {catalog: null, loading: null};

  function categoryFor(record = {}) {
    if (record.discovery_type === 'Animal') return 'fauna';
    if (record.discovery_type === 'Flora') return 'flora';
    if (record.discovery_type === 'Mineral') return 'minerals';
    if (record.discovery_type === 'Planet') return 'planets';
    if (record.asset_type === 'Frigate') return 'frigates';
    if (record.asset_type === 'Multitool') return 'multitools';
    return '';
  }

  function stableIndex(value, count) {
    if (!count) return -1;
    let hash = 2166136261;
    for (const char of String(value || 'wonder-codex')) {
      hash ^= char.codePointAt(0);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0) % count;
  }

  function identitySignal(record = {}) {
    return record.vp0
      || record.seed
      || record.resource_filename
      || record.identity_fingerprint
      || record.record_hash
      || record.message_id
      || record.wc_id
      || record.id
      || 'wonder-codex';
  }

  function eligiblePool(record = {}, catalog = state.catalog) {
    const category = categoryFor(record);
    if (!category || !catalog || !Array.isArray(catalog.entries)) return [];
    let entries = catalog.entries.filter((entry) => (
      entry.record_eligible === true
      && entry.exact_specimen === false
      && entry.category_id === category
    ));
    if (category === 'fauna') {
      const family = String(record.fauna_family_id || '').toUpperCase();
      if (!family) return [];
      const identitySource = String(
        record.fauna_identity_source
        || record.wonder_family_source
        || '',
      );
      if (
        identitySource
        && !['exact_pet_match', 'confirmed_vp1_mapping'].includes(identitySource)
      ) return [];
      entries = entries.filter((entry) => entry.family_id === family);
    }
    if (category === 'planets') {
      const family = String(record.planet_family_id || record.forge_family_id || '').toUpperCase();
      const size = String(record.planet_size_class || '').toLowerCase();
      if (!family || !size) return [];
      entries = entries.filter((entry) => (
        entry.family_id === family
        && String(entry.size_class || '').toLowerCase() === size
      ));
    }
    return entries;
  }

  function resolveFromCatalog(record = {}, catalog = state.catalog) {
    const pool = eligiblePool(record, catalog);
    const index = stableIndex(identitySignal(record), pool.length);
    if (index < 0) return null;
    const entry = pool[index];
    return Object.freeze({
      ...entry,
      category: entry.category_id,
      category_label: entry.category_display,
      name: entry.form_name,
      public_label: entry.display_label,
      selection_basis: 'deterministic_category_or_confirmed_family_pool',
    });
  }

  function resolve(record = {}) {
    return resolveFromCatalog(record, state.catalog);
  }

  async function load() {
    if (state.catalog) return state.catalog;
    if (!state.loading) {
      state.loading = fetch(CATALOG_URL)
        .then(async (response) => {
          const data = await response.json();
          if (!response.ok) throw new Error(`Expedition catalog request failed (${response.status})`);
          if (!Array.isArray(data.entries)) {
            throw new Error('Wonder Forge catalog is malformed.');
          }
          state.catalog = Object.freeze(data);
          return state.catalog;
        })
        .catch((error) => {
          state.loading = null;
          throw error;
        });
    }
    return state.loading;
  }

  function catalog() {
    return state.catalog;
  }

  const api = Object.freeze({
    load,
    resolve,
    resolveFromCatalog,
    eligiblePool,
    catalog,
    categoryFor,
    stableIndex,
  });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WCExpedition = api;
})();
