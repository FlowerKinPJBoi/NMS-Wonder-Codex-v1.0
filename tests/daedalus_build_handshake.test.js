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

function response(status, data) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: {get() { return null; }},
    json: async () => data
  };
}

const ids = new Map();
const get = (selector) => {
  if (!ids.has(selector)) ids.set(selector, element());
  return ids.get(selector);
};
const calls = [];
let buildAttempts = 0;
const jobId = '11111111-1111-4111-8111-111111111111';
const clientIncidentId = '22222222-2222-4222-8222-222222222222';
let uuidCalls = 0;

const fetch = async (url, options = {}) => {
  calls.push({url, options});
  if (url.endsWith('/build-jobs') && options.method === 'POST') {
    const payload = JSON.parse(options.body);
    assert.deepEqual(payload, {
      job_id: jobId,
      instruction: 'Build a portable sign.',
      session_id: ''
    });
    return response(201, {job: {id: jobId, status: 'preparing', phase: 'request_reserved'}});
  }
  if (url.endsWith('/build-sessions') && options.method === 'POST') {
    buildAttempts += 1;
    assert.equal(options.body.get('job_id'), jobId);
    assert.equal(options.body.get('instruction'), 'Build a portable sign.');
    if (buildAttempts === 1) return response(504, {detail: 'Gateway timeout'});
    return response(202, {job: {id: jobId, status: 'queued'}});
  }
  if (url.endsWith(`/build-jobs/${jobId}`)) {
    return response(200, {job: {id: jobId, status: 'completed'}, result: {ok: true, pass: {version: 1}}});
  }
  if (url.endsWith('/submissions')) return response(200, {items: []});
  return response(200, {
    operator: 'PJ',
    permissions: {submit: true, review: true, release: true},
    counts: {},
    corpus: {active: 0, disabled: 0, version: 0},
    generation: {ready: true, maximum_references: 4},
    max_upload_bytes: 40 * 1024 * 1024,
    storage_ready: true,
    production_rule: 'Only released, active corpus lessons may influence Daedalus retrieval.'
  });
};

const storage = new Map();
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
  window: {
    clearTimeout() {},
    confirm: () => true,
    crypto: {randomUUID: () => (uuidCalls++ === 0 ? jobId : clientIncidentId)},
    location: {assign() {}, replace() {}},
    localStorage: {
      getItem(key) { return storage.get(key) || null; },
      removeItem(key) { storage.delete(key); },
      setItem(key, value) { storage.set(key, value); }
    },
    setTimeout(callback) {
      Promise.resolve().then(callback);
      return 1;
    }
  }
};
sandbox.localStorage = sandbox.window.localStorage;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const source = fs.readFileSync(path.resolve(__dirname, '..', 'admin', 'apps', 'daedalus', 'shared.js'), 'utf8');
vm.runInContext(source, sandbox, {filename: 'shared.js'});

(async () => {
  await new Promise((resolve) => setImmediate(resolve));
  const progress = [];
  const result = await sandbox.window.DaedalusShared.generateBuild({
    instruction: 'Build a portable sign.',
    onProgress: (update) => progress.push(update)
  });
  assert.equal(result.pass.version, 1);
  assert.equal(buildAttempts, 2);
  const reservationIndex = calls.findIndex((call) => call.url.endsWith('/build-jobs') && call.options.method === 'POST');
  const buildIndex = calls.findIndex((call) => call.url.endsWith('/build-sessions') && call.options.method === 'POST');
  assert.ok(reservationIndex >= 0 && reservationIndex < buildIndex);
  assert.equal(storage.has('wc_daedalus_pending_build_job'), false);
  assert.ok(progress.some((update) => update.phase === 'job_reservation'));
  assert.ok(progress.some((update) => update.phase === 'request_reserved'));
  assert.ok(progress.some((update) => update.phase === 'completed'));
  console.log('Daedalus durable build handshake passed.');
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
