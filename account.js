(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);
  const escapeHtml = (value) => String(value ?? '').replace(/[&<>"']/g, (char) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
  const platformLabel = (value) => ({
    steam: 'Steam',
    gog: 'GOG',
    xbox: 'Xbox / Game Pass',
    playstation: 'PlayStation',
    switch: 'Nintendo Switch',
  })[value] || 'Platform not selected';

  function result(message, error = false) {
    const node = $('#accountResult');
    node.textContent = message;
    node.className = `notice account-result${error ? ' error' : ' success'}`;
    node.hidden = false;
  }

  function renderNmsProfiles(profiles = []) {
    const node = $('#nmsProfiles');
    if (!profiles.length) {
      node.innerHTML = '<p class="account-note">No NMS profiles saved yet. Add the account you want Wonder Bot to join first.</p>';
      return;
    }
    node.innerHTML = profiles.map((profile) => {
      const state = profile.active ? 'Active' : 'Disabled';
      const verified = profile.native_owner_verified
        ? `Owner UID verified · ${escapeHtml(profile.native_owner_uid)}`
        : profile.friend_code_verified
          ? 'Friend Code verified'
          : 'Friend Code stored · owner verification pending';
      return `<article class="nms-profile-card${profile.active ? '' : ' disabled'}">
        <div class="nms-profile-heading">
          <div><strong>${escapeHtml(profile.label)}</strong><span>${escapeHtml(platformLabel(profile.platform))}</span></div>
          <div class="nms-profile-badges">
            ${profile.is_default ? '<span class="tier-badge">Default</span>' : ''}
            <span class="nms-state">${state}</span>
          </div>
        </div>
        <p>${verified}</p>
        <p>${profile.bot_connect_consent ? 'Bot connection allowed for explicit requests.' : 'Bot connection consent is off.'}</p>
        <div class="nms-profile-actions">
          ${profile.is_default ? '' : `<button class="text-button" type="button" data-nms-action="default" data-nms-id="${profile.id}">Make default</button>`}
          <button class="text-button" type="button" data-nms-action="toggle" data-nms-id="${profile.id}" data-nms-active="${profile.active}">${profile.active ? 'Disable' : 'Enable'}</button>
        </div>
      </article>`;
    }).join('');
  }

  function showProfile(profile) {
    $('#accountLoading').hidden = true;
    $('#accountUnavailable').hidden = true;
    $('#accountLogin').hidden = true;
    $('#accountProfile').hidden = false;
    $('#profileGreeting').textContent = `Welcome, ${profile.contributor_name}`;
    $('#tierBadge').textContent = profile.access_tier;
    $('#profileContributor').value = profile.contributor_name;
    $('#profilePlatform').value = profile.platform || '';
    $('#profilePrivate').checked = !profile.public_attribution;
    renderNmsProfiles(profile.nms_profiles || []);
  }

  async function start() {
    const status = await window.WCAccount.ready;
    $('#accountLoading').hidden = true;
    if (!status.enabled) {
      $('#accountUnavailable').hidden = false;
    } else if (status.profile) {
      showProfile(status.profile);
    } else {
      $('#accountLogin').hidden = false;
    }
  }

  $('#discordLogin').addEventListener('click', async () => {
    try { await window.WCAccount.signInWithDiscord(); } catch (error) { result(error.message, true); }
  });

  $('#magicForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await window.WCAccount.sendMagicLink($('#magicEmail').value.trim());
      result('Magic link sent. Check your inbox to finish signing in.');
    } catch (error) { result(error.message, true); }
  });

  $('#profileForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      const profile = await window.WCAccount.saveProfile({
        contributor_name: $('#profileContributor').value.trim(),
        public_attribution: !$('#profilePrivate').checked,
        platform: $('#profilePlatform').value,
      });
      showProfile(profile);
      result('Galactic Passport saved.');
    } catch (error) { result(error.message, true); }
  });

  $('#nmsProfileForm').addEventListener('submit', async (event) => {
    event.preventDefault();
    try {
      await window.WCAccount.createNmsProfile({
        label: $('#nmsProfileLabel').value.trim(),
        platform: $('#nmsProfilePlatform').value,
        nms_friend_code: $('#nmsProfileFriendCode').value.trim(),
        bot_connect_consent: $('#nmsProfileConsent').checked,
        is_default: $('#nmsProfileDefault').checked,
      });
      event.currentTarget.reset();
      showProfile(window.WCAccount.profile);
      result('NMS profile added. It is ready to select for future bot services.');
    } catch (error) { result(error.message, true); }
  });

  $('#nmsProfiles').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-nms-action]');
    if (!button) return;
    button.disabled = true;
    try {
      if (button.dataset.nmsAction === 'default') {
        await window.WCAccount.updateNmsProfile(button.dataset.nmsId, {is_default: true});
        result('Default NMS profile updated.');
      } else if (button.dataset.nmsAction === 'toggle') {
        await window.WCAccount.updateNmsProfile(button.dataset.nmsId, {
          active: button.dataset.nmsActive !== 'true',
        });
        result(button.dataset.nmsActive === 'true' ? 'NMS profile disabled.' : 'NMS profile enabled.');
      }
      showProfile(window.WCAccount.profile);
    } catch (error) {
      result(error.message, true);
      button.disabled = false;
    }
  });

  $('#signOut').addEventListener('click', () => window.WCAccount.signOut());
  start().catch((error) => result(error.message, true));
})();
