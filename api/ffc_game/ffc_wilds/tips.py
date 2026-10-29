"""Persistent, low-frequency player tips for a configured game channel.

The schedule shares the game engine's SQLite connection and transaction lock.
An attempt reserves its next hourly slot before Discord is called. If the
process stops after sending but before confirming, a restart therefore cannot
immediately repeat a tip. Known failures retry after five minutes without
advancing the rotation. No player data or message content is stored here.
"""
from __future__ import annotations

from dataclasses import dataclass
import sqlite3
import uuid

from .engine import GRADE_SECONDS, GRADE_XP, GameEngine


TIP_INTERVAL_SECONDS = 60 * 60
TIP_RETRY_SECONDS = 5 * 60
PLAYER_TIPS = (
    "Type **`/ffc inventory`** to see your fish, plants, minerals, companions, and crafted keepsakes. Choose the **ffc** command group for this game.",
    "Try **`/ffc catalog`** to see what you have discovered and what is still waiting to be found.",
    "Got duplicates? **`/ffc recipes`** shows the materials you can turn into FFC keepsakes.",
    "Ready to make something? Use **`/ffc craft`** and choose a recipe. Missing ingredients are shown before anything is spent.",
    "Check **`/ffc status`** for your remaining powered collections, the current appearance, and shared powerup timers.",
    "Use **`/ffc profile`** to see your Explorer title, XP progress bar, and recent badges. Every **100 Discovery XP** earns a new level.",
    "See how the crew is doing with **`/ffc leaderboard`**. You can compare collections, items gathered, first claims, and more.",
    "New to the Wilds? **`/ffc help`** explains catching, picking, mining, taming, powerups, and crafting.",
    ("Gas nodes start a shared **Frenzy**: "
     + " · ".join(f"{grade} {GRADE_SECONDS[grade] // 60} min" for grade in "CBAS")
     + ". Type **`powerup`** or press the node's button to activate one."),
    ("Discovery XP grows with class: **"
     + " · ".join(f"{grade} {GRADE_XP[grade]}" for grade in "CBAS")
     + "**. Powered quantities give more items; each successful collection still earns its normal XP."),
    "Every successful collection earns **1 Warp point**. **`/ffc warp`** spends 50 of your points to take the whole crew one galaxy forward or backward.",
    "Which way next? **`/ffc galaxy`** shows the crew's location and recent jumps. The shared Warp drive recharges for **2 minutes** after a jump.",
    "Your **two daily missions** each offer **10 Warp points**. Check **`/ffc missions`** for goals and progress; missions reset at midnight Eastern.",
    "Watch for a surprise **POWER DRIVE**! For **30 minutes**, collections earn **double or triple Warp progress**. Your inventory and Discovery XP follow their usual rules.",
    "Try **`/ffc leaderboard period:today`** or **`/ffc leaderboard period:week`** to compare the crew's recent collections and items gathered.",
    "Your next badge is waiting! **`/ffc achievements`** shows 20 permanent goals for fishing, farming, mining, companions, crafting, and helping the crew.",
    "Want to chase the next milestone? Try **`/ffc achievements filter:locked`** for badges still to earn, or **`filter:earned`** to admire your collection.",
    "Both typed words and button clicks count. Successful collections, new levels, and achievements appear in the crew feed so everyone can celebrate together.",
    "Compare Explorer levels with **`/ffc leaderboard metric:xp`**. Class sets your XP: C 10, B 20, A 40, S 80. Powered quantities keep the usual XP.",
)


@dataclass(frozen=True)
class TipReservation:
    guild_id: str
    channel_id: str
    lease_id: str
    tip_index: int
    text: str


class TipSchedule:
    """Store one rotating schedule per channel, without catch-up bursts."""

    def __init__(self, engine: GameEngine):
        self.engine = engine
        with engine._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS channel_tips (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
              tip_index INTEGER NOT NULL DEFAULT 0 CHECK(tip_index >= 0),
              next_due_at REAL NOT NULL, paused INTEGER NOT NULL,
              lease_id TEXT, last_sent_at REAL, last_message_id TEXT,
              PRIMARY KEY(guild_id,channel_id),
              FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id))""")

    @staticmethod
    def _sync(db: sqlite3.Connection, guild_id: str, channel_id: str,
              enabled: bool, now: float) -> sqlite3.Row:
        paused = int(not enabled)
        db.execute("""INSERT OR IGNORE INTO channel_tips
                      (guild_id,channel_id,next_due_at,paused) VALUES(?,?,?,?)""",
                   (guild_id, channel_id, now + TIP_INTERVAL_SECONDS, paused))
        row = db.execute("SELECT * FROM channel_tips WHERE guild_id=? AND channel_id=?",
                         (guild_id, channel_id)).fetchone()
        if row["paused"] != paused:
            # A pause stops notifications. Resuming starts a fresh hour instead
            # of delivering a backlog from time spent paused.
            db.execute("""UPDATE channel_tips SET paused=?,next_due_at=?,lease_id=NULL
                          WHERE guild_id=? AND channel_id=?""",
                       (paused, now + TIP_INTERVAL_SECONDS, guild_id, channel_id))
            row = db.execute("SELECT * FROM channel_tips WHERE guild_id=? AND channel_id=?",
                             (guild_id, channel_id)).fetchone()
        return row

    def sync_state(self, guild_id: str, channel_id: str, enabled: bool) -> None:
        """Observe startup or an explicit host pause/resume without posting."""
        now = self.engine._now()
        with self.engine._transaction() as db:
            self._sync(db, str(guild_id), str(channel_id), bool(enabled), now)

    def reserve(self, guild_id: str, channel_id: str, *, enabled: bool,
                blocked: bool = False) -> TipReservation | None:
        """Reserve one due tip, unless paused or temporarily busy collecting."""
        guild, channel, now = str(guild_id), str(channel_id), self.engine._now()
        with self.engine._transaction() as db:
            row = self._sync(db, guild, channel, bool(enabled), now)
            if not enabled or blocked or now < row["next_due_at"]:
                return None
            index = row["tip_index"] % len(PLAYER_TIPS)
            lease_id = uuid.uuid4().hex
            db.execute("""UPDATE channel_tips SET next_due_at=?,lease_id=?
                          WHERE guild_id=? AND channel_id=?""",
                       (now + TIP_INTERVAL_SECONDS, lease_id, guild, channel))
            return TipReservation(guild, channel, lease_id, index, PLAYER_TIPS[index])

    def sent(self, reservation: TipReservation, message_id: str) -> bool:
        """Advance only the matching attempt; stale completion cannot skip tips."""
        now = self.engine._now()
        with self.engine._transaction() as db:
            cursor = db.execute("""UPDATE channel_tips
                  SET tip_index=?,next_due_at=?,lease_id=NULL,last_sent_at=?,last_message_id=?
                  WHERE guild_id=? AND channel_id=? AND lease_id=?""",
                  ((reservation.tip_index + 1) % len(PLAYER_TIPS), now + TIP_INTERVAL_SECONDS,
                   now, str(message_id), reservation.guild_id, reservation.channel_id,
                   reservation.lease_id))
            return cursor.rowcount == 1

    def failed(self, reservation: TipReservation) -> bool:
        """Back off a known failed send while retaining the current tip."""
        now = self.engine._now()
        with self.engine._transaction() as db:
            cursor = db.execute("""UPDATE channel_tips SET next_due_at=?,lease_id=NULL
                  WHERE guild_id=? AND channel_id=? AND lease_id=?""",
                  (now + TIP_RETRY_SECONDS, reservation.guild_id, reservation.channel_id,
                   reservation.lease_id))
            return cursor.rowcount == 1
