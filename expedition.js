(() => {
  'use strict';

  const CATALOG_URL = 'assets/forge/forge-catalog.json?v=1.25.0';
  const state = {catalog: null, loading: null};

  function categoryFor(record = {}) {
    if (record.discovery_type === 'Animal') return 'fauna';
    if (record.discovery_type === 'Flora') return 'flora';
    if (record.discovery_type === 'Mineral') return 'minerals';
    if (record.discovery_type === 'Planet') return 'planets';
    if (record.asset_type === 'Starship') return 'starships';
    if (record.asset_type === 'Freighter') return 'freighters';
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

  const SELECTOR_FIELDS = Object.freeze({
    forge_selector_fingerprints: ['forge_selector_fingerprint'],
    visual_profile_fingerprints: ['visual_profile_fingerprint'],
    identity_fingerprints: ['identity_fingerprint'],
    record_hashes: ['record_hash'],
    message_ids: ['message_id'],
    wc_ids: ['wc_id'],
  });

  function selectorMatches(entry = {}, record = {}) {
    const selectors = entry.record_selectors;
    if (!selectors || typeof selectors !== 'object') return false;
    return Object.entries(SELECTOR_FIELDS).some(([selectorName, recordFields]) => {
      const expected = selectors[selectorName];
      if (!Array.isArray(expected) || !expected.length) return false;
      if (
        selectorName === 'visual_profile_fingerprints'
        && record.descriptor_evidence_status !== 'observed_save_tokens'
      ) return false;
      const actual = recordFields
        .map((field) => String(record[field] || '').trim().toUpperCase())
        .find(Boolean);
      return Boolean(actual && expected.some((value) => String(value || '').trim().toUpperCase() === actual));
    });
  }

  function eligiblePool(record = {}, catalog = state.catalog) {
    const category = categoryFor(record);
    if (!category || !catalog || !Array.isArray(catalog.entries)) return [];
    let entries = catalog.entries.filter((entry) => (
      entry.record_eligible === true
      && entry.exact_specimen === false
      && entry.category_id === category
      && selectorMatches(entry, record)
    ));
    if (category === 'fauna') {
      const family = String(record.fauna_family_id || '').toUpperCase();
      if (!family) return [];
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
    if (!pool.length) return null;
    const highestPriority = Math.max(...pool.map((entry) => Number(entry.record_match_priority || 0)));
    const winners = pool.filter((entry) => Number(entry.record_match_priority || 0) === highestPriority);
    if (winners.length !== 1) return null;
    const entry = winners[0];
    return Object.freeze({
      ...entry,
      category: entry.category_id,
      category_label: entry.category_display,
      name: entry.form_name,
      public_label: entry.display_label,
      selection_basis: 'explicit_catalog_record_selector',
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
    selectorMatches,
    stableIndex,
  });
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WCExpedition = api;
})();
