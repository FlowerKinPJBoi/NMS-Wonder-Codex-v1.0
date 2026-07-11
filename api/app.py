
import hashlib
import json
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime
from typing import Any

from fastapi import FastAPI, HTTPException, Request
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


APP_VERSION = "0.3.0"
MAX_DISCOVERIES = 20_000
MAX_MATCHES = 2_000
MAX_ISSUES = 5_000
MAX_REQUESTS_PER_HOUR = int(os.environ.get("MAX_REQUESTS_PER_HOUR", "5"))


def database_url() -> str:
    value = os.environ.get("DATABASE_URL", "").strip()
    if not value:
        raise RuntimeError("DATABASE_URL is not configured.")
    if value.startswith("postgres://"):
        value = "postgresql+psycopg://" + value[len("postgres://"):]
    elif value.startswith("postgresql://"):
        value = "postgresql+psycopg://" + value[len("postgresql://"):]
    return value


class Base(DeclarativeBase):
    pass


class SubmissionBatch(Base):
    __tablename__ = "submission_batches"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    contributor: Mapped[str] = mapped_column(String(120), nullable=False)
    save_name: Mapped[str] = mapped_column(String(200), nullable=False)
    platform: Mapped[str] = mapped_column(String(40), default="", nullable=False)
    client_version: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    source_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    summary: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    submitter_ip_hash: Mapped[str] = mapped_column(String(64), default="", nullable=False)
    user_agent: Mapped[str] = mapped_column(Text, default="", nullable=False)


class SubmittedDiscovery(Base):
    __tablename__ = "submitted_discoveries"
    __table_args__ = (
        UniqueConstraint("record_hash", name="uq_submitted_discovery_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(
        ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False
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
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SubmittedPetMatch(Base):
    __tablename__ = "submitted_pet_matches"
    __table_args__ = (
        UniqueConstraint("record_hash", name="uq_submitted_pet_match_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(
        ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False
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
    review_status: Mapped[str] = mapped_column(String(30), default="pending", nullable=False)
    raw_record: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class SubmissionIssue(Base):
    __tablename__ = "submission_issues"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    submission_batch_id: Mapped[str] = mapped_column(
        ForeignKey("submission_batches.id", ondelete="CASCADE"), nullable=False
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


class SubmissionPayload(BaseModel):
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
    website: str = ""  # Honeypot. Real users never see or fill this.


engine = create_engine(database_url(), pool_pre_ping=True, pool_recycle=300)
Base.metadata.create_all(engine)

app = FastAPI(title="Wonder Codex Submission API", version=APP_VERSION)

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
    allow_headers=["Content-Type"],
)

_rate_windows: dict[str, deque[float]] = defaultdict(deque)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce_rate_limit(request: Request) -> str:
    ip = client_ip(request)
    now = time.time()
    window = _rate_windows[ip]
    while window and window[0] < now - 3600:
        window.popleft()
    if len(window) >= MAX_REQUESTS_PER_HOUR:
        raise HTTPException(
            status_code=429,
            detail="Submission limit reached. Please try again later.",
        )
    window.append(now)
    salt = os.environ.get("IP_HASH_SALT", "wonder-codex-alpha")
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()


def canonical_hash(record: dict[str, Any], keys: list[str]) -> str:
    normalized = {key: str(record.get(key, "") or "").strip() for key in keys}
    encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@app.get("/api/health")
def health() -> dict[str, Any]:
    with Session(engine) as session:
        session.execute(select(1))
    return {
        "ok": True,
        "service": "Wonder Codex Submission API",
        "version": APP_VERSION,
        "mode": "review-queue",
    }


@app.get("/api/stats")
def stats() -> dict[str, Any]:
    with Session(engine) as session:
        batches = session.scalar(select(func.count()).select_from(SubmissionBatch)) or 0
        discoveries = session.scalar(select(func.count()).select_from(SubmittedDiscovery)) or 0
        matches = session.scalar(select(func.count()).select_from(SubmittedPetMatch)) or 0
        pending_batches = session.scalar(
            select(func.count()).select_from(SubmissionBatch).where(
                SubmissionBatch.status == "pending"
            )
        ) or 0
    return {
        "submission_batches": batches,
        "pending_batches": pending_batches,
        "submitted_discoveries": discoveries,
        "submitted_pet_matches": matches,
    }


@app.post("/api/submissions")
def submit_to_review_queue(
    payload: SubmissionPayload,
    request: Request,
) -> dict[str, Any]:
    if payload.website:
        # Quietly accept bot honeypot submissions without storing them.
        return {"ok": True, "queued": False}

    ip_hash = enforce_rate_limit(request)

    if len(payload.discoveries) > MAX_DISCOVERIES:
        raise HTTPException(status_code=413, detail="Too many discoveries in one submission.")
    if len(payload.matches) > MAX_MATCHES:
        raise HTTPException(status_code=413, detail="Too many pet matches in one submission.")
    if len(payload.issues) > MAX_ISSUES:
        raise HTTPException(status_code=413, detail="Too many issues in one submission.")

    contributor = payload.contributor.strip()
    save_name = payload.saveName.strip()
    if contributor.lower() in {"anonymous", "unknown", "test"}:
        raise HTTPException(status_code=400, detail="Please enter a recognizable contributor name.")

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
            row, ["DT", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"]
        )
        discovery_rows.append(
            {
                "submission_batch_id": batch_id,
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
                "review_status": "pending",
                "raw_record": row,
            }
        )

    match_rows: list[dict[str, Any]] = []
    for row in payload.matches:
        record_hash = canonical_hash(
            row, ["CreatureID", "UA", "VP0", "VP1", "VP2", "VP3", "VP4"]
        )
        match_rows.append(
            {
                "submission_batch_id": batch_id,
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
                "review_status": "pending",
                "raw_record": row,
            }
        )

    issue_rows = [
        {
            "submission_batch_id": batch_id,
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
        for row in payload.issues
    ]

    with Session(engine) as session:
        try:
            session.add(
                SubmissionBatch(
                    id=batch_id,
                    contributor=contributor,
                    save_name=save_name,
                    platform=payload.platform,
                    client_version=payload.version,
                    status="pending",
                    source_fingerprint=source_fingerprint,
                    summary=payload.summary,
                    submitter_ip_hash=ip_hash,
                    user_agent=request.headers.get("user-agent", "")[:1000],
                )
            )
            session.flush()

            discovery_queued = 0
            match_queued = 0

            if discovery_rows:
                result = session.execute(
                    insert(SubmittedDiscovery)
                    .values(discovery_rows)
                    .on_conflict_do_nothing(index_elements=["record_hash"])
                    .returning(SubmittedDiscovery.id)
                )
                discovery_queued = len(result.scalars().all())

            if match_rows:
                result = session.execute(
                    insert(SubmittedPetMatch)
                    .values(match_rows)
                    .on_conflict_do_nothing(index_elements=["record_hash"])
                    .returning(SubmittedPetMatch.id)
                )
                match_queued = len(result.scalars().all())

            if issue_rows:
                session.execute(insert(SubmissionIssue).values(issue_rows))

            session.commit()
        except Exception:
            session.rollback()
            raise

    return {
        "ok": True,
        "queued": True,
        "status": "pending_review",
        "submission_id": batch_id,
        "contributor": contributor,
        "save_name": save_name,
        "received": {
            "discoveries": len(discovery_rows),
            "pet_matches": len(match_rows),
            "issues": len(issue_rows),
        },
        "queued_records": {
            "discoveries": discovery_queued,
            "pet_matches": match_queued,
        },
        "duplicates_skipped": {
            "discoveries": len(discovery_rows) - discovery_queued,
            "pet_matches": len(match_rows) - match_queued,
        },
    }
