'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

const root = path.resolve(__dirname, '..');
const read = (relativePath) => fs.readFileSync(path.join(root, relativePath), 'utf8');
const catalog = JSON.parse(read('assets/forge/forge-catalog.json'));
const components = JSON.parse(read('assets/forge/forge-components.json'));

assert.equal(catalog.entry_count, 221);
assert.equal(catalog.entries.length, catalog.entry_count);
assert.deepEqual(catalog.category_counts, {
  fauna: 160,
  flora: 8,
  frigates: 5,
  minerals: 13,
  multitools: 6,
  planets: 29,
});
assert.equal(
  catalog.record_image_policy.representative_label,
  'Representative family image — not this exact specimen.',
);
assert.equal(catalog.record_image_policy.exact_screenshots_override_representatives, true);
assert.equal(catalog.record_image_policy.raw_evidence_unchanged, true);
assert.equal(catalog.record_image_policy.ringless_presentation, true);

for (const entry of catalog.entries) {
  assert.equal(entry.exact_specimen, false);
  assert.equal(entry.ringless, true);
  assert.ok(fs.existsSync(path.join(root, entry.image_url)), `Missing Forge image: ${entry.image_url}`);
  assert.doesNotMatch(JSON.stringify(entry), /scene-mbin|wc-part/i);
}

assert.equal(components.entry_count, 329);
assert.equal(components.entries.length, components.entry_count);
assert.equal(components.policy.component_previews_are_not_complete_discoveries, true);
assert.equal(components.policy.ringless_presentation, true);
for (const entry of components.entries) {
  assert.equal(entry.complete_discovery, false);
  assert.equal(entry.ringless, true);
  assert.ok(fs.existsSync(path.join(root, entry.image_url)), `Missing component image: ${entry.image_url}`);
  assert.doesNotMatch(JSON.stringify(entry), /scene-mbin|wc-part|targeted-/i);
}

const index = read('index.html');
const database = read('database.js');
const databasePage = read('database.html');
const record = read('record.js');
const recordPage = read('record.html');
const assetPage = read('asset.html');
const expeditionScript = read('expedition.js');
const forge = read('forge.html');
const forgeScript = read('forge.js');
const forgeStyles = read('forge.css');
const catalogStyles = read('catalog.css');
const contribute = read('contribute.html');
assert.match(index, /interactive, user-contributed museum of the galaxies/i);
assert.match(index, /Preserve the procedural universe/i);
assert.match(index, /account\.html[^>]*class="nav-cta"[^>]*>Passport/i);
assert.doesNotMatch(index.match(/<nav id="primaryNav"[\s\S]*?<\/nav>/i)[0], /Submit screenshot|decoder\.html/i);
assert.match(database, /Representative family image — not this exact specimen\./);
assert.match(record, /Representative family image — not this exact specimen\./);
assert.match(databasePage, /expedition\.js\?v=1\.23\.0/);
assert.match(recordPage, /expedition\.js\?v=1\.23\.0/);
assert.match(assetPage, /expedition\.js\?v=1\.23\.0/);
assert.match(expeditionScript, /assets\/forge\/forge-catalog\.json\?v=1\.23\.0/);
assert.match(expeditionScript, /record_eligible === true/);
assert.match(forge, /Construction component library/);
assert.match(forge, /id="decoder"[\s\S]*Wonder Projector Decoder[\s\S]*href="decoder\.html"/i);
assert.match(forge, /id="forgeDiscoveryCategory"/);
assert.match(forge, /id="forgeDiscoveryFamily"/);
assert.match(forge, /id="forgeDiscoveryForm"/);
assert.match(forge, /Twenty-six confirmed fauna families now have approved close-match pools/i);
assert.match(forge, /id="forgeBuilderFamily"/);
assert.match(forge, /Blue Diplo · long tail · spiky horns · XL/);
assert.match(forgeScript, /componentMatches/);
assert.match(forgeScript, /discoveryMatches/);
assert.match(forgeScript, /forge-components\.json/);
assert.match(forgeStyles, /forge-stage-starfield\.svg/);
assert.match(catalogStyles, /forge-stage-starfield\.svg/);
assert.ok(fs.existsSync(path.join(root, 'assets/brand/forge-stage-starfield.svg')));
assert.match(contribute, /NEW DISCOVERIES &amp; CATALOG EVIDENCE/);
assert.match(contribute, /Preserve a new find/);
assert.match(contribute, /contribute\.html\?mode=image[^>]*>Submit a screenshot/);

const planetBridge = JSON.parse(read('research/planet_hologram_bridge_v1.json'));
const starCensus = JSON.parse(read('research/star_system_census_v1.json'));
const faunaGallery = JSON.parse(read('research/fauna_close_match_gallery_v1.json'));
const starsPage = read('stars.html');
assert.equal(planetBridge.summary.planetDiscoveryRecords, 621);
assert.equal(planetBridge.assets.length, 29);
assert.equal(planetBridge.familyMap.length, 16);
assert.equal(planetBridge.privateControlsOmitted, true);
assert.doesNotMatch(JSON.stringify(planetBridge), /universalAddress|vp0/i);
assert.doesNotMatch(JSON.stringify(planetBridge), /"vp1Low":/i);
assert.equal(starCensus.systems.length, 50);
assert.equal(starCensus.summary.verifiedSystems, 50);
assert.equal(starCensus.colorFamilies.length, 5);
assert.doesNotMatch(JSON.stringify(starCensus), /universalAddress|portalGlyphs|vp0|screenshotFile/i);
assert.match(starsPage, /Fifty systems\. Five colors\./i);
assert.match(index, /href="stars\.html"/);
assert.equal(faunaGallery.summary.approvedFamiliesAdded, 6);
assert.equal(faunaGallery.summary.approvedFormsAdded, 20);
assert.equal(faunaGallery.summary.approvedFormsTotal, 48);
assert.equal(faunaGallery.summary.confirmedFamiliesCoveredAfter, 26);
assert.equal(faunaGallery.approvedForms.length, 48);
assert.equal(faunaGallery.evidencePolicy.branchOnlyFindsAreNotPublished, true);
assert.equal(faunaGallery.evidencePolicy.ambiguousSceneLinksAreNotPublished, true);

console.log('Wonder Codex v1.23.0 site invariants passed.');
