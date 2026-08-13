'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const recordHtml = fs.readFileSync(path.join(root, 'record.html'), 'utf8');
const recordJs = fs.readFileSync(path.join(root, 'record.js'), 'utf8');
const router = fs.readFileSync(path.join(root, 'api/app/routers/pegasus.py'), 'utf8');

test('record page uses Passport identity for Pegasus Live', () => {
  assert.match(recordHtml, /account-session\.js/);
  assert.match(recordJs, /WCAccount\.session\.access_token/);
  assert.match(recordJs, /\/api\/pegasus\/dispatches/);
  assert.match(recordJs, /pegasusFriendCode/);
  assert.match(recordHtml, /Add Pegasus in No Man's Sky/);
  assert.doesNotMatch(recordJs, /wc_admin_key/);
  assert.doesNotMatch(recordJs, /\.wctransit/);
});

test('server owns role and route authorization', () => {
  assert.match(router, /require_live_requester/);
  assert.match(router, /session\.get\(Discovery, request\.discovery_id\)/);
  assert.match(router, /destination_for\(discovery\)/);
  assert.match(router, /require_pegasus_worker_key/);
});
