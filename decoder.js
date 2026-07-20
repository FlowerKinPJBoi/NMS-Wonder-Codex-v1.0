(() => {
  'use strict';

  const BLOB_EXAMPLE = 'ZqniBgA6MQADAAAAAwAAAHyJB5PlyI65muhaQA1PffQNWecLX+bHLQ==';
  const RESEARCH_POOLS = {
    Flora: {
      ua: ['0x208BFF11112111', '0x1103FF11111111'],
      vp0: ['0x024B1D416BFF2A12', '0x8D01BE6AE65B07F0', '0xF243322E6E74D901'],
      vp1: ['0x535A637B0E58E6D3', '0x8BA72147379E272A'],
    },
    Mineral: {
      ua: ['0x208BFF11112111', '0x1103FF11111111'],
      vp0: ['0xBA570CFA38C0C9F8', '0x34C4C1888E917FA1', '0xE605AFADE7034D74', '0x95670B579DF1CBC3', '0xA92CFCCD8AB2F675', '0xF22A39042CBF4526', '0xE02C503198DC5B5D'],
      vp1: ['0xB2702F9F5BC0ABEC', '0xD09E5E2E3D41357C', '0xBC21B504577D421C', '0x083ED8ABA804EC05', '0x00D1D43C68097536', '0x47E2752B21A2A3BC', '0x0142F4675BC8D11B'],
    },
  };
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
    $('#decoderIdentityModel').textContent = `VP1 visual-family signal present · VP0 generated-name/individual signal present · ${projector.vpCount} VP components · complete Message ID supports exact cross-account reproduction.`;
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

  function randomIndex(length) {
    if (globalThis.crypto?.getRandomValues) {
      const value = new Uint32Array(1);
      globalThis.crypto.getRandomValues(value);
      return value[0] % length;
    }
    return Math.floor(Math.random() * length);
  }

  function pick(values) { return values[randomIndex(values.length)]; }

  async function documentedRandomWonder() {
    const first = await fetch('/api/discoveries?limit=1&offset=0');
    const firstData = await first.json();
    if (!first.ok) throw new Error(firstData.detail || 'The public catalog could not be reached.');
    const total = Number(firstData.total || 0);
    if (!total) throw new Error('No public Wonder records are available yet.');
    for (let attempt = 0; attempt < 6; attempt += 1) {
      const offset = randomIndex(total);
      const response = await fetch(`/api/discoveries?limit=1&offset=${offset}`);
      const data = await response.json();
      const record = data.items?.[0];
      if (response.ok && record?.message_id) {
        return {messageId: record.message_id, note: `Documented catalog specimen ${record.wc_id} · ${record.display_name}`};
      }
    }
    throw new Error('A documented Projector ID was not found after several random selections. Try again.');
  }

  function researchRandomWonder(discoveryType) {
    const pool = RESEARCH_POOLS[discoveryType];
    return {
      messageId: WCProjector.encodeMessageId({
        universalAddress: pick(pool.ua),
        discoveryType,
        vpValues: [pick(pool.vp0), pick(pool.vp1)],
      }),
      note: `${discoveryType} research remix · VP0 individual/name component + VP1 visual-family component · not catalog-verified`,
    };
  }

  async function randomWonder() {
    const button = $('#randomWonder');
    const status = $('#randomWonderStatus');
    button.disabled = true;
    button.textContent = 'Opening Wonder…';
    try {
      const mode = $('#randomWonderMode').value;
      const result = mode === 'catalog'
        ? await documentedRandomWonder()
        : researchRandomWonder(mode === 'flora' ? 'Flora' : 'Mineral');
      $('#projectorMessageId').value = result.messageId;
      status.textContent = result.note;
      decode();
      window.WonderAnalytics?.track('random_wonder', {randomizer_mode: mode});
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : 'A random Wonder could not be created.';
    } finally {
      button.disabled = false;
      button.innerHTML = 'Random Wonder <span aria-hidden="true">✦</span>';
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
  $('#randomWonder').addEventListener('click', randomWonder);
  configureTransit();
})();
