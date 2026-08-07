'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const page = read('admin/apps/daedalus/index.html');
const guided = read('admin/apps/daedalus/guided.js');
const styles = read('admin/apps/daedalus/guided.css');
const analyzer = read('admin/apps/daedalus/app.js');
const learning = read('admin/apps/daedalus/learning.js');

assert.match(page, /id="guidedWorkspace"/);
assert.match(page, /Chat with Daedalus/);
assert.match(page, /id="guidedBuildInput"[^>]*accept="\.nmsship,\.nmsprefab,\.nmsbase,\.json/);
assert.match(page, /id="guidedReferenceInput"/);
assert.match(page, /id="guidedDownloadOutput"[^>]*>Download latest build</);
assert.match(page, /id="guidedSubmitLearning"[^>]*>Finish &amp; submit for learning review</);
assert.match(page, /I inspected this source and confirm it is accurate ground truth/);
assert.match(page, /<details class="advanced-workspace"/);
assert.ok(page.indexOf('id="guidedWorkspace"') < page.indexOf('id="sharedHub"'));

assert.match(guided, /DaedalusShared\.retrieveLessons/);
assert.match(guided, /DaedalusLearning\.loadAttempt/);
assert.match(guided, /DaedalusLearning\.approveGroundTruth/);
assert.match(guided, /DaedalusLearning\.submitForReview/);
assert.match(guided, /maximumParts: 3000/);
assert.match(guided, /objectIdsOnly: true/);
assert.match(guided, /protectedAnchorPreserved: true/);
assert.match(guided, /uniformScaleRequired: true/);
assert.match(guided, /status: "PLANNED_NOT_APPLIED"/);
assert.match(guided, /generatedBuildFile: null/);
assert.match(guided, /Automatic NMSBASE and prefab creation is not connected yet/);
assert.doesNotMatch(guided, /modified NMSBASE (?:is|was) ready/i);

assert.match(analyzer, /window\.DaedalusApp =/);
assert.match(analyzer, /loadBuildFile: loadPackage/);
assert.match(analyzer, /sourceIds\.has\("\^BASE_FLAG"\)/);
assert.match(analyzer, /sourceIds\.has\("\^U_PARAGON"\)/);
assert.match(learning, /addRevision: recordRevision/);
assert.match(learning, /submitForReview: submitLearningForReview/);
assert.match(styles, /\.guided-layout/);
assert.match(styles, /\.advanced-workspace/);

console.log('Daedalus guided-workspace contracts passed.');
