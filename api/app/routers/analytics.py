from __future__ import annotations

from collections import OrderedDict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ..config import get_settings
from ..database import get_session
from ..models import AnalyticsDailyMetric, AnalyticsEvent
from ..schemas import AnalyticsEventPayload
from ..services.analytics import (
    classify_user_agent,
    clean_referrer,
    normalize_path,
    sanitize_properties,
    session_hash,
)
from ..services.rate_limit import enforce_analytics
from ..services.security import require_owner_key


public_router = APIRouter(prefix="/analytics", tags=["analytics"])
owner_router = APIRouter(
    prefix="/owner/analytics",
    tags=["owner-analytics"],
    dependencies=[Depends(require_owner_key)],
)

_last_cleanup_day: date | None = None


def _increment(
    session: Session,
    *,
    day: date,
    metric: str,
    dimension: str,
    value: str,
) -> None:
    statement = insert(AnalyticsDailyMetric).values(
        day=day,
        metric=metric,
        dimension=dimension,
        value=value[:300],
        count=1,
    ).on_conflict_do_update(
        constraint="uq_analytics_daily_metric",
        set_={"count": AnalyticsDailyMetric.count + 1},
    )
    session.execute(statement)


def _cleanup_if_due(session: Session, now: datetime) -> None:
    global _last_cleanup_day
    if _last_cleanup_day == now.date():
        return
    retention = max(1, get_settings().analytics_retention_days)
    session.execute(delete(AnalyticsEvent).where(
        AnalyticsEvent.occurred_at < now - timedelta(days=retention)
    ))
    _last_cleanup_day = now.date()


def _origin_allowed(request: Request) -> bool:
    origin = (request.headers.get("origin") or "").rstrip("/")
    if not origin:
        return True
    allowed = {item.rstrip("/") for item in get_settings().allowed_origins}
    return origin in allowed


@public_router.post("/events", status_code=204)
def collect_event(
    payload: AnalyticsEventPayload,
    request: Request,
    session: Session = Depends(get_session),
):
    settings = get_settings()
    if not settings.analytics_enabled:
        return Response(status_code=204)
    if not _origin_allowed(request):
        raise HTTPException(status_code=403, detail="Analytics origin is not allowed.")
    enforce_analytics(request)

    path = normalize_path(payload.path)
    if not path:
        return Response(status_code=204)

    agent = classify_user_agent(request.headers.get("user-agent", ""))
    if agent["is_bot"]:
        return Response(status_code=204)

    now = datetime.now(timezone.utc)
    day_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    hashed_session = session_hash(payload.session_id)
    first_session_event_today = session.scalar(
        select(AnalyticsEvent.id).where(
            AnalyticsEvent.session_hash == hashed_session,
            AnalyticsEvent.occurred_at >= day_start,
        ).limit(1)
    ) is None
    properties = sanitize_properties(payload.properties)
    referrer = clean_referrer(payload.referrer)

    session.add(AnalyticsEvent(
        occurred_at=now,
        session_hash=hashed_session,
        event_type=payload.event_type,
        path=path,
        page_title=" ".join(payload.title.strip().split())[:200],
        referrer_domain=referrer,
        device_class=str(agent["device_class"]),
        browser_family=str(agent["browser_family"]),
        os_family=str(agent["os_family"]),
        properties=properties,
    ))

    _increment(session, day=now.date(), metric="event", dimension="event_type", value=payload.event_type)
    if payload.event_type == "page_view":
        _increment(session, day=now.date(), metric="page_view", dimension="all", value="all")
        _increment(session, day=now.date(), metric="page_view", dimension="path", value=path)
        _increment(session, day=now.date(), metric="page_view", dimension="referrer", value=referrer)
        _increment(session, day=now.date(), metric="page_view", dimension="device", value=str(agent["device_class"]))
        _increment(session, day=now.date(), metric="page_view", dimension="browser", value=str(agent["browser_family"]))
        _increment(session, day=now.date(), metric="page_view", dimension="os", value=str(agent["os_family"]))
    if first_session_event_today:
        _increment(session, day=now.date(), metric="session", dimension="all", value="all")
    for key, value in properties.items():
        if key in {"query_length", "result_count", "has_query", "public_attribution"}:
            continue
        _increment(
            session,
            day=now.date(),
            metric="event_property",
            dimension=key,
            value=str(value),
        )

    _cleanup_if_due(session, now)
    session.commit()
    return Response(status_code=204)


def _date_condition(days: int):
    if days <= 0:
        return None
    return AnalyticsDailyMetric.day >= datetime.now(timezone.utc).date() - timedelta(days=days - 1)


def _raw_time_condition(days: int):
    if days <= 0:
        days = get_settings().analytics_retention_days
    return AnalyticsEvent.occurred_at >= datetime.now(timezone.utc) - timedelta(days=days)


def _total(session: Session, *, metric: str, dimension: str, value: str, days: int) -> int:
    statement = select(func.coalesce(func.sum(AnalyticsDailyMetric.count), 0)).where(
        AnalyticsDailyMetric.metric == metric,
        AnalyticsDailyMetric.dimension == dimension,
        AnalyticsDailyMetric.value == value,
    )
    condition = _date_condition(days)
    if condition is not None:
        statement = statement.where(condition)
    return int(session.scalar(statement) or 0)


def _top(
    session: Session,
    *,
    metric: str,
    dimension: str,
    days: int,
    limit: int = 10,
) -> list[dict[str, Any]]:
    statement = select(
        AnalyticsDailyMetric.value,
        func.sum(AnalyticsDailyMetric.count).label("count"),
    ).where(
        AnalyticsDailyMetric.metric == metric,
        AnalyticsDailyMetric.dimension == dimension,
    )
    condition = _date_condition(days)
    if condition is not None:
        statement = statement.where(condition)
    rows = session.execute(
        statement.group_by(AnalyticsDailyMetric.value)
        .order_by(func.sum(AnalyticsDailyMetric.count).desc(), AnalyticsDailyMetric.value.asc())
        .limit(limit)
    ).all()
    return [{"label": str(value), "count": int(count)} for value, count in rows]


def _series(session: Session, days: int) -> list[dict[str, Any]]:
    statement = select(
        AnalyticsDailyMetric.day,
        AnalyticsDailyMetric.metric,
        func.sum(AnalyticsDailyMetric.count).label("count"),
    ).where(
        AnalyticsDailyMetric.dimension == "all",
        AnalyticsDailyMetric.value == "all",
        AnalyticsDailyMetric.metric.in_(["page_view", "session"]),
    )
    condition = _date_condition(days)
    if condition is not None:
        statement = statement.where(condition)
    rows = session.execute(
        statement.group_by(AnalyticsDailyMetric.day, AnalyticsDailyMetric.metric)
        .order_by(AnalyticsDailyMetric.day.asc())
    ).all()
    grouped: OrderedDict[date, dict[str, Any]] = OrderedDict()
    for day, metric, count in rows:
        grouped.setdefault(day, {"day": day.isoformat(), "page_views": 0, "sessions": 0})
        grouped[day]["page_views" if metric == "page_view" else "sessions"] = int(count)
    return list(grouped.values())


def _journeys(session: Session, *, days: int, limit: int = 20) -> list[dict[str, Any]]:
    rows = session.scalars(
        select(AnalyticsEvent)
        .where(_raw_time_condition(days))
        .order_by(AnalyticsEvent.occurred_at.desc())
        .limit(1500)
    ).all()
    grouped: OrderedDict[str, list[AnalyticsEvent]] = OrderedDict()
    for row in rows:
        grouped.setdefault(row.session_hash, []).append(row)

    journeys = []
    for ordinal, events in enumerate(list(grouped.values())[:limit], start=1):
        ordered = sorted(events, key=lambda item: item.occurred_at)
        pages = []
        actions = []
        for event in ordered:
            if event.event_type == "page_view":
                label = event.page_title or event.path
                if not pages or pages[-1]["path"] != event.path:
                    pages.append({"path": event.path, "title": label})
            else:
                actions.append({
                    "type": event.event_type,
                    "entity": str(event.properties.get("entity_id", "")),
                })
        journeys.append({
            "label": f"Anonymous journey {ordinal}",
            "started_at": ordered[0].occurred_at.isoformat(),
            "last_seen_at": ordered[-1].occurred_at.isoformat(),
            "device": ordered[-1].device_class,
            "browser": ordered[-1].browser_family,
            "pages": pages[-20:],
            "actions": actions[-20:],
        })
    return journeys


@owner_router.get("/summary")
def owner_summary(
    days: int = Query(default=7, ge=0, le=3650),
    session: Session = Depends(get_session),
):
    page_views = _total(session, metric="page_view", dimension="all", value="all", days=days)
    sessions = _total(session, metric="session", dimension="all", value="all", days=days)
    live_since = datetime.now(timezone.utc) - timedelta(minutes=5)
    live_sessions = session.scalar(
        select(func.count(distinct(AnalyticsEvent.session_hash))).where(
            AnalyticsEvent.occurred_at >= live_since
        )
    ) or 0
    event_count = sum(item["count"] for item in _top(
        session, metric="event", dimension="event_type", days=days, limit=100
    ) if item["label"] != "page_view")

    filter_dimensions = [
        "catalog_lane", "discovery_type", "fauna_family", "location_status",
        "image_status", "query_kind", "map_galaxy", "map_lane", "map_quality",
        "evidence_type", "download_type",
    ]
    return {
        "range": {"days": days, "label": "All time" if days == 0 else f"Last {days} day{'s' if days != 1 else ''}"},
        "totals": {
            "page_views": page_views,
            "sessions": sessions,
            "custom_events": event_count,
            "live_sessions": int(live_sessions),
            "pages_per_session": round(page_views / sessions, 2) if sessions else 0,
        },
        "series": _series(session, days),
        "top_pages": _top(session, metric="page_view", dimension="path", days=days, limit=12),
        "top_referrers": _top(session, metric="page_view", dimension="referrer", days=days, limit=10),
        "devices": _top(session, metric="page_view", dimension="device", days=days, limit=10),
        "browsers": _top(session, metric="page_view", dimension="browser", days=days, limit=10),
        "operating_systems": _top(session, metric="page_view", dimension="os", days=days, limit=10),
        "top_events": [item for item in _top(
            session, metric="event", dimension="event_type", days=days, limit=12
        ) if item["label"] != "page_view"],
        "top_entities": _top(session, metric="event_property", dimension="entity_id", days=days, limit=12),
        "filters": {
            name: _top(session, metric="event_property", dimension=name, days=days, limit=12)
            for name in filter_dimensions
        },
        "journeys": _journeys(session, days=days),
        "privacy": {
            "raw_event_retention_days": get_settings().analytics_retention_days,
            "raw_ip_addresses_stored": False,
            "raw_user_agents_stored": False,
            "admin_pages_tracked": False,
        },
    }
