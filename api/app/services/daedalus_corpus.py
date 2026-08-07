from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import DaedalusCorpusEntry, DaedalusCorpusState, DaedalusTrainingSubmission

CORPUS_NAME = "production"
ACTIVE = "active"
DISABLED = "disabled"
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_^+-]{2,}")


def _mapping(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any, maximum: int = 12_000) -> str:
    return " ".join(str(value or "").split())[:maximum]


def _string_list(value: Any, maximum: int = 100) -> list[str]:
    output: list[str] = []
    for item in _list(value):
        cleaned = _text(item, 160)
        if cleaned and cleaned not in output:
            output.append(cleaned)
        if len(output) >= maximum:
            break
    return output


def _tokens(value: str) -> set[str]:
    return {match.group(0).casefold() for match in TOKEN_PATTERN.finditer(value or "")}


def extract_lesson(
    record: dict[str, Any],
    submission: DaedalusTrainingSubmission,
    *,
    actor: str,
    release_note: str,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Extract the useful lesson while leaving heavy evidence in private object storage."""
    intent = _mapping(record.get("designIntent"))
    ground = _mapping(record.get("groundTruth"))
    teacher = _mapping(record.get("teacherFeedback"))
    trust = _mapping(record.get("trust"))
    safety = _mapping(record.get("safety"))
    attempt = _mapping(record.get("attemptedBuild"))
    inspection = _mapping(record.get("interactiveInspection"))
    inventory = []
    object_ids: list[str] = []
    for part in _list(ground.get("partInventory")):
        if not isinstance(part, dict):
            continue
        object_id = _text(part.get("objectId"), 120)
        if not object_id.startswith("^"):
            continue
        try:
            count = max(1, int(part.get("count") or 1))
        except (TypeError, ValueError):
            count = 1
        inventory.append({"objectId": object_id, "count": count, "userData": part.get("userData")})
        object_ids.append(object_id)

    original_request = _text(intent.get("originalRequest"))
    style_tags = _string_list(intent.get("styleTags"), 40)
    category = _text(intent.get("recognizedCategory"), 120)
    teacher_note = _text(teacher.get("note"))
    revisions = _list(record.get("conversationalRevisions"))
    conversation = _list(record.get("conversation"))
    part_feedback = _list(teacher.get("partFeedback"))
    comparison = _mapping(attempt.get("comparison"))
    bounds = _mapping(ground.get("bounds"))

    semantic_parts = [
        original_request,
        " ".join(style_tags),
        category,
        teacher_note,
        " ".join(_text(item.get("instruction"), 1000) for item in revisions if isinstance(item, dict)),
        " ".join(_text(item.get("content"), 1000) for item in conversation if isinstance(item, dict)),
        " ".join(
            _text(item.get("feedback") or item.get("note") or item.get("explanation"), 1000)
            for item in part_feedback if isinstance(item, dict)
        ),
        " ".join(object_ids),
    ]
    semantic_text = _text(" ".join(part for part in semantic_parts if part), 24_000)
    fingerprint = {
        "domain": submission.domain,
        "format": submission.ground_truth_format,
        "recognizedCategory": category,
        "styleTags": style_tags,
        "objectIds": object_ids,
        "objectCount": submission.object_count,
        "distinctObjectIds": submission.distinct_object_ids,
        "bounds": bounds,
        "trustCollection": submission.trust_collection,
    }
    lesson = {
        "intent": {
            "originalRequest": original_request or None,
            "styleTags": style_tags,
            "recognizedCategory": category or None,
            "signSpecification": intent.get("signSpecification"),
        },
        "groundTruth": {
            "format": submission.ground_truth_format,
            "objectCount": submission.object_count,
            "distinctObjectIds": submission.distinct_object_ids,
            "bounds": bounds,
            "partInventory": inventory,
            "sourceKind": ground.get("sourceKind"),
            "geometryStatus": ground.get("geometryStatus"),
            "protectedAnchor": ground.get("protectedAnchor"),
            "reverseBlueprint": ground.get("reverseBlueprint"),
        },
        "corrections": {
            "teacherNote": teacher_note or None,
            "groundTruth": teacher.get("groundTruth"),
            "generatedAttempt": teacher.get("generatedAttempt"),
            "partFeedback": part_feedback,
            "conversationalRevisions": revisions,
            "comparison": comparison,
            "inspectionSummary": inspection.get("modelSummary"),
        },
        "trust": trust,
        "safety": safety,
    }
    provenance = {
        "submissionId": submission.id,
        "recordId": submission.record_id,
        "sourceSha256": submission.sha256,
        "sourceFilename": submission.original_filename,
        "contributor": submission.contributor,
        "reviewer": actor,
        "releaseNote": _text(release_note, 4000),
        "releasedAt": datetime.now(timezone.utc).isoformat(),
        "evidenceStorage": "private-object-storage",
    }
    return semantic_text, fingerprint, lesson, provenance


def _locked_state(session: Session) -> DaedalusCorpusState:
    state = session.scalar(
        select(DaedalusCorpusState).where(DaedalusCorpusState.name == CORPUS_NAME).with_for_update()
    )
    if state is None:
        state = DaedalusCorpusState(name=CORPUS_NAME, version=0)
        session.add(state)
        session.flush()
    return state


def publish_lesson(
    session: Session,
    submission: DaedalusTrainingSubmission,
    record: dict[str, Any],
    *,
    actor: str,
    release_note: str,
) -> DaedalusCorpusEntry:
    existing = session.scalar(
        select(DaedalusCorpusEntry).where(DaedalusCorpusEntry.submission_id == submission.id)
    )
    if existing is not None:
        if existing.source_sha256 != submission.sha256:
            raise HTTPException(status_code=409, detail="The existing corpus lesson has different source provenance.")
        return existing

    semantic_text, fingerprint, lesson, provenance = extract_lesson(
        record, submission, actor=actor, release_note=release_note
    )
    state = _locked_state(session)
    state.version += 1
    entry = DaedalusCorpusEntry(
        id=str(uuid.uuid4()),
        submission_id=submission.id,
        status=ACTIVE,
        published_version=state.version,
        last_changed_version=state.version,
        domain=submission.domain,
        recognized_category=_text(fingerprint.get("recognizedCategory"), 120),
        trust_collection=submission.trust_collection,
        source_sha256=submission.sha256,
        semantic_text=semantic_text,
        structural_fingerprint=fingerprint,
        lesson=lesson,
        provenance=provenance,
        disabled_reason="",
    )
    session.add(entry)
    session.flush()
    return entry


def set_entry_active(session: Session, entry: DaedalusCorpusEntry, *, active: bool, reason: str) -> int:
    cleaned_reason = _text(reason, 4000)
    if not cleaned_reason:
        raise HTTPException(status_code=400, detail="Record why this corpus state is changing.")
    target = ACTIVE if active else DISABLED
    if entry.status == target:
        return entry.last_changed_version
    state = _locked_state(session)
    state.version += 1
    entry.status = target
    entry.last_changed_version = state.version
    entry.disabled_at = None if active else datetime.now(timezone.utc)
    entry.disabled_reason = "" if active else cleaned_reason
    provenance = dict(entry.provenance or {})
    provenance["lastCorpusDecision"] = {
        "action": "enable" if active else "disable",
        "reason": cleaned_reason,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    entry.provenance = provenance
    session.flush()
    return state.version


def corpus_version(session: Session) -> int:
    state = session.get(DaedalusCorpusState, CORPUS_NAME)
    return int(state.version) if state is not None else 0


def corpus_counts(session: Session) -> dict[str, int]:
    counts = {ACTIVE: 0, DISABLED: 0}
    for status, count in session.execute(
        select(DaedalusCorpusEntry.status, func.count(DaedalusCorpusEntry.id)).group_by(DaedalusCorpusEntry.status)
    ):
        counts[str(status)] = int(count)
    return {"version": corpus_version(session), **counts}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def score_entry(
    entry: DaedalusCorpusEntry,
    *,
    query: str,
    category: str,
    style_tags: Iterable[str],
    object_ids: Iterable[str],
    part_count: int | None,
) -> tuple[float, list[str]]:
    score = 0.0
    reasons: list[str] = []
    query_tokens = _tokens(query)
    lesson_tokens = _tokens(entry.semantic_text)
    if query_tokens:
        overlap = len(query_tokens & lesson_tokens) / len(query_tokens)
        if overlap:
            score += overlap * 6.0
            reasons.append(f"intent overlap {overlap:.0%}")

    wanted_category = category.casefold().strip()
    if wanted_category and wanted_category == entry.recognized_category.casefold():
        score += 3.0
        reasons.append("same build category")

    fingerprint = _mapping(entry.structural_fingerprint)
    wanted_tags = {str(item).casefold() for item in style_tags if str(item).strip()}
    entry_tags = {str(item).casefold() for item in _list(fingerprint.get("styleTags"))}
    tag_similarity = _jaccard(wanted_tags, entry_tags)
    if tag_similarity:
        score += tag_similarity * 2.0
        reasons.append(f"style overlap {tag_similarity:.0%}")

    wanted_ids = {str(item) for item in object_ids if str(item).startswith("^")}
    entry_ids = {str(item) for item in _list(fingerprint.get("objectIds"))}
    id_similarity = _jaccard(wanted_ids, entry_ids)
    if id_similarity:
        score += id_similarity * 5.0
        reasons.append(f"Object ID overlap {id_similarity:.0%}")

    if part_count and part_count > 0:
        entry_count = max(1, int(fingerprint.get("objectCount") or 1))
        proximity = math.exp(-abs(math.log(entry_count / part_count)))
        if proximity >= 0.35:
            score += proximity
            reasons.append("similar build scale")
    return round(score, 5), reasons


def retrieve_lessons(
    session: Session,
    *,
    query: str,
    domain: str,
    category: str = "",
    style_tags: Iterable[str] = (),
    object_ids: Iterable[str] = (),
    part_count: int | None = None,
    limit: int = 8,
) -> dict[str, Any]:
    wanted_tags = list(style_tags)
    wanted_ids = list(object_ids)
    statement = select(DaedalusCorpusEntry).where(DaedalusCorpusEntry.status == ACTIVE)
    if domain:
        statement = statement.where(DaedalusCorpusEntry.domain == domain)
    candidates = session.scalars(statement.limit(500)).all()
    ranked = []
    for entry in candidates:
        score, reasons = score_entry(
            entry,
            query=query,
            category=category,
            style_tags=wanted_tags,
            object_ids=wanted_ids,
            part_count=part_count,
        )
        if score <= 0 and (query or category or wanted_tags or wanted_ids or part_count is not None):
            continue
        ranked.append((score, entry.published_version, entry, reasons))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return {
        "corpus_version": corpus_version(session),
        "items": [
            {
                "corpus_entry_id": entry.id,
                "submission_id": entry.submission_id,
                "score": score,
                "reasons": reasons,
                "lesson": entry.lesson,
                "provenance": entry.provenance,
            }
            for score, _, entry, reasons in ranked[:limit]
        ],
    }
