(() => {
  'use strict';

  if (location.pathname.toLowerCase().startsWith('/admin')) return;
  const dnt = navigator.doNotTrack || globalThis.doNotTrack || navigator.msDoNotTrack;
  if (dnt === '1' || dnt === 'yes' || navigator.globalPrivacyControl === true) return;

  const ENDPOINT = '/api/analytics/events';
  const SESSION_KEY = 'wc_analytics_session';
  const allowedProperties = new Set([
    'page_kind', 'entity_type', 'entity_id', 'catalog_lane', 'discovery_type',
    'fauna_family', 'location_status', 'image_status', 'query_kind',
    'query_length', 'result_count', 'has_query', 'map_galaxy', 'map_lane',
    'map_quality', 'evidence_type', 'download_type', 'public_attribution',
  ]);

  function newSessionId() {
    if (globalThis.crypto?.randomUUID) return crypto.randomUUID();
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`;
  }

  function sessionId() {
    try {
      let value = sessionStorage.getItem(SESSION_KEY);
      if (!value) {
        value = newSessionId();
        sessionStorage.setItem(SESSION_KEY, value);
      }
      return value;
    } catch {
      return newSessionId();
    }
  }

  function pageKind() {
    const name = location.pathname.split('/').filter(Boolean).pop() || 'index.html';
    return name.replace(/\.html$/i, '') || 'home';
  }

  function cleanProperties(values = {}) {
    return Object.fromEntries(Object.entries(values).filter(([key, value]) => (
      allowedProperties.has(key) && ['string', 'number', 'boolean'].includes(typeof value)
    )));
  }

  function track(eventType, properties = {}) {
    const payload = JSON.stringify({
      session_id: sessionId(),
      event_type: eventType,
      path: location.pathname,
      title: document.title,
      referrer: document.referrer,
      properties: cleanProperties({page_kind: pageKind(), ...properties}),
    });
    fetch(ENDPOINT, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: payload,
      keepalive: true,
      credentials: 'omit',
    }).catch(() => {});
  }

  function queryKind(value) {
    const query = String(value || '').trim();
    if (!query) return 'none';
    if (/^WC-[A-Z]{1,3}-\d+$/i.test(query)) return 'wc_id';
    if (/^\d+$/.test(query)) return 'numeric_id';
    return 'text';
  }

  document.addEventListener('click', (event) => {
    const link = event.target.closest('a[href]');
    if (!link) return;
    const href = link.getAttribute('href') || '';
    const downloadType = link.dataset.analyticsDownload
      || (/\.(zip|json|csv|pdf|docx)$/i.exec(href)?.[1] || '');
    if (downloadType) track('download', {download_type: downloadType.toLowerCase()});
  });

  window.WonderAnalytics = {track, queryKind};
  track('page_view');
})();
