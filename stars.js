(() => {
  'use strict';

  const DATA_URL = 'research/star_system_census_v1.json?v=1.21.0';
  const colors = Object.freeze({
    Yellow: '#ffd783',
    Red: '#ff7d86',
    Green: '#72efbd',
    Blue: '#6de7ff',
    Purple: '#b7a4ff',
  });
  const state = {data: null, color: 'All', query: ''};
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (character) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));

  function familyCard(item) {
    const color = colors[item.color] || '#6de7ff';
    return `<article class="stellar-family" style="--star-color:${color}">
      <span class="stellar-family-mark" aria-hidden="true">✦</span>
      <h3><span>${escapeHtml(item.color)}</span> · ${escapeHtml(item.spectralFamilies.join(' / '))}</h3>
      <p>${item.samples} independently paired systems</p>
      <dl><dt>Water systems</dt><dd>${item.water} / ${item.samples}</dd><dt>Dissonant</dt><dd>${item.dissonant} / ${item.samples}</dd></dl>
    </article>`;
  }

  function rowMarkup(item) {
    const color = colors[item.starColor] || '#6de7ff';
    const environment = item.dissonant ? 'Dissonant' : item.water ? 'Water' : 'Standard';
    return `<tr>
      <td><span class="stellar-id">${escapeHtml(item.researchId)}</span></td>
      <td><span class="stellar-system">${escapeHtml(item.systemName)}</span><br><small>Galaxy ${item.galaxyNumber} · ${escapeHtml(item.galaxyName)}</small></td>
      <td><span class="star-chip" style="--chip-color:${color}">${escapeHtml(item.starColor)}</span></td>
      <td><strong>${escapeHtml(item.spectralLabel)}</strong></td>
      <td><span class="environment-chip ${item.dissonant ? 'dissonant' : ''}">${environment}</span></td>
      <td>${Number(item.planetPages).toLocaleString()}</td>
      <td><span class="evidence-chip">${escapeHtml(item.confidence)}</span></td>
    </tr>`;
  }

  function renderRows() {
    const systems = state.data?.systems || [];
    const query = state.query.toLowerCase();
    const filtered = systems.filter((item) => (
      (state.color === 'All' || item.starColor === state.color)
      && (!query || `${item.systemName} ${item.spectralLabel} ${item.researchId}`.toLowerCase().includes(query))
    ));
    $('#stellarCount').textContent = `${filtered.length} of ${systems.length} verified systems`;
    $('#stellarRows').innerHTML = filtered.length
      ? filtered.map(rowMarkup).join('')
      : '<tr><td colspan="7">No verified systems match this view.</td></tr>';
  }

  function renderFilters() {
    $('#stellarFilters').innerHTML = ['All', ...Object.keys(colors)].map((color) => (
      `<button class="stellar-filter ${color === state.color ? 'active' : ''}" type="button" data-color="${color}" style="--filter-color:${color === 'All' ? '#6de7ff' : colors[color]}">${color}</button>`
    )).join('');
    document.querySelectorAll('.stellar-filter').forEach((button) => button.addEventListener('click', () => {
      state.color = button.dataset.color;
      renderFilters();
      renderRows();
    }));
  }

  async function load() {
    try {
      const response = await fetch(DATA_URL);
      const data = await response.json();
      if (!response.ok || !Array.isArray(data.systems)) throw new Error('Stellar research could not be loaded.');
      state.data = data;
      $('#starVerified').textContent = Number(data.summary.verifiedSystems).toLocaleString();
      $('#starScreens').textContent = Number(data.summary.mapScreenshots).toLocaleString();
      $('#starPlanets').textContent = Number(data.summary.planetScreenshots).toLocaleString();
      $('#starMedian').textContent = `${Number(data.summary.medianMapToDiscoverySeconds).toLocaleString()} sec`;
      $('#stellarFamilies').innerHTML = data.colorFamilies.map(familyCard).join('');
      $('#stellarFindings').innerHTML = data.findings.map((finding) => `<li>${escapeHtml(finding)}</li>`).join('');
      renderFilters();
      renderRows();
      window.WonderAnalytics?.track('stellar_census_view', {verified_systems: data.summary.verifiedSystems});
    } catch (error) {
      $('#stellarFamilies').innerHTML = `<div class="notice error">${escapeHtml(error.message)}</div>`;
      $('#stellarRows').innerHTML = `<tr><td colspan="7">${escapeHtml(error.message)}</td></tr>`;
    }
  }

  $('#stellarSearch').addEventListener('input', (event) => {
    state.query = event.target.value.trim();
    renderRows();
  });
  load();
})();
