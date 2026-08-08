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
assert.match(page, /Start with a chat prompt/);
assert.match(page, /Files and reference pictures are optional/);
assert.match(page, /id="guidedBuildInput"[^>]*accept="\.nmsship,\.nmsprefab,\.nmsbase,\.json/);
assert.match(page, /id="guidedReferenceInput"/);
assert.match(page, /id="guidedDownloadOutput"[^>]*>Download latest build</);
assert.match(page, /id="guidedSubmitLearning"[^>]*>Finish &amp; submit for learning review</);
assert.match(page, /I inspected the latest result in BBA or the game and confirm the source is accurate ground truth/);
assert.match(page, /<details class="advanced-workspace"/);
assert.ok(page.indexOf('id="guidedWorkspace"') < page.indexOf('id="sharedHub"'));

assert.match(guided, /DaedalusShared\.generateBuild/);
assert.match(guided, /DaedalusShared\.fetchGeneratedFile/);
assert.match(guided, /Download diagnostic/);
assert.match(guided, /gateway timed out/i);
assert.match(guided, /DaedalusLearning\.loadAttempt/);
assert.match(guided, /DaedalusLearning\.approveGroundTruth/);
assert.match(guided, /DaedalusLearning\.submitForReview/);
assert.match(guided, /Build Pass \$\{result\.pass\.version\} ready/);
assert.match(guided, /result\.pass\.operation_count/);
assert.match(guided, /attemptStatus === "correct"/);
assert.match(guided, /ui\.send\.disabled = busy/);
assert.match(guided, /const promptOnly = !guided\.sourceFile/);
assert.doesNotMatch(guided, /if \(!instruction \|\| !guided\.sourceFile/);
assert.doesNotMatch(guided, /PLANNED_NOT_APPLIED/);
assert.doesNotMatch(guided, /automatic NMSBASE or prefab creation is not connected yet/i);

assert.match(analyzer, /window\.DaedalusApp =/);
assert.match(analyzer, /loadBuildFile: loadPackage/);
assert.match(analyzer, /sourceIds\.has\("\^BASE_FLAG"\)/);
assert.match(analyzer, /sourceIds\.has\("\^U_PARAGON"\)/);
assert.match(learning, /addRevision: recordRevision/);
assert.match(learning, /submitForReview: submitLearningForReview/);
assert.match(styles, /\.guided-layout/);
assert.match(styles, /\.advanced-workspace/);

console.log('Daedalus guided-workspace contracts passed.');
