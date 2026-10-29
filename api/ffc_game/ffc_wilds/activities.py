"""Persistent crew activities, without a dependency on Discord.

All calendars use the crew's America/New_York timezone. Daily missions count
new successful appearances, not multiplied inventory units. Power Drives only
multiply Warp progress and become active after their announcement is confirmed.
The caller owns the existing transaction for claim hooks; public methods take
the engine transaction lock themselves.
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import uuid
from datetime import date, datetime, time as calendar_time, timedelta
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from .engine import GameEngine


CREW_TIMEZONE = "America/New_York"
DRIVE_SECONDS = 30 * 60
NOTICE_RETRY_SECONDS = 5 * 60
NOTICE_SPACING_SECONDS = 5 * 60
NOTICE_MAX_ATTEMPTS = 3
DAILY_DELIVERY_WINDOW_SECONDS = 2 * 60 * 60
MISSION_REWARD = 10
COLLECTIBLE_KINDS = ("fish", "plant", "mineral", "pet")
FOCUSED_MISSIONS = {
    "fish": (4, "Catch 4 fish"),
    "plant": (4, "Pick 4 plants"),
    "mineral": (4, "Mine 4 deposits"),
    "pet": (1, "Tame 1 companion"),
}


def _identifier(value: Any) -> str:
    value = str(value).strip()
    if not value or len(value) > 128:
        raise ValueError("IDs must be nonempty strings of at most 128 characters")
    return value


class Activities:
    def __init__(self, engine: "GameEngine", *, rng: Any = None):
        self.engine = engine
        # Planning a week must not consume the encounter selector's RNG.
        self.rng = rng or random.SystemRandom()
        self.timezone = ZoneInfo(CREW_TIMEZONE)
        statements = (
            """CREATE TABLE IF NOT EXISTS activity_channels (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
              created_at REAL NOT NULL, next_notice_at REAL NOT NULL DEFAULT 0,
              PRIMARY KEY(guild_id,channel_id),
              FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id))""",
            """CREATE TABLE IF NOT EXISTS activity_weeks (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, week TEXT NOT NULL,
              requested_drives INTEGER NOT NULL, scheduled_drives INTEGER NOT NULL,
              created_at REAL NOT NULL, PRIMARY KEY(guild_id,channel_id,week))""",
            """CREATE TABLE IF NOT EXISTS activity_missions (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, day TEXT NOT NULL,
              focus_kind TEXT NOT NULL, created_at REAL NOT NULL,
              PRIMARY KEY(guild_id,channel_id,day))""",
            """CREATE TABLE IF NOT EXISTS activity_mission_progress (
              guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, day TEXT NOT NULL,
              user_id TEXT NOT NULL, mission_id TEXT NOT NULL,
              progress INTEGER NOT NULL DEFAULT 0 CHECK(progress>=0),
              completed_at REAL, awarded INTEGER NOT NULL DEFAULT 0,
              PRIMARY KEY(guild_id,channel_id,day,user_id,mission_id),
              FOREIGN KEY(guild_id,channel_id,day)
                REFERENCES activity_missions(guild_id,channel_id,day))""",
            """CREATE TABLE IF NOT EXISTS activity_claims (
              event_id TEXT NOT NULL, user_id TEXT NOT NULL,
              PRIMARY KEY(event_id,user_id),
              FOREIGN KEY(event_id,user_id) REFERENCES claims(event_id,user_id))""",
            """CREATE TABLE IF NOT EXISTS activity_notices (
              id TEXT PRIMARY KEY, guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
              kind TEXT NOT NULL, slot_key TEXT NOT NULL, scheduled_at REAL NOT NULL,
              expires_at REAL NOT NULL, status TEXT NOT NULL DEFAULT 'scheduled',
              payload_json TEXT NOT NULL DEFAULT '{}', retry_at REAL NOT NULL DEFAULT 0,
              attempts INTEGER NOT NULL DEFAULT 0, lease_id TEXT, reserved_at REAL,
              starts_at REAL, ends_at REAL, sent_at REAL, message_id TEXT,
              UNIQUE(guild_id,channel_id,kind,slot_key))""",
            """CREATE INDEX IF NOT EXISTS activity_notices_due
              ON activity_notices(guild_id,channel_id,status,scheduled_at,retry_at)""",
            """CREATE INDEX IF NOT EXISTS claims_activity_period
              ON claims(claimed_at,event_id,user_id)""",
        )
        with engine._transaction() as db:
            for statement in statements:
                db.execute(statement)

    def _local_day(self, now: float) -> date:
        return datetime.fromtimestamp(now, self.timezone).date()

    def _at(self, day: date, hour: int = 0) -> float:
        return datetime.combine(day, calendar_time(hour), tzinfo=self.timezone).timestamp()

    @staticmethod
    def _monday(day: date) -> date:
        return day - timedelta(days=day.weekday())

    def _insert_notice(self, db: sqlite3.Connection, guild: str, channel: str,
                       kind: str, slot_key: str, scheduled_at: float,
                       expires_at: float, payload: dict, *, status: str = "scheduled") -> None:
        db.execute("""INSERT OR IGNORE INTO activity_notices
          (id,guild_id,channel_id,kind,slot_key,scheduled_at,expires_at,status,payload_json)
          VALUES(?,?,?,?,?,?,?,?,?)""",
          (uuid.uuid4().hex, guild, channel, kind, slot_key, scheduled_at,
           expires_at, status, json.dumps(payload, separators=(",", ":"))))

    def _ensure_week(self, db: sqlite3.Connection, guild: str, channel: str,
                     now: float) -> None:
        monday = self._monday(self._local_day(now))
        week = monday.isoformat()
        if db.execute("SELECT 1 FROM activity_weeks WHERE guild_id=? AND channel_id=? AND week=?",
                      (guild, channel, week)).fetchone():
            return
        eligible = []
        for offset in range(7):
            day = monday + timedelta(days=offset)
            earliest = max(math.ceil(now + 60), int(self._at(day, 10)))
            latest = int(self._at(day, 23))
            if earliest <= latest:
                eligible.append((day, earliest, latest))
        requested = self.rng.choice((2, 3))
        chosen = self.rng.sample(eligible, min(requested, len(eligible)))
        db.execute("""INSERT INTO activity_weeks
          (guild_id,channel_id,week,requested_drives,scheduled_drives,created_at)
          VALUES(?,?,?,?,?,?)""", (guild, channel, week, requested, len(chosen), now))
        for day, earliest, latest in chosen:
            scheduled = self.rng.randint(earliest, latest)
            self._insert_notice(db, guild, channel, "drive_start", day.isoformat(),
                                scheduled, scheduled + DRIVE_SECONDS,
                                {"multiplier": self.rng.choice((2, 3)), "week": week})

    def _ensure_day(self, db: sqlite3.Connection, guild: str, channel: str,
                    now: float) -> sqlite3.Row:
        day = self._local_day(now)
        day_key = day.isoformat()
        row = db.execute("""SELECT * FROM activity_missions
          WHERE guild_id=? AND channel_id=? AND day=?""", (guild, channel, day_key)).fetchone()
        if row is not None:
            return row
        focus = self.rng.choice(tuple(FOCUSED_MISSIONS))
        db.execute("""INSERT INTO activity_missions
          (guild_id,channel_id,day,focus_kind,created_at) VALUES(?,?,?,?,?)""",
          (guild, channel, day_key, focus, now))
        for kind, hour in (("missions", 10), ("standings", 20)):
            scheduled = self._at(day, hour)
            # Initializing after the scheduled hour must not post a backlog.
            status = "missed" if scheduled < now else "scheduled"
            self._insert_notice(db, guild, channel, kind, day_key, scheduled,
                                min(scheduled + DAILY_DELIVERY_WINDOW_SECONDS,
                                    self._at(day + timedelta(days=1))),
                                {"day": day_key}, status=status)
        return db.execute("""SELECT * FROM activity_missions
          WHERE guild_id=? AND channel_id=? AND day=?""", (guild, channel, day_key)).fetchone()

    def _ensure_channel(self, db: sqlite3.Connection, guild: str,
                        channel: str, now: float) -> None:
        self.engine._get_channel(db, guild, channel)
        db.execute("""INSERT OR IGNORE INTO activity_channels
          (guild_id,channel_id,created_at) VALUES(?,?,?)""", (guild, channel, now))
        self._ensure_week(db, guild, channel, now)
        self._ensure_day(db, guild, channel, now)

    def ensure_channel(self, guild: str, channel: str) -> None:
        guild, channel = _identifier(guild), _identifier(channel)
        with self.engine._transaction() as db:
            self._ensure_channel(db, guild, channel, self.engine._now())

    @staticmethod
    def _objectives(day: sqlite3.Row) -> list[dict]:
        focus = day["focus_kind"]
        target, title = FOCUSED_MISSIONS[focus]
        return [
            {"id": "any", "title": "Gather 8 discoveries", "kind": "any",
             "target": 8, "reward": MISSION_REWARD},
            {"id": "focus", "title": title, "kind": focus,
             "target": target, "reward": MISSION_REWARD},
        ]

    def record_claim(self, db: sqlite3.Connection, event: dict,
                     user: str, now: float) -> list[dict]:
        """Count one new committed collectible, within its existing transaction."""
        if event.get("kind") not in COLLECTIBLE_KINDS:
            return []
        guild, channel, user = (_identifier(event["guild_id"]),
                                _identifier(event["channel_id"]), _identifier(user))
        self._ensure_channel(db, guild, channel, now)
        inserted = db.execute("INSERT OR IGNORE INTO activity_claims(event_id,user_id) VALUES(?,?)",
                              (_identifier(event["id"]), user))
        if not inserted.rowcount:
            return []
        day = self._ensure_day(db, guild, channel, now)
        completed = []
        for objective in self._objectives(day):
            if objective["kind"] not in ("any", event["kind"]):
                continue
            keys = (guild, channel, day["day"], user, objective["id"])
            db.execute("""INSERT OR IGNORE INTO activity_mission_progress
              (guild_id,channel_id,day,user_id,mission_id) VALUES(?,?,?,?,?)""", keys)
            progress = db.execute("""SELECT progress,completed_at FROM activity_mission_progress
              WHERE guild_id=? AND channel_id=? AND day=? AND user_id=? AND mission_id=?""", keys).fetchone()
            if progress["completed_at"] is not None:
                continue
            count = min(objective["target"], progress["progress"] + 1)
            if count >= objective["target"]:
                credited = self.engine.progression.credit(db, guild, user, MISSION_REWARD)
                awarded = credited["awarded"]
                db.execute("""UPDATE activity_mission_progress
                  SET progress=?,completed_at=?,awarded=? WHERE guild_id=? AND channel_id=?
                  AND day=? AND user_id=? AND mission_id=?""", (count, now, awarded, *keys))
                completed.append({"title": objective["title"], "reward": MISSION_REWARD,
                                  "awarded": awarded})
            else:
                db.execute("""UPDATE activity_mission_progress SET progress=?
                  WHERE guild_id=? AND channel_id=? AND day=? AND user_id=? AND mission_id=?""",
                  (count, *keys))
        return completed

    def missions(self, guild: str, channel: str, user: str,
                 now: float | None = None) -> dict:
        guild, channel, user = _identifier(guild), _identifier(channel), _identifier(user)
        now = self.engine._now(now)
        with self.engine._transaction() as db:
            self._ensure_channel(db, guild, channel, now)
            day = self._ensure_day(db, guild, channel, now)
            objectives = self._objectives(day)
            for objective in objectives:
                row = db.execute("""SELECT progress,completed_at FROM activity_mission_progress
                  WHERE guild_id=? AND channel_id=? AND day=? AND user_id=? AND mission_id=?""",
                  (guild, channel, day["day"], user, objective["id"])).fetchone()
                objective.update(progress=row["progress"] if row else 0,
                                 completed=bool(row and row["completed_at"] is not None))
            return {"day": day["day"],
                    "resets_at": self._at(date.fromisoformat(day["day"]) + timedelta(days=1)),
                    "missions": objectives}

    @staticmethod
    def _active_drive(db: sqlite3.Connection, guild: str, channel: str,
                      now: float) -> sqlite3.Row | None:
        return db.execute("""SELECT payload_json,ends_at FROM activity_notices
          WHERE guild_id=? AND channel_id=? AND kind='drive_start' AND status='sent'
          AND starts_at<=? AND ends_at>? ORDER BY ends_at DESC LIMIT 1""",
          (guild, channel, now, now)).fetchone()

    def drive_multiplier(self, db: sqlite3.Connection, guild: str,
                         channel: str, now: float) -> int:
        row = self._active_drive(db, guild, channel, now)
        return int(json.loads(row["payload_json"])["multiplier"]) if row else 1

    def drive_status(self, guild: str, channel: str,
                     now: float | None = None) -> dict:
        guild, channel, now = _identifier(guild), _identifier(channel), self.engine._now(now)
        with self.engine._lock:
            self.engine._get_channel(self.engine.db, guild, channel)
            row = self._active_drive(self.engine.db, guild, channel, now)
            return {"active": bool(row),
                    "multiplier": int(json.loads(row["payload_json"])["multiplier"]) if row else 1,
                    "ends_at": row["ends_at"] if row else 0}

    def _period_bounds(self, period: str, now: float) -> tuple[float, float]:
        day = self._local_day(now)
        if period == "today":
            start, end = day, day + timedelta(days=1)
        elif period == "yesterday":
            start, end = day - timedelta(days=1), day
        elif period == "week":
            start = self._monday(day)
            end = start + timedelta(days=7)
        else:
            raise ValueError("Period must be today, week, or yesterday")
        return self._at(start), self._at(end)

    def _leaderboard(self, db: sqlite3.Connection, guild: str, channel: str,
                     period: str, limit: int, now: float, metric: str) -> list[dict]:
        start, end = self._period_bounds(period, now)
        # metric is allowlisted by the public API; limits/identifiers are bound.
        secondary = "units" if metric == "catches" else "catches"
        rows = db.execute(f"""SELECT c.user_id,COUNT(*) AS catches,SUM(c.quantity) AS units
          FROM claims c JOIN events e ON e.id=c.event_id
          WHERE e.guild_id=? AND e.channel_id=? AND c.quantity>0
          AND c.claimed_at>=? AND c.claimed_at<?
          GROUP BY c.user_id ORDER BY {metric} DESC,{secondary} DESC,c.user_id ASC LIMIT ?""",
          (guild, channel, start, end, limit)).fetchall()
        return [dict(row) for row in rows]

    def leaderboard(self, guild: str, channel: str, period: str = "today",
                    limit: int = 10, now: float | None = None, *,
                    metric: str = "catches") -> list[dict]:
        guild, channel, now = _identifier(guild), _identifier(channel), self.engine._now(now)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 50:
            raise ValueError("Leaderboard limit must be an integer from 1 through 50")
        if metric not in ("catches", "units"):
            raise ValueError("Daily and weekly leaderboards support catches or units")
        with self.engine._lock:
            self.engine._get_channel(self.engine.db, guild, channel)
            return self._leaderboard(self.engine.db, guild, channel, period, limit, now, metric)

    def reserve_notice(self, guild: str, channel: str, blocked: bool = False,
                       now: float | None = None) -> dict | None:
        """Reserve one due interlude; an uncertain prior send is never replayed."""
        guild, channel, now = _identifier(guild), _identifier(channel), self.engine._now(now)
        with self.engine._transaction() as db:
            self._ensure_channel(db, guild, channel, now)
            db.execute("""UPDATE activity_notices SET status='missed',lease_id=NULL
              WHERE guild_id=? AND channel_id=? AND status IN ('scheduled','reserved')
              AND expires_at<=?""", (guild, channel, now))
            state = self.engine._get_channel(db, guild, channel)
            activity_state = db.execute("""SELECT next_notice_at FROM activity_channels
              WHERE guild_id=? AND channel_id=?""", (guild, channel)).fetchone()
            if not state["enabled"] or blocked or now < activity_state["next_notice_at"]:
                return None
            row = db.execute("""SELECT * FROM activity_notices
              WHERE guild_id=? AND channel_id=? AND status='scheduled'
              AND scheduled_at<=? AND retry_at<=? AND expires_at>?
              ORDER BY CASE kind WHEN 'drive_start' THEN 0 ELSE 1 END,scheduled_at,id LIMIT 1""",
              (guild, channel, now, now, now)).fetchone()
            if row is None:
                return None
            lease = uuid.uuid4().hex
            starts_at = now if row["kind"] == "drive_start" else None
            ends_at = now + DRIVE_SECONDS if starts_at is not None else None
            db.execute("""UPDATE activity_notices SET status='reserved',lease_id=?,
              attempts=attempts+1,reserved_at=?,starts_at=?,ends_at=? WHERE id=?""",
              (lease, now, starts_at, ends_at, row["id"]))
            db.execute("""UPDATE activity_channels SET next_notice_at=?
              WHERE guild_id=? AND channel_id=?""",
              (now + NOTICE_SPACING_SECONDS, guild, channel))
            payload = json.loads(row["payload_json"])
            if row["kind"] == "drive_start":
                data = {"multiplier": payload["multiplier"],
                        "starts_at": starts_at, "ends_at": ends_at}
            elif row["kind"] == "missions":
                day = self._ensure_day(db, guild, channel, now)
                data = {"day": day["day"],
                        "resets_at": self._at(date.fromisoformat(day["day"]) + timedelta(days=1)),
                        "missions": self._objectives(day)}
            else:
                data = {"day": payload["day"],
                        "today": self._leaderboard(db, guild, channel, "today", 5, now, "catches"),
                        "week": self._leaderboard(db, guild, channel, "week", 5, now, "catches")}
            return {"id": row["id"], "lease_id": lease, "kind": row["kind"], "data": data}

    def notice_sent(self, reservation: dict, message_id: str) -> bool:
        now = self.engine._now()
        with self.engine._transaction() as db:
            updated = db.execute("""UPDATE activity_notices SET status='sent',lease_id=NULL,
              sent_at=?,message_id=? WHERE id=? AND lease_id=? AND status='reserved'""",
              (now, _identifier(message_id), reservation["id"], reservation["lease_id"]))
            return bool(updated.rowcount)

    def notice_failed(self, reservation: dict) -> bool:
        now = self.engine._now()
        with self.engine._transaction() as db:
            row = db.execute("""SELECT attempts,expires_at FROM activity_notices
              WHERE id=? AND lease_id=? AND status='reserved'""",
              (reservation["id"], reservation["lease_id"])).fetchone()
            if row is None:
                return False
            retry_at = now + NOTICE_RETRY_SECONDS
            retry = row["attempts"] < NOTICE_MAX_ATTEMPTS and retry_at < row["expires_at"]
            db.execute("""UPDATE activity_notices SET status=?,lease_id=NULL,retry_at=?,
              starts_at=NULL,ends_at=NULL WHERE id=? AND lease_id=?""",
              ("scheduled" if retry else "failed", retry_at,
               reservation["id"], reservation["lease_id"]))
            return True
