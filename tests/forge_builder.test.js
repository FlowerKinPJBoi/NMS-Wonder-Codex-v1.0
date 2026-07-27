'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {componentMatches, uniqueRows} = require('../forge.js');

const components = JSON.parse(
  fs.readFileSync(path.resolve(__dirname, '../assets/forge/forge-components.json'), 'utf8'),
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

console.log('Wonder Forge component compatibility passed.');
