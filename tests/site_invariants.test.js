'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const catalog = JSON.parse(read('assets/forge/forge-catalog.json'));

assert.equal(catalog.entry_count, 95);
assert.equal(catalog.verified_reference_count, 30);
assert.equal(catalog.synthetic_variant_count, 65);
assert.equal(catalog.entries.length, catalog.entry_count);
assert.equal(
  catalog.record_image_policy.representative_label,
  'Representative family image — not this exact specimen.',
);
assert.equal(catalog.record_image_policy.synthetic_variants_attach_to_records, false);

for (const entry of catalog.entries) {
  assert.equal(entry.exact_specimen, false);
  assert.ok(fs.existsSync(path.join(root, entry.image_url)), `Missing Forge image: ${entry.image_url}`);
  if (entry.record_eligible) {
    assert.equal(entry.authenticity_status, 'VERIFIED_REFERENCE_FORM');
  } else {
    assert.equal(entry.authenticity_status, 'NMS_PARTS_AUTHENTIC_SYNTHETIC_VARIANT');
  }
}

const index = read('index.html');
const database = read('database.js');
const record = read('record.js');
const forge = read('forge.html');
assert.match(index, /interactive, user-contributed museum of the galaxies/i);
assert.match(index, /Preserve the procedural universe/i);
assert.match(database, /Representative family image — not this exact specimen\./);
assert.match(record, /Representative family image — not this exact specimen\./);
assert.match(forge, /Synthetic variants.*never assigned to a discovery record/s);

console.log('Wonder Codex v1.18 site invariants passed.');
