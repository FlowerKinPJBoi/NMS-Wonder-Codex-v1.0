'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {componentMatches, discoveryMatches, uniqueRows} = require('../forge.js');

const components = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, '../assets/forge/forge-components.json'), 'utf8'),
).entries;
const representatives = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, '../assets/forge/forge-catalog.json'), 'utf8'),
).entries;

assert.equal(components.length, 329);
assert.equal(components.filter((entry) => entry.category_id === 'starship-parts').length, 218);
assert.equal(components.filter((entry) => entry.category_id === 'freighter-parts').length, 105);
assert.equal(components.filter((entry) => entry.category_id === 'multitool-parts').length, 6);

const categories = uniqueRows(components, 'category_id', 'category_display');
assert.deepEqual(categories.map(([id]) => id), ['freighter-parts', 'multitool-parts', 'starship-parts']);

const fighterWings = components.filter((entry) => componentMatches(entry, {
  componentCategory: 'starship-parts',
  componentFamily: 'fighter',
  componentSlot: 'wings',
}));
assert.ok(fighterWings.length >= 10);
assert.ok(fighterWings.every((entry) => entry.family_display === 'Fighter'));
assert.ok(fighterWings.every((entry) => entry.slot_display === 'Wings'));
assert.ok(fighterWings.every((entry) => !/scene|mbin|wc-part|[a-f0-9]{12}/i.test(entry.component_name)));

const faunaBlobs = representatives.filter((entry) => discoveryMatches(entry, {
  discoveryCategory: 'fauna',
  discoveryFamily: 'BLOB',
}));
assert.ok(faunaBlobs.length > 0);
assert.ok(faunaBlobs.every((entry) => entry.category_display === 'Fauna'));
assert.ok(faunaBlobs.every((entry) => entry.family_display === 'Blob'));
const closeMatchFamilies = new Set([
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
]);
for (const family of closeMatchFamilies) {
  const familyRows = representatives.filter((entry) => discoveryMatches(entry, {
    discoveryCategory: 'fauna',
    discoveryFamily: family,
  }));
  assert.ok(familyRows.length > 0, `Missing Forge family: ${family}`);
  assert.ok(familyRows.every((entry) => entry.record_eligible === true));
}
assert.equal(
  representatives.filter((entry) => discoveryMatches(entry, {
    discoveryCategory: 'planets',
    discoveryFamily: '',
  })).length,
  29,
);
const frozenPlanets = representatives.filter((entry) => discoveryMatches(entry, {
  discoveryCategory: 'planets',
  discoveryFamily: 'FROZEN',
}));
assert.deepEqual(frozenPlanets.map((entry) => entry.size_class).sort(), ['Giant', 'Standard']);
assert.ok(frozenPlanets.every((entry) => entry.display_label.includes('not this exact planet')));

console.log('Wonder Forge component compatibility passed.');
