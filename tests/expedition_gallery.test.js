'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  categoryFor,
  eligiblePool,
  resolveFromCatalog,
  selectorMatches,
  stableIndex,
} = require('../expedition.js');

const root = path.resolve(__dirname, '..');
const registry = JSON.parse(
  fs.readFileSync(path.join(root, 'assets/forge/forge-catalog.json'), 'utf8'),
);

assert.equal(registry.entries.length, 234);
assert.deepEqual(registry.category_counts, {
  fauna: 160,
  flora: 8,
  freighters: 5,
  frigates: 5,
  minerals: 13,
  multitools: 6,
  planets: 29,
  starships: 8,
});
assert.equal(registry.entries.filter((entry) => entry.record_eligible).length, 0);
assert.equal(
  registry.entries.filter((entry) => entry.category_id === 'planets' && entry.record_eligible).length,
  0,
);

for (const entry of registry.entries) {
  assert.equal(entry.exact_specimen, false);
  assert.equal(entry.ringless, true);
  assert.ok(
    fs.existsSync(path.join(root, entry.image_url)),
    `Missing ringless Forge image: ${entry.image_url}`,
  );
}

assert.equal(categoryFor({discovery_type: 'Animal'}), 'fauna');
assert.equal(categoryFor({discovery_type: 'Flora'}), 'flora');
assert.equal(categoryFor({discovery_type: 'Mineral'}), 'minerals');
assert.equal(categoryFor({discovery_type: 'Planet'}), 'planets');
assert.equal(categoryFor({asset_type: 'Starship'}), 'starships');
assert.equal(categoryFor({asset_type: 'Freighter'}), 'freighters');
assert.equal(categoryFor({asset_type: 'Frigate'}), 'frigates');
assert.equal(categoryFor({asset_type: 'Multitool'}), 'multitools');
assert.equal(categoryFor({asset_type: 'Planet'}), '');
assert.equal(stableIndex('same identity', 16), stableIndex('same identity', 16));

const blobRecord = {
  discovery_type: 'Animal',
  fauna_family_id: 'BLOB',
  fauna_identity_source: 'confirmed_vp1_mapping',
  wc_id: 'WC-A-TEST',
};
const blobPool = eligiblePool(blobRecord, registry);
assert.deepEqual(blobPool, []);
assert.equal(resolveFromCatalog(blobRecord, registry), null);

for (const family of [
  'ANTELOPE',
  'ARTHROPOD',
  'BIRD',
  'COW',
  'FLYINGLIZARD',
  'GRUNT',
  'PROTOROLLER',
  'ROBOTANTELOPE',
  'RODENT',
  'SEAHORSE',
  'SHARK',
  'SIXLEGCOW',
  'SMALLBIRD',
  'TWOLEGANTELOPE',
  'WEIRDBUTTERFLY',
]) {
  const galleryForms = registry.entries.filter((entry) => entry.family_id === family);
  assert.ok(galleryForms.length > 0, `Missing Forge gallery family: ${family}`);
  assert.ok(galleryForms.every((entry) => entry.record_eligible === false));
}

const boundBlobEntry = {
  ...registry.entries.find((entry) => entry.category_id === 'fauna' && entry.family_id === 'BLOB'),
  record_eligible: true,
  record_selectors: {forge_selector_fingerprints: ['WCF-BLOB-EXACT-VARIANT']},
  match_precision: 'visual_variant',
};
const boundCatalog = {entries: [boundBlobEntry]};
const boundBlobRecord = {
  ...blobRecord,
  forge_selector_fingerprint: 'WCF-BLOB-EXACT-VARIANT',
};
assert.equal(selectorMatches(boundBlobEntry, boundBlobRecord), true);
const blobMatch = resolveFromCatalog(boundBlobRecord, boundCatalog);
assert.equal(blobMatch.category, 'fauna');
assert.equal(blobMatch.category_label, 'Fauna');
assert.equal(blobMatch.selection_basis, 'explicit_catalog_record_selector');
assert.equal(resolveFromCatalog({...boundBlobRecord, forge_selector_fingerprint: 'WCF-OTHER'}, boundCatalog), null);

const descriptorEntry = {
  ...boundBlobEntry,
  record_selectors: {visual_profile_fingerprints: ['WCV-OBSERVED']},
};
assert.equal(selectorMatches(descriptorEntry, {
  visual_profile_fingerprint: 'WCV-OBSERVED',
  descriptor_evidence_status: 'no_descriptor_tokens_observed',
}), false);
assert.equal(selectorMatches(descriptorEntry, {
  visual_profile_fingerprint: 'WCV-OBSERVED',
  descriptor_evidence_status: 'observed_save_tokens',
}), true);

assert.equal(
  resolveFromCatalog({
    ...blobRecord,
    fauna_identity_source: 'unconfirmed_visual_guess',
  }, registry),
  null,
);
assert.equal(resolveFromCatalog({asset_type: 'Planet', wc_id: 'WC-P-TEST'}, registry), null);
assert.equal(resolveFromCatalog({
  discovery_type: 'Planet',
  planet_family_id: 'FROZEN',
  planet_size_class: 'Standard',
  wc_id: 'WC-P-TEST',
}, registry), null);
assert.equal(resolveFromCatalog({
  discovery_type: 'Planet',
  planet_family_id: 'FROZEN',
  wc_id: 'WC-P-UNRESOLVED-SIZE',
}, registry), null);
assert.equal(resolveFromCatalog({asset_type: 'Starship', wc_id: 'WC-S-TEST'}, registry), null);
assert.equal(resolveFromCatalog({asset_type: 'Freighter', wc_id: 'WC-FR-TEST'}, registry), null);
assert.equal(resolveFromCatalog({asset_type: 'Multitool', wc_id: 'WC-MT-TEST'}, registry), null);

console.log('Wonder Forge ringless Database bridge passed.');
