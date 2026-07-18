import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import test from 'node:test';

const page = readFileSync(new URL('../feedback.html', import.meta.url), 'utf8');
const client = readFileSync(new URL('../feedback.js', import.meta.url), 'utf8');
const ownerPage = readFileSync(new URL('../admin/feedback/index.html', import.meta.url), 'utf8');
const ownerClient = readFileSync(new URL('../admin/feedback/feedback-admin.js', import.meta.url), 'utf8');

test('questionnaire exposes the requested experience questions', () => {
  for (const field of [
    'task_success', 'ease_score', 'ui_score', 'usefulness_score',
    'most_useful', 'improvements', 'missing_feature',
  ]) {
    assert.match(page, new RegExp(`name="${field}"`));
  }
});

test('pricing includes fixed, custom, and no-pay choices plus credits', () => {
  for (const choice of ['5', '10', 'custom', 'none']) {
    assert.match(page, new RegExp(`name="price_choice" value="${choice}"`));
  }
  assert.match(page, /name="custom_monthly_price"/);
  assert.match(page, /name="monthly_credits"/);
  assert.match(page, /monthly allotment of service credits/i);
});

test('feedback submission is deliberate and uses the bounded API route', () => {
  assert.match(page, /name="research_consent"/);
  assert.match(page, /name="website"/);
  assert.match(client, /fetch\('\/api\/feedback'/);
  assert.match(client, /credentials: 'omit'/);
});

test('owner console escapes response text and supports CSV export', () => {
  assert.match(ownerPage, /OWNER-ONLY RESEARCH CONSOLE/);
  assert.match(ownerClient, /escapeHtml/);
  assert.match(ownerClient, /wonder-codex-feedback-/);
  assert.match(ownerClient, /\/owner\/feedback\/responses/);
});
