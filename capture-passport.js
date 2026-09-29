(() => {
  'use strict';
  const storageKey = 'wc-capture-connection';
  const codePattern = /^[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}-[A-HJ-NP-Z2-9]{4}$/;
  const $ = (id) => document.getElementById(id);
  const url = new URL(location.href);
  const incoming = url.searchParams.get('capture');
  let pending = null;
  let busy = false;
  let finished = false;
  let lastProfile = null;

  if (incoming !== null) {
    // Keep only the short, non-secret approval code across the existing OAuth redirect.
    url.searchParams.delete('capture');
    history.replaceState(null, '', url.pathname + url.search + url.hash);
    if (codePattern.test(incoming)) pending = {code: incoming, expires: Date.now() + 600000};
    try {
      sessionStorage.removeItem(storageKey);
      if (pending) sessionStorage.setItem(storageKey, JSON.stringify(pending));
    } catch {}
  } else {
    try { pending = JSON.parse(sessionStorage.getItem(storageKey)); } catch {}
  }
  if (!pending || !codePattern.test(pending.code) || !(pending.expires > Date.now())) {
    try { sessionStorage.removeItem(storageKey); } catch {}
    return;
  }

  $('captureConnect').hidden = false;
  $('captureConnectCode').textContent = pending.code;

  function update() {
    const profile = window.WCAccount.profile;
    if (lastProfile !== profile?.id) {
      $('captureCodeMatches').checked = false;
      lastProfile = profile?.id;
    }
    const allowed = profile?.account_status === 'active' && ['tester', 'admin'].includes(profile.access_tier);
    $('captureConnectIdentity').textContent = !profile
      ? 'Sign in below with your Galactic Passport to continue.'
      : allowed ? `Connect as ${profile.contributor_name} (${profile.access_tier}).`
      : `Signed in as ${profile.contributor_name}. Capture Companion currently requires a Tester or Admin Passport; ask PJ to enable Tester access.`;
    $('captureApprove').disabled = busy || finished || !allowed || !$('captureCodeMatches').checked;
    $('captureDecline').disabled = busy || finished || !profile;
    $('captureCodeMatches').disabled = busy || finished;
  }

  async function decide(approved) {
    update();
    if ($(approved ? 'captureApprove' : 'captureDecline').disabled) return;
    busy = true;
    update();
    $('captureConnectResult').textContent = 'Connecting…';
    try {
      const token = window.WCAccount.session?.access_token;
      if (!token) throw new Error('Sign in to your Passport again.');
      const response = await fetch('/api/auth/capture/approve', {
        method: 'POST', cache: 'no-store',
        headers: {'Content-Type': 'application/json', Authorization: `Bearer ${token}`},
        body: JSON.stringify({user_code: pending.code, approved, code_confirmed: $('captureCodeMatches').checked}),
      });
      const data = await response.json();
      if (!response.ok || data.ok !== true) throw new Error(data.detail || 'Connection could not be completed. Start sign-in again in Capture Companion.');
      finished = true;
      try { sessionStorage.removeItem(storageKey); } catch {}
      $('captureConnectResult').textContent = approved
        ? 'Connected. Return to Capture Companion to review and send your pairs. You can close this tab.'
        : 'Connection declined. You can close this tab.';
    } catch (error) {
      $('captureConnectResult').textContent = error.message;
    } finally { busy = false; update(); }
  }

  $('captureCodeMatches').addEventListener('change', update);
  $('captureApprove').addEventListener('click', () => decide(true));
  $('captureDecline').addEventListener('click', () => decide(false));
  window.addEventListener('wc-account-change', update);
  window.WCAccount.ready.then(update);
  update();
})();
