'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const vault = read('admin/apps/index.html');
const vaultClient = read('admin/apps/apps.js');
const page = read('admin/apps/daedalus/index.html');
const analyzer = read('admin/apps/daedalus/app.js');
const learning = read('admin/apps/daedalus/learning.js');
const shared = read('admin/apps/daedalus/shared.js');

assert.match(vault, /id="daedalusWorkspace"[^>]*href="\/admin\/apps\/daedalus\/"/);
assert.match(vaultClient, /state\.permissions\.daedalus/);
assert.match(page, /Build together\. Release deliberately\./);
assert.match(page, /cannot teach production Daedalus until an authorized reviewer approves and separately releases/i);
assert.match(page, /latest NMS Base Builder release/);
assert.match(page, /latest Blender/);
assert.match(page, /latest Python/);
assert.match(page, /No Python is required for the hosted trainer/);
assert.match(page, /id="sharedBbaVersion"/);
assert.match(page, /id="sharedBlenderVersion"/);
assert.match(page, /id="sharedPythonVersion"/);
assert.match(analyzer, /3,000-part game limit/);
assert.match(analyzer, /Normal Object ID shape/);
assert.match(analyzer, /\^BASE_FLAG/);
assert.match(analyzer, /\^U_PARAGON/);
assert.match(analyzer, /COPY_BASE_FLAG_SOURCE_RECORD_UNCHANGED_AND_USE_OBJECTID_ONLY_GEOMETRY/);
assert.match(learning, /COPY_BASE_FLAG_SOURCE_RECORD_UNCHANGED/);
assert.match(shared, /production_training_eligible/);
assert.match(shared, /Release to learning/);
assert.ok(fs.statSync(path.join(root, 'admin/apps/daedalus/vendor/jszip.min.js')).size > 50_000);
assert.ok(fs.statSync(path.join(root, 'admin/apps/daedalus/vendor/daedalus-inspector.bundle.js')).size > 500_000);

console.log('Daedalus shared-trainer contracts passed.');
