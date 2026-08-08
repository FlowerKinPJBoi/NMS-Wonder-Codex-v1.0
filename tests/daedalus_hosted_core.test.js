'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..', 'admin', 'apps', 'daedalus');
const workflow = require(path.join(root, 'base-workflow.js'));
const { generateSignPrefab } = require(path.join(root, 'sign-generator.js'));

const wrapper = workflow.classifyJsonBuild({
  Objects: [],
  Prefabs: [{
    PrefabID: 'Verified Sign',
    Position: [0, 0, 0],
    Up: [0, 1, 0],
    At: [0, 0, 1],
    Visibility: true
  }]
}, 'verified-sign.NMSBASE');
assert.equal(wrapper.sourceKind, 'prefab-instance-wrapper');
assert.equal(wrapper.geometryStatus, 'reference_only');
assert.equal(wrapper.objects.length, 0);

const definition = workflow.classifyJsonBuild({
  Name: 'Verified Sign',
  Prefab: [
    { ObjectID: '^BUILDFLATPANEL', Position: [0, 0, 0], Up: [0, 1, 0], At: [0, 0, 1] }
  ]
}, 'verified-sign.nmsprefab');
const resolved = workflow.resolvePrefabReferences(wrapper, [definition]);
assert.equal(resolved.geometryStatus, 'resolved_definition_relative');
assert.equal(resolved.unresolved.length, 0);
assert.equal(resolved.objects.length, 1);

const sign = generateSignPrefab({
  text: 'Cavern Below!',
  fontGrammar: 'flat-panel-block',
  timestampBase: 1785542400
});
assert.equal(sign.manifest.placedObjectCount, 64);
assert.equal(sign.manifest.objectIdOnly, true);
assert.equal(sign.prefab.Prefab.every((item) => item.ObjectID.startsWith('^')), true);
assert.equal(new Set(sign.prefab.Prefab.map((item) => item.Timestamp)).size, 64);

function element() {
  return {
    addEventListener() {}, append() {}, appendChild() {},
    classList: { add() {}, remove() {}, toggle() {} }, dataset: {}, disabled: false,
    focus() {}, getAttribute() { return null; }, hidden: false, innerHTML: '',
    scrollIntoView() {}, scrollHeight: 0, scrollTop: 0, setAttribute() {},
    textContent: '', value: ''
  };
}

const storage = new Map();
const sandbox = {
  console, Map, Set, Date, Math, JSON, Number, String, Array, Object, Promise,
  Uint8Array, Blob,
  document: {
    querySelector: () => element(),
    querySelectorAll: () => [],
    createElement: () => element()
  },
  localStorage: {
    getItem: (key) => storage.get(key) || null,
    setItem: (key, value) => storage.set(key, value)
  },
  state: {
    report: null, packageData: null, packageFile: null, images: [],
    primaryImageIndex: 0, mode: 'base'
  },
  setupDropZone() {}, isBuildFile: () => true, showToast() {},
  parseBuildFile: async () => null, safeArchiveName: (name) => name,
  safeFileName: (name) => name, downloadBlob() {},
  escapeHtml: (value) => String(value),
  round(value, digits = 2) {
    const factor = 10 ** digits;
    return Math.round(value * factor) / factor;
  },
  isPlacedObject(item) {
    return item && typeof item.ObjectID === 'string' && Array.isArray(item.Position)
      && item.Position.slice(0, 3).every(Number.isFinite);
  }
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;
vm.createContext(sandbox);
const learningPath = path.join(root, 'learning.js');
vm.runInContext(fs.readFileSync(learningPath, 'utf8'), sandbox, { filename: learningPath });

const learning = sandbox.DaedalusLearning;
assert.ok(learning);
assert.deepEqual(
  Array.from(learning.classifyRevision('Make the mast taller, preserve the hull.')),
  ['masts and rigging', 'hull', 'scale and proportions']
);
assert.equal(learning.deriveTrainingTrust({
  groundTruthStatus: 'unverified',
  attemptStatus: 'correct',
  validationFailures: [],
  attemptEvidencePresent: true,
  notePresent: true,
  partFeedbackCount: 0
}).eligibleForTraining, false);

const page = fs.readFileSync(path.join(root, 'index.html'), 'utf8');
for (const script of ['base-workflow.js', 'sign-generator.js', 'app.js', 'learning.js', 'preview.js', 'shared.js', 'guided.js']) {
  assert.ok(page.includes(`src="${script}`), `${script} must be loaded by the hosted page.`);
}
assert.ok(page.indexOf('src="base-workflow.js') < page.indexOf('src="app.js'));
assert.ok(page.indexOf('src="sign-generator.js') < page.indexOf('src="app.js'));
assert.ok(page.indexOf('src="learning.js') < page.indexOf('src="shared.js'));
assert.ok(page.indexOf('src="learning.js') < page.indexOf('src="preview.js'));
assert.ok(page.indexOf('src="preview.js') < page.indexOf('src="guided.js'));
assert.ok(page.indexOf('src="shared.js') < page.indexOf('src="guided.js'));

console.log('Hosted Daedalus core contracts passed.');
