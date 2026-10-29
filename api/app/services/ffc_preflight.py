"""Read-only Discord checks before the PC host is stopped for handoff.

Only the configured cloud credential is used. These requests never connect to
the Gateway, register commands, post a message, or forward a redirect.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import ssl
import time
from datetime import datetime, timezone

from ffc_game.ffc_wilds.cloud_control import (
    APPLICATION_ID, CHANNEL_ID, GUILD_ID, ControlConflict, ControlError,
    ControlUnavailable,
)

DISCORD_HOST = "discord.com"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
REQUIRED_PERMISSIONS = {
    "view_channel": 1 << 10,
    "send_messages": 1 << 11,
    "embed_links": 1 << 14,
    "attach_files": 1 << 15,
    "read_message_history": 1 << 16,
}
ADMINISTRATOR = 1 << 3
MESSAGE_CONTENT_FLAGS = (1 << 18) | (1 << 19)


def _discord_get(path: str, token: str) -> dict:
    # A fixed destination and direct HTTPS connection avoid proxy redirects or
    # user-supplied URLs receiving the Authorization header.
    connection = http.client.HTTPSConnection(DISCORD_HOST, timeout=8,
                                              context=ssl.create_default_context())
    try:
        connection.request("GET", "/api/v10" + path, headers={
            "Authorization": "Bot " + token,
            "Accept": "application/json",
            "User-Agent": "DiscordBot (https://wondercodex.com, FFC-Wilds-0.3.0)",
        })
        response = connection.getresponse()
        if response.status == 401:
            raise ControlConflict("The configured cloud Discord token was rejected. Keep the PC host running.")
        if response.status in (403, 404):
            raise ControlConflict("The cloud bot cannot access the required FFC server or game channel. Keep the PC host running.")
        if response.status != 200:
            raise ControlUnavailable("Discord verification is temporarily unavailable. Keep the PC host running and try again later.")
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise ControlUnavailable("Discord verification returned an unexpected response.")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ControlUnavailable("Discord verification returned an unexpected response.")
        return result
    except ControlError:
        raise
    except Exception:
        # Neither HTTP errors, response bodies, TLS details, nor request headers
        # reach the API incident tracker or the caller.
        raise ControlUnavailable("Discord verification could not be completed. Keep the PC host running and try again later.") from None
    finally:
        connection.close()


def _bits(value) -> int:
    if isinstance(value, str) and re.fullmatch(r"[0-9]{1,30}", value):
        return int(value)
    if type(value) is int and 0 <= value < (1 << 100):
        return value
    raise ControlUnavailable("Discord permission verification returned an unexpected response.")


def _permissions(guild: dict, member: dict, channel: dict, bot_id: str) -> dict:
    roles = guild.get("roles")
    member_roles = member.get("roles")
    overwrites = channel.get("permission_overwrites")
    if (not isinstance(roles, list) or not isinstance(member_roles, list)
            or not isinstance(overwrites, list) or not all(isinstance(v, str) for v in member_roles)):
        raise ControlUnavailable("Discord permission verification returned an unexpected response.")
    role_map = {role["id"]: role for role in roles if isinstance(role, dict) and isinstance(role.get("id"), str)}
    if GUILD_ID not in role_map or any(role not in role_map for role in member_roles):
        raise ControlUnavailable("Discord permission verification returned an incomplete role list.")
    bits = _bits(role_map[GUILD_ID].get("permissions"))
    for role in member_roles:
        bits |= _bits(role_map[role].get("permissions"))
    if bits & ADMINISTRATOR or guild.get("owner_id") == bot_id:
        return {name: True for name in REQUIRED_PERMISSIONS}

    # Discord's documented order: everyone, combined role overwrites, member.
    for scope in ("everyone", "roles", "member"):
        allow = deny = 0
        for overwrite in overwrites:
            if not isinstance(overwrite, dict):
                raise ControlUnavailable("Discord permission verification returned an unexpected response.")
            identity, kind = overwrite.get("id"), overwrite.get("type")
            selected = ((scope == "everyone" and kind == 0 and identity == GUILD_ID)
                        or (scope == "roles" and kind == 0 and identity != GUILD_ID and identity in member_roles)
                        or (scope == "member" and kind == 1 and identity == bot_id))
            if selected:
                allow |= _bits(overwrite.get("allow"))
                deny |= _bits(overwrite.get("deny"))
        bits = (bits & ~deny) | allow
    return {name: bool(bits & flag) for name, flag in REQUIRED_PERMISSIONS.items()}


def discord_preflight() -> dict:
    """Verify the configured bot without acquiring cloud leadership."""
    token = os.environ.get("FFC_DISCORD_BOT_TOKEN", "").strip()
    if not token:
        raise ControlConflict("Complete the cloud host's Discord token setup before handoff. Keep the PC host running.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]{20,256}", token):
        raise ControlConflict("The configured cloud Discord token has an invalid format. Keep the PC host running.")
    try:
        app = _discord_get("/applications/@me", token)
        if app.get("id") != APPLICATION_ID:
            raise ControlConflict("The configured cloud token belongs to another Discord application. Keep the PC host running.")
        if not _bits(app.get("flags", 0)) & MESSAGE_CONTENT_FLAGS:
            raise ControlConflict("Enable Message Content Intent for FFC Wilds before handoff. Keep the PC host running.")
        user = _discord_get("/users/@me", token)
        bot_id = user.get("id")
        if (user.get("bot") is not True or not isinstance(bot_id, str)
                or not re.fullmatch(r"[0-9]{15,22}", bot_id)
                or bot_id != APPLICATION_ID
                or (app.get("bot") and app["bot"].get("id") != bot_id)):
            raise ControlConflict("The cloud Discord bot identity could not be verified. Keep the PC host running.")
        guild = _discord_get("/guilds/" + GUILD_ID, token)
        channel = _discord_get("/channels/" + CHANNEL_ID, token)
        if (guild.get("id") != GUILD_ID or channel.get("id") != CHANNEL_ID
                or channel.get("guild_id") != GUILD_ID or channel.get("type") != 0):
            raise ControlConflict("The configured FFC text channel could not be verified. Keep the PC host running.")
        member = _discord_get("/guilds/" + GUILD_ID + "/members/" + bot_id, token)
        if not isinstance(member.get("user"), dict) or member["user"].get("id") != bot_id or member.get("pending"):
            raise ControlConflict("The cloud bot's FFC membership is not ready. Keep the PC host running.")
        until = member.get("communication_disabled_until")
        if until and datetime.fromisoformat(until.replace("Z", "+00:00")) > datetime.now(timezone.utc):
            raise ControlConflict("The cloud bot cannot send messages while timed out. Keep the PC host running.")
        permissions = _permissions(guild, member, channel, bot_id)
        missing = [name for name, present in permissions.items() if not present]
        if missing:
            raise ControlConflict("FFC Wilds needs these channel permissions before handoff: " + ", ".join(missing) + ". Keep the PC host running.")
    except ControlError:
        raise
    except Exception:
        raise ControlUnavailable("Discord verification could not be completed. Keep the PC host running and try again later.") from None
    return {"ok": True, "ready": True, "checked_at": time.time(), "application_id": APPLICATION_ID,
            "guild_id": GUILD_ID, "channel_id": CHANNEL_ID,
            "checks": {"application": True, "bot_account": True, "guild": True, "channel": True,
                       "message_content": True, "permissions": True},
            "permissions": permissions}
