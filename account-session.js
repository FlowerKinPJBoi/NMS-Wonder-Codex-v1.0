(() => {
  'use strict';

  const API = '/api';
  let client = null;
  let session = null;
  let profile = null;

  async function responseData(response) {
    let data = {};
    try { data = await response.json(); } catch {}
    if (!response.ok) throw new Error(data.detail || `Request failed (${response.status})`);
    return data;
  }

  async function loadProfile() {
    if (!session?.access_token) { profile = null; return null; }
    const data = await responseData(await fetch(`${API}/account/me`, {
      headers: {Authorization: `Bearer ${session.access_token}`},
    }));
    profile = data.profile;
    window.dispatchEvent(new CustomEvent('wc-account-change', {detail: {session, profile}}));
    return profile;
  }

  async function initialize() {
    const config = await responseData(await fetch(`${API}/auth/config`));
    if (!config.enabled || !window.supabase?.createClient) {
      return {enabled: false, session: null, profile: null};
    }
    client = window.supabase.createClient(config.supabase_url, config.supabase_anon_key, {
      auth: {persistSession: true, autoRefreshToken: true, detectSessionInUrl: true},
    });
    const result = await client.auth.getSession();
    session = result.data.session;
    if (session) await loadProfile();
    client.auth.onAuthStateChange((_event, nextSession) => {
      session = nextSession;
      setTimeout(() => loadProfile().catch(() => {}), 0);
    });
    return {enabled: true, session, profile};
  }

  const ready = initialize().catch((error) => ({enabled: false, session: null, profile: null, error}));

  window.WCAccount = {
    ready,
    get client() { return client; },
    get session() { return session; },
    get profile() { return profile; },
    async signInWithDiscord() {
      if (!client) throw new Error('Wonder Codex accounts are not enabled yet.');
      return client.auth.signInWithOAuth({
        provider: 'discord',
        options: {redirectTo: `${location.origin}/account.html`},
      });
    },
    async sendMagicLink(email) {
      if (!client) throw new Error('Wonder Codex accounts are not enabled yet.');
      return client.auth.signInWithOtp({
        email,
        options: {emailRedirectTo: `${location.origin}/account.html`},
      });
    },
    async signOut() {
      if (client) await client.auth.signOut();
      session = null;
      profile = null;
      location.reload();
    },
    async saveProfile(changes) {
      if (!session?.access_token) throw new Error('Sign in to save your profile.');
      const data = await responseData(await fetch(`${API}/account/me`, {
        method: 'PATCH',
        headers: {
          Authorization: `Bearer ${session.access_token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(changes),
      }));
      profile = data.profile;
      window.dispatchEvent(new CustomEvent('wc-account-change', {detail: {session, profile}}));
      return profile;
    },
  };
})();
