'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const sandbox = {};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(
  path.resolve(__dirname, '..', 'admin', 'apps', 'daedalus', 'preview.js'),
  'utf8'
);
vm.runInContext(source, sandbox, {filename: 'preview.js'});

const preview = sandbox.DaedalusPreview;
assert.ok(preview);

const sign = preview.buildSchematic([
  {ObjectID: '^C_WALL', Position: [0, 1.666667, 0], Visible: 'true'},
  {ObjectID: '^WALLLIGHTYELLOW', Position: [-0.42, 2.5, -0.18], Visible: 'true'},
  {ObjectID: '^WALLLIGHTYELLOW', Position: [0.42, 0.82, -0.18], Visible: 'true'}
], {label: 'Pass 1'});

assert.deepEqual(Array.from(sign.axes), ['X', 'Y']);
assert.equal(sign.objectCount, 3);
assert.match(sign.svg, /<rect[^>]+fill="#081015"/);
assert.match(sign.svg, /fill="#ffd95a"/);
assert.match(sign.svg, /Pass 1/);
assert.match(sign.svg, /verify exact appearance in BBA or the game/);
const wall = sign.svg.match(/<rect x="([\d.]+)"[^>]+width="([\d.]+)"[^>]+fill="#081015"/);
assert.ok(wall);
assert.ok(Number(wall[1]) >= 0);
assert.ok(Number(wall[1]) + Number(wall[2]) <= 960);

const floor = preview.buildSchematic([
  {ObjectID: '^C_FLOOR', Position: [-4, 0, -2]},
  {ObjectID: '^WALLLIGHTBLUE', Position: [4, 0, 2]}
]);
assert.deepEqual(Array.from(floor.axes), ['X', 'Z']);
assert.match(floor.svg, /fill="#58bfff"/);
assert.equal(preview.buildSchematic([]), null);

console.log('Daedalus schematic preview contracts passed.');
