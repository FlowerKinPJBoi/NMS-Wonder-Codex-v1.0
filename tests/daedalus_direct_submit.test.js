'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

function element() {
  return {
    addEventListener() {},
    disabled: false,
    files: [],
    innerHTML: '',
    querySelector() { return null; },
    querySelectorAll() { return []; },
    reset() {},
    style: {},
    textContent: '',
    value: ''
  };
}

const ids = new Map();
const get = (selector) => {
  if (!ids.has(selector)) ids.set(selector, element());
  return ids.get(selector);
};
const calls = [];
const fetch = async (url, options = {}) => {
  calls.push({url, options});
  if (options.method === 'POST') {
    return {ok: true, status: 200, json: async () => ({ok: true, submission: {id: 'submission-1'}})};
  }
  if (url.endsWith('/submissions')) return {ok: true, status: 200, json: async () => ({items: []})};
  return {
    ok: true,
    status: 200,
    json: async () => ({
      operator: 'PJ',
      permissions: {submit: true, review: true, release: true},
      counts: {},
      corpus: {active: 0, disabled: 0, version: 0},
      max_upload_bytes: 40 * 1024 * 1024,
      storage_ready: true,
      production_rule: 'Only released, active corpus lessons may influence Daedalus retrieval.'
    })
  };
};

const sandbox = {
  Blob,
  FormData,
  URLSearchParams,
  console,
  document: {querySelector: get},
  encodeURIComponent,
  fetch,
  sessionStorage: {
    getItem(key) {
      return key === 'wc_admin_key' ? 'secret' : key === 'wc_admin_actor' ? 'PJ' : '';
    }
  },
  window: {location: {assign() {}, replace() {}}, confirm: () => true}
};
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(path.resolve(__dirname, '..', 'admin', 'apps', 'daedalus', 'shared.js'), 'utf8');
vm.runInContext(source, sandbox, {filename: 'shared.js'});

(async () => {
  await new Promise((resolve) => setImmediate(resolve));
  assert.equal(typeof sandbox.window.DaedalusShared?.submitLearningBlob, 'function');
  const blob = new Blob(['learning'], {type: 'application/zip'});
  const result = await sandbox.window.DaedalusShared.submitLearningBlob(blob, 'session.zip', 'Reviewed session');
  assert.equal(result.submission.id, 'submission-1');
  const upload = calls.find((call) => call.options.method === 'POST');
  assert.equal(upload.url, '/api/admin/apps/daedalus/submissions');
  assert.equal(upload.options.body.get('archive').name, 'session.zip');
  assert.equal(upload.options.body.get('note'), 'Reviewed session');
  assert.equal(upload.options.headers['X-Admin-Actor'], 'PJ');
  console.log('Daedalus direct learning submission passed.');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
