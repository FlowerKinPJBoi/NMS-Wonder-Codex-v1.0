'use strict';

const assert = require('node:assert/strict');

global.window = {};
require('../locations.js');
require('../projector.js');

const blob = window.WCProjector.decodeMessageId('ZqniBgA6MQADAAAAAwAAAHyJB5PlyI65muhaQA1PffQNWecLX+bHLQ==');
assert.equal(blob.discoveryType, 'Animal');
assert.equal(blob.discoveryLabel, 'Fauna');
assert.equal(blob.vpCount, 3);
assert.equal(blob.universalAddressHex, '313A0006E2A966');

const route = window.WCLocation.decode(blob.universalAddressHex);
assert.equal(route.galaxy_number, 1);
assert.equal(route.galaxy_name, 'Euclid');
assert.equal(route.portal_glyphs, '313A06E2A966');

assert.throws(
  () => window.WCProjector.decodeMessageId('not-a-projector-id'),
  /valid Wonder Projector Message ID|could not be decoded|not a supported Wonder Projector/,
);

console.log('Wonder Projector decoder vectors passed.');
