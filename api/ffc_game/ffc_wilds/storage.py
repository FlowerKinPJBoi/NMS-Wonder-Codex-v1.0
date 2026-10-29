"""Small PostgreSQL backend for the game's existing parameterized SQL.

The game continues to support native sqlite3 connections. This adapter handles
only the SQLite constructs used by FFC: qmark parameters, INSERT OR IGNORE,
scalar MIN, schema introspection, and its integer/REAL declarations. It never
opens the public schema, reconnects silently, or exposes a database URL in an
exception. Every write transaction takes a schema-scoped advisory lock, keeping
the original BEGIN IMMEDIATE ordering across separate worker connections.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
import re
from typing import Any, Iterable, Iterator


class StorageError(RuntimeError):
    pass


def is_postgres(value: str) -> bool:
    return value.startswith(("postgresql://", "postgres://", "postgresql+psycopg://"))


def normalize_database_url(value: str) -> str:
    if not isinstance(value, str) or not is_postgres(value):
        raise ValueError("A PostgreSQL database URL is required.")
    if value.startswith("postgresql+psycopg://"):
        return "postgresql://" + value[len("postgresql+psycopg://"):]
    if value.startswith("postgres://"):
        return "postgresql://" + value[len("postgres://"):]
    return value


def validate_game_schema(value: str) -> str:
    if (not isinstance(value, str) or len(value) > 63
            or not re.fullmatch(r"ffc_wilds(?:_[a-z0-9_]+)?", value)
            or value.startswith("ffc_wilds_control")):
        raise ValueError("Use the dedicated FFC game schema or an isolated FFC test schema.")
    return value


def advisory_key(purpose: str, schema: str) -> int:
    return int.from_bytes(hashlib.sha256(f"ffc-wilds:{purpose}:{schema}".encode()).digest()[:8], "big", signed=True)


def _pieces(statement: str) -> Iterator[tuple[str, bool]]:
    """Yield unquoted SQL and protected literals/comments without rewriting them."""
    pattern = re.compile(r"'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|--[^\n]*|/\*[\s\S]*?\*/")
    offset = 0
    for match in pattern.finditer(statement):
        if match.start() > offset:
            yield statement[offset:match.start()], False
        yield match.group(), True
        offset = match.end()
    if offset < len(statement):
        yield statement[offset:], False


def split_statements(script: str) -> list[str]:
    result, current = [], ""
    for part, protected in _pieces(script):
        if protected:
            current += part
            continue
        parts = part.split(";")
        current += parts[0]
        for piece in parts[1:]:
            if current.strip():
                result.append(current.strip())
            current = piece
    if current.strip():
        result.append(current.strip())
    return result


def postgres_sql(statement: str, *, parameters: bool = False) -> str:
    """Translate known syntax while leaving quoted values and comments intact."""
    statement = statement.strip().rstrip(";").rstrip()
    ignore = bool(re.match(r"INSERT\s+OR\s+IGNORE\b", statement, re.I))
    if ignore:
        statement = re.sub(r"^INSERT\s+OR\s+IGNORE\b", "INSERT", statement, count=1, flags=re.I)
    ddl = bool(re.match(r"(?:CREATE|ALTER)\b", statement, re.I))
    translated = []
    for part, protected in _pieces(statement):
        if not protected:
            if ddl:
                part = re.sub(r"\bINTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b", "BIGSERIAL PRIMARY KEY", part, flags=re.I)
                part = re.sub(r"\bINTEGER\b", "BIGINT", part, flags=re.I)
                part = re.sub(r"\bREAL\b", "DOUBLE PRECISION", part, flags=re.I)
            # These are scalar two-argument expressions, not aggregate MIN().
            part = re.sub(r"\bMIN\(\s*(catches|next_spawn_at)\s*,", r"LEAST(\1,", part, flags=re.I)
        if parameters:
            part = part.replace("%", "%%")
        if not protected:
            part = part.replace("?", "%s")
        translated.append(part)
    result = "".join(translated)
    if ignore:
        result += " ON CONFLICT DO NOTHING"
    return result


def _value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


class Row:
    """sqlite3.Row-compatible named/indexed access, including dict(row)."""
    __slots__ = ("_names", "_values", "_indices")

    def __init__(self, names: Iterable[str], values: Iterable[Any]):
        self._names = tuple(names)
        self._values = tuple(_value(value) for value in values)
        self._indices = {name: index for index, name in reversed(tuple(enumerate(self._names)))}

    def __getitem__(self, key):
        return self._values[self._indices[key] if isinstance(key, str) else key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._names)


class Cursor:
    def __init__(self, raw):
        self.raw = raw
        self._names = tuple(column.name for column in (raw.description or ()))

    @property
    def rowcount(self):
        return self.raw.rowcount

    @property
    def description(self):
        return self.raw.description

    def fetchone(self):
        value = self.raw.fetchone()
        return None if value is None else Row(self._names, value)

    def fetchall(self):
        return [Row(self._names, value) for value in self.raw.fetchall()]

    def __iter__(self):
        for value in self.raw:
            yield Row(self._names, value)


class MemoryCursor:
    def __init__(self, rows):
        self.rows = list(rows)
        self.rowcount = len(self.rows)
        self.offset = 0

    def fetchone(self):
        if self.offset >= len(self.rows):
            return None
        value = self.rows[self.offset]
        self.offset += 1
        return value

    def fetchall(self):
        values = self.rows[self.offset:]
        self.offset = len(self.rows)
        return values

    def __iter__(self):
        while (value := self.fetchone()) is not None:
            yield value


class PostgresConnection:
    backend = "postgresql"

    def __init__(self, database_url: str, *, schema: str = "ffc_wilds"):
        self.schema = validate_game_schema(schema)
        try:
            import psycopg
            from psycopg import sql
        except ImportError:
            raise StorageError("Install the pinned PostgreSQL dependency for cloud hosting.") from None
        self._psycopg = psycopg
        self._write_key = advisory_key("write", self.schema)
        self._held_leader_keys: set[int] = set()
        self.raw = None
        try:
            self.raw = psycopg.connect(normalize_database_url(database_url), autocommit=True,
                                       connect_timeout=10, application_name="ffc-wilds")
            self.raw.execute("SET lock_timeout = '10s'")
            self.raw.execute("SET statement_timeout = '30s'")
            self.raw.execute("SET idle_in_transaction_session_timeout = '60s'")
            # Serialize schema creation too; IF NOT EXISTS alone does not make
            # simultaneous PostgreSQL DDL safe.
            with self.raw.transaction():
                self.raw.execute("SELECT pg_catalog.pg_advisory_xact_lock(%s)", (self._write_key,))
                self.raw.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(self.schema)))
            self.raw.execute(sql.SQL("SET search_path TO {}, pg_catalog").format(sql.Identifier(self.schema)))
        except Exception:
            if self.raw is not None:
                self.raw.close()
            raise StorageError("The dedicated PostgreSQL game storage could not be opened.") from None

    @property
    def closed(self) -> bool:
        return self.raw is None or self.raw.closed

    def _run(self, statement, parameters=None):
        try:
            return self.raw.execute(statement, parameters)
        except self._psycopg.Error as exc:
            state = exc.sqlstate or "connection"
            raise StorageError(f"PostgreSQL game storage operation failed ({state}).") from None

    def execute(self, statement: str, parameters=None):
        if not isinstance(statement, str):
            raise TypeError("Game SQL must be a string.")
        if re.fullmatch(r"\s*BEGIN\s+IMMEDIATE\s*;?\s*", statement, re.I):
            if self.raw.info.transaction_status != self._psycopg.pq.TransactionStatus.IDLE:
                raise StorageError("A game transaction is already open.")
            self._run("BEGIN")
            try:
                return Cursor(self._run("SELECT pg_catalog.pg_advisory_xact_lock(%s)", (self._write_key,)))
            except BaseException:
                self.raw.rollback()
                raise
        pragma = re.fullmatch(r"\s*PRAGMA\s+table_info\(([a-z_][a-z_0-9]*)\)\s*;?\s*", statement, re.I)
        if pragma:
            columns = self._run("""SELECT column_name,data_type,is_nullable,column_default
                FROM information_schema.columns WHERE table_schema=%s AND table_name=%s
                ORDER BY ordinal_position""", (self.schema, pragma[1])).fetchall()
            names = ("cid", "name", "type", "notnull", "dflt_value", "pk")
            return MemoryCursor(Row(names, (index, col[0], col[1], int(col[2] == "NO"), col[3], 0))
                                for index, col in enumerate(columns))
        if re.match(r"\s*PRAGMA\b", statement, re.I):
            raise StorageError("That SQLite-only operation is not available on the cloud backend.")
        if parameters is not None:
            parameters = tuple(int(value) if isinstance(value, bool) else value for value in parameters)
        return Cursor(self._run(postgres_sql(statement, parameters=parameters is not None), parameters))

    def executemany(self, statement: str, rows):
        cursor = None
        for values in rows:
            cursor = self.execute(statement, values)
        return cursor or MemoryCursor([])

    def executescript(self, script: str):
        own_transaction = self.raw.info.transaction_status == self._psycopg.pq.TransactionStatus.IDLE
        if own_transaction:
            self.execute("BEGIN IMMEDIATE")
        try:
            for statement in split_statements(script):
                self.execute(statement)
        except BaseException:
            if own_transaction:
                self.rollback()
            raise
        else:
            if own_transaction:
                self.commit()

    def commit(self):
        try:
            self.raw.commit()
        except self._psycopg.Error as exc:
            # A lost COMMIT acknowledgement has an uncertain outcome. Drop
            # this session and its leader lock; never keep playing on it.
            self.close()
            raise StorageError(f"PostgreSQL game commit failed ({exc.sqlstate or 'connection'}).") from None

    def rollback(self):
        if not self.closed:
            try:
                self.raw.rollback()
            except self._psycopg.Error:
                self.close()

    @staticmethod
    def _check_lock_key(key):
        if isinstance(key, bool) or not isinstance(key, int) or not -(2**63) <= key < 2**63:
            raise ValueError("Leader lock key must be a signed 64-bit integer.")

    def try_leader_lock(self, key: int) -> bool:
        """Take a session lock once; repeated checks never increment its count."""
        self._check_lock_key(key)
        if key in self._held_leader_keys:
            return self.verify_leader_lock(key)
        acquired = bool(self._run("SELECT pg_catalog.pg_try_advisory_lock(%s)", (key,)).fetchone()[0])
        if acquired:
            self._held_leader_keys.add(key)
        return acquired

    def verify_leader_lock(self, key: int) -> bool:
        self._check_lock_key(key)
        if key not in self._held_leader_keys or self.closed:
            return False
        unsigned = key & ((1 << 64) - 1)
        return bool(self._run("""SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_locks
            WHERE pid=pg_catalog.pg_backend_pid() AND locktype='advisory'
              AND classid=%s::oid AND objid=%s::oid AND objsubid=1
              AND mode='ExclusiveLock' AND granted)""",
            (unsigned >> 32, unsigned & 0xffffffff)).fetchone()[0])

    def release_leader_lock(self, key: int):
        self._check_lock_key(key)
        if key in self._held_leader_keys and not self.closed:
            self._run("SELECT pg_catalog.pg_advisory_unlock(%s)", (key,))
        self._held_leader_keys.discard(key)

    def close(self):
        self._held_leader_keys.clear()
        if self.raw is not None:
            self.raw.close()
