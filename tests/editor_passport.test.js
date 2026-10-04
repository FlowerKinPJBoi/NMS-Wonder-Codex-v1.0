const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync('editor-passport.js', 'utf8');

async function setup({query = '?editor=ABCD-EFGH-JKLM', saved = null, profile = null, fail = false} = {}) {
  const nodes = new Map();
  function element(id) {
    if (!nodes.has(id)) nodes.set(id, {hidden: true, checked: false, disabled: false, textContent: '', listeners: {},
      addEventListener(name, action) { this.listeners[name] = action; }});
    return nodes.get(id);
  }
  const storage = new Map(saved ? [['wc-editor-connection', JSON.stringify(saved)]] : []);
  const events = {};
  const requests = [];
  const account = {profile, session: profile ? {access_token: 'browser-only-session'} : null, ready: Promise.resolve({})};
  const context = {URL, Date, JSON, document: {getElementById: element}, location: {href: 'https://wondercodex.com/account.html' + query},
    history: {replaceState() {}}, sessionStorage: {getItem: key => storage.get(key) || null,
      setItem: (key, value) => storage.set(key, value), removeItem: key => storage.delete(key)},
    window: {WCAccount: account, addEventListener: (event, action) => { events[event] = action; }},
    fetch: async (url, options) => { requests.push({url, options}); return {ok: !fail, json: async () => fail ? {detail: 'Expired request.'} : {ok: true}}; }};
  vm.runInNewContext(code, context);
  await Promise.resolve();
  return {nodes, element, storage, account, events, requests};
}

(async () => {
  const profile = {id: 'one', contributor_name: 'Explorer', access_tier: 'tester', account_status: 'active'};
  const state = await setup({profile});
  assert.equal(state.element('editorConnect').hidden, false);
  assert.equal(state.requests.length, 0, 'Loading Passport must never approve automatically.');
  assert.equal(state.element('editorApprove').disabled, true);
  state.element('editorCodeMatches').checked = true;
  state.element('editorCodeMatches').listeners.change();
  assert.equal(state.element('editorApprove').disabled, false);
  await state.element('editorApprove').listeners.click();
  assert.equal(state.requests.length, 1);
  assert.equal(state.requests[0].url, '/api/auth/editor/approve');
  assert.deepEqual(JSON.parse(state.requests[0].options.body), {user_code: 'ABCD-EFGH-JKLM', approved: true, code_confirmed: true});
  assert.equal(state.storage.size, 0);
  assert.equal(state.element('editorApprove').disabled, true);

  const anonymous = await setup();
  assert.equal(anonymous.element('editorApprove').disabled, true);
  assert.equal(anonymous.storage.size, 1, 'Approval code must survive the normal Discord redirect.');
  const resumed = await setup({query: '', saved: {code: 'ABCD-EFGH-JKLM', expires: Date.now() + 600000}, profile});
  assert.equal(resumed.element('editorConnect').hidden, false);
  resumed.element('editorCodeMatches').checked = true;
  resumed.account.profile = {...profile, id: 'two'};
  resumed.events['wc-account-change']();
  assert.equal(resumed.element('editorCodeMatches').checked, false, 'Account switching must require fresh confirmation.');
  const regular = await setup({profile: {...profile, access_tier: 'regular'}});
  regular.element('editorCodeMatches').checked = true;
  regular.element('editorCodeMatches').listeners.change();
  assert.equal(regular.element('editorApprove').disabled, true);
  await regular.element('editorDecline').listeners.click();
  assert.equal(JSON.parse(regular.requests[0].options.body).approved, false);
  for (const options of [{query: '?editor=malicious'}, {query: '', saved: {code: 'ABCD-EFGH-JKLM', expires: 1}}]) {
    const invalid = await setup(options);
    assert.equal(invalid.element('editorConnect').hidden, true);
    assert.equal(invalid.requests.length, 0);
  }
  console.log('PASS: Passport connection consent, redirect recovery, account changes, tier gating and decline.');
})().catch(error => { console.error(error); process.exitCode = 1; });
