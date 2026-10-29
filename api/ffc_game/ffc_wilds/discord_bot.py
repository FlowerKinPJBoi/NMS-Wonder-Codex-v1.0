"""Discord transport for FFC Wilds. Game rules and persistence live in engine.py.

Only the explicitly configured server/channel is accepted. Regular message text
is never stored. No member-list, presence, administrator, or message-deletion
permission is required. Bot tokens are supplied by the launcher at runtime.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging
from logging.handlers import RotatingFileHandler
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Callable

import discord
from discord import app_commands
from discord.ext import tasks

from . import __version__
from .config import CATALOG_PATH, DATA_PATH, ROOT, Settings
from .engine import GameEngine, GRADE_MULTIPLIERS, GRADE_SECONDS, POWERUP_KINDS
from .progression import WARP_BANK_CAP, WARP_COST, WARP_COOLDOWN_SECONDS
from .tips import TipSchedule
from .async_store import GameIO, GuardFailed, _completion_before_cancel

LOG = logging.getLogger("ffc_wilds")
COLORS = {"C": 0x62D4A2, "B": 0x57B9EF, "A": 0xB28BF5, "S": 0xFFE26F}
EMOJI = {"fish": "🐟", "plant": "🌱", "mineral": "⛏️", "pet": "🐾",
         "electromagnetic": "⚡", "gas": "💨", "mineral_powerup": "⏱️", "crafted": "🛠️"}
CATEGORY_NAMES = {"fish": "Aquarium", "plant": "Greenhouse", "mineral": "Mineral cabinet",
                  "pet": "Companion register", "crafted": "Crafted trophies"}
ACTIONS = {"catch", "pick", "mine", "tame", "powerup"}
INTERLUDE_SPACING_SECONDS = 120
RECEIPT_INTERVAL_SECONDS = 2
RECEIPT_MESSAGE_LIMIT = 1800
ACHIEVEMENTS_PER_PAGE = 8
CATEGORY_CHOICES = [app_commands.Choice(name=name, value=key) for key, name in CATEGORY_NAMES.items()]
KIND_CHOICES = [app_commands.Choice(name=name, value=key) for key, name in {
    "random": "Surprise encounter", "fish": "Fish", "plant": "Plant", "mineral": "Mineable deposit",
    "pet": "Companion", "electromagnetic": "Electromagnetic hotspot", "gas": "Gas hotspot",
    "mineral_powerup": "Mineral hotspot powerup"}.items()]


def clean_name(value: str) -> str:
    return discord.utils.escape_markdown(discord.utils.escape_mentions(" ".join(value.split())))[:80]


def progress_bar(current: int, target: int, width: int = 10) -> str:
    """A compact visual paired with exact numbers in every player panel."""
    filled = min(width, max(0, int(current) * width // max(1, int(target))))
    return "▰" * filled + "▱" * (width - filled)


def message_units(text: str) -> int:
    # Discord measures message limits in UTF-16 units, including astral emoji.
    return len(text.encode("utf-16-le")) // 2


def message_chunks(text: str, limit: int = RECEIPT_MESSAGE_LIMIT) -> list[str]:
    """Bound even an unusually large receipt without blocking later players."""
    chunks, characters, length = [], [], 0
    for character in text:
        size = 2 if ord(character) > 0xFFFF else 1
        if length + size > limit:
            chunks.append("".join(characters))
            characters, length = [], 0
        characters.append(character)
        length += size
    if characters:
        chunks.append("".join(characters))
    return chunks


def milestone_lines(result: dict, display_name: str | None = None) -> list[str]:
    """Describe only milestones earned by this committed action."""
    subject = clean_name(display_name) if display_name is not None else "You"
    lines = []
    level = result.get("level_up")
    if level:
        lines.append(f"🎉 **{subject} reached Explorer level {level['to_level']}!** · {level['title']}")
    for badge in result.get("achievements_unlocked", []):
        lines.append(f"🏅 **{subject} unlocked {badge['emoji']} {badge['title']}!** — {badge['description']}")
    return lines


def galaxy_label(galaxy: dict) -> str:
    return f"{clean_name(galaxy['name'])} · #{galaxy['number']}"


def warp_failure_text(result: dict) -> str:
    reason = result.get("reason")
    if reason == "cooldown":
        return f"The crew's drive is recharging. Try again <t:{int(result.get('cooldown_until', 0))}:R>. No points were spent."
    if reason == "insufficient_points":
        return f"A Warp needs **{WARP_COST} points**. Your bank has **{result.get('balance', 0)}**. Keep collecting or complete /ffc missions."
    return {
        "duplicate_request": "That Warp action has already been handled. Check /ffc galaxy for the crew's location.",
        "stale_selection": "The crew has already moved! Open /ffc warp again to choose from the current galaxy. No points were spent.",
        "channel_unavailable": "The game is paused or unavailable. No Warp points were spent.",
        "invalid_direction": "Choose Previous or Next from a fresh /ffc warp panel. No points were spent.",
        "invalid_revision": "Open /ffc warp again for a current destination. No points were spent.",
    }.get(reason, "That Warp could not complete. Check /ffc galaxy and try a fresh /ffc warp panel.")


def board_lines(rows: list[dict], metric: str = "catches", limit: int = 10) -> str:
    return "\n".join(f"**{i}.** <@{row['user_id']}> — **{row[metric]}**"
                     for i, row in enumerate(rows[:limit], 1)) or "No discoveries recorded for this period yet."


def mission_embed(state: dict, drive: dict) -> discord.Embed:
    embed = discord.Embed(title="Your daily FFC missions", color=0x62D4A2,
        description=("Collect with the crew to complete your own goals. Each mission rewards "
                     "**10 Warp points** once; rewards respect your bank limit.\n"
                     f"New missions arrive <t:{int(state['resets_at'])}:R>."))
    for mission in state["missions"]:
        progress = min(mission["progress"], mission["target"])
        mark = "✅" if mission["completed"] else "○"
        embed.add_field(name=f"{mark} {mission['title']}",
                        value=f"{progress_bar(progress, mission['target'])} **{progress}/{mission['target']}**\n+{mission['reward']} Warp points", inline=False)
    if drive.get("active"):
        embed.add_field(name=f"⚡ Power Drive · ×{drive['multiplier']}",
            value=f"Collection Warp progress is boosted until <t:{int(drive['ends_at'])}:R>. Mission counts and rewards stay the same.", inline=False)
    embed.set_footer(text="Daily reset: midnight America/New_York • /ffc warp spends points on a shared jump")
    return embed


def activity_embed(reservation: dict) -> discord.Embed:
    data, kind = reservation["data"], reservation["kind"]
    if kind == "drive_start":
        embed = discord.Embed(title=f"⚡ POWER DRIVE · ×{data['multiplier']} Warp progress", color=0xB28BF5,
            description=("The crew's scanners catch a surge of hyperdrive energy!\n\n"
                f"For **30 minutes**, every successful collection earns **{data['multiplier']} Warp points**. "
                "Fish, pick, mine, or tame to build your next jump.\n\n"
                f"Ends <t:{int(data['ends_at'])}:R>. Use **/ffc warp** to see your bank and destinations."))
        embed.set_footer(text="Power Drive boosts Warp progress • Item quantities, Discovery XP and mission counts keep their usual rules")
        return embed
    if kind == "missions":
        embed = discord.Embed(title="🌄 FFC expedition briefing", color=0x62D4A2,
            description=("A fresh pair of missions for the crew! Everyone earns their own rewards.\n"
                         "Use **/ffc missions** to check your progress."))
        for mission in data["missions"]:
            embed.add_field(name=mission["title"], value=f"Goal: **{mission['target']}** · Reward: **{mission['reward']} Warp points**", inline=False)
        embed.add_field(name="Today's route", value=f"Missions reset <t:{int(data['resets_at'])}:R>. Keep collecting and choose the crew's next jump with **/ffc warp**.", inline=False)
        return embed
    if kind == "standings":
        embed = discord.Embed(title="🏆 FFC daily crew report", color=0xFFE26F,
                              description="A moment around the campfire to celebrate the crew's discoveries.")
        embed.add_field(name="Today so far · top collectors", value=board_lines(data["today"], limit=5), inline=False)
        embed.add_field(name="This week so far · top collectors", value=board_lines(data["week"], limit=5), inline=False)
        embed.set_footer(text="Successful collections • America/New_York days • Week starts Monday • /ffc leaderboard")
        return embed
    raise ValueError("Unknown crew notice kind")


def icon_path(item: dict) -> Path | None:
    path = (ROOT / item.get("icon", "")).resolve()
    if path.is_relative_to((ROOT / "assets").resolve()) and path.is_file():
        return path
    return None


def event_embed(event: dict, *, closed: bool = False) -> discord.Embed:
    item, kind, grade = event["item"], event["kind"], event["grade"]
    heading = f"{EMOJI.get(kind, '✨')} {grade}-class {item['name']}"
    if kind == "electromagnetic":
        description = (f"An electromagnetic hotspot crackles nearby!\n"
                       f"Claim **×{GRADE_MULTIPLIERS[grade]} items** on your next **5 successful collections**.")
    elif kind == "gas":
        description = ("A concentrated gas hotspot is venting!\n"
                       f"Activate a **{GRADE_SECONDS[grade] // 60}-minute community frenzy** with rapid shared encounters.")
    elif kind == "mineral_powerup":
        description = (f"Your scanner finds a rich mineral hotspot!\nEveryone gets **5 extra seconds** on new encounters "
                       f"for **{GRADE_SECONDS[grade] // 60} minute(s)**. A new encounter follows shortly.")
    else:
        description = item.get("appearance", f"A wild {item['name']} has appeared nearby!")
    if not closed:
        description += f"\n\nType **`{event['action']}`** or press the button below."
    else:
        description += "\n\n**This appearance is closed.**"
    embed = discord.Embed(title=heading, description=description, color=COLORS.get(grade, 0x57B9EF))
    if not closed:
        community = event["mode"] == "community"
        embed.add_field(name="Who can collect?", value="Everyone, once each" if community else "First successful player", inline=True)
        deadline = event.get("expires_at")
        if deadline is not None:
            timing = f"Closes <t:{int(deadline)}:R>"
        elif event.get("frenzy"):
            timing = f"{event['window_seconds']} seconds once posted"
        elif community:
            timing = f"Waiting for the first claim; then {event['window_seconds']} seconds for everyone."
        else:
            timing = "Waiting for the first successful claim."
        embed.add_field(name="Collection window", value=timing, inline=True)
    if event.get("galaxy"):
        embed.add_field(name="Discovery location", value="🪐 " + galaxy_label(event["galaxy"]), inline=False)
    if icon_path(item):
        embed.set_thumbnail(url="attachment://" + icon_path(item).name)
    suffix = "Community frenzy" if event.get("frenzy") else "Fishing • Farming • Crafting"
    embed.set_footer(text=f"FFC Wilds • {suffix} • " + ("Collection saved" if closed else "One claim per member"))
    return embed


def claim_text(result: dict) -> str:
    if not result.get("ok"):
        return {
            "already_claimed": "You already collected from this appearance.",
            "duplicate_request": "That action has already been handled.",
            "wrong_action": f"This appearance needs **{result.get('event', {}).get('action', 'the displayed action')}**.",
            "expired": "That appearance has finished. Watch for the next one!",
            "not_open": "That appearance is closed or is still arriving.",
            "no_event": "There is no open appearance right now.",
            "wrong_event": "That button belongs to another appearance.",
            "channel_unavailable": "The game is paused. A moderator can use /ffc-admin start.",
        }.get(result.get("reason"), "That action could not be completed.")
    effect = result.get("effect")
    if effect:
        if effect["kind"] == "electromagnetic":
            prefix = "Your stronger charge stays active: " if effect.get("preserved_stronger") else "Power charged! "
            text = prefix + f"**×{effect['multiplier']}** for **{effect['remaining']}** successful collections."
        elif effect["kind"] == "gas":
            text = f"**Community frenzy activated!** Everyone can collect until <t:{int(effect['until'])}:R>."
        else:
            text = f"**Extra collection time activated!** New appearances get **+5 seconds** until <t:{int(effect['until'])}:R>."
        return "\n".join([text, *milestone_lines(result)])
    suffix = f" · {result['remaining_charges']} powered collections left" if result["multiplier"] > 1 else ""
    points = f" · **+{result['xp_awarded']} XP**" if result.get("xp_awarded") else ""
    warp = ""
    if "warp_balance" in result:
        awarded = result.get("warp_points_awarded", 0)
        warp = f" · **+{awarded} Warp**" if awarded else " · Warp bank full"
        if result.get("warp_multiplier", 1) > 1:
            warp += f" (×{result['warp_multiplier']} Power Drive)"
        warp += f" · bank **{result['warp_balance']}/{WARP_BANK_CAP}**"
    text = f"Collected **{result['item']['name']} ×{result['quantity']}**{points}{suffix}{warp}."
    for mission in result.get("missions_completed", []):
        text += f"\n✅ **{mission['title']}** complete · **+{mission['awarded']} Warp points**"
        if mission["awarded"] < mission["reward"]:
            text += " (bank limit reached)"
    return "\n".join([text, *milestone_lines(result)])


def public_claim_text(display_name: str, result: dict) -> str:
    """One social receipt for button and typed claims, with no economy writes."""
    if not result.get("ok"):
        return ""
    event = result["event"]
    kind, grade = event["kind"], event["grade"]
    name = clean_name(display_name)
    item = clean_name(result["item"]["name"])
    effect = result.get("effect")
    if effect:
        text = f"{EMOJI.get(kind, '⚡')} **{name}** activated **{grade}-class {item}**! "
        if kind == "electromagnetic":
            text += f"**×{effect['multiplier']} items** for their next **{effect['remaining']} collections**."
            if effect.get("preserved_stronger"):
                text += " Their stronger charge stays active."
        elif kind == "gas":
            text += f"**Community Frenzy** for everyone until <t:{int(effect['until'])}:R>."
        else:
            text += f"Everyone gets **+5 seconds** on new appearances until <t:{int(effect['until'])}:R>."
    else:
        verb = {"fish": "caught", "plant": "picked", "mineral": "mined", "pet": "tamed"}.get(kind, "collected")
        text = f"{EMOJI.get(kind, '✨')} **{name}** {verb} **{grade}-class {item} ×{result['quantity']}** · **+{result['xp_awarded']} XP**"
        if result.get("warp_points_awarded"):
            text += f" · +{result['warp_points_awarded']} Warp"
            if result.get("warp_multiplier", 1) > 1:
                text += f" (×{result['warp_multiplier']} Power Drive)"
        text += "."
    lines = [text]
    for mission in result.get("missions_completed", []):
        line = f"✅ **{name}** completed **{mission['title']}** · **+{mission['awarded']} Warp points**"
        if mission["awarded"] < mission["reward"]:
            line += " (bank limit reached)"
        lines.append(line)
    lines.extend(milestone_lines(result, display_name))
    return "\n".join(lines)


class WarpView(discord.ui.View):
    """An invoker-owned, short-lived destination confirmation."""

    def __init__(self, client: "WildsBot", user_id: int, snapshot: dict):
        super().__init__(timeout=120)
        self.client, self.user_id, self.snapshot = client, user_id, snapshot
        self.deadline = time.monotonic() + 120
        self.resolved = False
        for direction, emoji in (("previous", "⬅️"), ("next", "➡️")):
            destination = snapshot[direction]
            button = discord.ui.Button(label=f"{direction.title()}: {destination['name'][:35]} · {WARP_COST} points",
                emoji=emoji, style=discord.ButtonStyle.primary,
                disabled=snapshot["balance"] < WARP_COST or snapshot["cooldown_remaining"] > 0)

            async def select(interaction: discord.Interaction, chosen: str = direction):
                await self.choose(interaction, chosen)

            button.callback = select
            self.add_item(button)
        cancel = discord.ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        cancel.callback = self.cancel
        self.add_item(cancel)

    def finish(self):
        self.resolved = True
        self.stop()
        self.client.warp_views.discard(self)

    async def on_timeout(self):
        self.finish()

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        self.client.log_safe_error("warp_callback", error)
        with contextlib.suppress(discord.HTTPException):
            await self.client.reply(interaction, "That Warp could not be confirmed. Check /ffc galaxy before choosing another jump.", ephemeral=True)

    async def check_owner(self, interaction: discord.Interaction) -> bool:
        if not self.client.channel_matches(interaction):
            return await self.client.require_channel(interaction)
        if interaction.user.id != self.user_id:
            await self.client.reply(interaction, "This is another explorer's Warp panel. Open **/ffc warp** for your own.", ephemeral=True)
            return False
        if self.resolved or time.monotonic() >= self.deadline:
            await self.client.reply(interaction, "This Warp panel has expired or finished. Open **/ffc warp** again.", ephemeral=True)
            return False
        return await self.client.require_channel(interaction)

    async def clear_controls(self, interaction: discord.Interaction):
        source = getattr(interaction, "message", None)
        if source:
            with contextlib.suppress(discord.HTTPException):
                await self.client.edit_public(source, view=None)

    async def cancel(self, interaction: discord.Interaction):
        if not await self.check_owner(interaction):
            return
        self.finish()
        await self.client.reply(interaction, "Warp canceled. Your points stay in your bank.", ephemeral=True)
        await self.clear_controls(interaction)

    async def choose(self, interaction: discord.Interaction, direction: str):
        if not await self.check_owner(interaction):
            return
        if not self.client.channel_ready or not self.client.game_channel:
            await self.client.reply(interaction, "The game channel is reconnecting. No Warp points were spent.", ephemeral=True)
            return
        await self.client.acknowledge(interaction, force=True)
        async with self.client.game_lock:
            await self.client.ensure_host()
            if self.resolved or time.monotonic() >= self.deadline:
                result = {"ok": False, "reason": "duplicate_request"}
            else:
                result = await self.client.db_call(self.client.engine.progression.warp,
                    str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id),
                    direction, self.snapshot["revision"], request_id="warp:" + str(interaction.id))
                self.finish()
        await self.clear_controls(interaction)
        if not result.get("ok"):
            await interaction.followup.send(warp_failure_text(result), ephemeral=True)
            return
        destination = galaxy_label(result["to_galaxy"])
        receipt = (f"🚀 The crew has arrived in **{destination}**! **{WARP_COST} Warp points** spent; "
                   f"your bank now holds **{result['balance']}/{WARP_BANK_CAP}**.\n"
                   f"The next shared jump is available <t:{int(result['cooldown_until'])}:R>.")
        try:
            await interaction.followup.send(receipt, ephemeral=True)
        finally:
            # The journey has committed. Discord receipt failure cannot spend
            # twice, reverse the crew's location, or hide it from /ffc galaxy.
            await self.client.announce_warp(interaction.user.display_name, result)


class EncounterView(discord.ui.View):
    def __init__(self, client: "WildsBot", event: dict):
        super().__init__(timeout=None)
        self.client = client
        self.event_id = event["id"]
        self.action = event["action"]
        button = discord.ui.Button(label=self.action.title(), emoji=EMOJI.get(event["kind"]),
                                   style=discord.ButtonStyle.success,
                                   custom_id=f"ffc:{self.event_id}:{self.action}")
        button.callback = self.collect
        self.add_item(button)

    async def collect(self, interaction: discord.Interaction):
        if not await self.client.require_channel(interaction):
            return
        await self.client.acknowledge(interaction, force=True)
        async with self.client.game_lock:
            result = await self.client.db_call(self.client.engine.claim, str(interaction.guild_id), str(interaction.channel_id),
                str(interaction.user.id), self.action, event_id=self.event_id,
                request_id="interaction:" + str(interaction.id))
        self.client.queue_claim(interaction.user.display_name, result)
        try:
            await interaction.followup.send(claim_text(result), ephemeral=True)
        finally:
            # The database reward has already committed. A failed Discord
            # receipt must not leave a claimed powerup's controls active.
            if result.get("event"):
                await self.client.finish_if_closed(result["event"], refresh=result.get("ok") and result.get("first"))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item):
        self.client.log_safe_error("collection_callback", error)
        with contextlib.suppress(discord.HTTPException):
            await self.client.reply(interaction, "That collection could not be confirmed. Check /ffc inventory before trying again.", ephemeral=True)


class WildsCommands(app_commands.Group):
    def __init__(self, client: "WildsBot"):
        super().__init__(name="ffc", description="Fishing, Farming & Crafting in FFC Wilds", guild_only=True)
        self.client = client

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return await self.client.require_channel(interaction)

    @app_commands.command(name="help", description="Learn how to collect, power up and craft")
    async def help_command(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Welcome to FFC Wilds", color=0x62D4A2, description=(
            "Watch for an illustrated appearance, then type its word or press its button.\n\n"
            "🐟 **catch** fish · 🌱 **pick** crops · ⛏️ **mine** deposits · 🐾 **tame** companions\n"
            "⚡ **powerup** claims an electromagnetic, gas or mineral hotspot.\n\n"
            "Ordinary appearances wait until somebody collects.\n"
            "**Community mode:** the first claim starts a 15-second window; every member can collect once.\n"
            "**Classic mode:** first correct claim wins. Frenzies are always shared.\n\n"
            "**Electromagnetic:** C ×2 / B ×4 / A ×6 / S ×8 for your next five successful collections.\n"
            "**Gas:** shared Frenzy for C 1 / B 2 / A 3 / S 4 minutes.\n"
            "**Mineral:** +5 seconds on new appearances for C 1 / B 2 / A 3 / S 4 minutes.\n\n"
            "**Warp:** each successful collection earns 1 Warp point. Spend 50 with **/ffc warp** "
            "to move the crew to the next or previous galaxy. The shared drive recharges in 2 minutes.\n"
            "**Power Drives:** surprise 30-minute events give ×2 or ×3 collection Warp progress.\n"
            "**Daily missions:** two personal goals earn 10 extra Warp points each; check **/ffc missions**.\n\n"
            "**Explorer levels:** every 100 Discovery XP gains a level. C/B/A/S collections earn 10/20/40/80 XP.\n"
            "**Achievements:** earn permanent badges for collecting, crafting, powerups, missions, and your first Warp. "
            "Check **/ffc achievements** for your next goal.\n"
            "Successful collections, new levels, and achievements appear in the crew feed, whether you type or click.\n\n"
            "Use **/ffc inventory** for this game's collection (choose the **ffc** command group), "
            "**/ffc catalog**, **/ffc profile**, **/ffc recipes**, "
            "**/ffc craft**, **/ffc leaderboard** and **/ffc status**.\n\n"
            "**/ffc galaxy** shows the crew's route and recent jumps. Your collection and travel live in this Discord game."
        ))
        await self.client.reply(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="inventory", description="See your fish, crops, minerals, companions and trophies")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def inventory(self, interaction: discord.Interaction, category: str | None = None,
                        page: app_commands.Range[int, 1, 20] = 1):
        await self.client.acknowledge(interaction)
        rows = await self.client.db_call(self.client.engine.inventory, str(interaction.guild_id), str(interaction.user.id))
        if category:
            rows = [row for row in rows if row["kind"] == category]
        pages = max(1, (len(rows) + 9) // 10)
        if page > pages:
            await self.client.reply(interaction, f"That collection has {pages} page(s).", ephemeral=True)
            return
        lines = [f"{EMOJI.get(row['kind'], '✨')} **{row['name']}** ×{row['quantity']}" for row in rows[(page-1)*10:page*10]]
        embed = discord.Embed(title=CATEGORY_NAMES.get(category, "Your FFC collection"),
                              description="\n".join(lines) or "Your first discovery is waiting. Watch for an appearance!", color=0x62D4A2)
        embed.set_footer(text=f"Page {page}/{pages} • Ingredients spent on crafting leave your inventory, but remain discovered.")
        await self.client.reply(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="catalog", description="Browse collectible discoveries and see what you have found")
    @app_commands.choices(category=CATEGORY_CHOICES)
    async def catalog(self, interaction: discord.Interaction, category: str | None = None,
                      page: app_commands.Range[int, 1, 20] = 1):
        await self.client.acknowledge(interaction)
        items = list(self.client.engine.all_items.values())
        if category:
            items = [item for item in items if item["kind"] == category]
        profile = await self.client.db_call(self.client.engine.profile, str(interaction.guild_id), str(interaction.user.id))
        discovered = set(profile.get("discovered_item_ids", []))
        pages = max(1, (len(items)+9)//10)
        if page > pages:
            await self.client.reply(interaction, f"That catalog has {pages} page(s).", ephemeral=True)
            return
        lines = [f"{'✓' if item['id'] in discovered else '○'} **{item['name']}** · {item.get('rarity', 'C')}" for item in items[(page-1)*10:page*10]]
        embed = discord.Embed(title="Field guide · " + CATEGORY_NAMES.get(category, "All discoveries"),
                              description="\n".join(lines), color=0x57B9EF)
        embed.set_footer(text=f"Page {page}/{pages} • ✓ discovered · ○ still to find • FFC collection classes")
        await self.client.reply(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="profile", description="Your successful collections, discoveries and powerups")
    async def profile(self, interaction: discord.Interaction):
        await self.client.acknowledge(interaction, force=True)
        await self.client.ensure_host()
        def read_profile():
            return (self.client.engine.profile(str(interaction.guild_id), str(interaction.user.id)),
                    self.client.engine.progression.status(str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id)))
        p, journey = await self.client.db_call(read_profile)
        embed = discord.Embed(title=f"{clean_name(interaction.user.display_name)} · Explorer level {p['level']}",
            description=(f"**{p['title']}**\n"
                         f"{progress_bar(p['xp_into_level'], p['xp_for_next_level'])} "
                         f"**{p['xp_into_level']}/{p['xp_for_next_level']} XP** toward level {p['next_level']}\n"
                         f"**{p['xp_to_next_level']} XP** to your next level."), color=0xB28BF5)
        for label, key in (("Discovery XP", "xp"), ("Successful collections", "catches"), ("Items gathered", "units"),
                           ("Unique discoveries", "unique_items"), ("First claims", "firsts"),
                           ("Powerups activated", "powerups"), ("Trophies crafted", "crafts")):
            embed.add_field(name=label, value=str(p[key]))
        recent = "\n".join(f"{badge['emoji']} **{badge['title']}**" for badge in p["recent_achievements"])
        embed.add_field(name=f"Achievements · {p['achievements_unlocked']}/{p['achievements_total']}",
                        value=(recent + "\n" if recent else "") + "Use **/ffc achievements** for every badge and its progress.", inline=False)
        embed.add_field(name="Warp bank", value=f"**{journey['balance']}/{WARP_BANK_CAP}** points · {journey['charges']} jump(s)", inline=False)
        embed.add_field(name="Crew location", value=galaxy_label(journey["galaxy"]), inline=False)
        embed.set_footer(text="One successful collection counts once, even when its item quantity is multiplied.")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="achievements", description="See your earned badges and progress toward the next ones")
    @app_commands.choices(filter=[app_commands.Choice(name=name, value=value) for name, value in
                                 (("All badges", "all"), ("Earned badges", "earned"), ("Still to earn", "locked"))])
    async def achievements(self, interaction: discord.Interaction,
                           page: app_commands.Range[int, 1, 20] = 1, filter: str = "all"):
        await self.client.acknowledge(interaction, force=True)
        await self.client.ensure_host()
        state = await self.client.db_call(self.client.engine.honours.status, str(interaction.guild_id), str(interaction.user.id))
        badges = [badge for badge in state["achievements"]
                  if filter == "all" or (filter == "earned" and badge["unlocked"])
                  or (filter == "locked" and not badge["unlocked"])]
        pages = max(1, (len(badges) + ACHIEVEMENTS_PER_PAGE - 1) // ACHIEVEMENTS_PER_PAGE)
        if page > pages:
            await interaction.followup.send(f"That achievement view has {pages} page(s).", ephemeral=True)
            return
        embed = discord.Embed(title=f"🏅 {clean_name(interaction.user.display_name)} · FFC achievements",
            description=(f"**{state['unlocked_count']}/{state['total_count']} permanent badges earned**\n"
                         "Collect with the crew and watch your milestones grow."), color=0xFFE26F)
        for badge in badges[(page - 1) * ACHIEVEMENTS_PER_PAGE:page * ACHIEVEMENTS_PER_PAGE]:
            current = min(badge["progress"], badge["target"])
            mark = "✅" if badge["unlocked"] else "○"
            value = (f"{badge['description']}\n"
                     f"{progress_bar(current, badge['target'])} **{current}/{badge['target']}**")
            if badge["unlocked"]:
                value += " · Earned"
            embed.add_field(name=f"{mark} {badge['emoji']} {badge['title']}", value=value, inline=False)
        if not badges:
            embed.add_field(name="Your field journal", value=("All current badges earned!" if filter == "locked" else
                            "Your first badge is waiting. Collect from an appearance to get started."), inline=False)
        embed.set_footer(text=f"Page {page}/{pages} • {filter.title()} badges • One collection counts once, even with powered quantities")
        await interaction.followup.send(embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="status", description="Check your charge and the channel's shared powerups")
    async def status(self, interaction: discord.Interaction):
        await self.client.acknowledge(interaction)
        def read_status():
            return (self.client.engine.status(str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id)),
                    self.client.engine.progression.status(str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id)),
                    self.client.engine.activities.drive_status(str(interaction.guild_id), str(interaction.channel_id)))
        s, journey, drive = await self.client.db_call(read_status)
        b = s.get("boost", {"remaining": 0, "multiplier": 1})
        lines = ["Game: **" + ("running" if s["enabled"] else "paused") + "** · " + s.get("mode", "community"),
                 f"Crew galaxy: **{galaxy_label(journey['galaxy'])}**.",
                 f"Your Warp bank: **{journey['balance']}/{WARP_BANK_CAP} points** · **{journey['charges']}** jump(s). Use **/ffc warp**.",
                 f"Your charge: **×{b['multiplier']}**, **{b['remaining']}** successful collections remaining.",
                 "Community frenzy: " + (f"ends <t:{int(s['frenzy_until'])}:R>" if s["frenzy_remaining"] else "inactive"),
                 "Extra time: " + (f"+5s on new appearances until <t:{int(s['mineral_until'])}:R>" if s["mineral_remaining"] else "inactive")]
        lines.append("Power Drive: " + (f"**×{drive['multiplier']} Warp progress** until <t:{int(drive['ends_at'])}:R>." if drive["active"] else "watch for a surprise surge."))
        if journey["cooldown_remaining"]:
            lines.append(f"Shared Warp drive recharges <t:{int(journey['cooldown_until'])}:R>.")
        active = s.get("active_event")
        if active:
            lines.append(f"Open appearance: **{active['item']['name']}** — type **{active['action']}**.")
            if active["expires_at"] is None:
                lines.append("Waiting for the first successful claim.")
            else:
                lines.append(f"Collection closes <t:{int(active['expires_at'])}:R>.")
        await self.client.reply(interaction, "\n".join(lines), ephemeral=True)

    @app_commands.command(name="recipes", description="Find a use for duplicates: craft FFC cosmetic trophies")
    async def recipes(self, interaction: discord.Interaction):
        embed = discord.Embed(title="FFC Workshop", description="These original FFC recipes consume inventory items and award cosmetic trophies.", color=0xFFA182)
        for recipe in self.client.engine.recipes.values():
            ingredients = ", ".join(f"{self.client.engine.all_items[item]['name']} ×{count}" for item, count in recipe["ingredients"].items())
            embed.add_field(name=recipe["name"], value=ingredients + f"\n`/ffc craft recipe:{recipe['id']}`", inline=False)
        await self.client.reply(interaction, embed=embed, ephemeral=True)

    @app_commands.command(name="craft", description="Spend ingredients to make a cosmetic FFC trophy")
    async def craft(self, interaction: discord.Interaction, recipe: str):
        await self.client.acknowledge(interaction, force=True)
        await self.client.ensure_host()
        result = await self.client.db_call(self.client.engine.craft, str(interaction.guild_id), str(interaction.user.id), recipe,
                                          request_id="interaction:" + str(interaction.id))
        if result["ok"]:
            text = f"🛠️ Crafted **{result['item']['name']} ×{result['quantity']}**! Find it in your inventory."
            earned = milestone_lines(result, interaction.user.display_name)
            if earned:
                self.client.queue_acknowledgment("\n".join(earned))
                text += "\n" + "\n".join(milestone_lines(result))
        elif result["reason"] == "missing_ingredients":
            text = "You still need:\n" + "\n".join(f"• {item['name']}: have {item['have']}, need {item['need']}" for item in result["missing"])
        else:
            text = "Choose a recipe from /ffc recipes." if result["reason"] == "unknown_recipe" else "That crafting action has already been handled."
        await interaction.followup.send(text, ephemeral=True)

    @craft.autocomplete("recipe")
    async def recipe_autocomplete(self, interaction: discord.Interaction, current: str):
        return [app_commands.Choice(name=r["name"], value=r["id"]) for r in self.client.engine.recipes.values()
                if current.casefold() in (r["name"] + " " + r["id"]).casefold()][:25]

    @app_commands.command(name="leaderboard", description="See this server's collectors and community helpers")
    @app_commands.choices(metric=[app_commands.Choice(name=name, value=key) for key, name in {
        "catches": "Successful collections", "units": "Items gathered", "firsts": "First claims",
        "powerups": "Powerups activated", "crafts": "Trophies crafted", "xp": "Discovery XP / Explorer levels"}.items()],
        period=[app_commands.Choice(name=name, value=key) for key, name in {
            "all": "All time", "today": "Today", "week": "This week"}.items()])
    async def leaderboard(self, interaction: discord.Interaction, metric: str = "catches", period: str = "all"):
        await self.client.acknowledge(interaction)
        if period == "all":
            rows = await self.client.db_call(self.client.engine.leaderboard, str(interaction.guild_id), metric=metric)
        elif metric in ("catches", "units"):
            rows = await self.client.db_call(self.client.engine.activities.leaderboard, str(interaction.guild_id), str(interaction.channel_id), period=period, metric=metric)
        else:
            await self.client.reply(interaction, "Daily and weekly boards track **Successful collections** or **Items gathered**. Choose **All time** for the other statistics.", ephemeral=True)
            return
        title = {"all": "All time", "today": "Today", "week": "This week"}.get(period, period)
        label = {"catches": "collections", "units": "items gathered", "firsts": "first claims", "powerups": "powerups", "crafts": "trophies", "xp": "Discovery XP"}.get(metric, metric)
        lines = ("\n".join(f"**{i}.** <@{row['user_id']}> — **{row['xp']} XP** · Level {1 + row['xp'] // 100}"
                           for i, row in enumerate(rows[:10], 1)) or "No discoveries recorded yet.") if metric == "xp" else board_lines(rows, metric)
        embed = discord.Embed(title=f"FFC leaderboard · {title} · {label}", description=lines, color=0xFFE26F)
        if period != "all":
            embed.set_footer(text="America/New_York days • Week starts Monday • Current totals")
        await self.client.reply(interaction, embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    @app_commands.command(name="warp", description="Spend earned Warp points to take the crew forward or backward")
    async def warp(self, interaction: discord.Interaction):
        await self.client.show_warp(interaction)

    @app_commands.command(name="galaxy", description="See the crew's galaxy, nearby destinations, and recent jumps")
    async def galaxy(self, interaction: discord.Interaction):
        await self.client.show_galaxy(interaction)

    @app_commands.command(name="missions", description="See your two daily collection missions and Power Drive bonus")
    async def missions(self, interaction: discord.Interaction):
        await self.client.show_missions(interaction)


class AdminCommands(app_commands.Group):
    def __init__(self, client: "WildsBot"):
        super().__init__(name="ffc-admin", description="Host FFC Wilds in its configured channel", guild_only=True,
                         default_permissions=discord.Permissions(manage_guild=True))
        self.client = client

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self.client.channel_matches(interaction):
            return await self.client.require_channel(interaction)
        if not interaction.permissions.manage_guild:
            await self.client.reply(interaction, "Hosting controls require Manage Server permission.", ephemeral=True)
            return False
        return await self.client.require_channel(interaction)

    @app_commands.command(name="start", description="Start or resume encounters in this game channel")
    async def start(self, interaction: discord.Interaction):
        if not self.client.channel_ready:
            await self.client.reply(interaction, "The bot cannot use this channel yet. Check its console for missing permissions.", ephemeral=True)
            return
        await self.client.acknowledge(interaction, force=True)
        async with self.client.game_lock:
            def resume():
                self.client.engine.set_enabled(str(interaction.guild_id), str(interaction.channel_id), True)
                self.client.tips.sync_state(str(interaction.guild_id), str(interaction.channel_id), True)
            await self.client.db_call(resume)
        await interaction.followup.send("FFC Wilds is running. The first appearance will arrive shortly.", ephemeral=True)

    @app_commands.command(name="pause", description="Pause appearances and close the current one")
    async def pause(self, interaction: discord.Interaction):
        await self.client.acknowledge(interaction, force=True)
        async with self.client.game_lock:
            def pause():
                active = self.client.engine.active_event(str(interaction.guild_id), str(interaction.channel_id))
                self.client.engine.set_enabled(str(interaction.guild_id), str(interaction.channel_id), False)
                self.client.tips.sync_state(str(interaction.guild_id), str(interaction.channel_id), False)
                return active
            active = await self.client.db_call(pause)
        await interaction.followup.send("FFC Wilds paused. Collections are saved. Timed shared effects still use real time.", ephemeral=True)
        if active:
            await self.client.close_post(active)

    @app_commands.command(name="mode", description="Choose shared collection windows or fastest-player encounters")
    @app_commands.choices(mode=[app_commands.Choice(name="Community: everyone can collect once", value="community"),
                               app_commands.Choice(name="Classic: first player wins", value="classic")])
    async def mode(self, interaction: discord.Interaction, mode: str):
        await self.client.acknowledge(interaction)
        settings = replace(self.client.settings, mode=mode)
        def change_mode():
            if self.client.persist_settings:
                settings.save()
            self.client.engine.configure_channel(str(interaction.guild_id), str(interaction.channel_id), mode)
        await self.client.db_call(change_mode)
        self.client.settings = settings
        text = f"New appearances will use **{mode}** mode. Frenzies always let everyone collect."
        if mode == "classic":
            text += " Mineral boosts extend the deadline, but do not reopen an appearance after its winner."
        await self.client.reply(interaction, text, ephemeral=True)

    @app_commands.command(name="spawn", description="Host one encounter now; an existing encounter must finish first")
    @app_commands.choices(kind=KIND_CHOICES, grade=[app_commands.Choice(name=c, value=c) for c in "CBAS"])
    async def spawn(self, interaction: discord.Interaction, kind: str = "random", grade: str | None = None):
        await self.client.acknowledge(interaction, force=True)
        try:
            if grade and kind not in POWERUP_KINDS:
                raise ValueError("Choose a hotspot type to set its class. Collectibles use their catalog class.")
            event = await self.client.publish_encounter(kind=None if kind == "random" else kind, grade=grade)
            await interaction.followup.send(f"Appearance posted: **{event['item']['name']}**.", ephemeral=True)
        except (ValueError, discord.HTTPException) as exc:
            LOG.warning("Hosted encounter failed: %s", type(exc).__name__)
            text = str(exc) if isinstance(exc, ValueError) else "Discord could not publish this appearance. The game has not awarded anything."
            await interaction.followup.send(text, ephemeral=True)


class HostLeadershipLost(RuntimeError):
    """A cloud host must stop before doing any more game or channel work."""


class WildsBot(discord.Client):
    def __init__(self, settings: Settings, engine: GameEngine | None = None, *,
                 operation_guard: Callable[[], None] | None = None,
                 backup_callback: Callable[[], Awaitable[dict]] | None = None,
                 persist_settings: bool = True, automatic_backups: bool = True):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.guild_messages = settings.message_content
        intents.message_content = settings.message_content
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(),
                         activity=discord.Game(name="FFC Wilds • catch / pick / mine / tame"))
        self.settings = settings
        self.operation_guard = operation_guard
        self.backup_callback = backup_callback
        self.persist_settings = persist_settings
        self.automatic_backups = automatic_backups
        self._host_failed = False
        self.engine = engine or GameEngine(DATA_PATH / "wilds.sqlite", CATALOG_PATH)
        self.io = GameIO(self.engine, self._storage_guard)
        self.tips = TipSchedule(self.engine)
        with self.engine._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS channel_interludes (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, last_attempt_at REAL NOT NULL,
              PRIMARY KEY(guild_id,channel_id),
              FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id))""")
        self.tree = app_commands.CommandTree(self)
        self.tree.on_error = self.command_error
        self.game_lock = asyncio.Lock()
        self.channel_ready = False
        self.game_channel: discord.TextChannel | None = None
        self.views: dict[str, EncounterView] = {}
        self.warp_views: set[WarpView] = set()
        self.acknowledgments: list[str] = []
        self.last_attempt: dict[int, float] = {}
        self.last_feedback: dict[int, float] = {}
        self._last_flush = 0.0
        self._last_backup = 0.0
        self._closed_engine = False
        self._closing = False
        self._close_task = None
        self._acknowledged_interactions: dict[int, float] = {}

    def _storage_guard(self) -> None:
        """Executed by GameIO on its storage worker; never mutates Discord state."""
        if self._host_failed:
            raise RuntimeError("host_already_fenced")
        if self.operation_guard is not None:
            self.operation_guard()

    def _fence_host(self) -> None:
        if not self._host_failed:
            self._host_failed = True
            self.channel_ready = False
            self.acknowledgments.clear()
            try:
                asyncio.get_running_loop().create_task(self.close())
            except RuntimeError:
                pass

    async def db_call(self, operation, *args, **kwargs):
        """Run guarded storage work without occupying Discord's event loop."""
        if self._host_failed or self._closing:
            raise HostLeadershipLost("Cloud ownership was lost; this game connection is closing.")
        try:
            return await self.io.run(operation, *args, **kwargs)
        except GuardFailed:
            self._fence_host()
            raise HostLeadershipLost("Cloud ownership could not be verified; this game connection is closing.") from None

    async def ensure_host(self) -> None:
        await self.db_call(lambda: None)

    @staticmethod
    def log_safe_error(stage: str, error: Exception) -> None:
        # Only caller-controlled stages, type names and numeric codes; never
        # stringify exceptions, interaction objects, tokens, headers or bodies.
        code = getattr(error, "code", None)
        status = getattr(error, "status", None)
        LOG.warning("FFC operation failed stage=%s type=%s code=%s status=%s",
                    stage[:40], type(error).__name__[:60],
                    code if type(code) is int else 0,
                    status if type(status) is int else 0)

    def channel_matches(self, interaction: discord.Interaction) -> bool:
        return (str(interaction.guild_id) == self.settings.guild_id and
                str(interaction.channel_id) == self.settings.channel_id and not interaction.user.bot)

    def response_done(self, interaction: discord.Interaction) -> bool:
        return bool(interaction.response.is_done() or interaction.id in self._acknowledged_interactions)

    async def acknowledge(self, interaction: discord.Interaction, *, force: bool = False) -> None:
        """Cloud interactions acknowledge before any network-backed storage call."""
        if getattr(interaction, "type", None) == discord.InteractionType.autocomplete:
            return
        if (not force and getattr(self.engine, "backend", "sqlite") != "postgresql") or self.response_done(interaction):
            return
        started = time.monotonic()
        try:
            await interaction.response.defer(ephemeral=True, thinking=True)
        except Exception as error:
            self.log_safe_error("interaction_defer", error)
            raise
        self._acknowledged_interactions[interaction.id] = time.monotonic()
        if len(self._acknowledged_interactions) > 2048:
            now = time.monotonic()
            self._acknowledged_interactions = {
                key: value for key, value in self._acknowledged_interactions.items() if now - value < 900
            }
            while len(self._acknowledged_interactions) > 2048:
                self._acknowledged_interactions.pop(next(iter(self._acknowledged_interactions)))
        elapsed = time.monotonic() - started
        if elapsed > 1:
            LOG.warning("FFC interaction acknowledgement slow duration_ms=%d", min(int(elapsed * 1000), 3600000))

    async def reply(self, interaction: discord.Interaction, *args, **kwargs):
        if self.response_done(interaction):
            return await interaction.followup.send(*args, **kwargs)
        return await interaction.response.send_message(*args, **kwargs)

    def assert_host(self) -> None:
        """Fence cloud work using the same PostgreSQL session as game writes.

        The ordinary Windows host has no extra guard. A failed cloud guard
        permanently invalidates this client; it never reconnects its storage
        session or resumes work under an old ownership claim.
        """
        if self._host_failed:
            raise HostLeadershipLost("Cloud ownership was lost; this game connection is closing.")
        if self.operation_guard is None:
            return
        try:
            self.operation_guard()
        except Exception:
            self._fence_host()
            raise HostLeadershipLost("Cloud ownership could not be verified; this game connection is closing.") from None

    async def send_public(self, *args, **kwargs):
        await self.ensure_host()
        channel = self.game_channel
        if (not self.channel_ready or not channel
                or str(channel.id) != self.settings.channel_id
                or str(channel.guild.id) != self.settings.guild_id):
            raise ValueError("The configured game channel is not ready.")
        kwargs.setdefault("silent", True)
        kwargs["allowed_mentions"] = discord.AllowedMentions.none()
        cancelled = False
        try:
            return await channel.send(*args, **kwargs)
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            await self._verify_after_public_send(cancelled)

    async def edit_public(self, message, **kwargs):
        await self.ensure_host()
        cancelled = False
        try:
            return await message.edit(**kwargs)
        except asyncio.CancelledError:
            cancelled = True
            raise
        finally:
            await self._verify_after_public_send(cancelled)

    async def _verify_after_public_send(self, cancelled: bool):
        try:
            await self.ensure_host()
        except HostLeadershipLost:
            # A failed guard still fences the client. Preserve cancellation so
            # a scheduler cannot swallow it as a routine retryable exception.
            if not cancelled:
                raise

    def queue_acknowledgment(self, text: str):
        """Enqueue a public receipt only; rewards have already committed."""
        self.acknowledgments.extend(message_chunks(text))

    def queue_claim(self, display_name: str, result: dict):
        if result.get("ok"):
            self.queue_acknowledgment(public_claim_text(display_name, result))

    async def flush_acknowledgments(self, now: float | None = None):
        await self.ensure_host()
        now = time.monotonic() if now is None else now
        channel = self.game_channel
        if (not self.acknowledgments or now - self._last_flush < RECEIPT_INTERVAL_SECONDS
                or not self.channel_ready or not channel
                or str(channel.id) != self.settings.channel_id
                or str(channel.guild.id) != self.settings.guild_id):
            return
        batch, length = [], 0
        while self.acknowledgments:
            head = self.acknowledgments[0]
            # Also defend against oversized entries queued by a future caller.
            if message_units(head) > RECEIPT_MESSAGE_LIMIT:
                self.acknowledgments[0:1] = message_chunks(head)
                head = self.acknowledgments[0]
            if not head:
                self.acknowledgments.pop(0)
                continue
            size = message_units(head) + (1 if batch else 0)
            if batch and length + size > RECEIPT_MESSAGE_LIMIT:
                break
            batch.append(self.acknowledgments.pop(0))
            length += size
        self._last_flush = now
        if not batch:
            return
        try:
            await self.send_public("\n".join(batch))
        except (discord.HTTPException, OSError, asyncio.TimeoutError):
            # A timeout can occur after Discord accepted the message. Do not
            # repeat the receipt or any economy write after uncertain delivery.
            LOG.warning("A collection acknowledgment could not be confirmed; collections and milestones remain saved. The receipt will not be replayed.")

    async def setup_hook(self):
        if self.settings.application_id and self.user and str(self.user.id) != self.settings.application_id:
            raise RuntimeError("This token belongs to a different bot than the configured application. Check your game bot settings.")
        def prepare_game():
            self.engine.configure_channel(self.settings.guild_id, self.settings.channel_id, self.settings.mode)
            state = self.engine.status(self.settings.guild_id, self.settings.channel_id)
            self.tips.sync_state(self.settings.guild_id, self.settings.channel_id, state["enabled"])
            self.engine.recover_pending(max_age_seconds=0)
        await self.db_call(prepare_game)
        guild = discord.Object(id=int(self.settings.guild_id))
        self.tree.add_command(WildsCommands(self), guild=guild)
        self.tree.add_command(AdminCommands(self), guild=guild)
        await self.tree.sync(guild=guild)
        await self.ensure_host()
        self.scheduler.start()

    async def on_ready(self):
        await self.ensure_host()
        self.channel_ready = False
        try:
            channel = self.get_channel(int(self.settings.channel_id)) or await self.fetch_channel(int(self.settings.channel_id))
            await self.ensure_host()
            if not isinstance(channel, discord.TextChannel) or str(channel.guild.id) != self.settings.guild_id:
                raise ValueError("Game channel must be a text channel in the configured server.")
            member = channel.guild.me
            if not member:
                raise ValueError("Bot membership is not available for the configured server.")
            permissions = channel.permissions_for(member)
            required = ("view_channel", "send_messages", "embed_links", "attach_files", "read_message_history")
            missing = [name for name in required if not getattr(permissions, name)]
            if missing:
                raise ValueError("Game channel permissions missing: " + ", ".join(missing))
            self.game_channel = channel
            for event in await self.db_call(self.engine.expire_events):
                await self.close_post(event)
            event = await self.db_call(self.engine.active_event, self.settings.guild_id, self.settings.channel_id)
            if event:
                try:
                    post = await channel.fetch_message(int(event["message_id"]))
                except discord.NotFound:
                    await self.db_call(self.engine.cancel_event, event["id"])
                    previous = self.views.pop(event["id"], None)
                    if previous:
                        previous.stop()
                else:
                    await self.ensure_host()
                    previous = self.views.pop(event["id"], None)
                    if previous:
                        previous.stop()
                    view = EncounterView(self, event)
                    self.views[event["id"]] = view
                    self.add_view(view, message_id=int(event["message_id"]))
                    # Refresh an old deadline after a rules migration, or a
                    # first-claim countdown whose previous edit failed.
                    with contextlib.suppress(discord.HTTPException):
                        await self.edit_public(post, embed=event_embed(event))
            await self.ensure_host()
            self.channel_ready = True
            def sync_ready():
                state = self.engine.status(self.settings.guild_id, self.settings.channel_id)
                self.tips.sync_state(self.settings.guild_id, self.settings.channel_id, state["enabled"])
                return state
            state = await self.db_call(sync_ready)
            LOG.info("FFC Wilds v%s ready in configured channel. Game %s.", __version__, "running" if state["enabled"] else "paused; use /ffc-admin start")
        except (discord.HTTPException, ValueError) as error:
            self.channel_ready = False
            self.log_safe_error("channel_ready", error)

    async def on_disconnect(self):
        self.channel_ready = False

    async def on_resumed(self):
        # A successful gateway resume does not emit a second on_ready event.
        await self.on_ready()

    async def require_channel(self, interaction: discord.Interaction) -> bool:
        okay = self.channel_matches(interaction)
        if not okay:
            await self.reply(interaction, "FFC Wilds runs only in its configured game channel.", ephemeral=True)
            return False
        if getattr(interaction, "type", None) == discord.InteractionType.autocomplete:
            # Recipe completion reads static catalog metadata only and cannot
            # defer using the regular command response type.
            return not self._host_failed and not self._closing
        # Acknowledge before even the leadership check: cloud ownership uses
        # remote storage, while this acknowledgement cannot award anything.
        await self.acknowledge(interaction)
        try:
            await self.ensure_host()
        except HostLeadershipLost:
            with contextlib.suppress(discord.HTTPException):
                await self.reply(interaction, "The cloud game is reconnecting. No collection or Warp was started by this request.", ephemeral=True)
            return False
        return True

    async def show_warp(self, interaction: discord.Interaction):
        if not await self.require_channel(interaction):
            return
        def read_warp():
            return (self.engine.progression.status(str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id)),
                    self.engine.status(str(interaction.guild_id), str(interaction.channel_id)))
        journey, state = await self.db_call(read_warp)
        embed = discord.Embed(title="🚀 Choose the crew's next jump", color=0xB28BF5,
            description=(f"Current galaxy: **{galaxy_label(journey['galaxy'])}**\n"
                f"Your bank: **{journey['balance']}/{WARP_BANK_CAP} Warp points** · **{journey['charges']}** jump(s).\n\n"
                f"Selecting a destination below confirms spending **{WARP_COST} of your Warp points** "
                "to move the whole crew. Everyone keeps their collection."))
        embed.add_field(name="⬅️ Previous galaxy", value=galaxy_label(journey["previous"]))
        embed.add_field(name="➡️ Next galaxy", value=galaxy_label(journey["next"]))
        if journey["balance"] < WARP_COST:
            embed.add_field(name="Earn your next jump", value=f"Collect **{WARP_COST - journey['balance']}** more Warp points. Each collection earns 1; Power Drives and **/ffc missions** help you reach the goal.", inline=False)
        if journey["cooldown_remaining"]:
            embed.add_field(name="Drive recharging", value=f"The next shared jump is available <t:{int(journey['cooldown_until'])}:R>.", inline=False)
        if not state["enabled"]:
            embed.add_field(name="Game paused", value="A moderator must resume the game before the crew can Warp.", inline=False)
        embed.set_footer(text=f"Choices expire in 2 minutes • Shared cooldown: {WARP_COOLDOWN_SECONDS // 60} minutes • An open discovery keeps its original location")
        view = WarpView(self, interaction.user.id, journey)
        if not state["enabled"]:
            for button in view.children[:2]:
                button.disabled = True
        self.warp_views.add(view)
        try:
            await self.reply(interaction, embed=embed, view=view, ephemeral=True)
        except BaseException:
            view.finish()
            raise

    async def show_galaxy(self, interaction: discord.Interaction):
        if not await self.require_channel(interaction):
            return
        journey = await self.db_call(self.engine.progression.status, str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id))
        embed = discord.Embed(title="🪐 " + galaxy_label(journey["galaxy"]), color=0x57B9EF,
            description=("The crew's shared FFC Wilds destination. Earn points by collecting and use **/ffc warp** to choose the next jump.\n"
                         f"Your bank: **{journey['balance']}/{WARP_BANK_CAP} points** · **{journey['charges']}** jump(s)."))
        embed.add_field(name="Previous", value=galaxy_label(journey["previous"]))
        embed.add_field(name="Next", value=galaxy_label(journey["next"]))
        embed.add_field(name="Shared drive", value=(f"Recharges <t:{int(journey['cooldown_until'])}:R>" if journey["cooldown_remaining"] else "Ready for a member with 50 Warp points"), inline=False)
        history = journey.get("history", [])[:5]
        lines = [f"<@{entry['user_id']}> · {galaxy_label(entry['from_galaxy'])} → **{galaxy_label(entry['to_galaxy'])}** · <t:{int(entry['at'])}:R>" for entry in history]
        embed.add_field(name="Recent jumps", value="\n".join(lines) or "The crew's journey begins here.", inline=False)
        embed.set_footer(text="FFC game route: 1–256, wrapping both ways • Collections stay with their explorers")
        await self.reply(interaction, embed=embed, ephemeral=True, allowed_mentions=discord.AllowedMentions.none())

    async def show_missions(self, interaction: discord.Interaction):
        if not await self.require_channel(interaction):
            return
        def read_missions():
            return (self.engine.activities.missions(str(interaction.guild_id), str(interaction.channel_id), str(interaction.user.id)),
                    self.engine.activities.drive_status(str(interaction.guild_id), str(interaction.channel_id)))
        state, drive = await self.db_call(read_missions)
        await self.reply(interaction, embed=mission_embed(state, drive), ephemeral=True)

    async def announce_warp(self, display_name: str, result: dict):
        await self.ensure_host()
        channel = self.game_channel
        if (not self.channel_ready or not channel or str(channel.id) != self.settings.channel_id
                or str(channel.guild.id) != self.settings.guild_id):
            LOG.warning("Warp committed while channel unavailable; journey history retains the result.")
            return
        text = (f"🚀 **{clean_name(display_name)} engaged the crew's Warp drive!**\n"
                f"**{galaxy_label(result['from_galaxy'])} → {galaxy_label(result['to_galaxy'])}**\n"
                "New discoveries belong to our new destination. Any discovery already open stays available.\n"
                f"The shared drive recharges <t:{int(result['cooldown_until'])}:R>. Check **/ffc galaxy** for the route.")
        earned = milestone_lines(result, display_name)
        if earned:
            text += "\n" + "\n".join(earned)
        try:
            await self.send_public(text)
        except (discord.HTTPException, OSError, asyncio.TimeoutError):
            LOG.warning("Warp announcement could not be posted; the completed journey is available in /ffc galaxy.")

    def interlude_available(self) -> bool:
        """Persist spacing across reconnects without delaying collectible posts."""
        now = self.engine._now()
        with self.engine._lock:
            row = self.engine.db.execute("SELECT last_attempt_at FROM channel_interludes WHERE guild_id=? AND channel_id=?",
                                         (self.settings.guild_id, self.settings.channel_id)).fetchone()
            tip = self.engine.db.execute("SELECT last_sent_at FROM channel_tips WHERE guild_id=? AND channel_id=?",
                                         (self.settings.guild_id, self.settings.channel_id)).fetchone()
        latest = max(row[0] if row else 0, (tip[0] or 0) if tip else 0)
        return now - latest >= INTERLUDE_SPACING_SECONDS

    def mark_interlude_attempt(self):
        with self.engine._transaction() as db:
            db.execute("""INSERT INTO channel_interludes(guild_id,channel_id,last_attempt_at)
                          VALUES(?,?,?) ON CONFLICT(guild_id,channel_id)
                          DO UPDATE SET last_attempt_at=excluded.last_attempt_at""",
                       (self.settings.guild_id, self.settings.channel_id, self.engine._now()))

    async def on_message(self, message: discord.Message):
        if (not self.settings.message_content or message.author.bot or message.webhook_id or not message.guild
                or str(message.guild.id) != self.settings.guild_id or str(message.channel.id) != self.settings.channel_id):
            return
        action = message.content.strip().casefold()
        if action not in ACTIONS:
            return
        await self.ensure_host()
        now = time.monotonic()
        if now - self.last_attempt.get(message.author.id, -100) < 0.5:
            return
        self.last_attempt[message.author.id] = now
        async with self.game_lock:
            message_id, user_id = str(message.id), str(message.author.id)
            reply_to = str(message.reference.message_id) if message.reference else None
            def claim_message():
                event = self.engine.active_event(self.settings.guild_id, self.settings.channel_id)
                if not event:
                    return None
                # A delayed/replayed message must never claim a new discovery.
                if int(message_id) <= int(event["message_id"]):
                    return None
                if reply_to and reply_to != str(event["message_id"]):
                    return None
                return self.engine.claim(self.settings.guild_id, self.settings.channel_id, user_id, action,
                                         event_id=event["id"], request_id="message:" + message_id)
            result = await self.db_call(claim_message)
        if result is None:
            return
        if result.get("ok"):
            self.queue_claim(message.author.display_name, result)
        elif result.get("reason") == "wrong_action" and now - self.last_feedback.get(message.author.id, -100) > 10:
            self.last_feedback[message.author.id] = now
            with contextlib.suppress(discord.HTTPException):
                await self.ensure_host()
                try:
                    await message.reply(claim_text(result), mention_author=False, delete_after=8)
                finally:
                    await self.ensure_host()
        if result.get("event"):
            await self.finish_if_closed(result["event"], refresh=result.get("ok") and result.get("first"))

    async def publish_encounter(self, kind: str | None = None, grade: str | None = None) -> dict:
        await self.ensure_host()
        if not self.channel_ready or not self.game_channel:
            raise ValueError("The game channel is not ready. Check the bot console.")
        async with self.game_lock:
            event = await self.db_call(self.engine.spawn, self.settings.guild_id, self.settings.channel_id, kind=kind, grade=grade)
            view = None
            message = None
            file = None
            try:
                view = EncounterView(self, event)
                art = icon_path(event["item"])
                file = discord.File(art, filename=art.name) if art else None
                kwargs = {"embed": event_embed(event), "view": view, "silent": True}
                if file:
                    kwargs["file"] = file
                message = await self.send_public(**kwargs)
                event = await self.db_call(self.engine.bind_message, event["id"], str(message.id))
                if event["status"] != "open":
                    view.stop()
                    await self.edit_public(message, embed=event_embed(event, closed=True), view=None)
                    return event
                self.views[event["id"]] = view
                with contextlib.suppress(discord.HTTPException):
                    await self.edit_public(message, embed=event_embed(event))
                return event
            except BaseException:
                if not self._host_failed and not self._closing:
                    await self.db_call(self.engine.cancel_event, event["id"])
                if view:
                    view.stop()
                if message and not self._host_failed and not self._closing:
                    with contextlib.suppress(discord.HTTPException):
                        await self.edit_public(message, embed=event_embed(event, closed=True), view=None)
                raise
            finally:
                if file:
                    file.close()

    async def finish_if_closed(self, event: dict, *, refresh: bool = False):
        await self.ensure_host()
        if event["status"] != "open":
            await self.close_post(event)
        elif refresh and not event["frenzy"] and self.game_channel and event.get("message_id"):
            # Only the first claim changes the deadline. Later claims do not
            # generate repeated card edits or extend the shared window.
            current = await self.db_call(self.engine.event, event["id"])
            if current and current["status"] == "open":
                with contextlib.suppress(discord.HTTPException):
                    await self.edit_public(self.game_channel.get_partial_message(int(current["message_id"])), embed=event_embed(current))

    async def close_post(self, event: dict):
        await self.ensure_host()
        view = self.views.pop(event["id"], None)
        if view:
            view.stop()
        if not event.get("message_id") or not self.game_channel:
            return
        if str(event["channel_id"]) != self.settings.channel_id:
            return
        with contextlib.suppress(discord.HTTPException):
            await self.edit_public(self.game_channel.get_partial_message(int(event["message_id"])), embed=event_embed(event, closed=True), view=None)

    async def maybe_publish_tip(self):
        """Send one due channel tip without interrupting a timed collection."""
        await self.ensure_host()
        channel = self.game_channel
        if (not self.is_ready() or not self.channel_ready or not channel
                or str(channel.id) != self.settings.channel_id
                or str(channel.guild.id) != self.settings.guild_id):
            return
        async with self.game_lock:
            def reserve_tip():
                if not self.interlude_available():
                    return None, None
                state = self.engine.status(self.settings.guild_id, self.settings.channel_id)
                active = state.get("active_event")
                blocked = bool(state["frenzy_remaining"] or
                               (active and (active.get("frenzy") or active.get("expires_at") is not None)))
                reservation = self.tips.reserve(self.settings.guild_id, self.settings.channel_id,
                                                enabled=state["enabled"], blocked=blocked)
                if reservation is not None:
                    self.mark_interlude_attempt()
                return reservation, active
            reservation, active = await self.db_call(reserve_tip)
        if reservation is None:
            return
        text = "💡 **FFC tip** · " + reservation.text
        if active and active.get("message_id") and active.get("expires_at") is None:
            link = f"https://discord.com/channels/{self.settings.guild_id}/{self.settings.channel_id}/{active['message_id']}"
            text += f"\n[Your current discovery is still waiting.]({link})"
        try:
            message = await self.send_public(text)
        except (discord.HTTPException, OSError, asyncio.TimeoutError) as exc:
            if isinstance(exc, discord.HTTPException) and 400 <= exc.status < 500:
                await self.db_call(self.tips.failed, reservation)
                LOG.warning("Player tip was rejected; retrying in five minutes: %s", type(exc).__name__)
            else:
                LOG.warning("Player tip delivery is uncertain; keeping its reserved hourly slot to avoid a duplicate: %s", type(exc).__name__)
            return
        await self.db_call(self.tips.sent, reservation, str(message.id))

    async def maybe_publish_activity(self):
        """Publish one durable crew notice between collection windows."""
        await self.ensure_host()
        channel = self.game_channel
        if (not self.is_ready() or not self.channel_ready or not channel
                or str(channel.id) != self.settings.channel_id
                or str(channel.guild.id) != self.settings.guild_id):
            return
        async with self.game_lock:
            def reserve_activity():
                if not self.interlude_available():
                    return None, None
                state = self.engine.status(self.settings.guild_id, self.settings.channel_id)
                if not state["enabled"]:
                    return None, None
                active = state.get("active_event")
                blocked = bool(state["frenzy_remaining"] or
                               self.engine.activities.drive_status(self.settings.guild_id, self.settings.channel_id)["active"] or
                               (active and (active.get("frenzy") or active.get("expires_at") is not None)))
                reservation = self.engine.activities.reserve_notice(self.settings.guild_id, self.settings.channel_id,
                                                                    blocked=blocked)
                if reservation is not None:
                    self.mark_interlude_attempt()
                return reservation, active
            reservation, active = await self.db_call(reserve_activity)
        if reservation is None:
            return
        embed = activity_embed(reservation)
        if active and active.get("message_id") and active.get("expires_at") is None:
            link = f"https://discord.com/channels/{self.settings.guild_id}/{self.settings.channel_id}/{active['message_id']}"
            embed.add_field(name="Your discovery is still waiting", value=f"[Return to the open appearance.]({link})", inline=False)
        try:
            message = await self.send_public(embed=embed)
        except (discord.HTTPException, OSError, asyncio.TimeoutError) as exc:
            if isinstance(exc, discord.HTTPException) and 400 <= exc.status < 500:
                await self.db_call(self.engine.activities.notice_failed, reservation)
                LOG.warning("Crew notice was rejected; its persisted retry policy applies: %s", type(exc).__name__)
            else:
                LOG.warning("Crew notice delivery is uncertain; preserving the reservation to avoid a duplicate: %s", type(exc).__name__)
            return
        await self.db_call(self.engine.activities.notice_sent, reservation, str(message.id))

    @tasks.loop(seconds=1)
    async def scheduler(self):
        if not self.is_ready() or not self.channel_ready:
            return
        try:
            await self.ensure_host()
            for event in await self.db_call(self.engine.expire_events):
                await self.close_post(event)
            for channel in await self.db_call(self.engine.due_channels):
                if channel["guild_id"] == self.settings.guild_id and channel["channel_id"] == self.settings.channel_id:
                    try:
                        await self.publish_encounter()
                    except (ValueError, discord.HTTPException) as exc:
                        LOG.warning("Encounter not posted: %s", type(exc).__name__)
            now = time.monotonic()
            await self.flush_acknowledgments(now)
            await self.maybe_publish_activity()
            await self.maybe_publish_tip()
            if self.automatic_backups and now - self._last_backup > 21600:
                if self.backup_callback:
                    await self.backup_callback()
                else:
                    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
                    await self.db_call(self.engine.backup, DATA_PATH / "backups" / f"wilds-{stamp}.sqlite")
                self._last_backup = now
            if len(self.last_attempt) > 2000:
                self.last_attempt = {k: v for k, v in self.last_attempt.items() if now-v < 300}
                self.last_feedback = {k: v for k, v in self.last_feedback.items() if now-v < 300}
        except Exception as error:
            self.log_safe_error("scheduler", error)

    @scheduler.before_loop
    async def before_scheduler(self):
        await self.wait_until_ready()

    async def command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.CheckFailure):
            return
        self.log_safe_error("slash_command", error)
        text = "That action could not complete. Your saved collection is safe; check the bot console."
        with contextlib.suppress(discord.HTTPException):
            await self.reply(interaction, text, ephemeral=True)

    async def on_error(self, event_method: str, *args, **kwargs):
        # discord.Client's default handler prints traceback/local exception text.
        # Report only the fixed event-method name and exception class instead.
        import sys
        error = sys.exception()
        if error is not None:
            self.log_safe_error("gateway_" + event_method[:25], error)

    async def close(self):
        if self._close_task is None:
            self._closing = True
            self._close_task = asyncio.create_task(self._close_resources(), name="ffc-discord-close")
        if asyncio.current_task() is self._close_task:
            return
        await _completion_before_cancel(self._close_task)

    async def _close_resources(self):
        try:
            task = self.scheduler.get_task()
            self.scheduler.stop()
            self.scheduler.cancel()
            if task and task is not asyncio.current_task():
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as error:
                    self.log_safe_error("scheduler_shutdown", error)
            for view in self.views.values():
                view.stop()
            for view in list(self.warp_views):
                view.finish()
            await super().close()
        finally:
            # A transport-close error must not abandon an in-flight commit or
            # allow runtime cleanup to close its connection prematurely.
            if not self._closed_engine:
                await self.io.close()
                if getattr(self.engine, "backend", "sqlite") == "postgresql":
                    await asyncio.to_thread(self.engine.close)
                else:
                    self.engine.close()
                self._closed_engine = True


def run_bot(settings: Settings, token: str):
    log_directory = DATA_PATH / "logs"
    log_directory.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(log_directory / "ffc-wilds.log", maxBytes=1024 * 1024,
                                       backupCount=3, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), file_handler], force=True)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    client = WildsBot(settings)
    try:
        client.run(token, log_handler=None)
    except discord.LoginFailure as exc:
        LOG.error("Discord rejected the game bot token; enter the FFC Wilds token at the local prompt.")
        raise ValueError("Discord rejected the game bot token. Get its bot token from the Developer Portal; do not paste it into chat.") from exc
    except discord.PrivilegedIntentsRequired as exc:
        LOG.error("Message Content Intent is unavailable; enable it in the Developer Portal or use button-only mode.")
        raise ValueError("Enable Message Content Intent for typed words, or configure message_content=false to use buttons and slash commands.") from exc
