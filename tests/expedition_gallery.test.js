'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {
  categoryFor,
  eligiblePool,
  resolveFromCatalog,
  stableIndex,
} = require('../expedition.js');

const root = path.resolve(__dirname, '..');
const registry = JSON.parse(
  fs.readFileSync(path.join(root, 'assets/forge/forge-catalog.json'), 'utf8'),
);

assert.equal(registry.entries.length, 221);
assert.deepEqual(registry.category_counts, {
  fauna: 160,
  flora: 8,
  frigates: 5,
  minerals: 13,
  multitools: 6,
  planets: 29,
});
assert.equal(registry.entries.filter((entry) => entry.record_eligible).length, 207);
assert.equal(
  registry.entries.filter((entry) => entry.category_id === 'planets' && entry.record_eligible).length,
  29,
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
assert.equal(categoryFor({asset_type: 'Frigate'}), 'frigates');
assert.equal(categoryFor({asset_type: 'Multitool'}), 'multitools');
assert.equal(categoryFor({asset_type: 'Starship'}), '');
assert.equal(categoryFor({asset_type: 'Freighter'}), '');
assert.equal(categoryFor({asset_type: 'Planet'}), '');
assert.equal(stableIndex('same identity', 16), stableIndex('same identity', 16));

const blobRecord = {
  discovery_type: 'Animal',
  fauna_family_id: 'BLOB',
  fauna_identity_source: 'confirmed_vp1_mapping',
  wc_id: 'WC-A-TEST',
};
const blobPool = eligiblePool(blobRecord, registry);
assert.ok(blobPool.length > 0);
assert.ok(blobPool.every((entry) => entry.record_eligible && entry.family_id === 'BLOB'));
const blobRepresentative = resolveFromCatalog(blobRecord, registry);
assert.equal(blobRepresentative.category, 'fauna');
assert.equal(blobRepresentative.category_label, 'Fauna');
assert.equal(blobRepresentative.public_label, 'Representative family image — not this exact specimen.');

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
  const pool = eligiblePool({
    ...blobRecord,
    fauna_family_id: family,
  }, registry);
  assert.ok(pool.length > 0, `Missing close-match family pool: ${family}`);
  assert.ok(pool.every((entry) => entry.match_scope === 'confirmed_family'));
}

assert.equal(
  resolveFromCatalog({
    ...blobRecord,
    fauna_identity_source: 'unconfirmed_visual_guess',
  }, registry),
  null,
);
assert.equal(resolveFromCatalog({asset_type: 'Planet', wc_id: 'WC-P-TEST'}, registry), null);
const frozenPlanet = resolveFromCatalog({
  discovery_type: 'Planet',
  planet_family_id: 'FROZEN',
  planet_size_class: 'Standard',
  wc_id: 'WC-P-TEST',
}, registry);
assert.equal(frozenPlanet.category, 'planets');
assert.equal(frozenPlanet.name, 'Frozen · Standard');
assert.match(frozenPlanet.image_url, /04-frozen-standard\.svg$/);
assert.equal(resolveFromCatalog({
  discovery_type: 'Planet',
  planet_family_id: 'FROZEN',
  wc_id: 'WC-P-UNRESOLVED-SIZE',
}, registry), null);
assert.equal(resolveFromCatalog({asset_type: 'Starship', wc_id: 'WC-S-TEST'}, registry), null);
assert.equal(resolveFromCatalog({asset_type: 'Multitool', wc_id: 'WC-MT-TEST'}, registry).category, 'multitools');

console.log('Wonder Forge ringless Database bridge passed.');
