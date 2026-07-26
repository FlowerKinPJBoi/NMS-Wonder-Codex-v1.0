'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const {imageSubmissionAccepted} = require('../contribute.js');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');

assert.equal(imageSubmissionAccepted({ok:true, queued:true, image_id:'image-123'}), true);
assert.equal(imageSubmissionAccepted({ok:true, queued:false}), false);
assert.equal(imageSubmissionAccepted({ok:true, queued:true}), false);

const page = read('contribute.html');
const styles = read('catalog.css');
const client = read('contribute.js');
assert.match(page, /id="evidenceWebsite"[^>]*class="honeypot"/);
assert.match(styles, /\.honeypot\{[^}]*left:-10000px!important[^}]*pointer-events:none!important/);
assert.match(client, /state\.humanInteracted \? '' : \$\('#evidenceWebsite'\)\.value/);

console.log('Screenshot evidence submission safeguards passed.');
