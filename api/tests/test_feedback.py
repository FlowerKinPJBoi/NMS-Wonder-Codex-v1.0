from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.routers import feedback
from app.schemas import FeedbackPayload


def base_payload(**overrides):
    values = {
        "visitor_type": "alpha_beta_tester",
        "page_area": "overall_site",
        "ease_score": 4,
        "ui_score": 5,
        "usefulness_score": 5,
        "task_success": "yes",
        "price_choice": "5",
        "monthly_credits": 10,
        "credit_uses": ["transit", "delivery"],
        "research_consent": True,
    }
    values.update(overrides)
    return values


def test_fixed_price_requires_a_monthly_credit_expectation():
    with pytest.raises(ValidationError, match="how many monthly credits"):
        FeedbackPayload(**base_payload(monthly_credits=None))


def test_custom_price_requires_an_amount_and_preserves_decimal_precision():
    with pytest.raises(ValidationError, match="custom monthly amount"):
        FeedbackPayload(**base_payload(price_choice="custom", custom_monthly_price=None))
    payload = FeedbackPayload(**base_payload(
        price_choice="custom",
        custom_monthly_price="7.50",
        monthly_credits=12,
    ))
    assert payload.custom_monthly_price == Decimal("7.50")


def test_no_pay_option_cannot_smuggle_price_or_credit_fields():
    payload = FeedbackPayload(**base_payload(
        price_choice="none",
        monthly_credits=None,
        credit_uses=[],
    ))
    assert payload.price_choice == "none"
    with pytest.raises(ValidationError, match="No-pay responses"):
        FeedbackPayload(**base_payload(price_choice="none", monthly_credits=10))


def test_feedback_text_is_bounded_cleaned_and_credit_uses_are_unique():
    payload = FeedbackPayload(**base_payload(
        respondent_name="  PJ   Explorer  ",
        improvements="  Keep the map controls visible.\x00  ",
        credit_uses=["transit", "transit", "delivery"],
    ))
    assert payload.respondent_name == "PJ Explorer"
    assert payload.improvements == "Keep the map controls visible."
    assert payload.credit_uses == ["transit", "delivery"]


def test_submit_stores_only_deliberate_feedback_fields(monkeypatch):
    payload = FeedbackPayload(**base_payload(
        respondent_name="Visceral",
        price_choice="custom",
        custom_monthly_price="7.50",
        monthly_credits=12,
    ))

    class FakeSession:
        added = None
        committed = False

        def add(self, row):
            self.added = row

        def commit(self):
            self.committed = True

    session = FakeSession()
    monkeypatch.setattr(feedback, "check_database", lambda: True)
    monkeypatch.setattr(feedback, "enforce_feedback", lambda request: None)
    result = feedback.submit_feedback(payload, SimpleNamespace(headers={}), session)

    assert result["ok"] is True
    assert session.committed is True
    assert session.added.custom_price_cents == 750
    assert session.added.monthly_credits == 12
    assert not hasattr(session.added, "user_agent")
    assert not hasattr(session.added, "submitter_ip_hash")


def test_feedback_summary_helpers_are_stable_and_sorted():
    assert feedback._average([5, 4, 3]) == 4
    assert feedback._average([]) == 0
    assert feedback._counter(["10", "5", "10"]) == [
        {"label": "10", "count": 2},
        {"label": "5", "count": 1},
    ]
