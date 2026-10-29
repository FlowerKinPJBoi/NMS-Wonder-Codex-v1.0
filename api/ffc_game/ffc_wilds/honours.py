"""Permanent explorer badges and progress through the existing XP levels.

Badges describe saved accomplishments; they do not mint currency or XP. New
unlocks share the transaction that saved the collection, craft or crew Warp.
The initial migration quietly recognises history so installing the feature
does not flood the channel with old achievements.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import GameEngine


XP_PER_LEVEL = 100
TITLES = (
    (1, "New Arrival"), (5, "Field Scout"), (10, "Planet Roamer"),
    (20, "Seasoned Explorer"), (35, "Starfarer"), (50, "Wilds Legend"),
)
COLLECTION_KINDS = frozenset(("fish", "plant", "mineral", "pet"))
POWERUP_KINDS = frozenset(("electromagnetic", "gas", "mineral_powerup"))


def level_progress(total_xp: int) -> dict:
    """Return progress without changing the established 100-XP level curve."""
    if isinstance(total_xp, bool) or not isinstance(total_xp, int) or total_xp < 0:
        raise ValueError("Discovery XP must be a nonnegative integer")
    level, earned = 1 + total_xp // XP_PER_LEVEL, total_xp % XP_PER_LEVEL
    title = next(title for minimum, title in reversed(TITLES) if level >= minimum)
    return {"level": level, "title": title, "xp_into_level": earned,
            "xp_for_next_level": XP_PER_LEVEL, "xp_to_next_level": XP_PER_LEVEL - earned,
            "next_level": level + 1, "total_xp": total_xp}


@dataclass(frozen=True)
class Badge:
    id: str
    title: str
    description: str
    emoji: str
    metric: str
    target: int


BADGES = (
    Badge("first_discovery", "First Footprints", "Make your first successful collection.", "👣", "catches", 1),
    Badge("collector_25", "Getting Your Boots Muddy", "Make 25 successful collections.", "🥾", "catches", 25),
    Badge("collector_100", "Wilds Regular", "Make 100 successful collections.", "🧭", "catches", 100),
    Badge("collector_500", "Expedition Legend", "Make 500 successful collections.", "🏆", "catches", 500),
    Badge("fish_10", "Gone Fishing", "Catch fish from 10 appearances.", "🐟", "fish", 10),
    Badge("fish_50", "Reel Deal", "Catch fish from 50 appearances.", "🎣", "fish", 50),
    Badge("plant_10", "Green Fingers", "Pick plants from 10 appearances.", "🌱", "plant", 10),
    Badge("plant_50", "Harvest Hero", "Pick plants from 50 appearances.", "🌾", "plant", 50),
    Badge("mineral_10", "Rock Hound", "Mine 10 mineral deposits.", "⛏️", "mineral", 10),
    Badge("mineral_50", "Deep Delver", "Mine 50 mineral deposits.", "💎", "mineral", 50),
    Badge("pet_1", "New Best Friend", "Tame your first companion.", "🐾", "pet", 1),
    Badge("pet_10", "Creature Keeper", "Tame companions from 10 appearances.", "💚", "pet", 10),
    Badge("all_rounder", "All-Round Explorer", "Collect a fish, plant, mineral and companion.", "🪐", "categories", 4),
    Badge("s_class_1", "S-Class Surprise", "Collect your first S-class item.", "⭐", "s_class", 1),
    Badge("s_class_10", "Star Collector", "Collect S-class items from 10 appearances.", "🌟", "s_class", 10),
    Badge("craft_1", "Made It Myself", "Craft your first trophy.", "🔨", "crafts", 1),
    Badge("craft_10", "Master Maker", "Craft 10 trophies.", "🛠️", "crafts", 10),
    Badge("powerup_trio", "Crew Energizer", "Activate electromagnetic, gas and mineral powerups.", "⚡", "powerup_kinds", 3),
    Badge("warp_1", "Take the Helm", "Complete your first crew Warp.", "🚀", "warps", 1),
    Badge("mission_10", "Mission Specialist", "Complete 10 daily missions.", "✅", "missions", 10),
)


def _identifier(value: object) -> str:
    value = str(value).strip()
    if not value or len(value) > 128:
        raise ValueError("Invalid identifier")
    return value


class Honours:
    def __init__(self, engine: GameEngine):
        self.engine = engine
        with engine._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS player_achievements (
              guild_id TEXT NOT NULL, user_id TEXT NOT NULL, badge_id TEXT NOT NULL,
              unlocked_at REAL NOT NULL,
              PRIMARY KEY(guild_id,user_id,badge_id),
              FOREIGN KEY(guild_id,user_id) REFERENCES profiles(guild_id,user_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS claims_honours_player ON claims(user_id,event_id)")
            db.execute("CREATE INDEX IF NOT EXISTS warp_history_player ON warp_history(guild_id,user_id)")
            db.execute("""CREATE INDEX IF NOT EXISTS mission_progress_player
                          ON activity_mission_progress(guild_id,user_id,completed_at)""")
            version = db.execute("SELECT value FROM metadata WHERE key='honours_version'").fetchone()
            if version is None:
                now = engine._now()
                # The transaction commits the badges and marker together. A
                # restart never replays these historical celebrations.
                for row in db.execute("SELECT guild_id,user_id FROM profiles").fetchall():
                    self.evaluate(db, row["guild_id"], row["user_id"], now)
                db.execute("INSERT INTO metadata(key,value) VALUES('honours_version','1')")
            elif version["value"] != "1":
                raise ValueError(f"Unsupported honours version: {version['value']}")

    @staticmethod
    def _stats(db: sqlite3.Connection, guild: str, user: str) -> dict:
        profile = db.execute("SELECT catches,crafts FROM profiles WHERE guild_id=? AND user_id=?",
                             (guild, user)).fetchone()
        stats = {"catches": profile["catches"] if profile else 0,
                 "crafts": profile["crafts"] if profile else 0,
                 **{kind: 0 for kind in COLLECTION_KINDS}, "s_class": 0}
        powerup_kinds = set()
        for row in db.execute("""SELECT e.kind,e.grade,COUNT(*) AS appearances
          FROM claims AS c JOIN events AS e ON e.id=c.event_id
          WHERE e.guild_id=? AND c.user_id=? GROUP BY e.kind,e.grade""", (guild, user)):
            if row["kind"] in COLLECTION_KINDS:
                stats[row["kind"]] += row["appearances"]
                if row["grade"] == "S":
                    stats["s_class"] += row["appearances"]
            elif row["kind"] in POWERUP_KINDS:
                powerup_kinds.add(row["kind"])
        stats["categories"] = sum(stats[kind] > 0 for kind in COLLECTION_KINDS)
        stats["powerup_kinds"] = len(powerup_kinds)
        stats["warps"] = db.execute("SELECT COUNT(*) FROM warp_history WHERE guild_id=? AND user_id=?",
                                    (guild, user)).fetchone()[0]
        stats["missions"] = db.execute("""SELECT COUNT(*) FROM activity_mission_progress
          WHERE guild_id=? AND user_id=? AND completed_at IS NOT NULL""", (guild, user)).fetchone()[0]
        return stats

    @staticmethod
    def _describe(badge: Badge, progress: int, unlocked_at: float | None) -> dict:
        unlocked = unlocked_at is not None
        return {"id": badge.id, "title": badge.title, "description": badge.description,
                "emoji": badge.emoji, "progress": badge.target if unlocked else min(progress, badge.target),
                "target": badge.target, "unlocked": unlocked, "unlocked_at": unlocked_at}

    def evaluate(self, db: sqlite3.Connection, guild: str, user: str, now: float) -> list[dict]:
        """Record new badges inside the caller's successful action transaction."""
        guild, user = _identifier(guild), _identifier(user)
        stats = self._stats(db, guild, user)
        newly_earned = []
        for badge in BADGES:
            progress = stats[badge.metric]
            if progress < badge.target:
                continue
            inserted = db.execute("""INSERT OR IGNORE INTO player_achievements
              (guild_id,user_id,badge_id,unlocked_at) VALUES(?,?,?,?)""", (guild, user, badge.id, now))
            if inserted.rowcount:
                newly_earned.append(self._describe(badge, progress, now))
        return newly_earned

    def status(self, guild_id: str, user_id: str) -> dict:
        """Read progress without awarding anything or creating a new profile."""
        guild, user = _identifier(guild_id), _identifier(user_id)
        with self.engine._lock:
            stats = self._stats(self.engine.db, guild, user)
            earned = {row["badge_id"]: row["unlocked_at"] for row in self.engine.db.execute(
                "SELECT badge_id,unlocked_at FROM player_achievements WHERE guild_id=? AND user_id=?",
                (guild, user))}
            achievements = [self._describe(badge, stats[badge.metric], earned.get(badge.id)) for badge in BADGES]
            return {"unlocked_count": sum(badge["unlocked"] for badge in achievements),
                    "total_count": len(BADGES), "achievements": achievements}
