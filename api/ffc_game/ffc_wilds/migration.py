"""Bounded, verifiable game-save transfer between SQLite and PostgreSQL.

Only the twenty-one FFC game tables are transferred. Cloud control sessions,
credentials, Wonder Codex tables, and arbitrary SQL are never part of a save.
Import is a separate operation from activating a Discord host.
"""
from __future__ import annotations

import argparse
from functools import lru_cache
import gzip
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import tempfile
import time

from .config import CATALOG_PATH, snowflake
from .engine import GameEngine
from .tips import TipSchedule


FORMAT = "ffc-wilds-save"
FORMAT_VERSION = 1
APPLICATION_ID = "1565167975248695456"
MAX_SNAPSHOT_BYTES = 20 * 1024 * 1024
MAX_ROWS = 250_000
MAX_CELL_TEXT = 2 * 1024 * 1024
TABLES = (
    "metadata", "channels", "profiles", "inventory", "discoveries", "boosts",
    "events", "claims", "requests", "activity_channels", "activity_weeks",
    "activity_missions", "activity_mission_progress", "activity_claims",
    "activity_notices", "warp_accounts", "galaxy_journeys", "warp_history",
    "player_achievements", "channel_tips", "channel_interludes",
)
REQUIRED_VERSIONS = {"schema_version": "2", "warp_progression_version": "1", "honours_version": "1"}


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _digest(payload: dict) -> str:
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def _finite_number(value) -> bool:
    try:
        return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        return False


@lru_cache(maxsize=1)
def _reference_schema() -> dict:
    """Derive trusted column metadata from this release, never an uploaded SQL file."""
    with GameEngine(":memory:", CATALOG_PATH) as reference:
        TipSchedule(reference)
        result = {}
        for table in TABLES:
            result[table] = [dict(row) for row in reference.db.execute(f"PRAGMA table_info({table})")]
        return result


def _table_names(db, backend: str) -> set[str]:
    if backend == "postgresql":
        rows = db.raw.execute("""SELECT table_name FROM information_schema.tables
            WHERE table_schema=%s AND table_type='BASE TABLE'""", (db.schema,)).fetchall()
    else:
        rows = db.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


def _columns(table: str) -> list[str]:
    return [column["name"] for column in _reference_schema()[table]]


def _normalize_rows(table: str, rows: list) -> list[list]:
    schema = _reference_schema()[table]
    result = []
    for values in rows:
        if not isinstance(values, (list, tuple)) or len(values) != len(schema):
            raise ValueError(f"Invalid row shape in {table}.")
        row = []
        for column, value in zip(schema, values):
            label = f"{table}.{column['name']}"
            if value is None:
                if column["notnull"] or column["pk"]:
                    raise ValueError(f"Missing required value in {label}.")
            elif column["type"] == "TEXT":
                if not isinstance(value, str) or len(value.encode("utf-8")) > MAX_CELL_TEXT or "\x00" in value:
                    raise ValueError(f"Invalid text value in {label}.")
            elif column["type"] == "INTEGER":
                if isinstance(value, bool) or not isinstance(value, int) or not -(2**63) <= value < 2**63:
                    raise ValueError(f"Invalid integer value in {label}.")
            elif column["type"] == "REAL":
                if not _finite_number(value):
                    raise ValueError(f"Invalid timestamp value in {label}.")
                value = float(value)
            else:
                raise ValueError("Unrecognized game column type.")
            row.append(value)
        result.append(row)
    primary = [index for _, index in sorted((column["pk"], index) for index, column in enumerate(schema) if column["pk"])]
    result.sort(key=lambda row: tuple(row[index] for index in primary))
    seen = set()
    for row in result:
        key = tuple(row[index] for index in primary)
        if key in seen:
            raise ValueError(f"Duplicate primary key in {table}.")
        seen.add(key)
    return result


def _read_tables(db, backend: str) -> dict:
    names = _table_names(db, backend)
    unknown = names - set(TABLES) - {"sqlite_sequence", "storage_import_receipts"}
    if unknown:
        raise ValueError("The save contains unrecognized game tables; update the migration tool before continuing.")
    missing = set(TABLES) - names
    if missing - {"channel_tips", "channel_interludes"}:
        raise ValueError("The save is missing required game tables.")
    tables, total = {}, 0
    for table in TABLES:
        columns = _columns(table)
        if table in missing:
            rows = []
        else:
            present = {row[1] for row in db.execute(f"PRAGMA table_info({table})")}
            if present != set(columns):
                raise ValueError(f"The save schema for {table} does not match this release.")
            # Stop before materializing an unbounded table from an old save.
            cursor = db.execute(f"SELECT {','.join(columns)} FROM {table}")
            raw = []
            for row in cursor:
                raw.append(row)
                if total + len(raw) > MAX_ROWS:
                    raise ValueError("The game save exceeds the supported transfer row limit.")
            total += len(raw)
            if total > MAX_ROWS:
                raise ValueError("The game save exceeds the supported transfer row limit.")
            rows = _normalize_rows(table, [list(row) for row in raw])
        tables[table] = {"columns": columns, "rows": rows}
    return tables


def _sequence(db, backend: str) -> int:
    if backend == "postgresql":
        last, called = db.raw.execute("SELECT last_value,is_called FROM warp_history_id_seq").fetchone()
        return int(last if called else last - 1)
    row = db.execute("SELECT seq FROM sqlite_sequence WHERE name='warp_history'").fetchone()
    return int(row[0]) if row else 0


def _identity(tables, application_id, expected_guild_id, expected_channel_id):
    channels = tables["channels"]
    if len(channels["rows"]) != 1:
        raise ValueError("An FFC cloud handoff requires exactly one configured game channel.")
    row = dict(zip(channels["columns"], channels["rows"][0]))
    guild, channel = row["guild_id"], row["channel_id"]
    if expected_guild_id is not None and guild != str(expected_guild_id):
        raise ValueError("This save belongs to a different Discord server.")
    if expected_channel_id is not None and channel != str(expected_channel_id):
        raise ValueError("This save belongs to a different Discord channel.")
    if not isinstance(application_id, str):
        raise ValueError("A valid bot application ID is required for the handoff.")
    snowflake(application_id, "Application ID")
    for table, data in tables.items():
        columns = data["columns"]
        for label, expected in (("guild_id", guild), ("channel_id", channel)):
            if label in columns:
                index = columns.index(label)
                if any(values[index] != expected for values in data["rows"]):
                    raise ValueError(f"The save contains a different Discord location in {table}.")
    return application_id, guild, channel


def _payload(db, backend, *, application_id, expected_guild_id, expected_channel_id):
    tables = _read_tables(db, backend)
    application, guild, channel = _identity(tables, application_id, expected_guild_id, expected_channel_id)
    metadata = dict(tables["metadata"]["rows"])
    if any(metadata.get(key) != version for key, version in REQUIRED_VERSIONS.items()):
        raise ValueError("The source needs the current FFC game migrations before transfer.")
    return {"format": FORMAT, "version": FORMAT_VERSION, "application_id": application,
            "guild_id": guild, "channel_id": channel, "game_schema_version": "2",
            "tables": tables, "sequences": {"warp_history": _sequence(db, backend)}}


def _envelope(payload, receipt=None):
    snapshot = {"payload": payload, "sha256": _digest(payload), "exported_at": time.time(),
                "import_receipt": receipt}
    if len(_json(snapshot).encode("utf-8")) > MAX_SNAPSHOT_BYTES:
        raise ValueError("The game save exceeds the supported transfer size.")
    return snapshot


def export_snapshot(engine: GameEngine, *, application_id: str = APPLICATION_ID,
                    expected_guild_id: str | None = None,
                    expected_channel_id: str | None = None) -> dict:
    """Return a consistent canonical JSON-ready snapshot, including a prior receipt."""
    with engine._transaction() as db:
        payload = _payload(db, engine.backend, application_id=application_id,
                           expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)
        receipt = _receipt_from_db(db, engine.backend)
        return _envelope(payload, receipt)


def snapshot_from_sqlite(source: str | Path, *, application_id: str = APPLICATION_ID,
                         expected_guild_id: str | None = None,
                         expected_channel_id: str | None = None) -> dict:
    """Read an existing save without creating files or running source schema SQL."""
    path = Path(source).resolve()
    if not path.is_file():
        raise ValueError("The source SQLite save does not exist.")
    db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, isolation_level=None)
    db.row_factory = sqlite3.Row
    try:
        db.execute("PRAGMA query_only=ON")
        db.execute("PRAGMA trusted_schema=OFF")
        db.execute("BEGIN")
        if db.execute("PRAGMA quick_check").fetchone()[0] != "ok" or db.execute("PRAGMA foreign_key_check").fetchone():
            raise ValueError("The source SQLite save failed its integrity checks.")
        for row in db.execute("SELECT name,type,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'"):
            if row["type"] == "view" or (row["type"] == "table" and not re.match(r"\s*CREATE\s+TABLE\b", row["sql"] or "", re.I)):
                raise ValueError("The source save contains unsupported views or virtual tables.")
        payload = _payload(db, "sqlite", application_id=application_id,
                           expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)
        return _envelope(payload, _receipt_from_db(db, "sqlite"))
    except sqlite3.Error:
        raise ValueError("The source SQLite save could not be read safely.") from None
    finally:
        db.rollback()
        db.close()


def validate_snapshot(snapshot, *, expected_application_id: str = APPLICATION_ID,
                      expected_guild_id: str | None = None,
                      expected_channel_id: str | None = None) -> dict:
    if isinstance(snapshot, bytes):
        if len(snapshot) > MAX_SNAPSHOT_BYTES:
            raise ValueError("The game save exceeds the supported transfer size.")
        try:
            snapshot = snapshot.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("The save is not valid UTF-8 JSON.") from None
    if isinstance(snapshot, dict):
        try:
            # Also detach validated data from a caller's mutable dictionary.
            snapshot = _json(snapshot)
        except (TypeError, ValueError, OverflowError, RecursionError):
            raise ValueError("The save is not a valid JSON snapshot.") from None
    if isinstance(snapshot, str):
        if len(snapshot.encode("utf-8")) > MAX_SNAPSHOT_BYTES:
            raise ValueError("The game save exceeds the supported transfer size.")
        try:
            snapshot = json.loads(snapshot, parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Invalid JSON number.")))
        except (json.JSONDecodeError, RecursionError):
            raise ValueError("The save is not a valid JSON snapshot.") from None
    if not isinstance(snapshot, dict) or set(snapshot) != {"payload", "sha256", "exported_at", "import_receipt"}:
        raise ValueError("Invalid FFC snapshot envelope.")
    exported = snapshot["exported_at"]
    if not _finite_number(exported):
        raise ValueError("Invalid snapshot export time.")
    payload = snapshot["payload"]
    fields = {"format", "version", "application_id", "guild_id", "channel_id", "game_schema_version", "tables", "sequences"}
    if (not isinstance(payload, dict) or set(payload) != fields or payload["format"] != FORMAT
            or type(payload["version"]) is not int or payload["version"] != 1
            or payload["game_schema_version"] != "2"):
        raise ValueError("Unsupported FFC snapshot format.")
    if payload["application_id"] != expected_application_id:
        raise ValueError("This snapshot belongs to a different bot application.")
    tables = payload["tables"]
    if not isinstance(tables, dict) or set(tables) != set(TABLES):
        raise ValueError("The snapshot must contain exactly the FFC game tables.")
    total = 0
    for table in TABLES:
        data = tables[table]
        if not isinstance(data, dict) or set(data) != {"columns", "rows"} or data["columns"] != _columns(table) or not isinstance(data["rows"], list):
            raise ValueError(f"Invalid table definition for {table}.")
        total += len(data["rows"])
        if total > MAX_ROWS:
            raise ValueError("The game save exceeds the supported transfer row limit.")
        if _json(_normalize_rows(table, data["rows"])) != _json(data["rows"]):
            raise ValueError(f"The table {table} is not in canonical order.")
    application, guild, channel = _identity(tables, expected_application_id, expected_guild_id, expected_channel_id)
    if (payload["application_id"], payload["guild_id"], payload["channel_id"]) != (application, guild, channel):
        raise ValueError("The snapshot identity does not match its game records.")
    metadata = dict(tables["metadata"]["rows"])
    if any(metadata.get(key) != value for key, value in REQUIRED_VERSIONS.items()):
        raise ValueError("The snapshot has incompatible game schema versions.")
    sequences = payload["sequences"]
    if not isinstance(sequences, dict) or set(sequences) != {"warp_history"}:
        raise ValueError("Invalid game sequence state.")
    sequence = sequences["warp_history"]
    if isinstance(sequence, bool) or not isinstance(sequence, int) or not 0 <= sequence < 2**63 - 1:
        raise ValueError("Invalid Warp history sequence.")
    if any(row[0] > sequence or row[0] <= 0 for row in tables["warp_history"]["rows"]):
        raise ValueError("The Warp history sequence would reuse an existing record ID.")
    digest = snapshot["sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest) or not hmac.compare_digest(digest, _digest(payload)):
        raise ValueError("The game snapshot checksum does not match its contents.")
    if snapshot["import_receipt"] is not None:
        receipt = _validate_receipt(snapshot["import_receipt"])
        if any(receipt[key] != payload[key] for key in ("application_id", "guild_id", "channel_id")):
            raise ValueError("The backup import receipt belongs to a different game.")
    return snapshot


def _create_receipts(db):
    db.execute("""CREATE TABLE IF NOT EXISTS storage_import_receipts (
        singleton INTEGER PRIMARY KEY CHECK(singleton=1), sha256 TEXT UNIQUE NOT NULL,
        format_version INTEGER NOT NULL, game_schema_version TEXT NOT NULL,
        application_id TEXT NOT NULL, guild_id TEXT NOT NULL, channel_id TEXT NOT NULL,
        imported_at REAL NOT NULL, status TEXT NOT NULL CHECK(status='complete'),
        counts_json TEXT NOT NULL, receipt_json TEXT NOT NULL)""")


def _validate_receipt(receipt):
    fields = {"sha256", "format_version", "game_schema_version", "application_id", "guild_id",
              "channel_id", "imported_at", "status", "counts"}
    try:
        if (not isinstance(receipt, dict) or set(receipt) != fields
                or type(receipt["format_version"]) is not int or receipt["format_version"] != 1
                or receipt["game_schema_version"] != "2" or receipt["status"] != "complete"
                or not isinstance(receipt["sha256"], str) or not re.fullmatch(r"[a-f0-9]{64}", receipt["sha256"])
                or not all(isinstance(receipt[key], str) and receipt[key] for key in ("application_id", "guild_id", "channel_id"))
                or not _finite_number(receipt["imported_at"])
                or not isinstance(receipt["counts"], dict) or set(receipt["counts"]) != set(TABLES)
                or any(type(value) is not int or value < 0 for value in receipt["counts"].values())
                or sum(receipt["counts"].values()) > MAX_ROWS):
            raise ValueError()
        snowflake(receipt["application_id"], "Application ID")
        return receipt
    except (KeyError, TypeError, ValueError):
        raise ValueError("The game import receipt failed validation.") from None


def _receipt_from_db(db, backend):
    if "storage_import_receipts" not in _table_names(db, backend):
        return None
    rows = db.execute("SELECT * FROM storage_import_receipts").fetchall()
    if not rows:
        return None
    if len(rows) != 1:
        raise ValueError("The game import receipt is ambiguous.")
    row = dict(rows[0])
    try:
        receipt = _validate_receipt(json.loads(row["receipt_json"]))
        counts = json.loads(row["counts_json"])
        if (row["singleton"] != 1 or row["status"] != "complete" or row["format_version"] != 1
                or row["game_schema_version"] != "2" or not re.fullmatch(r"[a-f0-9]{64}", row["sha256"])
                or set(counts) != set(TABLES)
                or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in counts.values())):
            raise ValueError()
        expected = {key: row[key] for key in ("sha256", "format_version", "game_schema_version", "application_id", "guild_id", "channel_id", "imported_at", "status")}
        if receipt != {**expected, "counts": counts}:
            raise ValueError()
        return receipt
    except (ValueError, TypeError, KeyError):
        raise ValueError("The game import receipt failed validation.") from None


def get_import_receipt(engine: GameEngine) -> dict | None:
    with engine._lock:
        return _receipt_from_db(engine.db, engine.backend)


def _assert_empty(db):
    for table in TABLES:
        if table != "metadata" and db.execute(f"SELECT 1 FROM {table} LIMIT 1").fetchone():
            raise ValueError("The target already contains game data; it was not overwritten.")
    metadata = dict(db.execute("SELECT key,value FROM metadata").fetchall())
    if metadata != REQUIRED_VERSIONS:
        raise ValueError("The target contains non-default metadata; it was not overwritten.")


def _reset_sequence(engine, sequence):
    db = engine.db
    if engine.backend == "postgresql":
        # ALTER SEQUENCE RESTART is transactional, unlike setval().
        db.execute(f'ALTER SEQUENCE "{db.schema}"."warp_history_id_seq" RESTART WITH {sequence + 1}')
    else:
        if db.execute("SELECT 1 FROM sqlite_sequence WHERE name='warp_history'").fetchone():
            db.execute("UPDATE sqlite_sequence SET seq=? WHERE name='warp_history'", (sequence,))
        else:
            db.execute("INSERT INTO sqlite_sequence(name,seq) VALUES('warp_history',?)", (sequence,))


def _load_payload(engine, payload):
    db = engine.db
    db.execute("DELETE FROM metadata")
    for table in TABLES:
        data = payload["tables"][table]
        sql = f"INSERT INTO {table}({','.join(data['columns'])}) VALUES({','.join('?' for _ in data['columns'])})"
        db.executemany(sql, data["rows"])
    _reset_sequence(engine, payload["sequences"]["warp_history"])
    actual = _payload(db, engine.backend, application_id=payload["application_id"],
                      expected_guild_id=payload["guild_id"], expected_channel_id=payload["channel_id"])
    if actual != payload or not hmac.compare_digest(_digest(actual), _digest(payload)):
        raise ValueError("The imported save did not match its source; the transaction was rolled back.")


def import_snapshot(snapshot, target_engine: GameEngine, *,
                    expected_application_id: str = APPLICATION_ID,
                    expected_guild_id: str | None = None,
                    expected_channel_id: str | None = None) -> dict:
    """Import into an empty PostgreSQL game schema, or safely recognize a replay."""
    if target_engine.backend != "postgresql":
        raise ValueError("A cloud handoff requires the PostgreSQL game backend.")
    snapshot = validate_snapshot(snapshot, expected_application_id=expected_application_id,
                                 expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)
    payload = snapshot["payload"]
    TipSchedule(target_engine)
    with target_engine._transaction() as db:
        _create_receipts(db)
        existing = _receipt_from_db(db, target_engine.backend)
        if existing:
            if existing["sha256"] == snapshot["sha256"] and all(existing[key] == payload[key] for key in ("application_id", "guild_id", "channel_id")):
                return {**existing, "already_imported": True}
            raise ValueError("This target has already completed a different handoff; no progress was overwritten.")
        _assert_empty(db)
        _load_payload(target_engine, payload)
        receipt = {"sha256": snapshot["sha256"], "format_version": 1, "game_schema_version": "2",
                   "application_id": payload["application_id"], "guild_id": payload["guild_id"],
                   "channel_id": payload["channel_id"], "imported_at": time.time(), "status": "complete",
                   "counts": {table: len(payload["tables"][table]["rows"]) for table in TABLES}}
        db.execute("""INSERT INTO storage_import_receipts(singleton,sha256,format_version,game_schema_version,
            application_id,guild_id,channel_id,imported_at,status,counts_json,receipt_json)
            VALUES(1,?,?,?,?,?,?,?,?,?,?)""", (receipt["sha256"], 1, "2", receipt["application_id"],
            receipt["guild_id"], receipt["channel_id"], receipt["imported_at"], "complete",
            _json(receipt["counts"]), _json(receipt)))
    return {**receipt, "already_imported": False}


def import_sqlite(source: str | Path, target_engine: GameEngine, *,
                  application_id: str = APPLICATION_ID,
                  expected_guild_id: str | None = None,
                  expected_channel_id: str | None = None) -> dict:
    snapshot = snapshot_from_sqlite(source, application_id=application_id,
                                    expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)
    return import_snapshot(snapshot, target_engine, expected_application_id=application_id,
                           expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)


def restore_sqlite(snapshot, destination: str | Path, *, catalog_path=CATALOG_PATH) -> str:
    """Create a verified portable rollback save without replacing an existing file."""
    snapshot = validate_snapshot(snapshot)
    destination = Path(destination).resolve()
    if destination.exists():
        raise ValueError("The backup destination already exists; choose a new filename.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".ffc-restore-", suffix=".sqlite", dir=destination.parent)
    os.close(descriptor)
    try:
        with GameEngine(temporary, catalog_path) as target:
            TipSchedule(target)
            with target._transaction() as db:
                _assert_empty(db)
                _load_payload(target, snapshot["payload"])
                receipt = snapshot.get("import_receipt")
                if receipt:
                    _create_receipts(db)
                    db.execute("""INSERT INTO storage_import_receipts(singleton,sha256,format_version,game_schema_version,
                        application_id,guild_id,channel_id,imported_at,status,counts_json,receipt_json)
                        VALUES(1,?,?,?,?,?,?,?,?,?,?)""", (receipt["sha256"], receipt["format_version"],
                        receipt["game_schema_version"], receipt["application_id"], receipt["guild_id"],
                        receipt["channel_id"], receipt["imported_at"], receipt["status"], _json(receipt["counts"]), _json(receipt)))
                    _receipt_from_db(db, "sqlite")
            if target.db.execute("PRAGMA integrity_check").fetchone()[0] != "ok" or target.db.execute("PRAGMA foreign_key_check").fetchone():
                raise ValueError("The rollback save failed integrity verification.")
        # The final SQLite close checkpoints its WAL before installing the file.
        os.chmod(temporary, 0o600)
        # A caller racing another backup must not replace that other result.
        os.link(temporary, destination)
        return str(destination)
    finally:
        for suffix in ("", "-wal", "-shm"):
            Path(temporary + suffix).unlink(missing_ok=True)


def export_sqlite(engine: GameEngine, destination: str | Path) -> str:
    return restore_sqlite(export_snapshot(engine), destination, catalog_path=engine.catalog)


def write_snapshot(snapshot: dict, destination: str | Path) -> str:
    snapshot = validate_snapshot(snapshot)
    path = Path(destination).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(_json(snapshot) + "\n")
    return str(path)


def load_snapshot(source: str | Path, *, expected_application_id: str = APPLICATION_ID,
                  expected_guild_id: str | None = None,
                  expected_channel_id: str | None = None) -> dict:
    """Read plain JSON or a downloaded gzip backup with a decompressed bound."""
    try:
        with Path(source).open("rb") as handle:
            compressed = handle.read(2) == b"\x1f\x8b"
            handle.seek(0)
            if compressed:
                with gzip.GzipFile(fileobj=handle, mode="rb") as stream:
                    data = stream.read(MAX_SNAPSHOT_BYTES + 1)
            else:
                data = handle.read(MAX_SNAPSHOT_BYTES + 1)
    except (OSError, EOFError):
        raise ValueError("The backup file could not be read as complete JSON or gzip.") from None
    return validate_snapshot(data, expected_application_id=expected_application_id,
                             expected_guild_id=expected_guild_id, expected_channel_id=expected_channel_id)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepare and verify an FFC cloud save; this never starts the Discord bot.")
    parser.add_argument("operation", choices=("export", "import", "verify", "restore"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--schema", default="ffc_wilds")
    parser.add_argument("--application-id", default=APPLICATION_ID)
    parser.add_argument("--guild-id")
    parser.add_argument("--channel-id")
    args = parser.parse_args()
    try:
        if args.operation in {"export", "import", "restore"} and args.source is None:
            raise ValueError("Supply --source.")
        if args.operation in {"export", "restore"} and args.destination is None:
            raise ValueError("Supply --destination.")
        if args.operation == "export":
            snapshot = snapshot_from_sqlite(args.source, application_id=args.application_id,
                                            expected_guild_id=args.guild_id, expected_channel_id=args.channel_id)
            write_snapshot(snapshot, args.destination)
            print(_json({"ok": True, "sha256": snapshot["sha256"], "path": str(args.destination),
                         "counts": {table: len(snapshot["payload"]["tables"][table]["rows"]) for table in TABLES}}))
        elif args.operation == "restore":
            snapshot = load_snapshot(args.source, expected_application_id=args.application_id,
                                     expected_guild_id=args.guild_id, expected_channel_id=args.channel_id)
            print(_json({"ok": True, "path": restore_sqlite(snapshot, args.destination)}))
        else:
            database_url = os.environ.get("FFC_DATABASE_URL") or os.environ.get("DATABASE_URL")
            if not database_url:
                raise ValueError("Supply FFC_DATABASE_URL in the private process environment.")
            with GameEngine(database_url, CATALOG_PATH, schema=args.schema) as target:
                if args.operation == "verify":
                    receipt = get_import_receipt(target)
                    print(_json({"ok": bool(receipt), "receipt": receipt}))
                else:
                    snapshot = (load_snapshot(args.source, expected_application_id=args.application_id,
                                               expected_guild_id=args.guild_id, expected_channel_id=args.channel_id)
                                if args.source.suffix.casefold() in {".json", ".gz", ".gzip"} else
                                snapshot_from_sqlite(args.source, application_id=args.application_id,
                                                     expected_guild_id=args.guild_id, expected_channel_id=args.channel_id))
                    print(_json(import_snapshot(snapshot, target, expected_application_id=args.application_id,
                                                expected_guild_id=args.guild_id, expected_channel_id=args.channel_id)))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(_json({"ok": False, "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
