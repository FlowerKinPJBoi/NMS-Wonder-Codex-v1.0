'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const analyticsPage = read('admin/analytics/index.html');
const analyticsClient = read('admin/analytics/analytics-admin.js');
const daedalusShared = read('admin/apps/daedalus/shared.js');
const daedalusGuided = read('admin/apps/daedalus/guided.js');

assert.match(analyticsPage, /OPERATIONAL DIAGNOSTICS/);
assert.match(analyticsPage, /id="errorLedger"/);
assert.match(analyticsPage, /never store API keys, prompts, uploaded file contents, filenames, or reference images/i);
assert.match(analyticsClient, /owner\/analytics\/errors\/.*\/diagnostic/);
assert.match(analyticsClient, /Download diagnostic/);
assert.match(daedalusShared, /wonder-codex\.daedalus-client-diagnostic\.v1/);
assert.match(daedalusShared, /storedInOwnerLedger/);
assert.match(daedalusShared, /promptIncluded: false/);
assert.match(daedalusShared, /apiKeysIncluded: false/);
assert.match(daedalusShared, /uploadedFileContentsIncluded: false/);
assert.match(daedalusShared, /AbortController/);
assert.match(daedalusGuided, /daedalus-error-.*\.json/);

console.log('Wonder Codex operational diagnostic safeguards passed.');
