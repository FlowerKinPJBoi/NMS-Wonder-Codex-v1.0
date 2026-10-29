"""Earned Warp points and the channel's persistent shared galaxy journey.

All debits, destination changes and history writes share the game engine's
SQLite transaction. A revision binds a player's destination selection to the
galaxy they actually saw, so competing confirmations cannot spend against an
outdated route. The inventory and lifetime catch totals are never debited.
"""
from __future__ import annotations

import json
import sqlite3
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .engine import GameEngine


WARP_COST = 50
WARP_BANK_CAP = 150
WARP_COOLDOWN_SECONDS = 120
GALAXY_COUNT = 256


def _identifier(value: object) -> str:
    value = str(value).strip()
    if not value or len(value) > 128:
        raise ValueError("Invalid identifier")
    return value


@lru_cache(maxsize=1)
def _roster() -> dict[int, str]:
    path = Path(__file__).resolve().parent.parent / "content" / "galaxies.json"
    entries = json.loads(path.read_text(encoding="utf-8"))["galaxies"]
    if not isinstance(entries, list) or len(entries) != GALAXY_COUNT:
        raise ValueError("The FFC route requires 256 galaxy names")
    names = {}
    for entry in entries:
        number, name = entry.get("number"), entry.get("name")
        if (isinstance(number, bool) or not isinstance(number, int)
                or number in names or not isinstance(name, str) or not name.strip()):
            raise ValueError("Invalid galaxy roster entry")
        names[number] = name.strip()
    if set(names) != set(range(1, GALAXY_COUNT + 1)):
        raise ValueError("The FFC route must contain galaxies 1 through 256")
    return names


def galaxy(number: int) -> dict:
    """Return a fresh number/name descriptor from the validated local roster."""
    if isinstance(number, bool) or not isinstance(number, int) or number not in _roster():
        raise ValueError("Invalid galaxy number")
    return {"number": number, "name": _roster()[number]}


class Progression:
    def __init__(self, engine: GameEngine):
        self.engine = engine
        _roster()
        with engine._transaction() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS warp_accounts (
              guild_id TEXT NOT NULL, user_id TEXT NOT NULL,
              balance INTEGER NOT NULL DEFAULT 0 CHECK(balance BETWEEN 0 AND 150),
              legacy_credit INTEGER NOT NULL DEFAULT 0 CHECK(legacy_credit >= 0),
              PRIMARY KEY(guild_id,user_id),
              FOREIGN KEY(guild_id,user_id) REFERENCES profiles(guild_id,user_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS galaxy_journeys (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
              galaxy_number INTEGER NOT NULL DEFAULT 1 CHECK(galaxy_number BETWEEN 1 AND 256),
              revision INTEGER NOT NULL DEFAULT 0 CHECK(revision >= 0),
              last_warp_at REAL,
              PRIMARY KEY(guild_id,channel_id),
              FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id))""")
            db.execute("""CREATE TABLE IF NOT EXISTS warp_history (
              id INTEGER PRIMARY KEY AUTOINCREMENT,
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, user_id TEXT NOT NULL,
              from_number INTEGER NOT NULL CHECK(from_number BETWEEN 1 AND 256),
              to_number INTEGER NOT NULL CHECK(to_number BETWEEN 1 AND 256),
              direction TEXT NOT NULL CHECK(direction IN ('next','previous')),
              cost INTEGER NOT NULL, warped_at REAL NOT NULL, revision INTEGER NOT NULL,
              UNIQUE(guild_id,channel_id,revision),
              FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id))""")
            db.execute("CREATE INDEX IF NOT EXISTS warp_history_channel ON warp_history(guild_id,channel_id,id DESC)")
            # Per-account INSERT OR IGNORE is the migration marker. A restart
            # cannot refill an account after its owner spends their points.
            db.execute("""INSERT OR IGNORE INTO warp_accounts(guild_id,user_id,balance,legacy_credit)
                          SELECT guild_id,user_id,MIN(catches,?),MIN(catches,?)
                          FROM profiles""", (WARP_BANK_CAP, WARP_BANK_CAP))
            db.execute("""INSERT OR IGNORE INTO galaxy_journeys(guild_id,channel_id)
                          SELECT guild_id,channel_id FROM channels""")
            db.execute("INSERT OR IGNORE INTO metadata(key,value) VALUES('warp_progression_version','1')")
            version = db.execute("SELECT value FROM metadata WHERE key='warp_progression_version'").fetchone()[0]
            if version != "1":
                raise ValueError(f"Unsupported Warp progression version: {version}")

    @staticmethod
    def _ensure_journey(db: sqlite3.Connection, guild: str, channel: str) -> sqlite3.Row:
        db.execute("INSERT OR IGNORE INTO galaxy_journeys(guild_id,channel_id) VALUES(?,?)", (guild, channel))
        return db.execute("SELECT * FROM galaxy_journeys WHERE guild_id=? AND channel_id=?", (guild, channel)).fetchone()

    def ensure_channel(self, guild: str, channel: str) -> None:
        guild, channel = _identifier(guild), _identifier(channel)
        with self.engine._transaction() as db:
            self.engine._get_channel(db, guild, channel)
            self._ensure_journey(db, guild, channel)

    @staticmethod
    def account(db: sqlite3.Connection, guild: str, user: str) -> dict:
        row = db.execute("SELECT balance FROM warp_accounts WHERE guild_id=? AND user_id=?", (str(guild), str(user))).fetchone()
        balance = row["balance"] if row else 0
        return {"balance": balance, "charges": balance // WARP_COST,
                "next_charge_in": 0 if balance >= WARP_BANK_CAP else WARP_COST - balance % WARP_COST}

    def credit(self, db: sqlite3.Connection, guild: str, user: str, amount: int) -> dict:
        """Credit earned points inside the caller's existing claim transaction."""
        guild, user = _identifier(guild), _identifier(user)
        if isinstance(amount, bool) or not isinstance(amount, int) or amount < 0:
            raise ValueError("Warp credit must be a nonnegative integer")
        self.engine._ensure_profile(db, guild, user)
        db.execute("INSERT OR IGNORE INTO warp_accounts(guild_id,user_id) VALUES(?,?)", (guild, user))
        before = self.account(db, guild, user)["balance"]
        awarded = min(amount, WARP_BANK_CAP - before)
        db.execute("UPDATE warp_accounts SET balance=balance+? WHERE guild_id=? AND user_id=?", (awarded, guild, user))
        return {"awarded": awarded, **self.account(db, guild, user)}

    @staticmethod
    def _cooldown_until(journey: sqlite3.Row) -> float:
        return (journey["last_warp_at"] + WARP_COOLDOWN_SECONDS
                if journey["last_warp_at"] is not None else 0.0)

    def status(self, guild: str, channel: str, user: str | None = None,
               now: float | None = None) -> dict:
        guild, channel, now = _identifier(guild), _identifier(channel), self.engine._now(now)
        if user is not None:
            user = _identifier(user)
        with self.engine._transaction() as db:
            self.engine._get_channel(db, guild, channel)
            journey = self._ensure_journey(db, guild, channel)
            current = journey["galaxy_number"]
            cooldown_until = self._cooldown_until(journey)
            history = [
                {"user_id": row["user_id"], "from_galaxy": galaxy(row["from_number"]),
                 "to_galaxy": galaxy(row["to_number"]), "at": row["warped_at"],
                 "direction": row["direction"]}
                for row in db.execute("""SELECT * FROM warp_history
                    WHERE guild_id=? AND channel_id=? ORDER BY id DESC LIMIT 5""", (guild, channel))
            ]
            result = {
                "galaxy": galaxy(current), "previous": galaxy((current - 2) % GALAXY_COUNT + 1),
                "next": galaxy(current % GALAXY_COUNT + 1), "revision": journey["revision"],
                "cooldown_until": cooldown_until, "cooldown_remaining": max(0, cooldown_until - now),
                "history": history,
            }
            result.update(self.account(db, guild, user) if user is not None else
                          {"balance": 0, "charges": 0, "next_charge_in": WARP_COST})
            return result

    def warp(self, guild: str, channel: str, user: str, direction: str,
             expected_revision: int, request_id: str | None = None,
             now: float | None = None) -> dict:
        """Spend one earned charge and move the shared journey atomically.

        A direction-button click is a confirmation of a previously displayed
        revision. Stale, repeated, paused or unaffordable confirmations do not
        consume points, alter catch windows, or touch inventory.
        """
        guild, channel, user = _identifier(guild), _identifier(channel), _identifier(user)
        request_id = _identifier(request_id) if request_id is not None else None
        now = self.engine._now(now)
        with self.engine._transaction() as db:
            if self.engine._request_seen(db, guild, request_id):
                return {"ok": False, "reason": "duplicate_request"}

            def finish(result: dict) -> dict:
                return self.engine._finish(db, guild, request_id, "warp", result, now)

            if direction not in ("next", "previous"):
                return finish({"ok": False, "reason": "invalid_direction"})
            if isinstance(expected_revision, bool) or not isinstance(expected_revision, int) or expected_revision < 0:
                return finish({"ok": False, "reason": "invalid_revision"})
            state = db.execute("SELECT enabled FROM channels WHERE guild_id=? AND channel_id=?", (guild, channel)).fetchone()
            if state is None or not state["enabled"]:
                return finish({"ok": False, "reason": "channel_unavailable"})
            journey = self._ensure_journey(db, guild, channel)
            account = self.account(db, guild, user)
            if journey["revision"] != expected_revision:
                return finish({"ok": False, "reason": "stale_selection", **account,
                               "revision": journey["revision"], "galaxy": galaxy(journey["galaxy_number"])})
            cooldown_until = self._cooldown_until(journey)
            if now < cooldown_until:
                return finish({"ok": False, "reason": "cooldown", **account,
                               "cooldown_until": cooldown_until})
            if account["balance"] < WARP_COST:
                return finish({"ok": False, "reason": "insufficient_points", **account,
                               "required": WARP_COST})
            source = journey["galaxy_number"]
            destination = (source + (1 if direction == "next" else -1) - 1) % GALAXY_COUNT + 1
            revision = journey["revision"] + 1
            db.execute("UPDATE warp_accounts SET balance=balance-? WHERE guild_id=? AND user_id=?", (WARP_COST, guild, user))
            db.execute("""UPDATE galaxy_journeys SET galaxy_number=?,revision=?,last_warp_at=?
                          WHERE guild_id=? AND channel_id=?""", (destination, revision, now, guild, channel))
            db.execute("""INSERT INTO warp_history(guild_id,channel_id,user_id,from_number,
                          to_number,direction,cost,warped_at,revision) VALUES(?,?,?,?,?,?,?,?,?)""",
                       (guild, channel, user, source, destination, direction, WARP_COST, now, revision))
            achievements = self.engine.honours.evaluate(db, guild, user, now)
            return finish({"ok": True, "reason": "warped", "from_galaxy": galaxy(source),
                           "to_galaxy": galaxy(destination), "revision": revision,
                           "cooldown_until": now + WARP_COOLDOWN_SECONDS,
                           "achievements_unlocked": achievements,
                           **self.account(db, guild, user)})
