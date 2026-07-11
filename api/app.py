
import hashlib
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    create_engine,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


APP_VERSION = "0.2.0"
MAX_DISCOVERIES = 20_000
MAX_MATCHES = 2_000
MAX_ISSUES = 5_000


def database_url() -> str:
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    # SQLAlchemy/psycopg expects the explicit driver name.
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


class Base(DeclarativeBase):
    pass


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    client_version: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class Discovery(Base):
    __tablename__ = "discoveries"
    __table_args__ = (
        UniqueConstraint("record_hash", name="uq_discoveries_record_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    discovery_type: Mapped[str] = mapped_column(String(40), nullable=False)
    ua: Mapped[str] = mapped_column(String(32), nullable=False)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    owner: Mapped[str] = mapped_column(String(160), default="", nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PetDiscoveryMatch(Base):
    __tablename__ = "pet_discovery_matches"
    __table_args__ = (
        UniqueConstraint("record_hash", name="uq_pet_matches_record_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    creature_id: Mapped[str] = mapped_column(String(120), nullable=False)
    creature_type: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ua: Mapped[str] = mapped_column(String(32), nullable=False)
    vp0: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp1: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp2: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp3: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    vp4: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_seed: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    secondary_check: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    message_id: Mapped[str] = mapped_column(Text, default="", nullable=False)
    pet_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    discovery_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    import_batch_id: Mapped[str] = mapped_column(
        ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    severity: Mapped[str] = mapped_column(String(30), default="", nullable=False)
    record_type: Mapped[str] = mapped_column(String(50), default="", nullable=False)
    creature_id: Mapped[str] = mapped_column(String(120), default="", nullable=False)
    ua: Mapped[str] = mapped_column(String(32), default="", nullable=False)
    issue: Mapped[str] = mapped_column(Text, nullable=False)
    source_path: Mapped[str] = mapped_column(Text, default="", nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FlexibleRow(BaseModel):
    model_config = ConfigDict(extra="allow")


class ImportPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: str = ""
    createdUTC: str = ""
    contributor: str = Field(min_length=1, max_length=120)
    saveName: str = Field(min_length=1, max_length=200)
    platform: str = Field(default="", max_length=40)
    summary: dict[str, Any] = Field(default_factory=dict)
    matches: list[dict[str, Any]] = Field(default_factory=list)
    discoveries: list[dict[str, Any]] = Field(default_factory=list)
    issues: list[dict[str, Any]] = Field(default_factory=list)


engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=300)
Base.metadata.create_all(engine)

app = FastAPI(title="Wonder Codex Import API", version=APP_VERSION)

allowed_origins = [
    x.strip()
    for x in os.environ.get(
        "ALLOWED_ORIGINS",
        "https://wondercodex.com,https://www.wondercodex.com",
    ).split(",")
    if x.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Wonder-Import-Key"],
)


def canonical_hash(record: dict[str, Any], keys: list[str]) -> str:
    normalized = {key: str(record.get(key, "") or "").strip() for key in keys}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def require_submission_key(value: str | None) -> None:
    configured = os.environ.get("IMPORT_SUBMISSION_KEY", "").strip()
    if not configured:
        raise HTTPException(status_code=503, detail="Submission key is not configured.")
    if not value or not hashlib.compare_digest(value, configured):
        raise HTTPException(status_code=401, detail="Invalid submission key.")


@app.get("/api/health")
def health() -> dict[str, Any]:
    with Session(engine) as session:
        session.execute(select(1))
    return {"ok": True, "service": "Wonder Codex Import API", "version": APP_VERSION}


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    with Session(engine) as session:
        discoveries = session.scalar(select(func.count()).select_from(Discovery)) or 0
        matches = session.scalar(select(func.count()).select_from(PetDiscoveryMatch)) or 0
        imports = session.scalar(select(func.count()).select_from(ImportBatch)) or 0
        animals = session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.discovery_type == "Animal")
        ) or 0
        flora = session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.discovery_type == "Flora")
        ) or 0
        minerals = session.scalar(
            select(func.count()).select_from(Discovery).where(Discovery.discovery_type == "Mineral")
        ) or 0
    return {
        "imports": imports,
        "discoveries": discoveries,
        "pet_matches": matches,
        "animals": animals,
        "flora": flora,
        "minerals": minerals,
    }


@app.post("/api/imports")
def submit_import(
    payload: ImportPayload,
    x_wonder_import_key: str | None = Header(default=None),
) -> dict[str, Any]:
    require_submission_key(x_wonder_import_key)

    if len(payload.discoveries) > MAX_DISCOVERIES:
        raise HTTPException(status_code=413, detail="Too many discoveries in one import.")
    if len(payload.matches) > MAX_MATCHES:
        raise HTTPException(status_code=413, detail="Too many pet matches in one import.")
    if len(payload.issues) > MAX_ISSUES:
        raise HTTPException(status_code=413, detail="Too many issues in one import.")

    contributor = payload.contributor.strip()
    save_name = payload.saveName.strip()
    batch_id = str(uuid.uuid4())
    source_fingerprint = hashlib.sha256(
        json.dumps(
            {
                "contributor": contributor,
                "save": save_name,
                "platform": payload.platform,
                "summary": payload.summary,
                "discoveries": len(payload.discoveries),
                "matches": len(payload.matches),
            },
            sort_keys=True,
        ).encode()
    ).hexdigest()

    discovery_rows: list[dict[str, Any]] = []
    for row in payload.discoveries:
        record_hash = canonical_hash(
            row,
            ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"],
        )
        discovery_rows.append(
            {
                "import_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
                "discovery_type": str(row.get("DT", "") or "")[:40],
                "ua": str(row.get("UA", "") or "")[:32],
                "vp0": str(row.get("VP0", "") or "")[:32],
                "vp1": str(row.get("VP1", "") or "")[:32],
                "vp2": str(row.get("VP2", "") or "")[:32],
                "vp3": str(row.get("VP3", "") or "")[:32],
                "vp4": str(row.get("VP4", "") or "")[:32],
                "message_id": str(row.get("MessageID", "") or ""),
                "owner": str(row.get("Owner", "") or "")[:160],
                "platform": str(row.get("Platform", "") or "")[:40],
                "source_path": str(row.get("Path", "") or ""),
                "record_hash": record_hash,
                "raw_record": row,
            }
        )

    match_rows: list[dict[str, Any]] = []
    for row in payload.matches:
        record_hash = canonical_hash(
            row,
            ["CreatureID", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"],
        )
        match_rows.append(
            {
                "import_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
                "creature_id": str(row.get("CreatureID", "") or "")[:120],
                "creature_type": str(row.get("CreatureType", "") or "")[:120],
                "ua": str(row.get("UA", "") or "")[:32],
                "vp0": str(row.get("VP0", "") or "")[:32],
                "vp1": str(row.get("VP1", "") or "")[:32],
                "vp2": str(row.get("VP2", "") or "")[:32],
                "vp3": str(row.get("VP3", "") or "")[:32],
                "vp4": str(row.get("VP4", "") or "")[:32],
                "secondary_seed": str(row.get("SecondarySeed", "") or "")[:32],
                "secondary_check": str(row.get("SecondaryCheck", "") or "")[:40],
                "message_id": str(row.get("MessageID", "") or ""),
                "pet_path": str(row.get("PetPath", "") or ""),
                "discovery_path": str(row.get("DiscoveryPath", "") or ""),
                "record_hash": record_hash,
                "raw_record": row,
            }
        )

    issue_rows: list[dict[str, Any]] = []
    for row in payload.issues:
        issue_rows.append(
            {
                "import_batch_id": batch_id,
                "contributor": contributor,
                "save_name": save_name,
                "severity": str(row.get("Severity", "") or "")[:30],
                "record_type": str(row.get("RecordType", "") or "")[:50],
                "creature_id": str(row.get("CreatureID", "") or "")[:120],
                "ua": str(row.get("UA", "") or "")[:32],
                "issue": str(row.get("Issue", "") or ""),
                "source_path": str(row.get("Path", "") or ""),
                "raw_record": row,
            }
        )

    with Session(engine) as session:
        try:
            session.add(
                ImportBatch(
                    id=batch_id,
                    contributor=contributor,
                    save_name=save_name,
                    platform=payload.platform,
                    client_version=payload.version,
                    source_fingerprint=source_fingerprint,
                    summary=payload.summary,
                )
            )
            session.flush()

            discovery_added = 0
            match_added = 0

            if discovery_rows:
                result = session.execute(
                    insert(Discovery)
                    .values(discovery_rows)
                    .on_conflict_do_nothing(index_elements=["record_hash"])
                    .returning(Discovery.id)
                )
                discovery_added = len(result.scalars().all())

            if match_rows:
                result = session.execute(
                    insert(PetDiscoveryMatch)
                    .values(match_rows)
                    .on_conflict_do_nothing(index_elements=["record_hash"])
                    .returning(PetDiscoveryMatch.id)
                )
                match_added = len(result.scalars().all())

            if issue_rows:
                session.execute(insert(ImportIssue).values(issue_rows))

            session.commit()
        except Exception:
            session.rollback()
            raise

    return {
        "ok": True,
        "batch_id": batch_id,
        "contributor": contributor,
        "save_name": save_name,
        "received": {
            "discoveries": len(discovery_rows),
            "pet_matches": len(match_rows),
            "issues": len(issue_rows),
        },
        "added": {
            "discoveries": discovery_added,
            "pet_matches": match_added,
        },
        "duplicates": {
            "discoveries": len(discovery_rows) - discovery_added,
            "pet_matches": len(match_rows) - match_added,
        },
    }
