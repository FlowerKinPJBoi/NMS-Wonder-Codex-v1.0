from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from decimal import Decimal
from typing import Iterable

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import check_database, get_session
from ..models import FeedbackResponse
from ..schemas import FeedbackPayload
from ..services.rate_limit import enforce_feedback
from ..services.security import require_owner_key


public_router = APIRouter(prefix="/feedback", tags=["feedback"])
owner_router = APIRouter(
    prefix="/owner/feedback",
    tags=["owner-feedback"],
    dependencies=[Depends(require_owner_key)],
)


def _origin_allowed(request: Request) -> bool:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return True
    allowed = {item.rstrip("/") for item in get_settings().allowed_origins}
    return origin in allowed


def _counter(values: Iterable[str]) -> list[dict[str, int | str]]:
    counts = Counter(values)
    return [
        {"label": label, "count": count}
        for label, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    ]


def _average(values: Iterable[int]) -> float:
    numbers = list(values)
    return round(sum(numbers) / len(numbers), 2) if numbers else 0


def _serialize(row: FeedbackResponse) -> dict[str, object]:
    return {
        "id": row.id,
        "created_at": row.created_at.isoformat() if row.created_at else "",
        "respondent_name": row.respondent_name,
        "visitor_type": row.visitor_type,
        "page_area": row.page_area,
        "ease_score": row.ease_score,
        "ui_score": row.ui_score,
        "usefulness_score": row.usefulness_score,
        "task_success": row.task_success,
        "most_useful": row.most_useful,
        "improvements": row.improvements,
        "missing_feature": row.missing_feature,
        "price_choice": row.price_choice,
        "custom_monthly_price": (
            str(Decimal(row.custom_price_cents) / Decimal(100))
            if row.custom_price_cents is not None
            else None
        ),
        "monthly_credits": row.monthly_credits,
        "credit_uses": row.credit_uses,
        "additional_notes": row.additional_notes,
    }


@public_router.post("", status_code=201)
def submit_feedback(
    payload: FeedbackPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    if payload.website:
        return {"ok": True, "feedback_id": None}
    if not _origin_allowed(request):
        raise HTTPException(status_code=403, detail="Feedback origin is not allowed.")
    if not check_database():
        raise HTTPException(status_code=503, detail="Feedback storage is temporarily unavailable.")
    enforce_feedback(request)

    feedback_id = str(uuid.uuid4())
    custom_price_cents = (
        int(payload.custom_monthly_price * 100)
        if payload.custom_monthly_price is not None
        else None
    )
    row = FeedbackResponse(
        id=feedback_id,
        respondent_name=payload.respondent_name,
        visitor_type=payload.visitor_type,
        page_area=payload.page_area,
        ease_score=payload.ease_score,
        ui_score=payload.ui_score,
        usefulness_score=payload.usefulness_score,
        task_success=payload.task_success,
        most_useful=payload.most_useful,
        improvements=payload.improvements,
        missing_feature=payload.missing_feature,
        price_choice=payload.price_choice,
        custom_price_cents=custom_price_cents,
        monthly_credits=payload.monthly_credits,
        credit_uses=payload.credit_uses,
        additional_notes=payload.additional_notes,
    )
    session.add(row)
    session.commit()
    return {"ok": True, "feedback_id": feedback_id}


@owner_router.get("/summary")
def feedback_summary(session: Session = Depends(get_session)):
    rows = list(session.scalars(
        select(FeedbackResponse).order_by(FeedbackResponse.created_at.desc())
    ).all())
    credits_by_price: dict[str, list[int]] = defaultdict(list)
    custom_prices: list[int] = []
    for row in rows:
        if row.monthly_credits is not None:
            credits_by_price[row.price_choice].append(row.monthly_credits)
        if row.custom_price_cents is not None:
            custom_prices.append(row.custom_price_cents)

    return {
        "total_responses": len(rows),
        "averages": {
            "ease": _average(row.ease_score for row in rows),
            "ui": _average(row.ui_score for row in rows),
            "usefulness": _average(row.usefulness_score for row in rows),
        },
        "visitor_types": _counter(row.visitor_type for row in rows),
        "page_areas": _counter(row.page_area for row in rows),
        "task_success": _counter(row.task_success for row in rows),
        "pricing": _counter(row.price_choice for row in rows),
        "average_credits_by_price": {
            choice: _average(values) for choice, values in credits_by_price.items()
        },
        "average_custom_price": (
            str(Decimal(round(sum(custom_prices) / len(custom_prices))) / Decimal(100))
            if custom_prices
            else None
        ),
        "credit_uses": _counter(
            credit_use for row in rows for credit_use in (row.credit_uses or [])
        ),
    }


@owner_router.get("/responses")
def feedback_responses(
    limit: int = Query(default=250, ge=1, le=500),
    session: Session = Depends(get_session),
):
    rows = session.scalars(
        select(FeedbackResponse)
        .order_by(FeedbackResponse.created_at.desc())
        .limit(limit)
    ).all()
    return {"items": [_serialize(row) for row in rows]}
