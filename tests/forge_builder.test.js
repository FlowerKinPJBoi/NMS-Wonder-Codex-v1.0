'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {entriesMatchingPrefix, slotLabel, traitEntries, unique} = require('../forge.js');

const catalog = JSON.parse(fs.readFileSync(path.resolve(__dirname, '../assets/forge/forge-catalog.json'), 'utf8'));
const trex = traitEntries(catalog.entries.filter((entry) => entry.family_id === 'TREX'));

assert.ok(trex.length > 1, 'T-Rex should expose configurable certified recipes');
assert.equal(slotLabel('TREX', 0), 'Body');
assert.equal(slotLabel('TREX', 2), 'Tail');

const bodies = unique(trex.map((entry) => entry.traits[0]));
assert.ok(bodies.includes('Bird-Rex Body'));

const birdRex = entriesMatchingPrefix(trex, ['Bird-Rex Body']);
assert.ok(birdRex.length > 1);
assert.ok(birdRex.every((entry) => entry.traits[0] === 'Bird-Rex Body'));

const birdHeads = unique(birdRex.map((entry) => entry.traits[1]));
const chosenHead = birdHeads[0];
const headMatches = entriesMatchingPrefix(trex, ['Bird-Rex Body', chosenHead]);
assert.ok(headMatches.length >= 1);
assert.ok(headMatches.every((entry) => entry.traits[0] === 'Bird-Rex Body' && entry.traits[1] === chosenHead));

for (const entry of trex) {
  assert.ok(entriesMatchingPrefix(trex, entry.traits).some((candidate) => candidate.id === entry.id));
}

console.log('Wonder Forge progressive recipe compatibility passed.');
