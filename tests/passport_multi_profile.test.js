'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');

const root = path.resolve(__dirname, '..');
const accountHtml = fs.readFileSync(path.join(root, 'account.html'), 'utf8');
const accountJs = fs.readFileSync(path.join(root, 'account.js'), 'utf8');
const accountSession = fs.readFileSync(path.join(root, 'account-session.js'), 'utf8');

test('Passport supports multiple saved NMS profiles', () => {
  assert.match(accountHtml, /id="nmsProfiles"/);
  assert.match(accountHtml, /id="nmsProfileForm"/);
  assert.match(accountHtml, /value="gog"/);
  assert.match(accountJs, /createNmsProfile/);
  assert.match(accountJs, /updateNmsProfile/);
  assert.match(accountJs, /Make default/);
  assert.match(accountSession, /\/account\/nms-profiles/);
});

test('saved profile list does not render the raw friend code', () => {
  const renderStart = accountJs.indexOf('function renderNmsProfiles');
  const renderEnd = accountJs.indexOf('function showProfile');
  const renderBody = accountJs.slice(renderStart, renderEnd);
  assert.doesNotMatch(renderBody, /nms_friend_code/);
  assert.match(renderBody, /native_owner_verified/);
});
