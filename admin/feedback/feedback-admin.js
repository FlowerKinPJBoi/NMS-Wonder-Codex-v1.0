(() => {
  'use strict';

  const API = '/api';
  const state = {key:'', actor:'PJ', responses:[]};
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const number = (value) => Number(value || 0).toLocaleString();
  const labels = {
    overall_site:'Overall site',database_catalog:'Database / catalog',cluster_map:'Cluster Map',projector_decoder:'Projector Decoder',contribution_importer:'Contributions / Importer',private_apps:'Private apps',pegasus_transit:'Pegasus Transit',capture_companion:'Capture Companion',
    alpha_beta_tester:'Alpha / beta tester',contributor:'Contributor',explorer:'Explorer',first_time_visitor:'First-time visitor',admin_operator:'Admin / operator',
    yes:'Yes',partly:'Partly',no:'No',browsing:'Just browsing','5':'$5 / month','10':'$10 / month',custom:'Custom amount',none:'Would not pay',
    transit:'Pegasus transit',delivery:'Item delivery',sourcing:'Discovery sourcing',priority_requests:'Priority requests',supporter_only_tools:'Supporter-only tools',other:'Other',
  };
  const named = (value) => labels[value] || String(value || '—').replaceAll('_',' ');
  const headers = () => ({'X-Admin-Key':state.key,'X-Admin-Actor':state.actor,Accept:'application/json'});

  async function api(path) {
    const response = await fetch(API + path, {headers:headers()});
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  function toast(message, error = false) {
    const element = $('#toast'); element.textContent = message; element.className = `toast${error ? ' error' : ''}`; element.hidden = false;
    clearTimeout(toast.timer); toast.timer = setTimeout(() => { element.hidden = true; }, 4000);
  }

  function lock() {
    sessionStorage.removeItem('wc_admin_key'); sessionStorage.removeItem('wc_admin_actor'); state.key = '';
    $('#dashboard').hidden = true; $('#loginPanel').hidden = false; $('#lockButton').hidden = true; $('#adminKeyInput').value = '';
    $('#connectionBadge').textContent = 'Locked'; $('#connectionBadge').className = 'connection-badge';
  }

  function rows(items, suffix = '') {
    if (!items?.length) return '<div class="empty-state">No responses yet.</div>';
    return items.map((item) => `<div class="signal-row"><span>${escapeHtml(named(item.label))}</span><strong>${escapeHtml(number(item.count))}${suffix}</strong></div>`).join('');
  }

  function answer(label, value) {
    if (!value) return '';
    return `<div><small>${escapeHtml(label)}</small><p>${escapeHtml(value)}</p></div>`;
  }

  function renderResponses(items) {
    state.responses = items || [];
    $('#responses').innerHTML = state.responses.length ? state.responses.map((item) => {
      const price = item.price_choice === 'custom' ? `$${Number(item.custom_monthly_price).toFixed(2)} / month` : named(item.price_choice);
      return `<article class="response-card"><div class="response-head"><strong>${escapeHtml(item.respondent_name || 'Anonymous explorer')}</strong><span>${escapeHtml(new Date(item.created_at).toLocaleString())}</span></div><div class="response-meta"><span>${escapeHtml(named(item.visitor_type))}</span><span>${escapeHtml(named(item.page_area))}</span><span>${escapeHtml(price)}</span>${item.monthly_credits ? `<span>${escapeHtml(item.monthly_credits)} credits / month</span>` : ''}</div><div class="score-strip"><div><small>Ease</small><strong>${item.ease_score} / 5</strong></div><div><small>UI</small><strong>${item.ui_score} / 5</strong></div><div><small>Usefulness</small><strong>${item.usefulness_score} / 5</strong></div><div><small>Task</small><strong>${escapeHtml(named(item.task_success))}</strong></div></div><div class="answer-grid">${answer('Most useful',item.most_useful)}${answer('Needs change',item.improvements)}${answer('Missing feature',item.missing_feature)}${answer('Likely credit uses',(item.credit_uses || []).map(named).join(', '))}${answer('Additional notes',item.additional_notes)}</div></article>`;
    }).join('') : '<div class="empty-state">No questionnaire responses have arrived yet.</div>';
  }

  function render(summary, responses) {
    $('#totalResponses').textContent = number(summary.total_responses); $('#easeAverage').textContent = summary.averages.ease || '—';
    $('#uiAverage').textContent = summary.averages.ui || '—'; $('#usefulnessAverage').textContent = summary.averages.usefulness || '—';
    $('#pricingSignals').innerHTML = rows(summary.pricing); $('#pageAreas').innerHTML = rows(summary.page_areas); $('#taskSuccess').innerHTML = rows(summary.task_success); $('#creditUses').innerHTML = rows(summary.credit_uses);
    const creditRows = Object.entries(summary.average_credits_by_price || {}).map(([label,count]) => ({label,count}));
    $('#creditExpectations').innerHTML = rows(creditRows, ' avg.');
    $('#customAverage').textContent = summary.average_custom_price ? `Average custom amount: $${Number(summary.average_custom_price).toFixed(2)} per month.` : 'No custom amounts yet.';
    renderResponses(responses.items); $('#lastRefresh').textContent = `Updated ${new Date().toLocaleTimeString()}`;
  }

  async function load() {
    const [summary,responses] = await Promise.all([api('/owner/feedback/summary'),api('/owner/feedback/responses?limit=250')]);
    render(summary,responses);
  }

  async function unlock(event) {
    event?.preventDefault(); state.key = $('#adminKeyInput').value.trim(); state.actor = $('#actorInput').value.trim() || 'PJ'; $('#loginError').hidden = true;
    try { await load(); sessionStorage.setItem('wc_admin_key',state.key); sessionStorage.setItem('wc_admin_actor',state.actor); $('#loginPanel').hidden = true; $('#dashboard').hidden = false; $('#lockButton').hidden = false; $('#connectionBadge').textContent = 'Owner connected'; $('#connectionBadge').className = 'connection-badge online'; }
    catch (error) { state.key = ''; $('#loginError').textContent = error.message; $('#loginError').hidden = false; }
  }

  async function refresh() {
    $('#refreshButton').disabled = true; try { await load(); toast('Feedback refreshed.'); } catch (error) { toast(error.message,true); } finally { $('#refreshButton').disabled = false; }
  }

  function downloadCsv() {
    if (!state.responses.length) { toast('There are no responses to download yet.',true); return; }
    const fields = ['id','created_at','respondent_name','visitor_type','page_area','ease_score','ui_score','usefulness_score','task_success','most_useful','improvements','missing_feature','price_choice','custom_monthly_price','monthly_credits','credit_uses','additional_notes'];
    const cell = (value) => `"${String(Array.isArray(value) ? value.join('|') : value ?? '').replaceAll('"','""')}"`;
    const csv = [fields.join(','),...state.responses.map((item) => fields.map((field) => cell(item[field])).join(','))].join('\r\n');
    const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob([csv],{type:'text/csv;charset=utf-8'})); link.download = `wonder-codex-feedback-${new Date().toISOString().slice(0,10)}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(link.href),1000);
  }

  $('#loginForm').addEventListener('submit',unlock); $('#lockButton').addEventListener('click',lock); $('#refreshButton').addEventListener('click',refresh); $('#downloadButton').addEventListener('click',downloadCsv);
  const savedKey = sessionStorage.getItem('wc_admin_key'); const savedActor = sessionStorage.getItem('wc_admin_actor'); if (savedActor) $('#actorInput').value = savedActor;
  if (savedKey && savedActor) { state.key = savedKey; state.actor = savedActor; $('#adminKeyInput').value = savedKey; unlock(); }
})();
