'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const pages = [
  'index.html',
  'database.html',
  'forge.html',
  'map.html',
  'contributors.html',
  'contribute.html',
  'feedback.html',
  'decoder.html',
  'stars.html',
  'account.html',
  'privacy.html',
  'record.html',
  'asset.html',
  'import.html'
];

for (const page of pages) {
  const html = fs.readFileSync(path.join(root, page), 'utf8');
  assert.match(html, /humanized\.css\?v=1\.28\.0/, `${page} must load the humanized theme last.`);
  assert.match(html, /class="nav-discord"/i, `${page} must expose the Discord button.`);
  assert.match(html, /https:\/\/discord\.gg\/Xpn6Ep22Nu/, `${page} must use the permanent Wonder Codex invite.`);
  assert.match(html, /target="_blank"/, `${page} must keep the external invite outside the site tab.`);
  assert.match(html, /rel="noopener noreferrer"/, `${page} must isolate the external tab.`);
}

const theme = fs.readFileSync(path.join(root, 'humanized.css'), 'utf8');
assert.match(theme, /font-family: Bitter/);
assert.match(theme, /Source Sans 3/);
assert.match(theme, /Barlow Condensed/);
assert.match(theme, /\.nav-discord/);
assert.match(theme, /#8793ff/i);
assert.doesNotMatch(theme, /#(?:c9a76b|c89d58|d4a65a|ffd783)/i);

console.log('Wonder Codex humanized public-site contracts passed.');
