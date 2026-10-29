"""Persistent, transport-independent rules for FFC Wilds.

All IDs are strings. Times are Unix seconds. Ordinary collections count one
successful catch regardless of the number of units awarded. SQLite transactions
make claims and crafting atomic, including when separate processes race.

An appearance is ``pending`` until ``bind_message`` confirms its Discord post.
Only ``open`` appearances can award items. This prevents an unsuccessful send
from producing an invisible, claimable appearance.

Ordinary appearances wait for their first successful claim. That claim starts
the shared collection window; frenzy appearances have a fixed deadline instead.
"""

from __future__ import annotations

import json
import math
import random
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator


COLLECTION_ACTIONS = {"fish": "catch", "plant": "pick", "mineral": "mine", "pet": "tame"}
POWERUP_KINDS = ("electromagnetic", "gas", "mineral_powerup")
GRADE_MULTIPLIERS = {"C": 2, "B": 4, "A": 6, "S": 8}
GRADE_SECONDS = {"C": 60, "B": 120, "A": 180, "S": 240}
GRADE_XP = {"C": 10, "B": 20, "A": 40, "S": 80}
HOTSPOT_GRADE_WEIGHTS = {"C": 50, "B": 28, "A": 16, "S": 6}
KIND_WEIGHTS = {"fish": 34, "plant": 24, "mineral": 22, "pet": 8,
                "electromagnetic": 6, "gas": 3, "mineral_powerup": 3}


def _identifier(value: Any) -> str:
    value = str(value).strip()
    if not value or len(value) > 128:
        raise ValueError("IDs must be nonempty strings of at most 128 characters")
    return value


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{label} must be a positive integer")
    return value


class GameEngine:
    """SQLite/PostgreSQL game engine; owns its connection and supports ``close``.

    ``catalog_path`` can be a JSON path or an already-loaded dictionary. Public
    methods return plain dictionaries/lists suitable for a Discord adapter.
    ``claim``/``craft`` failures return ``ok=False`` with a stable ``reason``.
    Invalid setup/configuration raises ``ValueError`` instead.
    """

    def __init__(self, db_path: str | Path, catalog_path: str | Path | dict,
                 clock: Callable[[], float] = time.time, rng: Any = None,
                 *, schema: str = "ffc_wilds"):
        self.clock = clock
        self.rng = rng or random.SystemRandom()
        self._lock = threading.RLock()
        from .storage import PostgresConnection, is_postgres
        database_location = str(db_path)
        self.backend = "postgresql" if is_postgres(database_location) else "sqlite"
        # The PostgreSQL URL can contain credentials. Never keep it in the
        # public path/debug field used by local tools and status reports.
        self.db_path = "<PostgreSQL game storage>" if self.backend == "postgresql" else database_location
        self.catalog = (catalog_path if isinstance(catalog_path, dict)
                        else json.loads(Path(catalog_path).read_text(encoding="utf-8")))
        self.items: dict[str, dict] = {}
        self.crafted_items: dict[str, dict] = {}
        self.recipes: dict[str, dict] = {}
        self._validate_catalog()
        if self.backend == "postgresql":
            self.db = PostgresConnection(database_location, schema=schema)
        else:
            if self.db_path != ":memory:":
                Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
            self.db = sqlite3.connect(self.db_path, timeout=10, isolation_level=None,
                                      check_same_thread=False)
            self.db.row_factory = sqlite3.Row
            self.db.execute("PRAGMA busy_timeout=10000")
            self.db.execute("PRAGMA foreign_keys=ON")
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.execute("PRAGMA synchronous=FULL")
        try:
            self._create_schema()
            # Add-on services share the existing transaction lock and database.
            # Their schemas are additive, keeping the original save readable.
            from .activities import Activities
            from .progression import Progression
            from .honours import Honours
            self.activities = Activities(self)
            self.progression = Progression(self)
            self.honours = Honours(self)
        except BaseException:
            self.db.close()
            raise

    def _validate_catalog(self) -> None:
        if not isinstance(self.catalog, dict):
            raise ValueError("Catalog must be a JSON object")
        for raw in self.catalog.get("items", []):
            item = dict(raw)
            key = _identifier(item.get("id", ""))
            if key in self.items:
                raise ValueError(f"Duplicate item ID: {key}")
            kind = item.get("kind")
            if kind not in COLLECTION_ACTIONS:
                raise ValueError(f"Invalid item kind: {kind}")
            if item.get("action", COLLECTION_ACTIONS[kind]) != COLLECTION_ACTIONS[kind]:
                raise ValueError(f"Wrong action for {key}")
            grade = item.get("rarity", "C")
            if grade not in GRADE_MULTIPLIERS:
                raise ValueError(f"Invalid rarity for {key}")
            weight = item.get("weight", 1)
            if (isinstance(weight, bool) or not isinstance(weight, (int, float))
                    or not math.isfinite(weight) or weight <= 0):
                raise ValueError(f"Invalid weight for {key}")
            if not isinstance(item.get("name"), str) or not item["name"].strip():
                raise ValueError(f"Item {key} needs a name")
            item.update(id=key, action=COLLECTION_ACTIONS[kind], rarity=grade, weight=weight)
            self.items[key] = item
        if not self.items:
            raise ValueError("Catalog must contain collectible items")
        for raw in self.catalog.get("crafted_items", []):
            item = dict(raw)
            key = _identifier(item.get("id", ""))
            if key in self.items or key in self.crafted_items:
                raise ValueError(f"Duplicate item ID: {key}")
            if not item.get("name"):
                raise ValueError(f"Crafted item {key} needs a name")
            item.setdefault("kind", "crafted")
            item.setdefault("rarity", "C")
            self.crafted_items[key] = item
        self.all_items = {**self.items, **self.crafted_items}
        for raw in self.catalog.get("recipes", []):
            recipe = dict(raw)
            key = _identifier(recipe.get("id", ""))
            if key in self.recipes:
                raise ValueError(f"Duplicate recipe ID: {key}")
            ingredients = recipe.get("ingredients")
            if not isinstance(ingredients, dict) or not ingredients:
                raise ValueError(f"Recipe {key} needs ingredients")
            for item_id, amount in ingredients.items():
                if item_id not in self.all_items:
                    raise ValueError(f"Unknown ingredient: {item_id}")
                _positive_int(amount, f"Ingredient {item_id}")
            if recipe.get("output_item_id") not in self.all_items:
                raise ValueError(f"Unknown output for {key}")
            recipe["output_count"] = _positive_int(recipe.get("output_count", 1), "Output count")
            self.recipes[key] = recipe

    def _create_schema(self) -> None:
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT OR IGNORE INTO metadata VALUES ('schema_version', '2');
        CREATE TABLE IF NOT EXISTS channels (
          guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, mode TEXT NOT NULL,
          enabled INTEGER NOT NULL DEFAULT 0, next_spawn_at REAL NOT NULL,
          frenzy_until REAL NOT NULL DEFAULT 0, mineral_until REAL NOT NULL DEFAULT 0,
          mineral_grade TEXT, next_collection INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY(guild_id,channel_id));
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY, guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
          kind TEXT NOT NULL, item_id TEXT, grade TEXT NOT NULL, action TEXT NOT NULL,
          item_json TEXT NOT NULL, created_at REAL NOT NULL, starts_at REAL,
          expires_at REAL, status TEXT NOT NULL, message_id TEXT,
          mode TEXT NOT NULL, window_seconds INTEGER NOT NULL, frenzy INTEGER NOT NULL,
          first_user_id TEXT,
          FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id));
        CREATE UNIQUE INDEX IF NOT EXISTS one_live_event ON events(guild_id,channel_id)
          WHERE status IN ('pending','open');
        CREATE TABLE IF NOT EXISTS profiles (
          guild_id TEXT NOT NULL, user_id TEXT NOT NULL, catches INTEGER NOT NULL DEFAULT 0,
          units INTEGER NOT NULL DEFAULT 0, xp INTEGER NOT NULL DEFAULT 0,
          firsts INTEGER NOT NULL DEFAULT 0, powerups INTEGER NOT NULL DEFAULT 0,
          crafts INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id,user_id));
        CREATE TABLE IF NOT EXISTS inventory (
          guild_id TEXT NOT NULL, user_id TEXT NOT NULL, item_id TEXT NOT NULL,
          quantity INTEGER NOT NULL CHECK(quantity >= 0),
          PRIMARY KEY(guild_id,user_id,item_id));
        CREATE TABLE IF NOT EXISTS discoveries (
          guild_id TEXT NOT NULL, user_id TEXT NOT NULL, item_id TEXT NOT NULL,
          PRIMARY KEY(guild_id,user_id,item_id));
        INSERT OR IGNORE INTO discoveries SELECT guild_id,user_id,item_id FROM inventory;
        CREATE TABLE IF NOT EXISTS boosts (
          guild_id TEXT NOT NULL, user_id TEXT NOT NULL, multiplier INTEGER NOT NULL,
          remaining INTEGER NOT NULL CHECK(remaining BETWEEN 0 AND 5), grade TEXT NOT NULL,
          PRIMARY KEY(guild_id,user_id));
        CREATE TABLE IF NOT EXISTS claims (
          event_id TEXT NOT NULL, user_id TEXT NOT NULL, quantity INTEGER NOT NULL,
          multiplier INTEGER NOT NULL, claimed_at REAL NOT NULL,
          PRIMARY KEY(event_id,user_id), FOREIGN KEY(event_id) REFERENCES events(id));
        CREATE TABLE IF NOT EXISTS requests (
          guild_id TEXT NOT NULL, request_id TEXT NOT NULL, operation TEXT NOT NULL,
          result_json TEXT NOT NULL, created_at REAL NOT NULL,
          PRIMARY KEY(guild_id,request_id));
        CREATE INDEX IF NOT EXISTS events_expiry ON events(status,expires_at);
        CREATE TABLE IF NOT EXISTS channel_interludes (
          guild_id TEXT NOT NULL, channel_id TEXT NOT NULL, last_attempt_at REAL NOT NULL,
          PRIMARY KEY(guild_id,channel_id),
          FOREIGN KEY(guild_id,channel_id) REFERENCES channels(guild_id,channel_id));
        """)
        with self._transaction() as db:
            if "next_collection" not in {r[1] for r in db.execute("PRAGMA table_info(channels)")}:
                db.execute("ALTER TABLE channels ADD COLUMN next_collection INTEGER NOT NULL DEFAULT 0")
            if "galaxy_number" not in {r[1] for r in db.execute("PRAGMA table_info(events)")}:
                db.execute("ALTER TABLE events ADD COLUMN galaxy_number INTEGER NOT NULL DEFAULT 1 CHECK(galaxy_number BETWEEN 1 AND 256)")
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()[0]
            if version == "1":
                # Earlier releases timed ordinary appearances from posting.
                # Preserve completed events and windows that already have a
                # claimant, but let unclaimed open discoveries wait on restart.
                db.execute("""UPDATE events SET expires_at=NULL WHERE status='open'
                              AND frenzy=0 AND first_user_id IS NULL""")
                db.execute("UPDATE metadata SET value='2' WHERE key='schema_version'")
            elif version != "2":
                raise ValueError(f"Unsupported database schema version: {version}")

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.rollback()
                raise
            else:
                self.db.commit()

    def _now(self, now: float | None = None) -> float:
        result = float(self.clock() if now is None else now)
        if not math.isfinite(result):
            raise ValueError("Time must be finite")
        return result

    @staticmethod
    def _channel(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        result = dict(row)
        result["enabled"] = bool(result["enabled"])
        return result

    @staticmethod
    def _event(row: sqlite3.Row | None) -> dict | None:
        if row is None:
            return None
        result = dict(row)
        result["item"] = json.loads(result.pop("item_json"))
        result["frenzy"] = bool(result["frenzy"])
        from .progression import galaxy
        result["galaxy"] = galaxy(result.get("galaxy_number", 1))
        return result

    def _get_channel(self, db: sqlite3.Connection, guild: str, channel: str) -> sqlite3.Row:
        row = db.execute("SELECT * FROM channels WHERE guild_id=? AND channel_id=?", (guild, channel)).fetchone()
        if row is None:
            raise ValueError("Channel is not configured")
        return row

    def configure_channel(self, guild_id: str, channel_id: str, mode: str = "community") -> dict:
        """Create a disabled channel, or change the mode for future appearances."""
        guild, channel = _identifier(guild_id), _identifier(channel_id)
        if mode not in ("community", "classic"):
            raise ValueError("Mode must be community or classic")
        with self._transaction() as db:
            db.execute("""INSERT INTO channels(guild_id,channel_id,mode,next_spawn_at)
                          VALUES(?,?,?,?) ON CONFLICT(guild_id,channel_id)
                          DO UPDATE SET mode=excluded.mode""", (guild, channel, mode, self._now()+2))
            result = self._channel(self._get_channel(db, guild, channel))
        self.progression.ensure_channel(guild, channel)
        self.activities.ensure_channel(guild, channel)
        return result

    def set_enabled(self, guild_id: str, channel_id: str, enabled: bool) -> dict:
        """Pause/resume spawns. Pausing cancels the current appearance immediately."""
        guild, channel = _identifier(guild_id), _identifier(channel_id)
        with self._transaction() as db:
            self._get_channel(db, guild, channel)
            if not enabled:
                db.execute("UPDATE events SET status='cancelled' WHERE guild_id=? AND channel_id=? AND status IN ('open','pending')", (guild, channel))
            db.execute("UPDATE channels SET enabled=?,next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                       (int(bool(enabled)), self._now()+2, guild, channel))
            return self._channel(self._get_channel(db, guild, channel))

    def channels(self) -> list[dict]:
        with self._lock:
            return [self._channel(r) for r in self.db.execute("SELECT * FROM channels ORDER BY guild_id,channel_id")]

    def status(self, guild_id: str, channel_id: str, user_id: str | None = None) -> dict:
        guild, channel, now = _identifier(guild_id), _identifier(channel_id), self._now()
        with self._lock:
            row = self.db.execute("SELECT * FROM channels WHERE guild_id=? AND channel_id=?", (guild, channel)).fetchone()
            if row is None:
                return {"configured": False, "enabled": False, "guild_id": guild, "channel_id": channel,
                        "active_event": None, "frenzy_remaining": 0, "mineral_remaining": 0}
            result = self._channel(row)
            result.update(configured=True, active_event=self.active_event(guild, channel, now),
                          frenzy_remaining=max(0, row["frenzy_until"]-now),
                          mineral_remaining=max(0, row["mineral_until"]-now))
            if user_id is not None:
                result["boost"] = self._boost(self.db, guild, _identifier(user_id))
            return result

    def event(self, event_id: str) -> dict | None:
        with self._lock:
            return self._event(self.db.execute("SELECT * FROM events WHERE id=?", (_identifier(event_id),)).fetchone())

    def active_event(self, guild_id: str, channel_id: str, now: float | None = None) -> dict | None:
        """Return a posted appearance, including one waiting for its first claim."""
        guild, channel, now = _identifier(guild_id), _identifier(channel_id), self._now(now)
        with self._lock:
            return self._event(self.db.execute("""SELECT * FROM events WHERE guild_id=? AND channel_id=?
                           AND status='open' AND (expires_at IS NULL OR expires_at>?)""", (guild, channel, now)).fetchone())

    def expire_events(self, now: float | None = None) -> list[dict]:
        """Close and return newly expired appearances, for editing their posts."""
        now = self._now(now)
        with self._transaction() as db:
            rows = db.execute("SELECT * FROM events WHERE status='open' AND expires_at<=?", (now,)).fetchall()
            db.execute("UPDATE events SET status='expired' WHERE status='open' AND expires_at<=?", (now,))
            results = [self._event(r) for r in rows]
            for result in results:
                result["status"] = "expired"
            return results

    def recover_pending(self, max_age_seconds: float = 60, now: float | None = None) -> list[dict]:
        """Cancel abandoned sends after a restart; call with zero under a process lock."""
        if max_age_seconds < 0:
            raise ValueError("Recovery age cannot be negative")
        now = self._now(now)
        with self._transaction() as db:
            rows = db.execute("SELECT * FROM events WHERE status='pending' AND created_at<=?", (now-max_age_seconds,)).fetchall()
            db.execute("UPDATE events SET status='cancelled' WHERE status='pending' AND created_at<=?", (now-max_age_seconds,))
            results = [self._event(r) for r in rows]
            for result in results:
                result["status"] = "cancelled"
            return results

    def due_channels(self, now: float | None = None) -> list[dict]:
        """Read candidates only. ``spawn`` atomically rechecks channel occupancy."""
        now = self._now(now)
        with self._lock:
            rows = self.db.execute("""SELECT c.* FROM channels c WHERE c.enabled=1
              AND c.next_spawn_at<=? AND (c.frenzy_until<=? OR c.frenzy_until>=?)
              AND NOT EXISTS(SELECT 1 FROM events e
                WHERE e.guild_id=c.guild_id AND e.channel_id=c.channel_id
                AND (e.status='pending' OR (e.status='open' AND (e.expires_at IS NULL OR e.expires_at>?))))
              ORDER BY c.next_spawn_at""", (now, now, now+5, now)).fetchall()
            return [self._channel(r) for r in rows]

    def _weighted(self, entries: list[Any], weights: list[float]) -> Any:
        return self.rng.choices(entries, weights=weights, k=1)[0]

    def spawn(self, guild_id: str, channel_id: str, kind: str | None = None,
              item_id: str | None = None, grade: str | None = None,
              now: float | None = None) -> dict:
        """Reserve one pending appearance. Forced variants support moderator demos.

        Raises ``ValueError`` for a disabled/occupied channel or an invalid forced
        choice. Powerups cannot be forced during a gas frenzy either.
        """
        guild, channel, now = _identifier(guild_id), _identifier(channel_id), self._now(now)
        if grade is not None and grade not in GRADE_MULTIPLIERS:
            raise ValueError("Invalid grade")
        with self._transaction() as db:
            state = self._get_channel(db, guild, channel)
            if not state["enabled"]:
                raise ValueError("Channel is paused")
            db.execute("UPDATE events SET status='expired' WHERE guild_id=? AND channel_id=? AND status='open' AND expires_at<=?", (guild, channel, now))
            if db.execute("SELECT 1 FROM events WHERE guild_id=? AND channel_id=? AND status IN ('pending','open')", (guild, channel)).fetchone():
                raise ValueError("Channel already has an active appearance")
            frenzy = now < state["frenzy_until"]
            if frenzy and state["frenzy_until"]-now < 5:
                raise ValueError("Frenzy is ending; there is not enough time for another appearance")
            if item_id is not None:
                if item_id not in self.items:
                    raise ValueError("Unknown collectible")
                item = self.items[item_id]
                if kind is not None and kind != item["kind"]:
                    raise ValueError("Item does not match requested kind")
                kind = item["kind"]
            if kind is None:
                kinds = [k for k in KIND_WEIGHTS if (k in POWERUP_KINDS and not frenzy and not state["next_collection"])
                         or any(i["kind"] == k for i in self.items.values())]
                kind = self._weighted(kinds, [KIND_WEIGHTS[k] for k in kinds])
            if kind not in COLLECTION_ACTIONS and kind not in POWERUP_KINDS:
                raise ValueError("Unknown appearance kind")
            if frenzy and kind in POWERUP_KINDS:
                raise ValueError("Powerups cannot spawn during a gas frenzy")
            if kind in COLLECTION_ACTIONS:
                if item_id is None:
                    pool = [i for i in self.items.values() if i["kind"] == kind]
                    if not pool:
                        raise ValueError("No items for requested kind")
                    item = self._weighted(pool, [i["weight"] for i in pool])
                item = dict(item)
                if grade is not None and grade != item["rarity"]:
                    raise ValueError("Collectible grades are fixed by the catalog; choose a grade only for a hotspot")
                item_id, grade, action = item["id"], grade or item["rarity"], COLLECTION_ACTIONS[kind]
                mode = "community" if frenzy else state["mode"]
            else:
                grade = grade or self._weighted(list(HOTSPOT_GRADE_WEIGHTS), list(HOTSPOT_GRADE_WEIGHTS.values()))
                names = {"electromagnetic": "Electromagnetic Hotspot", "gas": "Gas Hotspot", "mineral_powerup": "Mineral Hotspot"}
                icon_kind = "mineral" if kind == "mineral_powerup" else kind
                item = {"id": kind, "name": names[kind], "kind": kind, "rarity": grade,
                        "action": "powerup", "icon": f"assets/icons/power_{icon_kind}_{grade.lower()}.png"}
                item_id, action, mode = None, "powerup", "classic"
            # Snapshot the mineral bonus for this appearance. Its earned grace
            # survives a quiet wait; later appearances after the effect ends
            # receive no bonus.
            window = (10 if frenzy else 15) + (5 if now < state["mineral_until"] else 0)
            event_id = uuid.uuid4().hex
            journey = self.progression._ensure_journey(db, guild, channel)
            db.execute("""INSERT INTO events(id,guild_id,channel_id,kind,item_id,grade,action,
              item_json,created_at,status,mode,window_seconds,frenzy,galaxy_number)
              VALUES(?,?,?,?,?,?,?,?,?,'pending',?,?,?,?)""",
              (event_id, guild, channel, kind, item_id, grade, action,
               json.dumps(item, ensure_ascii=False), now, mode, window, int(frenzy), journey["galaxy_number"]))
            return self._event(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    def bind_message(self, event_id: str, message_id: str) -> dict:
        """Open a successfully sent appearance.

        Ordinary appearances have no deadline until their first claim. Binding
        twice is idempotent. A frenzy's timer starts now and is capped at the
        absolute end of the frenzy.
        """
        event_id, message_id, now = _identifier(event_id), _identifier(message_id), self._now()
        with self._transaction() as db:
            row = db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
            if row is None:
                raise ValueError("Unknown appearance")
            if row["status"] != "pending":
                if row["message_id"] == message_id:
                    return self._event(row)
                raise ValueError("Appearance is no longer pending")
            channel = self._get_channel(db, row["guild_id"], row["channel_id"])
            expires_at = None
            if row["frenzy"]:
                expires_at = min(now + row["window_seconds"], channel["frenzy_until"])
            if not channel["enabled"] or (row["frenzy"] and expires_at-now < 5):
                db.execute("UPDATE events SET status='cancelled',message_id=? WHERE id=?", (message_id, event_id))
                if row["frenzy"]:
                    db.execute("UPDATE channels SET next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                               (max(now, channel["frenzy_until"])+self.rng.randint(120, 300), row["guild_id"], row["channel_id"]))
            else:
                db.execute("UPDATE events SET status='open',message_id=?,starts_at=?,expires_at=? WHERE id=?",
                           (message_id, now, expires_at, event_id))
                delay = max(15, row["window_seconds"]+1) if row["frenzy"] else self.rng.randint(120, 300)
                next_spawn = now+delay
                if row["frenzy"] and next_spawn > channel["frenzy_until"]-5:
                    next_spawn = channel["frenzy_until"]+self.rng.randint(120, 300)
                if row["kind"] in COLLECTION_ACTIONS:
                    db.execute("UPDATE channels SET next_collection=0 WHERE guild_id=? AND channel_id=?", (row["guild_id"], row["channel_id"]))
                db.execute("UPDATE channels SET next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                           (next_spawn, row["guild_id"], row["channel_id"]))
            return self._event(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    def cancel_event(self, event_id: str) -> dict | None:
        """Cancel an appearance after a failed post; retry spawning after 30s."""
        with self._transaction() as db:
            row = db.execute("SELECT * FROM events WHERE id=?", (_identifier(event_id),)).fetchone()
            if row is None:
                return None
            if row["status"] in ("pending", "open"):
                db.execute("UPDATE events SET status='cancelled' WHERE id=?", (event_id,))
                db.execute("UPDATE channels SET next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                           (self._now()+30, row["guild_id"], row["channel_id"]))
            return self._event(db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone())

    @staticmethod
    def _boost(db: sqlite3.Connection, guild: str, user: str) -> dict:
        row = db.execute("SELECT multiplier,remaining,grade FROM boosts WHERE guild_id=? AND user_id=?", (guild, user)).fetchone()
        if row is None or row["remaining"] <= 0:
            return {"multiplier": 1, "remaining": 0, "grade": None}
        return dict(row)

    @staticmethod
    def _ensure_profile(db: sqlite3.Connection, guild: str, user: str) -> None:
        db.execute("INSERT OR IGNORE INTO profiles(guild_id,user_id) VALUES(?,?)", (guild, user))

    @staticmethod
    def _add_inventory(db: sqlite3.Connection, guild: str, user: str, item: str, quantity: int) -> None:
        db.execute("""INSERT INTO inventory(guild_id,user_id,item_id,quantity) VALUES(?,?,?,?)
                      ON CONFLICT(guild_id,user_id,item_id) DO UPDATE SET quantity=inventory.quantity+excluded.quantity""",
            (guild, user, item, quantity))
        db.execute("INSERT OR IGNORE INTO discoveries(guild_id,user_id,item_id) VALUES(?,?,?)", (guild, user, item))

    @staticmethod
    def _request_seen(db: sqlite3.Connection, guild: str, request_id: str | None) -> bool:
        return bool(request_id is not None and db.execute("SELECT 1 FROM requests WHERE guild_id=? AND request_id=?", (guild, request_id)).fetchone())

    @staticmethod
    def _finish(db: sqlite3.Connection, guild: str, request_id: str | None, operation: str,
                result: dict, now: float) -> dict:
        if request_id is not None:
            # Store only outcome metadata, never Discord message text or tokens.
            summary = {k: result[k] for k in ("ok", "reason", "quantity", "multiplier") if k in result}
            db.execute("INSERT INTO requests(guild_id,request_id,operation,result_json,created_at) VALUES(?,?,?,?,?)",
                       (guild, request_id, operation, json.dumps(summary), now))
        return result

    def claim(self, guild_id: str, channel_id: str, user_id: str, action: str,
              event_id: str | None = None, request_id: str | None = None,
              now: float | None = None) -> dict:
        """Atomically claim a posted appearance once per player.

        Failures: duplicate_request, invalid_action, channel_unavailable,
        no_event, wrong_event, not_open, expired, wrong_action, already_claimed.
        Accepted command words are case-insensitive with outside whitespace;
        extra words/punctuation do not count. Only successful collections consume
        an electromagnetic charge. Powerup claims do not consume charges.
        """
        guild, channel, user = _identifier(guild_id), _identifier(channel_id), _identifier(user_id)
        now = self._now(now)
        request_id = _identifier(request_id) if request_id is not None else None
        word = action.strip().casefold() if isinstance(action, str) else ""
        with self._transaction() as db:
            if self._request_seen(db, guild, request_id):
                return {"ok": False, "reason": "duplicate_request"}
            def finish(result: dict) -> dict:
                return self._finish(db, guild, request_id, "claim", result, now)
            if word not in (*COLLECTION_ACTIONS.values(), "powerup"):
                return finish({"ok": False, "reason": "invalid_action"})
            state = db.execute("SELECT * FROM channels WHERE guild_id=? AND channel_id=?", (guild, channel)).fetchone()
            if state is None or not state["enabled"]:
                return finish({"ok": False, "reason": "channel_unavailable"})
            if event_id is not None:
                row = db.execute("SELECT * FROM events WHERE id=?", (_identifier(event_id),)).fetchone()
                if row is not None and (row["guild_id"] != guild or row["channel_id"] != channel):
                    return finish({"ok": False, "reason": "wrong_event"})
            else:
                row = db.execute("SELECT * FROM events WHERE guild_id=? AND channel_id=? AND status IN ('pending','open')", (guild, channel)).fetchone()
            if row is None:
                return finish({"ok": False, "reason": "no_event"})
            event = self._event(row)
            if row["status"] != "open":
                return finish({"ok": False, "reason": "not_open", "event": event})
            if row["expires_at"] is not None and row["expires_at"] <= now:
                db.execute("UPDATE events SET status='expired' WHERE id=?", (row["id"],))
                event["status"] = "expired"
                return finish({"ok": False, "reason": "expired", "event": event})
            if word != row["action"]:
                return finish({"ok": False, "reason": "wrong_action", "event": event})
            if db.execute("SELECT 1 FROM claims WHERE event_id=? AND user_id=?", (row["id"], user)).fetchone():
                return finish({"ok": False, "reason": "already_claimed", "event": event})
            first = row["first_user_id"] is None
            if first and not row["frenzy"]:
                # A discovery can wait for hours. Schedule the next ordinary
                # appearance from this successful claim, not its old post time.
                # Gas/mineral activations below replace this normal interval.
                db.execute("UPDATE channels SET next_spawn_at=? WHERE guild_id=? AND channel_id=?",
                           (now+self.rng.randint(120, 300), guild, channel))
            self._ensure_profile(db, guild, user)
            quantity, multiplier, xp_awarded, effect = 0, 1, 0, None
            if row["kind"] in POWERUP_KINDS:
                db.execute("UPDATE profiles SET powerups=powerups+1 WHERE guild_id=? AND user_id=?", (guild, user))
                if row["kind"] == "electromagnetic":
                    old = self._boost(db, guild, user)
                    incoming = GRADE_MULTIPLIERS[row["grade"]]
                    preserved = old["remaining"] > 0 and old["multiplier"] > incoming
                    if not preserved:
                        db.execute("""INSERT INTO boosts(guild_id,user_id,multiplier,remaining,grade) VALUES(?,?,?,5,?)
                          ON CONFLICT(guild_id,user_id) DO UPDATE SET multiplier=excluded.multiplier,
                          remaining=5,grade=excluded.grade""", (guild, user, incoming, row["grade"]))
                    boost = self._boost(db, guild, user)
                    effect = {"kind": "electromagnetic", **boost, "preserved_stronger": preserved}
                elif row["kind"] == "gas":
                    duration = GRADE_SECONDS[row["grade"]]
                    until = now+duration
                    db.execute("UPDATE channels SET frenzy_until=?,next_spawn_at=? WHERE guild_id=? AND channel_id=?", (until, now+1, guild, channel))
                    effect = {"kind": "gas", "until": until, "seconds": duration, "community": True}
                else:
                    duration = GRADE_SECONDS[row["grade"]]
                    until = max(state["mineral_until"], now+duration)
                    effect_grade = (state["mineral_grade"] if state["mineral_until"] > now+duration else row["grade"])
                    db.execute("""UPDATE channels SET mineral_until=?,mineral_grade=?,
                               next_spawn_at=MIN(next_spawn_at,?),next_collection=1
                               WHERE guild_id=? AND channel_id=?""", (until, effect_grade, now+2, guild, channel))
                    effect = {"kind": "mineral_powerup", "until": until, "seconds": until-now, "bonus_seconds": 5}
            else:
                boost = self._boost(db, guild, user)
                multiplier = boost["multiplier"]
                quantity = multiplier
                xp_awarded = GRADE_XP[row["grade"]]
                self._add_inventory(db, guild, user, row["item_id"], quantity)
                db.execute("""UPDATE profiles SET catches=catches+1,units=units+?,xp=xp+?,firsts=firsts+?
                           WHERE guild_id=? AND user_id=?""", (quantity, xp_awarded, int(first), guild, user))
                if boost["remaining"] > 0:
                    db.execute("UPDATE boosts SET remaining=remaining-1 WHERE guild_id=? AND user_id=?", (guild, user))
            db.execute("INSERT INTO claims(event_id,user_id,quantity,multiplier,claimed_at) VALUES(?,?,?,?,?)",
                       (row["id"], user, quantity, multiplier, now))
            warp_awarded, warp_multiplier, completed_missions = 0, 1, []
            if row["kind"] in COLLECTION_ACTIONS:
                warp_multiplier = self.activities.drive_multiplier(db, guild, channel, now)
                warp_awarded = self.progression.credit(db, guild, user, warp_multiplier)["awarded"]
                completed_missions = self.activities.record_claim(db, event, user, now)
            warp_account = self.progression.account(db, guild, user)
            achievements = self.honours.evaluate(db, guild, user, now)
            if first:
                deadline = row["expires_at"]
                if not row["frenzy"] and row["mode"] == "community":
                    deadline = now+row["window_seconds"]
                db.execute("UPDATE events SET first_user_id=?,expires_at=? WHERE id=?",
                           (user, deadline, row["id"]))
            if row["mode"] == "classic":
                db.execute("UPDATE events SET status='claimed' WHERE id=?", (row["id"],))
            event = self._event(db.execute("SELECT * FROM events WHERE id=?", (row["id"],)).fetchone())
            boost = self._boost(db, guild, user)
            result = {"ok": True, "reason": "claimed", "event": event, "item": event["item"],
                      "quantity": quantity, "multiplier": multiplier, "first": first,
                      "xp_awarded": xp_awarded, "remaining_charges": boost["remaining"], "effect": effect,
                      "warp_points_awarded": warp_awarded, "warp_multiplier": warp_multiplier,
                      "warp_balance": warp_account["balance"], "warp_charges": warp_account["charges"],
                      "missions_completed": completed_missions,
                      "achievements_unlocked": achievements}
            if row["kind"] in COLLECTION_ACTIONS:
                from .honours import level_progress
                total_xp = db.execute("SELECT xp FROM profiles WHERE guild_id=? AND user_id=?",
                                      (guild, user)).fetchone()[0]
                progress = level_progress(total_xp)
                previous = level_progress(total_xp - xp_awarded)
                result["level_progress"] = progress
                result["level_up"] = ({"from_level": previous["level"], "to_level": progress["level"],
                                       "title": progress["title"]}
                                      if progress["level"] > previous["level"] else None)
            return finish(result)

    def inventory(self, guild_id: str, user_id: str) -> list[dict]:
        """Positive inventory rows with item_id, quantity, item and display name."""
        guild, user = _identifier(guild_id), _identifier(user_id)
        with self._lock:
            rows = self.db.execute("SELECT item_id,quantity FROM inventory WHERE guild_id=? AND user_id=? AND quantity>0 ORDER BY item_id", (guild, user)).fetchall()
            result = []
            for row in rows:
                item = self.all_items.get(row["item_id"], {"id": row["item_id"], "name": row["item_id"], "kind": "unknown"})
                result.append({**dict(row), "item": dict(item), "name": item["name"], "kind": item["kind"]})
            return result

    def profile(self, guild_id: str, user_id: str) -> dict:
        guild, user = _identifier(guild_id), _identifier(user_id)
        with self._lock:
            row = self.db.execute("SELECT * FROM profiles WHERE guild_id=? AND user_id=?", (guild, user)).fetchone()
            result = dict(row) if row else {"guild_id": guild, "user_id": user, "catches": 0,
                                          "units": 0, "xp": 0, "firsts": 0, "powerups": 0, "crafts": 0}
            result["boost"] = self._boost(self.db, guild, user)
            discovered = [r[0] for r in self.db.execute("SELECT item_id FROM discoveries WHERE guild_id=? AND user_id=? ORDER BY item_id", (guild, user))]
            result["discovered_item_ids"] = discovered
            result["unique_items"] = len(discovered)
            result["unique_collectibles"] = sum(item in self.items for item in discovered)
            result["categories"] = {kind: sum(self.all_items.get(item, {}).get("kind") == kind for item in discovered)
                                    for kind in (*COLLECTION_ACTIONS, "crafted")}
            from .honours import level_progress
            result.update(level_progress(result["xp"]))
            honours = self.honours.status(guild, user)
            result["achievements_unlocked"] = honours["unlocked_count"]
            result["achievements_total"] = honours["total_count"]
            result["recent_achievements"] = sorted(
                (badge for badge in honours["achievements"] if badge["unlocked"]),
                key=lambda badge: badge["unlocked_at"], reverse=True)[:3]
            return result

    def leaderboard(self, guild_id: str, limit: int = 10, metric: str = "catches") -> list[dict]:
        guild = _identifier(guild_id)
        if metric not in ("catches", "units", "xp", "firsts", "powerups", "crafts"):
            raise ValueError("Unknown leaderboard metric")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("Limit must be 1..100")
        with self._lock:
            # Metric comes exclusively from the fixed whitelist above.
            return [dict(r) for r in self.db.execute(f"SELECT * FROM profiles WHERE guild_id=? ORDER BY {metric} DESC,catches DESC,user_id ASC LIMIT ?", (guild, limit))]

    def craft(self, guild_id: str, user_id: str, recipe_id: str,
              request_id: str | None = None) -> dict:
        """Atomically consume ingredients and award a collectible craft, once.

        Crafting does not earn catches/XP or consume electromagnetic charges.
        Failure reasons are unknown_recipe, missing_ingredients, duplicate_request.
        """
        guild, user = _identifier(guild_id), _identifier(user_id)
        request_id, now = (_identifier(request_id) if request_id is not None else None), self._now()
        with self._transaction() as db:
            if self._request_seen(db, guild, request_id):
                return {"ok": False, "reason": "duplicate_request"}
            def finish(result: dict) -> dict:
                return self._finish(db, guild, request_id, "craft", result, now)
            recipe = self.recipes.get(recipe_id)
            if recipe is None:
                return finish({"ok": False, "reason": "unknown_recipe"})
            missing = []
            for item, amount in recipe["ingredients"].items():
                row = db.execute("SELECT quantity FROM inventory WHERE guild_id=? AND user_id=? AND item_id=?", (guild, user, item)).fetchone()
                have = row[0] if row else 0
                if have < amount:
                    missing.append({"item_id": item, "name": self.all_items[item]["name"], "have": have, "need": amount})
            if missing:
                return finish({"ok": False, "reason": "missing_ingredients", "missing": missing, "recipe": recipe})
            for item, amount in recipe["ingredients"].items():
                db.execute("UPDATE inventory SET quantity=quantity-? WHERE guild_id=? AND user_id=? AND item_id=?", (amount, guild, user, item))
            self._add_inventory(db, guild, user, recipe["output_item_id"], recipe["output_count"])
            self._ensure_profile(db, guild, user)
            db.execute("UPDATE profiles SET crafts=crafts+1 WHERE guild_id=? AND user_id=?", (guild, user))
            achievements = self.honours.evaluate(db, guild, user, now)
            return finish({"ok": True, "reason": "crafted", "recipe": recipe,
                           "item": self.all_items[recipe["output_item_id"]], "quantity": recipe["output_count"],
                           "achievements_unlocked": achievements})

    def backup(self, path: str | Path) -> str:
        """Create a consistent SQLite backup, including writes still in the WAL."""
        if self.backend == "postgresql":
            from .migration import export_sqlite
            return export_sqlite(self, path)
        path = Path(path).resolve()
        if self.db_path != ":memory:" and path == Path(self.db_path).resolve():
            raise ValueError("Backup must use a different path")
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            target = sqlite3.connect(str(path))
            try:
                self.db.backup(target)
            finally:
                target.close()
        return str(path)

    def close(self) -> None:
        with self._lock:
            self.db.close()

    def __enter__(self) -> "GameEngine":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()
