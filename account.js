(() => {
  'use strict';
  const $ = (selector) => document.querySelector(selector);

  function result(message, error = false) {
    const node = $('#accountResult');
    node.textContent = message;
    node.className = `notice account-result${error ? ' error' : ' success'}`;
    node.hidden = false;
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
    $('#profileFriendCode').value = profile.nms_friend_code || '';
    $('#profileBotConsent').checked = profile.bot_connect_consent;
    $('#friendCodeStatus').textContent = profile.friend_code_verified
      ? 'Friend code verified for future services.'
      : profile.has_nms_friend_code
        ? 'Friend code stored privately; verification will come with Wonder Bot.'
        : 'No friend code stored yet.';
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
        nms_friend_code: $('#profileFriendCode').value.trim(),
        bot_connect_consent: $('#profileBotConsent').checked,
      });
      showProfile(profile);
      result('Galactic Passport saved.');
    } catch (error) { result(error.message, true); }
  });
  $('#signOut').addEventListener('click', () => window.WCAccount.signOut());
  start().catch((error) => result(error.message, true));
})();
