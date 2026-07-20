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
assert.deepEqual(blob.vpHex, [
  '0xB98EC8E59307897C',
  '0xF47D4F0D405AE89A',
  '0x2DC7E65F0BE7590D',
]);
assert.equal(window.WCProjector.encodeMessageId({
  universalAddress: blob.universalAddress,
  discoveryType: 'Animal',
  vpValues: blob.vpValues,
}), blob.messageId);

const floraMessageId = window.WCProjector.encodeMessageId({
  universalAddress: '0x208BFF11112111',
  discoveryType: 'Flora',
  vpValues: ['0x024B1D416BFF2A12', '0x535A637B0E58E6D3'],
});
const flora = window.WCProjector.decodeMessageId(floraMessageId);
assert.equal(flora.discoveryType, 'Flora');
assert.equal(flora.universalAddressHex, '208BFF11112111');
assert.deepEqual(flora.vpHex, ['0x024B1D416BFF2A12', '0x535A637B0E58E6D3']);

const route = window.WCLocation.decode(blob.universalAddressHex);
assert.equal(route.galaxy_number, 1);
assert.equal(route.galaxy_name, 'Euclid');
assert.equal(route.portal_glyphs, '313A06E2A966');

assert.throws(
  () => window.WCProjector.decodeMessageId('not-a-projector-id'),
  /valid Wonder Projector Message ID|could not be decoded|not a supported Wonder Projector/,
);

console.log('Wonder Projector decoder vectors passed.');
