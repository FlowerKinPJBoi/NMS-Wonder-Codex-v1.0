const $ = (selector) => document.querySelector(selector);

const menuButton = $('.menu-toggle');
const navigation = $('#primaryNav');
if (menuButton && navigation) {
  menuButton.addEventListener('click', () => {
    const open = navigation.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(open));
  });
  navigation.querySelectorAll('a').forEach((link) => link.addEventListener('click', () => {
    navigation.classList.remove('open');
    menuButton.setAttribute('aria-expanded', 'false');
  }));
}

document.querySelectorAll('a[href^="#"]').forEach((link) => {
  link.addEventListener('click', (event) => {
    const target = document.querySelector(link.getAttribute('href'));
    if (!target) return;
    event.preventDefault();
    target.scrollIntoView({behavior: 'smooth', block: 'start'});
  });
});

function setText(id, value) {
  const element = document.getElementById(id);
  if (element) element.textContent = value;
}

function formatNumber(value) {
  const number = Number(value || 0);
  return Number.isFinite(number) ? number.toLocaleString() : '—';
}

async function loadStats() {
  const status = $('#apiStatus');
  try {
    const response = await fetch('/api/stats', {headers: {'Accept': 'application/json'}});
    if (!response.ok) throw new Error(`Status ${response.status}`);
    const data = await response.json();
    setText('statDiscoveries', formatNumber(data.published_discoveries));
    setText('statPending', formatNumber(data.pending_submissions));
    setText('statContributors', formatNumber(data.contributors));
    setText('statMatches', formatNumber(data.published_pet_matches));
    setText('statAnimals', formatNumber(data.types?.Animal));
    setText('statFlora', formatNumber(data.types?.Flora));
    setText('statMinerals', formatNumber(data.types?.Mineral));
    setText('statsNote', data.latest_approved_at ? `Last publication ${new Date(data.latest_approved_at).toLocaleString()}.` : 'The first approved records will appear here.');
    if (status) { status.textContent = 'Online'; status.className = 'console-status online'; }
  } catch (error) {
    if (status) { status.textContent = 'API online • stats pending'; status.className = 'console-status'; }
    setText('statsNote', 'Live statistics will appear after the v1.1 API deploys.');
  }
}

if ($('#apiStatus')) loadStats();
