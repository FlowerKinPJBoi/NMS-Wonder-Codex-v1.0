(() => {
  'use strict';

  const CATALOG_URL = 'assets/expedition/expedition-catalog.json?v=1.20.0';
  const state = {catalog: null, loading: null};

  function categoryFor(record = {}) {
    if (record.discovery_type === 'Animal') return 'fauna';
    if (record.discovery_type === 'Flora') return 'flora';
    if (record.discovery_type === 'Mineral') return 'minerals';
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

  function eligiblePool(record = {}) {
    const category = categoryFor(record);
    if (!category || !state.catalog) return [];
    let entries = state.catalog.catalog_entries.filter((entry) => entry.category === category);
    if (category === 'fauna') {
      const family = String(record.fauna_family_id || '').toUpperCase();
      if (!family) return [];
      entries = entries.filter((entry) => entry.family_id === family);
    }
    return entries;
  }

  function resolve(record = {}) {
    const pool = eligiblePool(record);
    const index = stableIndex(identitySignal(record), pool.length);
    if (index < 0) return null;
    const entry = pool[index];
    return Object.freeze({
      ...entry,
      selection_basis: 'deterministic_category_or_confirmed_family_pool',
    });
  }

  async function load() {
    if (state.catalog) return state.catalog;
    if (!state.loading) {
      state.loading = fetch(CATALOG_URL)
        .then(async (response) => {
          const data = await response.json();
          if (!response.ok) throw new Error(`Expedition catalog request failed (${response.status})`);
          if (!Array.isArray(data.catalog_entries) || !Array.isArray(data.component_entries)) {
            throw new Error('Expedition catalog is malformed.');
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

  const api = Object.freeze({load, resolve, catalog, categoryFor, stableIndex});
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WCExpedition = api;
})();
