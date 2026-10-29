"""Owner controls that use the same game rules as the Discord host commands.

These actions never activate a cloud host. The runtime must already own the
game and have a verified Discord connection before accepting them.
"""
from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from typing import Any

from .activities import DRIVE_SECONDS
from .engine import COLLECTION_ACTIONS, GRADE_SECONDS, POWERUP_KINDS


class UncertainHostAction(RuntimeError):
    """The action must be inspected, never automatically submitted again."""


def validate_action(action: str, arguments: dict) -> dict:
    if not isinstance(arguments, dict):
        raise ValueError("Control arguments must be an object.")
    if action in {"start", "pause", "backup"}:
        if arguments:
            raise ValueError("This control does not accept extra options.")
        return {}
    if action == "mode":
        if set(arguments) != {"mode"} or arguments["mode"] not in {"community", "classic"}:
            raise ValueError("Choose community or classic mode.")
        return dict(arguments)
    if action == "spawn":
        if set(arguments) - {"kind", "grade"}:
            raise ValueError("Unknown spawn option.")
        kind = arguments.get("kind", "random")
        if kind not in {"random", *COLLECTION_ACTIONS, *POWERUP_KINDS}:
            raise ValueError("Choose a discovery or powerup type.")
        grade = arguments.get("grade")
        if grade is not None and (kind not in POWERUP_KINDS or grade not in GRADE_SECONDS):
            raise ValueError("C/B/A/S selection is available for powerup nodes only.")
        return {"kind": kind, "grade": grade}
    if action == "frenzy":
        if set(arguments) != {"grade"} or arguments["grade"] not in GRADE_SECONDS:
            raise ValueError("Choose a C, B, A, or S Frenzy.")
        return dict(arguments)
    if action == "power_drive":
        multiplier = arguments.get("multiplier")
        if set(arguments) != {"multiplier"} or type(multiplier) is not int or multiplier not in (2, 3):
            raise ValueError("Choose a double or triple Power Drive.")
        return {"multiplier": multiplier}
    raise ValueError("Unknown Wilds control.")


class HostActions:
    def __init__(self, client, *, backup_callback=None):
        self.client = client
        self.engine = client.engine
        self.backup_callback = backup_callback

    async def execute(self, action: str, arguments: dict, *, request_id: str,
                      actor: str = "PJ") -> dict:
        options = validate_action(action, arguments)
        self.client.assert_host()
        if not self.client.channel_ready or not self.client.game_channel:
            raise ValueError("The Discord game connection is not ready yet.")
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 80:
            raise ValueError("A valid control request ID is required.")
        guild, channel = self.client.settings.guild_id, self.client.settings.channel_id
        if action == "spawn":
            event = await self.client.publish_encounter(
                kind=None if options["kind"] == "random" else options["kind"],
                grade=options.get("grade"))
            return {"ok": True, "message": f"Appearance posted: {event['item']['name']}.",
                    "event_id": event["id"], "message_id": event.get("message_id")}
        if action == "backup":
            if self.backup_callback is None:
                raise ValueError("Cloud backups are not configured yet.")
            result = await self.backup_callback()
            return {"ok": True, "message": "A private cloud save backup was verified.", "backup": result}
        async with self.client.game_lock:
            self.client.assert_host()
            if action in {"start", "pause"}:
                active = self.engine.active_event(guild, channel)
                enabled = action == "start"
                state = self.engine.set_enabled(guild, channel, enabled)
                self.client.tips.sync_state(guild, channel, enabled)
                if not enabled and active:
                    await self.client.close_post(active)
                return {"ok": True, "enabled": state["enabled"],
                        "message": "Appearances resumed." if enabled else "Appearances paused; collections remain saved."}
            if action == "mode":
                settings = replace(self.client.settings, mode=options["mode"])
                self.engine.configure_channel(guild, channel, settings.mode)
                if self.client.persist_settings:
                    settings.save()
                self.client.settings = settings
                return {"ok": True, "mode": settings.mode,
                        "message": f"Future appearances will use {settings.mode} mode."}
            return await self._host_event(action, options, request_id, actor)

    async def _host_event(self, action: str, options: dict, request_id: str, actor: str) -> dict:
        """Reserve once, announce once, then commit the effect after confirmation."""
        from .discord_bot import clean_name

        guild, channel = self.client.settings.guild_id, self.client.settings.channel_id
        key = "host:" + request_id
        payload = {"action": action, "arguments": options}
        with self.engine._transaction() as db:
            existing = db.execute("SELECT operation,result_json FROM requests WHERE guild_id=? AND request_id=?",
                                  (guild, key)).fetchone()
            if existing:
                result = json.loads(existing["result_json"])
                if result.get("payload") != payload:
                    raise ValueError("This request ID belongs to a different control.")
                if result.get("phase") == "done":
                    return result["result"]
                raise UncertainHostAction("This event was already attempted. Its announcement will not be replayed.")
            now = self.engine._now()
            state = self.engine._get_channel(db, guild, channel)
            if not state["enabled"]:
                raise ValueError("Resume appearances before hosting an event.")
            busy = db.execute("""SELECT 1 FROM events WHERE guild_id=? AND channel_id=?
              AND status IN ('pending','open') AND (expires_at IS NULL OR expires_at>?)""",
              (guild, channel, now)).fetchone()
            if action == "frenzy":
                if state["frenzy_until"] > now:
                    raise ValueError("A Frenzy is already running.")
                if busy:
                    raise ValueError("Let the current appearance finish before starting a Frenzy.")
            if action == "power_drive" and self.engine.activities._active_drive(db, guild, channel, now):
                raise ValueError("A Power Drive is already running.")
            reservation = {"payload": payload, "phase": "prepared"}
            db.execute("INSERT INTO requests(guild_id,request_id,operation,result_json,created_at) VALUES(?,?,?,?,?)",
                       (guild, key, "host:" + action, json.dumps(reservation), now))
        if action == "frenzy":
            seconds = GRADE_SECONDS[options["grade"]]
            announcement = (f"💨 **{clean_name(actor)} is hosting a {options['grade']}-class Community Frenzy!**\n"
                            f"**{seconds // 60} minute(s)** of shared discoveries. Everyone can collect each appearance!")
        else:
            seconds = DRIVE_SECONDS
            announcement = (f"🚀 **{clean_name(actor)} is hosting a Power Drive!**\n"
                            f"For **30 minutes**, every successful discovery earns **×{options['multiplier']} Warp progress**. "
                            "Your usual items, XP, and mission rewards stay the same.")
        try:
            message = await self.client.send_public(announcement)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Even a timeout may follow a successful Discord delivery. Keeping
            # the prepared ledger entry makes retries visible and non-replaying.
            raise UncertainHostAction("The event announcement could not be confirmed. The effect was not activated; this request will not be replayed.") from None
        try:
            self.client.assert_host()
            with self.engine._transaction() as db:
                now = self.engine._now()
                state = self.engine._get_channel(db, guild, channel)
                if not state["enabled"]:
                    raise ValueError("The game paused while the event announcement was being sent.")
                ends_at = now + seconds
                if action == "frenzy":
                    db.execute("UPDATE channels SET frenzy_until=?,next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                               (ends_at, now + 1, guild, channel))
                    result = {"ok": True, "message": f"{options['grade']}-class Frenzy started for {seconds // 60} minute(s).",
                              "grade": options["grade"], "ends_at": ends_at, "seconds": seconds}
                else:
                    db.execute("""INSERT INTO activity_notices
                      (id,guild_id,channel_id,kind,slot_key,scheduled_at,expires_at,status,payload_json,
                       starts_at,ends_at,sent_at,message_id)
                      VALUES(?,?,?,'drive_start',?,?,?,'sent',?,?,?,?,?)""",
                      ("host_" + request_id, guild, channel, key, now, ends_at,
                       json.dumps({"multiplier": options["multiplier"], "manual": True}),
                       now, ends_at, now, str(message.id)))
                    result = {"ok": True, "message": f"×{options['multiplier']} Power Drive started for 30 minutes.",
                              "multiplier": options["multiplier"], "ends_at": ends_at, "seconds": seconds}
                result["message_id"] = str(message.id)
                db.execute("UPDATE requests SET result_json=? WHERE guild_id=? AND request_id=?",
                           (json.dumps({"payload": payload, "phase": "done", "result": result}), guild, key))
            return result
        except Exception:
            raise UncertainHostAction("Discord received the announcement, but its saved effect could not be confirmed. Check the current game status before hosting another event.") from None


def status_snapshot(client) -> dict[str, Any]:
    """A small owner-only snapshot, with no message text or credentials."""
    engine, settings = client.engine, client.settings
    state = engine.status(settings.guild_id, settings.channel_id)
    journey = engine.progression.status(settings.guild_id, settings.channel_id)
    drive = engine.activities.drive_status(settings.guild_id, settings.channel_id)
    with engine._lock:
        counts = dict(engine.db.execute("""SELECT COUNT(*) AS players,COALESCE(SUM(catches),0) AS catches,
          COALESCE(SUM(units),0) AS items,COALESCE(SUM(xp),0) AS xp FROM profiles WHERE guild_id=?""",
          (settings.guild_id,)).fetchone())
        recent = engine.db.execute("""SELECT c.user_id,c.quantity,c.claimed_at,e.kind,e.grade,e.item_json
          FROM claims c JOIN events e ON e.id=c.event_id
          WHERE e.guild_id=? AND e.channel_id=? ORDER BY c.claimed_at DESC LIMIT 10""",
          (settings.guild_id, settings.channel_id)).fetchall()
    activity = []
    for row in recent:
        item = json.loads(row["item_json"])
        user = client.get_user(int(row["user_id"])) if row["user_id"].isdigit() else None
        activity.append({"user_id": row["user_id"], "display_name": getattr(user, "display_name", None),
                         "item": item.get("name", "Discovery"), "kind": row["kind"], "grade": row["grade"],
                         "quantity": row["quantity"], "at": row["claimed_at"]})
    return {"bot_ready": bool(client.is_ready() and client.channel_ready and not client._host_failed),
            "application_id": settings.application_id, "guild_id": settings.guild_id,
            "channel_id": settings.channel_id, "channel": {k: v for k, v in state.items() if k != "active_event"},
            "galaxy": journey.get("galaxy", journey.get("current")), "active_event": state.get("active_event"),
            "effects": {"frenzy_until": state.get("frenzy_until", 0),
                        "mineral_until": state.get("mineral_until", 0), "power_drive": drive},
            "counts": counts, "recent_activity": activity,
            "available_actions": ["start", "pause", "mode", "spawn", "frenzy", "power_drive", "backup"]}
