'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {categoryFor, stableIndex} = require('../expedition.js');

const root = path.resolve(__dirname, '..');
const registry = JSON.parse(
  fs.readFileSync(path.join(root, 'assets/expedition/expedition-catalog.json'), 'utf8'),
);

assert.equal(registry.catalog_entries.length, 186);
assert.equal(registry.component_entries.length, 166);
assert.deepEqual(registry.counts.catalog_by_category, {
  fauna: 133,
  flora: 16,
  frigates: 5,
  minerals: 16,
  multitools: 16,
});
assert.deepEqual(registry.counts.components_by_category, {
  'freighter-parts': 55,
  'multitool-parts': 6,
  'starship-parts': 105,
});

for (const entry of [...registry.catalog_entries, ...registry.component_entries]) {
  assert.equal(entry.exact_specimen, false);
  assert.ok(
    fs.existsSync(path.join(root, entry.image_url)),
    `Missing Expedition image: ${entry.image_url}`,
  );
}
for (const entry of registry.component_entries) {
  assert.equal(entry.complete_discovery, false);
  assert.equal(
    entry.public_label,
    'Wonder Forge component preview — not a complete discovery.',
  );
}
for (const entry of registry.catalog_entries) {
  assert.equal(entry.record_image_status_unchanged, true);
  assert.equal(
    entry.public_label,
    'Representative family image — not this exact specimen.',
  );
}

assert.equal(categoryFor({discovery_type: 'Flora'}), 'flora');
assert.equal(categoryFor({discovery_type: 'Mineral'}), 'minerals');
assert.equal(categoryFor({asset_type: 'Frigate'}), 'frigates');
assert.equal(categoryFor({asset_type: 'Multitool'}), 'multitools');
assert.equal(categoryFor({asset_type: 'Starship'}), '');
assert.equal(categoryFor({asset_type: 'Freighter'}), '');
assert.equal(stableIndex('same identity', 16), stableIndex('same identity', 16));

console.log('Wonder Forge Expedition v0.1.16 gallery passed.');
