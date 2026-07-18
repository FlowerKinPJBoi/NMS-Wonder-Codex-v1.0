(() => {
  'use strict';

  const form = document.getElementById('feedbackForm');
  if (!form) return;

  const state = {step: 1, total: 4};
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];
  const labels = {
    visitor_type: {alpha_beta_tester:'Alpha or beta tester',contributor:'Contributor',explorer:'Explorer / catalog user',first_time_visitor:'First-time visitor',admin_operator:'Admin or operator',other:'Other'},
    page_area: {overall_site:'Overall Wonder Codex site',database_catalog:'Wonder Database / catalog',cluster_map:'Galactic Cluster Map',projector_decoder:'Wonder Projector Decoder',contribution_importer:'Contributions / Importer',private_apps:'Private application vault',pegasus_transit:'Pegasus Transit',capture_companion:'Capture Companion',other:'Other page or tool'},
    task_success: {yes:'Yes — completed it',partly:'Partly — some friction',no:'No — could not finish',browsing:'Just browsing'},
    price_choice: {'5':'$5 per month','10':'$10 per month',custom:'Custom monthly amount',none:'I would not pay'},
  };

  function value(name) {
    return form.elements[name]?.value || '';
  }

  function renderStep(shouldScroll = true) {
    $$('.feedback-step', form).forEach((section) => { section.hidden = Number(section.dataset.step) !== state.step; });
    $$('[data-progress-step]').forEach((item) => {
      const step = Number(item.dataset.progressStep);
      item.classList.toggle('active', step === state.step);
      item.classList.toggle('complete', step < state.step);
    });
    $('#stepLabel').textContent = `Step ${state.step} of ${state.total}`;
    $('#stepFill').style.width = `${state.step / state.total * 100}%`;
    $('#backButton').hidden = state.step === 1;
    $('#nextButton').hidden = state.step === state.total;
    $('#submitButton').hidden = state.step !== state.total;
    $('#formError').hidden = true;
    if (state.step === state.total) renderReview();
    if (shouldScroll) $('.feedback-surface').scrollIntoView({behavior:'smooth', block:'start'});
  }

  function validateStep() {
    const section = $(`.feedback-step[data-step="${state.step}"]`, form);
    const controls = $$('input,select,textarea', section).filter((control) => !control.disabled);
    for (const control of controls) {
      if (!control.checkValidity()) {
        control.reportValidity();
        return false;
      }
    }
    return true;
  }

  function updatePricing() {
    const choice = value('price_choice');
    const custom = $('#customPricePanel');
    const credits = $('#creditPanel');
    const customInput = form.elements.custom_monthly_price;
    const creditInput = form.elements.monthly_credits;
    const paying = choice && choice !== 'none';
    custom.hidden = choice !== 'custom';
    credits.hidden = !paying;
    customInput.required = choice === 'custom';
    creditInput.required = paying;
    if (choice !== 'custom') customInput.value = '';
    if (!paying) {
      creditInput.value = '';
      $$('input[name="credit_uses"]', form).forEach((input) => { input.checked = false; });
    }
  }

  function renderReview() {
    const price = labels.price_choice[value('price_choice')] || '—';
    const custom = value('custom_monthly_price');
    const credits = value('monthly_credits');
    const items = [
      ['Reviewing', labels.page_area[value('page_area')] || '—'],
      ['Visitor type', labels.visitor_type[value('visitor_type')] || '—'],
      ['Task result', labels.task_success[value('task_success')] || '—'],
      ['Ease / UI / usefulness', `${value('ease_score')} / ${value('ui_score')} / ${value('usefulness_score')}`],
      ['Monthly preference', custom ? `$${Number(custom).toFixed(2)} per month` : price],
      ['Expected credits', credits ? `${credits} per month` : 'Not applicable'],
    ];
    $('#reviewSummary').replaceChildren(...items.map(([name, answer]) => {
      const row = document.createElement('div');
      const caption = document.createElement('span'); caption.textContent = name;
      const strong = document.createElement('strong'); strong.textContent = answer;
      row.append(caption, strong); return row;
    }));
  }

  function payload() {
    const choice = value('price_choice');
    return {
      respondent_name: value('respondent_name').trim(),
      visitor_type: value('visitor_type'),
      page_area: value('page_area'),
      ease_score: Number(value('ease_score')),
      ui_score: Number(value('ui_score')),
      usefulness_score: Number(value('usefulness_score')),
      task_success: value('task_success'),
      most_useful: value('most_useful').trim(),
      improvements: value('improvements').trim(),
      missing_feature: value('missing_feature').trim(),
      price_choice: choice,
      custom_monthly_price: choice === 'custom' ? value('custom_monthly_price') : null,
      monthly_credits: choice !== 'none' ? Number(value('monthly_credits')) : null,
      credit_uses: $$('input[name="credit_uses"]:checked', form).map((input) => input.value),
      additional_notes: value('additional_notes').trim(),
      research_consent: form.elements.research_consent.checked,
      website: value('website'),
    };
  }

  async function submit(event) {
    event.preventDefault();
    if (!validateStep()) return;
    const button = $('#submitButton');
    const error = $('#formError');
    button.disabled = true; button.textContent = 'Transmitting…'; error.hidden = true;
    try {
      const response = await fetch('/api/feedback', {
        method: 'POST',
        headers: {'Content-Type':'application/json','Accept':'application/json'},
        credentials: 'omit',
        body: JSON.stringify(payload()),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || `Feedback could not be sent (${response.status}).`);
      window.WonderAnalytics?.track('feedback_submitted');
      form.hidden = true; $('.step-meter').hidden = true; $('#successPanel').hidden = false;
    } catch (reason) {
      error.textContent = reason.message || 'Feedback could not be sent. Please try again.'; error.hidden = false;
    } finally {
      button.disabled = false; button.textContent = 'Send feedback to PJ';
    }
  }

  $('#nextButton').addEventListener('click', () => { if (validateStep()) { state.step += 1; renderStep(); } });
  $('#backButton').addEventListener('click', () => { state.step -= 1; renderStep(); });
  $$('input[name="price_choice"]', form).forEach((input) => input.addEventListener('change', updatePricing));
  form.addEventListener('submit', submit);
  renderStep(false);
})();
