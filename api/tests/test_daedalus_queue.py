from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routers import daedalus
from app.services.security import OperatorSession


class FakeSession:
    def __init__(self, row, entry=None):
        self.row = row
        self.entry = entry
        self.added = []
        self.committed = False

    def get(self, model, submission_id):
        del model
        return self.row if submission_id == self.row.id else None

    def add(self, value):
        self.added.append(value)

    def scalar(self, statement):
        del statement
        return self.entry

    def commit(self):
        self.committed = True


def row(*, status="approved", ground_truth_status="verified"):
    now = datetime.now(timezone.utc)
    return SimpleNamespace(
        id="submission-1",
        created_at=now,
        reviewed_at=now,
        released_at=None,
        status=status,
        contributor="Krosskelt",
        contributor_note="Please inspect the seating clearance.",
        reviewer="PJ",
        reviewer_note="Geometry checked.",
        original_filename="candidate.zip",
        object_key="admin-apps/daedalus-training/submission-1/source.zip",
        size_bytes=1234,
        sha256="a" * 64,
        schema_name="wonder-codex.daedalus.learning-record.v0.3",
        record_id="record-1",
        domain="NO_MANS_SKY_BASE_BUILDING",
        build_name="Test lounge",
        ground_truth_format="nmsbase",
        object_count=24,
        distinct_object_ids=5,
        ground_truth_status=ground_truth_status,
        attempt_status="needs_correction",
        trust_collection="TRUSTED_SUPERVISED_CORRECTION",
        server_validation={"passed": True},
        design_intent={"originalRequest": "Decorate the lounge."},
    )


REVIEWER = OperatorSession(
    "PJ",
    frozenset({"daedalus:submit", "daedalus:review", "daedalus:release"}),
)


def test_release_requires_human_verified_ground_truth():
    session = FakeSession(row(ground_truth_status="unverified"))
    with pytest.raises(HTTPException, match="human-verified ground truth"):
        daedalus.review_submission(
            "submission-1",
            daedalus.QueueAction(action="release", note="Release checked package."),
            REVIEWER,
            session,
        )
    assert session.committed is False


def test_release_requires_explicit_release_note():
    session = FakeSession(row())
    with pytest.raises(HTTPException, match="explicit release decision"):
        daedalus.review_submission(
            "submission-1",
            daedalus.QueueAction(action="release", note=""),
            REVIEWER,
            session,
        )
    assert session.committed is False


def test_release_rechecks_stored_digest_and_records_real_prior_state(monkeypatch):
    session = FakeSession(row())
    verified = {}

    def verify(object_key, *, expected_sha256, expected_size):
        verified.update({"key": object_key, "sha": expected_sha256, "size": expected_size})

    monkeypatch.setattr(daedalus, "verify_learning_package", verify)
    monkeypatch.setattr(
        daedalus,
        "read_learning_package",
        lambda *args, **kwargs: SimpleNamespace(record={"designIntent": {"originalRequest": "Test"}}),
    )
    corpus_entry = SimpleNamespace(
        status="active",
        published_version=7,
        last_changed_version=7,
        disabled_at=None,
        disabled_reason="",
    )
    monkeypatch.setattr(daedalus, "publish_lesson", lambda *args, **kwargs: corpus_entry)
    result = daedalus.review_submission(
        "submission-1",
        daedalus.QueueAction(action="release", note="PJ checked the archive and approves release."),
        REVIEWER,
        session,
    )
    assert result["submission"]["production_training_eligible"] is True
    assert result["submission"]["contributor_note"] == "Please inspect the seating clearance."
    assert verified == {
        "key": "admin-apps/daedalus-training/submission-1/source.zip",
        "sha": "a" * 64,
        "size": 1234,
    }
    assert session.row.status == "released"
    assert session.row.reviewer_note == "PJ checked the archive and approves release."
    assert result["submission"]["corpus"] == {
        "status": "active",
        "active": True,
        "version": 7,
        "last_changed_version": 7,
        "disabled_at": None,
        "disabled_reason": "",
    }
    assert session.added[-1].detail == {"from": "approved", "to": "released", "corpusVersion": 7}
    assert session.committed is True


def test_approval_does_not_publish_to_corpus(monkeypatch):
    session = FakeSession(row(status="pending_review"))

    def unexpected_publish(*args, **kwargs):
        raise AssertionError("approval must not publish")

    monkeypatch.setattr(daedalus, "publish_lesson", unexpected_publish)
    result = daedalus.review_submission(
        "submission-1",
        daedalus.QueueAction(action="approve", note="Geometry looks ready for release review."),
        REVIEWER,
        session,
    )
    assert result["submission"]["status"] == "approved"
    assert result["submission"]["production_training_eligible"] is False
    assert session.committed is True


def test_pre_consumer_release_can_be_explicitly_indexed(monkeypatch):
    session = FakeSession(row(status="released"))
    monkeypatch.setattr(daedalus, "verify_learning_package", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        daedalus,
        "read_learning_package",
        lambda *args, **kwargs: SimpleNamespace(record={"designIntent": {"originalRequest": "Legacy release"}}),
    )
    entry = SimpleNamespace(
        status="active",
        published_version=8,
        last_changed_version=8,
        disabled_at=None,
        disabled_reason="",
    )
    monkeypatch.setattr(daedalus, "publish_lesson", lambda *args, **kwargs: entry)
    result = daedalus.change_corpus_entry(
        "submission-1",
        daedalus.CorpusDecision(action="index", note="Revalidated after corpus migration."),
        REVIEWER,
        session,
    )
    assert result["corpus_version"] == 8
    assert result["corpus"]["active"] is True
    assert session.added[-1].event_type == "daedalus_corpus_indexed"
    assert session.committed is True
