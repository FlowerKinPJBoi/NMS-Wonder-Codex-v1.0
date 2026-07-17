(() => {
  'use strict';

  const BLOB_EXAMPLE = 'ZqniBgA6MQADAAAAAwAAAHyJB5PlyI65muhaQA1PffQNWecLX+bHLQ==';
  const $ = (selector) => document.querySelector(selector);
  let currentRoute = null;

  function showToast(message) {
    const toast = $('#decoderToast');
    toast.textContent = message;
    toast.hidden = false;
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => { toast.hidden = true; }, 3000);
  }

  function setError(message = '') {
    const error = $('#decoderError');
    error.textContent = message;
    error.hidden = !message;
  }

  function isAuthorizedOperator() {
    try {
      return Boolean(sessionStorage.getItem('wc_admin_key') && sessionStorage.getItem('wc_admin_actor'));
    } catch {
      return false;
    }
  }

  function configureTransit() {
    const button = $('#decoderTransit');
    const authorized = isAuthorizedOperator();
    button.disabled = !(authorized && currentRoute);
    button.textContent = authorized
      ? currentRoute ? 'PEGASUS TRANSIT — Download admin route' : 'PEGASUS TRANSIT — Decode a route first'
      : 'PEGASUS TRANSIT — Authorized operators only';
  }

  function renderResult(projector, location) {
    currentRoute = {...projector, ...location};
    $('#decoderType').textContent = `${projector.discoveryLabel} Projector ID`;
    $('#decoderGalaxy').textContent = `Galaxy ${location.galaxy_number} — ${location.galaxy_name || 'Unknown galaxy name'}`;
    $('#decoderGalaxyNumber').textContent = location.galaxy_number;
    $('#decoderGalaxyName').textContent = location.galaxy_name || 'Not catalogued';
    $('#decoderRouteSource').textContent = 'Decoded from Message ID';
    $('#decoderRouteStatus').textContent = 'Route derived — revisit unverified';
    WCGlyphs.render('#decoderGlyphs', location.portal_glyphs);
    $('#decoderGlyphCode').textContent = location.portal_glyphs;
    $('#decoderResult').hidden = false;
    configureTransit();
    window.WonderAnalytics?.track('projector_decode', {
      decoder_result: 'success',
      discovery_type: projector.discoveryType,
    });
  }

  function decode() {
    setError();
    currentRoute = null;
    $('#decoderResult').hidden = true;
    configureTransit();
    try {
      const projector = WCProjector.decodeMessageId($('#projectorMessageId').value);
      const location = WCLocation.decode(projector.universalAddressHex);
      if (!location) throw new Error('The embedded location could not be decoded.');
      renderResult(projector, location);
      $('#decoderResult').scrollIntoView({behavior: 'smooth', block: 'nearest'});
    } catch (error) {
      setError(error instanceof Error ? error.message : 'The Message ID could not be decoded.');
      window.WonderAnalytics?.track('projector_decode', {decoder_result: 'invalid'});
    }
  }

  async function copyGlyphs() {
    if (!currentRoute) return;
    try {
      await WCGlyphs.copy(currentRoute.portal_glyphs);
      showToast('Portal glyph code copied.');
    } catch {
      showToast('Copy failed. Select the glyph code and copy it manually.');
    }
  }

  function downloadTransitTicket() {
    if (!currentRoute || !isAuthorizedOperator()) return;
    const ticket = {
      format: 'wonder-codex-transit/0.1',
      wc_record_id: 'PROJECTOR-DECODED',
      galaxy_number: currentRoute.galaxy_number,
      galaxy_name: currentRoute.galaxy_name || '',
      portal_glyphs: currentRoute.portal_glyphs,
      universal_address: `0x${currentRoute.universalAddressHex}`,
      generated_utc: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(ticket, null, 2)], {type: 'application/vnd.wonder-codex.transit+json'});
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `Wonder-Projector-Route-G${currentRoute.galaxy_number}-${currentRoute.portal_glyphs}.wctransit`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(link.href), 0);
    window.WonderAnalytics?.track('transit_ticket_download', {entity_type: 'projector_decode', download_type: 'wctransit'});
    showToast('Pegasus Transit operator route downloaded.');
  }

  $('#projectorDecoderForm').addEventListener('submit', (event) => {
    event.preventDefault();
    decode();
  });
  $('#useBlobExample').addEventListener('click', () => {
    $('#projectorMessageId').value = BLOB_EXAMPLE;
    $('#projectorMessageId').focus();
    setError();
  });
  $('#copyDecoderGlyphs').addEventListener('click', copyGlyphs);
  $('#decoderTransit').addEventListener('click', downloadTransitTicket);
  configureTransit();
})();
