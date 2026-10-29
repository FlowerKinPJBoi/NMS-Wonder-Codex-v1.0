"""Private PostgreSQL control plane for the single FFC cloud host.

This module never imports Discord or changes game tables. A prepared database
is deliberately inactive. Activation is a separate operator handoff requiring
a committed game import receipt and acknowledgment that the PC host stopped.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import threading
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb


VERSION = "0.3.0"
PROTOCOL = 1
APPLICATION_ID = "1565167975248695456"
GUILD_ID = "1454806298565808151"
CHANNEL_ID = "1565143548737888326"
SESSION_SECONDS = 30 * 86400
HEARTBEAT_SECONDS = 20
COMMAND_SECONDS = 90
RUNNING_SECONDS = 120
TOKEN_PREFIX = "ffc1_"
ACTIONS = frozenset({"start", "pause", "mode", "spawn", "frenzy", "power_drive", "backup"})
STATES = frozenset({"prepared", "waiting_for_token", "waiting_for_import", "standby", "connecting",
                    "running", "paused", "offline", "error"})
KINDS = frozenset({"random", "fish", "plant", "mineral", "pet", "electromagnetic", "gas", "mineral_powerup"})
NODE_KINDS = frozenset({"electromagnetic", "gas", "mineral_powerup"})


class ControlError(ValueError):
    status_code = 400


class ControlUnauthorized(ControlError):
    status_code = 401


class ControlNotFound(ControlError):
    status_code = 404


class ControlConflict(ControlError):
    status_code = 409


class ControlRateLimited(ControlError):
    status_code = 429


class ControlUnavailable(ControlError):
    status_code = 503


def _schema(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"ffc_wilds(?:_[a-z0-9]+)*", value):
        raise ValueError("FFC schema name is invalid.")
    if len(value) > 63:
        raise ValueError("FFC schema name is too long.")
    return value


def leader_key(schema: str = "ffc_wilds") -> int:
    """One stable advisory-lock identity shared by runtime and handoff checks."""
    identity = f"{_schema(schema)}:{APPLICATION_ID}:{GUILD_ID}:{CHANNEL_ID}:discord-host"
    return int.from_bytes(hashlib.sha256(identity.encode()).digest()[:8], "big", signed=True)


def _actor(value: str) -> str:
    if not isinstance(value, str) or not value.strip() or not re.fullmatch(r"[A-Za-z0-9_. -]{1,64}", value):
        raise ControlUnauthorized("A valid FFC owner is required.")
    return value.strip()


def _request_id(value: str) -> str:
    try:
        parsed = uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError) as exc:
        raise ControlError("Request ID must be a UUID.") from exc
    if parsed.version != 4:
        raise ControlError("Request ID must be a random UUID.")
    return str(parsed)


def _worker_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", value):
        raise ControlError("Invalid cloud worker ID.")
    return value


def _json(value: Any, limit: int = 32768) -> str:
    def check(item: Any, depth: int = 0) -> None:
        if depth > 10:
            raise ControlError("Control data is too deeply nested.")
        if isinstance(item, dict):
            for key, val in item.items():
                if not isinstance(key, str) or len(key) > 100:
                    raise ControlError("Control data has an invalid key.")
                if re.search(r"token|secret|password|credential|authorization|database_url|admin_key|^dsn$", key, re.I):
                    raise ControlError("Credentials cannot be stored in control data.")
                check(val, depth + 1)
        elif isinstance(item, list):
            if len(item) > 200:
                raise ControlError("Control data has too many entries.")
            for val in item:
                check(val, depth + 1)
        elif item is not None and not isinstance(item, (str, int, float, bool)):
            raise ControlError("Control data must be JSON.")
    check(value)
    try:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (ValueError, TypeError) as exc:
        raise ControlError("Control data must be finite JSON.") from exc
    if len(encoded.encode("utf-8")) > limit:
        raise ControlError("Control data is too large.")
    return encoded


def validate_action(action: str, arguments: dict) -> dict:
    if not isinstance(action, str) or action not in ACTIONS or not isinstance(arguments, dict):
        raise ControlError("Unsupported FFC control action.")
    if action in {"start", "pause", "backup"}:
        if arguments:
            raise ControlError("This action does not accept arguments.")
        return {}
    if action == "mode":
        if set(arguments) != {"mode"} or not isinstance(arguments["mode"], str) or arguments["mode"] not in {"community", "classic"}:
            raise ControlError("Choose community or classic mode.")
    elif action == "spawn":
        kind = arguments.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ControlError("Choose a discovery or powerup type.")
        expected = {"kind", "grade"} if kind in NODE_KINDS else {"kind"}
        if set(arguments) != expected or (kind in NODE_KINDS and (not isinstance(arguments.get("grade"), str) or arguments["grade"] not in {"C", "B", "A", "S"})):
            raise ControlError("Only powerup nodes accept a C, B, A, or S class.")
        if kind in NODE_KINDS and (not isinstance(arguments.get("grade"), str) or len(arguments["grade"]) != 1):
            raise ControlError("Choose a C, B, A, or S class.")
    elif action == "frenzy":
        if set(arguments) != {"grade"} or not isinstance(arguments.get("grade"), str) or arguments["grade"] not in {"C", "B", "A", "S"}:
            raise ControlError("Choose a C, B, A, or S Frenzy.")
    elif action == "power_drive":
        if set(arguments) != {"multiplier"} or type(arguments.get("multiplier")) is not int or arguments["multiplier"] not in {2, 3}:
            raise ControlError("Choose a 2x or 3x Power Drive.")
    _json(arguments, 1024)
    return dict(arguments)


def _command(row: dict | None) -> dict:
    if row is None:
        raise ControlNotFound("This request has not been received by the cloud host.")
    return {key: row.get(key) for key in (
        "id", "status", "action", "arguments", "result", "error", "created_at", "started_at",
        "finished_at", "expires_at", "actor", "generation", "expected_worker_id",
    )}


class ControlStore:
    """Short bounded connections; qualified tables never touch public schema."""

    def __init__(self, database_url: str, schema: str = "ffc_wilds_control", *,
                 game_schema: str = "ffc_wilds", clock: Callable[[], float] = time.time):
        url = str(database_url or "").strip()
        for prefix in ("postgresql+psycopg://", "postgres://"):
            if url.startswith(prefix):
                url = "postgresql://" + url[len(prefix):]
        if not url.startswith("postgresql://"):
            raise ValueError("A PostgreSQL database is required for cloud control.")
        self._database_url = url
        self.schema = _schema(schema)
        self.game_schema = _schema(game_schema)
        self.clock = clock
        self._slots = threading.BoundedSemaphore(3)
        self._prefix = f'"{self.schema}".'

    def __repr__(self) -> str:
        return f"ControlStore(schema={self.schema!r})"

    @contextmanager
    def _connection(self):
        if not self._slots.acquire(timeout=2):
            raise ControlUnavailable("Cloud controls are busy. Try again shortly.")
        try:
            with psycopg.connect(self._database_url, row_factory=dict_row, connect_timeout=5,
                                 application_name="ffc-wilds-control",
                                 options="-c statement_timeout=5000 -c lock_timeout=3000") as connection:
                yield connection
        finally:
            self._slots.release()

    def _now(self) -> float:
        value = float(self.clock())
        if not math.isfinite(value):
            raise ValueError("Control clock must be finite.")
        return value

    def prepare(self) -> None:
        lock = int.from_bytes(hashlib.sha256((self.schema + ":prepare").encode()).digest()[:8], "big", signed=True)
        p = self._prefix
        with self._connection() as db:
            db.execute("SELECT pg_advisory_xact_lock(%s)", (lock,))
            db.execute(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"')
            db.execute(f"""CREATE TABLE IF NOT EXISTS {p}configuration (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1), protocol INTEGER NOT NULL,
                cloud_active BOOLEAN NOT NULL DEFAULT FALSE, generation BIGINT NOT NULL DEFAULT 0,
                import_digest TEXT, import_summary JSONB, import_verified_at DOUBLE PRECISION,
                updated_at DOUBLE PRECISION NOT NULL, last_backup JSONB)""")
            db.execute(f"INSERT INTO {p}configuration(singleton,protocol,updated_at) VALUES(1,%s,%s) ON CONFLICT DO NOTHING",
                       (PROTOCOL, self._now()))
            row = db.execute(f"SELECT protocol FROM {p}configuration WHERE singleton=1").fetchone()
            if row["protocol"] != PROTOCOL:
                raise ControlConflict("The cloud control schema needs a compatible version.")
            db.execute(f"""CREATE TABLE IF NOT EXISTS {p}workers (
                worker_id TEXT PRIMARY KEY, state TEXT NOT NULL, snapshot JSONB NOT NULL,
                heartbeat_at DOUBLE PRECISION NOT NULL, generation BIGINT NOT NULL)""")
            db.execute(f"""CREATE TABLE IF NOT EXISTS {p}sessions (
                token_hash TEXT PRIMARY KEY, actor TEXT NOT NULL, created_at DOUBLE PRECISION NOT NULL,
                expires_at DOUBLE PRECISION NOT NULL, revoked_at DOUBLE PRECISION)""")
            db.execute(f"CREATE INDEX IF NOT EXISTS sessions_actor_created ON {p}sessions(actor,created_at)")
            db.execute(f"""CREATE TABLE IF NOT EXISTS {p}commands (
                id TEXT PRIMARY KEY, actor TEXT NOT NULL, fingerprint TEXT NOT NULL, action TEXT NOT NULL,
                arguments JSONB NOT NULL, status TEXT NOT NULL CHECK(status IN ('queued','running','done','failed','expired','unknown')),
                result JSONB, error TEXT, generation BIGINT NOT NULL, expected_worker_id TEXT NOT NULL,
                created_at DOUBLE PRECISION NOT NULL, expires_at DOUBLE PRECISION NOT NULL,
                started_at DOUBLE PRECISION, finished_at DOUBLE PRECISION)""")
            db.execute(f"CREATE INDEX IF NOT EXISTS commands_pending ON {p}commands(created_at) WHERE status='queued'")
            db.execute(f"CREATE INDEX IF NOT EXISTS commands_actor_created ON {p}commands(actor,created_at)")

    def _configuration(self, db, *, lock: bool = False) -> dict:
        row = db.execute(f"SELECT * FROM {self._prefix}configuration WHERE singleton=1" + (" FOR UPDATE" if lock else "")).fetchone()
        if row is None or row["protocol"] != PROTOCOL:
            raise ControlUnavailable("Cloud setup has not been prepared yet.")
        return row

    def _worker(self, db, config: dict) -> dict | None:
        return db.execute(f"""SELECT * FROM {self._prefix}workers WHERE generation=%s
            ORDER BY CASE WHEN state IN ('running','paused') AND heartbeat_at>%s THEN 3
                          WHEN state='connecting' AND heartbeat_at>%s THEN 2
                          WHEN state NOT IN ('offline','error') AND heartbeat_at>%s THEN 1 ELSE 0 END DESC, heartbeat_at DESC LIMIT 1""",
                          (config["generation"], *([self._now() - HEARTBEAT_SECONDS] * 3))).fetchone()

    def _status(self, config: dict, worker: dict | None) -> dict:
        active = bool(config["cloud_active"])
        fresh = worker is not None and 0 <= self._now() - worker["heartbeat_at"] <= HEARTBEAT_SECONDS
        snapshot = dict(worker["snapshot"]) if worker else {}
        state = worker["state"] if fresh else ("offline" if active else "prepared")
        runtime_ready = bool(fresh and state not in {"offline", "error"})
        if not active and state != "error":
            state = "prepared"
        ready = bool(active and fresh and state in {"running", "paused"} and snapshot.get("bot_ready") is True)
        allowed = [x for x in snapshot.get("available_actions", []) if x in ACTIONS] if ready else []
        messages = {
            "prepared": "Cloud setup is prepared. The game stays on your PC until the handoff.",
            "waiting_for_token": "The cloud host is waiting for its Discord connection setup.",
            "waiting_for_import": "The cloud host is waiting for the verified game save.",
            "standby": "This cloud copy is waiting for the active host.",
            "connecting": "The cloud host is connecting to Discord.",
            "running": "The crew is playing from the cloud. Closing this hub does not stop the game.",
            "paused": "The cloud bot is connected; appearances are paused.",
            "offline": "The cloud host has not reported a recent connection. Controls are unavailable.",
            "error": "The cloud host needs attention. Controls are unavailable.",
        }
        return {"ok": True, "protocol": PROTOCOL, "version": VERSION, "prepared": True,
                "state": state, "bot_ready": ready, "cloud_active": active, "runtime_ready": runtime_ready,
                "application_id": APPLICATION_ID, "guild_id": GUILD_ID, "channel_id": CHANNEL_ID,
                "heartbeat_at": worker["heartbeat_at"] if worker else None,
                "worker_id": worker["worker_id"] if worker else None,
                "activation_generation": config["generation"], "import_digest": config["import_digest"],
                "channel": snapshot.get("channel"), "galaxy": snapshot.get("galaxy"),
                "active_event": snapshot.get("active_event"), "effects": snapshot.get("effects", {}),
                "counts": snapshot.get("counts", {}), "recent_activity": snapshot.get("recent_activity", [])[:20],
                "last_backup": config["last_backup"], "available_actions": allowed, "message": messages[state],
                "error_code": snapshot.get("error_code")}

    def state(self) -> dict:
        with self._connection() as db:
            config = self._configuration(db)
            return self._status(config, self._worker(db, config))

    def _verified_receipt(self, db, digest: str) -> dict:
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ControlConflict("A verified game import is required before activation.")
        try:
            row = db.execute(f'''SELECT * FROM "{self.game_schema}".storage_import_receipts
                WHERE singleton=1 AND sha256=%s AND status='complete' ''', (digest,)).fetchone()
        except psycopg.errors.UndefinedTable:
            raise ControlConflict("Import and verify the saved game before activation.") from None
        if row is None or (row["application_id"], row["guild_id"], row["channel_id"], row["format_version"], row["game_schema_version"]) != (
                APPLICATION_ID, GUILD_ID, CHANNEL_ID, 1, "2"):
            raise ControlConflict("The imported save does not match this FFC game.")
        receipt = json.loads(row["receipt_json"])
        if receipt.get("sha256") != digest:
            raise ControlConflict("The game import receipt is inconsistent.")
        return row

    def mark_import_verified(self, digest: str, summary: dict | None = None) -> dict:
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            if config["cloud_active"]:
                raise ControlConflict("Stop the cloud host before changing its import record.")
            authoritative = self._mark_import(db, digest)
        return authoritative

    def _mark_import(self, db, digest: str) -> dict:
        row = self._verified_receipt(db, digest)
        authoritative = {"sha256": digest, "counts": json.loads(row["counts_json"]), "imported_at": row["imported_at"]}
        _json(authoritative)
        db.execute(f"""UPDATE {self._prefix}configuration SET import_digest=%s,import_summary=%s,
            import_verified_at=%s,updated_at=%s WHERE singleton=1""",
                   (digest, Jsonb(authoritative), self._now(), self._now()))
        return authoritative

    def import_verified(self, operation: Callable[[], dict]) -> dict:
        """Hold the activation row locked across a separately atomic game import.

        The game importer commits its own schema before its receipt is read.
        If recording control verification fails after that commit, an identical
        import retry returns the receipt without replacing any game progress.
        """
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            if config["cloud_active"]:
                raise ControlConflict("The cloud host must be inactive before importing a save.")
            receipt = operation()
            summary = self._mark_import(db, receipt.get("sha256"))
            return {"ok": True, **summary, "already_imported": bool(receipt.get("already_imported"))}

    def handoff_status(self) -> dict:
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            status = self._status(config, self._worker(db, config))
            stopped = not config["cloud_active"] and status["runtime_ready"] and status["state"] == "prepared"
            if stopped:
                # A new dormant worker can report before the previous leader
                # has finished closing Discord. Require that leader's session
                # lock to be free, not merely a recent prepared heartbeat.
                stopped = bool(db.execute("SELECT pg_try_advisory_xact_lock(%s) AS available",
                                          (leader_key(self.game_schema),)).fetchone()["available"])
            return {"protocol": PROTOCOL, "application_id": APPLICATION_ID, "guild_id": GUILD_ID,
                    "channel_id": CHANNEL_ID, "cloud_active": config["cloud_active"],
                    "activation_generation": config["generation"], "import_digest": config["import_digest"],
                    "import_summary": config["import_summary"], "import_verified_at": config["import_verified_at"],
                    "state": status["state"], "runtime_ready": status["runtime_ready"],
                    "bot_ready": status["bot_ready"], "heartbeat_at": status["heartbeat_at"],
                    "stopped_confirmed": stopped}

    def set_active(self, active: bool, import_digest: str | None = None, *, local_host_stopped: bool = False) -> dict:
        if type(active) is not bool:
            raise ControlError("Cloud activation must be explicit.")
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            if active:
                if local_host_stopped is not True:
                    raise ControlConflict("Confirm that the PC host has stopped before activating the cloud.")
                self._verified_receipt(db, import_digest)
                if config["import_digest"] != import_digest or config["import_verified_at"] is None:
                    raise ControlConflict("Complete import verification before activating the cloud.")
            if active != config["cloud_active"]:
                db.execute(f"""UPDATE {self._prefix}configuration SET cloud_active=%s,
                    generation=generation+1,updated_at=%s WHERE singleton=1""", (active, self._now()))
                self._expire(db, self._now(), config["generation"] + 1)
        return self.state()

    def set_last_backup(self, metadata: dict) -> None:
        allowed = {"created_at", "sha256", "size_bytes", "name", "status", "retained_count"}
        if not isinstance(metadata, dict) or set(metadata) - allowed:
            raise ControlError("Backup metadata contains unsupported fields.")
        _json(metadata, 2048)
        with self._connection() as db:
            db.execute(f"UPDATE {self._prefix}configuration SET last_backup=%s WHERE singleton=1", (Jsonb(metadata),))

    def update_heartbeat(self, worker_id: str, state: str, snapshot: dict | None = None) -> None:
        worker_id = _worker_id(worker_id)
        if not isinstance(state, str) or state not in STATES or (snapshot is not None and not isinstance(snapshot, dict)):
            raise ControlError("Invalid cloud status.")
        snapshot = dict(snapshot or {})
        allowed = {"bot_ready", "channel", "galaxy", "active_event", "effects", "counts", "recent_activity", "last_backup", "available_actions", "error_code"}
        if set(snapshot) - allowed:
            raise ControlError("Cloud status contains unsupported fields.")
        if "recent_activity" in snapshot and not isinstance(snapshot["recent_activity"], list):
            raise ControlError("Recent activity must be a list.")
        if "available_actions" in snapshot and (not isinstance(snapshot["available_actions"], list) or any(not isinstance(x, str) or x not in ACTIONS for x in snapshot["available_actions"])):
            raise ControlError("Cloud status has unsupported actions.")
        if snapshot.get("error_code") is not None and (not isinstance(snapshot["error_code"], str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,100}", snapshot["error_code"])):
            raise ControlError("Cloud errors must use a bounded diagnostic code.")
        _json(snapshot)
        with self._connection() as db:
            config = self._configuration(db)
            db.execute(f"""INSERT INTO {self._prefix}workers(worker_id,state,snapshot,heartbeat_at,generation)
                VALUES(%s,%s,%s,%s,%s) ON CONFLICT(worker_id) DO UPDATE SET state=excluded.state,
                snapshot=excluded.snapshot,heartbeat_at=excluded.heartbeat_at,generation=excluded.generation""",
                       (worker_id, state, Jsonb(snapshot), self._now(), config["generation"]))
            db.execute(f"DELETE FROM {self._prefix}workers WHERE heartbeat_at<%s", (self._now() - 86400,))
        if snapshot.get("last_backup") is not None:
            self.set_last_backup(snapshot["last_backup"])

    def issue_session(self, actor: str) -> dict:
        actor = _actor(actor)
        now = self._now()
        token = TOKEN_PREFIX + secrets.token_urlsafe(48)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self._connection() as db:
            self._configuration(db, lock=True)
            count = db.execute(f"SELECT count(*) AS n FROM {self._prefix}sessions WHERE actor=%s AND created_at>%s", (actor, now - 3600)).fetchone()["n"]
            if count >= 10:
                raise ControlRateLimited("Too many hub connections. Try again later.")
            db.execute(f"INSERT INTO {self._prefix}sessions(token_hash,actor,created_at,expires_at) VALUES(%s,%s,%s,%s)",
                       (digest, actor, now, now + SESSION_SECONDS))
            db.execute(f"DELETE FROM {self._prefix}sessions WHERE expires_at<%s", (now - SESSION_SECONDS,))
        return {"access_token": token, "token_type": "Bearer", "expires_at": now + SESSION_SECONDS, "protocol": PROTOCOL}

    @staticmethod
    def _token_hash(token: str) -> str:
        if not isinstance(token, str) or not re.fullmatch(r"ffc1_[A-Za-z0-9_-]{64}", token):
            raise ControlUnauthorized("Connect The Wilds Control Hub again.")
        return hashlib.sha256(token.encode()).hexdigest()

    def validate_session(self, token: str, *, expected_owner: str) -> dict:
        digest = self._token_hash(token)
        with self._connection() as db:
            row = db.execute(f"SELECT actor,expires_at FROM {self._prefix}sessions WHERE token_hash=%s AND revoked_at IS NULL AND expires_at>%s",
                             (digest, self._now())).fetchone()
        if row is None or not expected_owner or row["actor"].casefold() != expected_owner.strip().casefold():
            raise ControlUnauthorized("Connect The Wilds Control Hub again.")
        return row

    def revoke_session(self, token: str) -> None:
        digest = self._token_hash(token)
        with self._connection() as db:
            db.execute(f"UPDATE {self._prefix}sessions SET revoked_at=%s WHERE token_hash=%s AND revoked_at IS NULL", (self._now(), digest))

    def _expire(self, db, now: float, generation: int) -> None:
        p = self._prefix
        db.execute(f"""UPDATE {p}commands SET status='expired',error='Request expired before execution.',finished_at=%s
            WHERE status='queued' AND (expires_at<=%s OR generation<>%s)""", (now, now, generation))
        db.execute(f"""UPDATE {p}commands c SET status='unknown',error='The host stopped reporting before this action was confirmed. It will not be replayed.',finished_at=%s
            WHERE c.status='running' AND (c.started_at<=%s OR c.generation<>%s OR NOT EXISTS
                (SELECT 1 FROM {p}workers w WHERE w.worker_id=c.expected_worker_id AND w.generation=c.generation AND w.heartbeat_at>%s))""",
                   (now, now - RUNNING_SECONDS, generation, now - HEARTBEAT_SECONDS))

    def enqueue(self, request_id: str, action: str, arguments: dict, actor: str) -> dict:
        request_id, actor = _request_id(request_id), _actor(actor)
        arguments = validate_action(action, arguments)
        fingerprint = hashlib.sha256(_json({"action": action, "arguments": arguments}).encode()).hexdigest()
        now = self._now()
        p = self._prefix
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            self._expire(db, now, config["generation"])
            existing = db.execute(f"SELECT * FROM {p}commands WHERE id=%s", (request_id,)).fetchone()
            if existing:
                if existing["actor"].casefold() != actor.casefold() or existing["fingerprint"] != fingerprint:
                    raise ControlConflict("This request ID was already used for a different action.")
                return _command(existing)
            status = self._status(config, self._worker(db, config))
            if not status["bot_ready"] or action not in status["available_actions"]:
                raise ControlConflict("The cloud host is not ready for this action.")
            count = db.execute(f"SELECT count(*) AS n FROM {p}commands WHERE actor=%s AND created_at>%s", (actor, now - 60)).fetchone()["n"]
            if count >= 30:
                raise ControlRateLimited("Please give the crew a moment before sending more controls.")
            row = db.execute(f"""INSERT INTO {p}commands(id,actor,fingerprint,action,arguments,status,generation,expected_worker_id,created_at,expires_at)
                VALUES(%s,%s,%s,%s,%s,'queued',%s,%s,%s,%s) RETURNING *""",
                             (request_id, actor, fingerprint, action, Jsonb(arguments), config["generation"], status["worker_id"], now, now + COMMAND_SECONDS)).fetchone()
            return _command(row)

    def get_command(self, request_id: str, actor: str) -> dict:
        request_id, actor = _request_id(request_id), _actor(actor)
        with self._connection() as db:
            config = self._configuration(db)
            self._expire(db, self._now(), config["generation"])
            row = db.execute(f"SELECT * FROM {self._prefix}commands WHERE id=%s AND lower(actor)=lower(%s)", (request_id, actor)).fetchone()
            return _command(row)

    def claim_next(self, worker_id: str) -> dict | None:
        worker_id = _worker_id(worker_id)
        now = self._now()
        p = self._prefix
        with self._connection() as db:
            config = self._configuration(db, lock=True)
            self._expire(db, now, config["generation"])
            status = self._status(config, self._worker(db, config))
            if not status["bot_ready"] or status["worker_id"] != worker_id:
                return None
            row = db.execute(f"""SELECT * FROM {p}commands WHERE status='queued' AND generation=%s
                AND expected_worker_id=%s AND expires_at>%s ORDER BY created_at,id FOR UPDATE SKIP LOCKED LIMIT 1""",
                             (config["generation"], worker_id, now)).fetchone()
            if row is None:
                return None
            row = db.execute(f"UPDATE {p}commands SET status='running',started_at=%s WHERE id=%s AND status='queued' RETURNING *", (now, row["id"])).fetchone()
            return _command(row)

    def complete(self, command_id: str, worker_id: str, result: dict | None = None, error: str | None = None,
                 *, unknown: bool = False) -> bool:
        command_id, worker_id = _request_id(command_id), _worker_id(worker_id)
        if result is not None:
            if not isinstance(result, dict):
                raise ControlError("Action result must be an object.")
            _json(result)
        if error is not None:
            if not isinstance(error, str) or not re.fullmatch(r"[A-Za-z0-9_ .,:;!?()/-]{1,200}", error):
                error = "Action failed. Check the cloud host status."
        with self._connection() as db:
            config = self._configuration(db)
            self._expire(db, self._now(), config["generation"])
            changed = db.execute(f"""UPDATE {self._prefix}commands SET status=%s,result=%s,error=%s,finished_at=%s
                WHERE id=%s AND expected_worker_id=%s AND generation=%s AND status='running'""",
                                  ("unknown" if unknown else ("failed" if error else "done"), Jsonb(result) if result is not None else None,
                                  error, self._now(), command_id, worker_id, config["generation"])).rowcount
            return changed == 1

    def mark_unknown(self, command_id: str, worker_id: str, error: str | None = None) -> bool:
        return self.complete(command_id, worker_id, error=(error or "The action could not be confirmed. It will not be replayed."), unknown=True)
