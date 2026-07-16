from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..models import AssetSighting, AssetSpecimen, Discovery, ImageContribution, LocationVerification


POINTS = {
    "discoveries": 1,
    "images": 3,
    "verifications": 2,
    "assets": 1,
    "sightings": 2,
}

RANKS = (
    (1000, "S", "Stellar"),
    (250, "A", "Astral"),
    (50, "B", "Beacon"),
    (1, "C", "Comet"),
)

WEEKLY_MISSIONS = (
    {
        "id": "first-contact-30",
        "title": "First Contact",
        "description": "Publish 30 new, previously unregistered discoveries.",
        "metric": "discoveries",
        "target": 30,
        "unit": "discoveries",
    },
    {
        "id": "missing-portraits-15",
        "title": "Missing Portraits",
        "description": "Add 15 approved primary specimen images.",
        "metric": "images",
        "target": 15,
        "unit": "images",
    },
    {
        "id": "route-scout-10",
        "title": "Route Scout",
        "description": "Complete 10 approved location verifications.",
        "metric": "verifications",
        "target": 10,
        "unit": "routes",
    },
)


def contributor_rank(points: int) -> dict[str, Any]:
    for threshold, code, label in RANKS:
        if points >= threshold:
            return {"code": code, "label": label, "minimum_points": threshold}
    return {"code": "C", "label": "Comet", "minimum_points": 1}


def contributor_slug(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
    return slug or "explorer"


def current_week(now: datetime | None = None) -> tuple[datetime, datetime]:
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    start = (current - timedelta(days=current.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=7)


def _merge(rows: Iterable[tuple[str, int]], output: dict[str, dict[str, Any]], metric: str) -> None:
    for contributor, count in rows:
        display = " ".join(str(contributor or "").split())
        if not display:
            continue
        key = display.casefold()
        profile = output.setdefault(key, {"display_name": display, "metrics": defaultdict(int), "weekly": defaultdict(int)})
        profile["metrics"][metric] += int(count or 0)


def _merge_weekly(rows: Iterable[tuple[str, int]], output: dict[str, dict[str, Any]], metric: str) -> None:
    for contributor, count in rows:
        display = " ".join(str(contributor or "").split())
        if not display:
            continue
        key = display.casefold()
        profile = output.setdefault(key, {"display_name": display, "metrics": defaultdict(int), "weekly": defaultdict(int)})
        profile["weekly"][metric] += int(count or 0)


def _grouped(session: Session, model, *conditions):
    return session.execute(
        select(model.contributor, func.count(model.id))
        .where(*conditions)
        .group_by(model.contributor)
    ).all()


def build_contributor_leaderboard(session: Session, *, limit: int = 100) -> dict[str, Any]:
    profiles: dict[str, dict[str, Any]] = {}
    week_start, week_end = current_week()

    lifetime_sources = (
        ("discoveries", _grouped(session, Discovery, Discovery.public_attribution.is_(True))),
        ("images", _grouped(session, ImageContribution, ImageContribution.public_attribution.is_(True), ImageContribution.status == "approved")),
        ("verifications", _grouped(session, LocationVerification, LocationVerification.public_attribution.is_(True), LocationVerification.status == "approved")),
        ("assets", _grouped(session, AssetSpecimen, AssetSpecimen.public_attribution.is_(True), AssetSpecimen.publication_state == "published")),
        ("sightings", _grouped(session, AssetSighting, AssetSighting.public_attribution.is_(True), AssetSighting.status == "verified")),
    )
    for metric, rows in lifetime_sources:
        _merge(rows, profiles, metric)

    weekly_sources = (
        ("discoveries", _grouped(session, Discovery, Discovery.public_attribution.is_(True), Discovery.created_at >= week_start, Discovery.created_at < week_end)),
        ("images", _grouped(session, ImageContribution, ImageContribution.public_attribution.is_(True), ImageContribution.status == "approved", ImageContribution.is_primary.is_(True), ImageContribution.reviewed_at >= week_start, ImageContribution.reviewed_at < week_end)),
        ("verifications", _grouped(session, LocationVerification, LocationVerification.public_attribution.is_(True), LocationVerification.status == "approved", LocationVerification.reviewed_at >= week_start, LocationVerification.reviewed_at < week_end)),
        ("assets", _grouped(session, AssetSpecimen, AssetSpecimen.public_attribution.is_(True), AssetSpecimen.publication_state == "published", AssetSpecimen.updated_at >= week_start, AssetSpecimen.updated_at < week_end)),
        ("sightings", _grouped(session, AssetSighting, AssetSighting.public_attribution.is_(True), AssetSighting.status == "verified", AssetSighting.reviewed_at >= week_start, AssetSighting.reviewed_at < week_end)),
    )
    for metric, rows in weekly_sources:
        _merge_weekly(rows, profiles, metric)

    items = []
    for profile in profiles.values():
        metrics = {name: int(profile["metrics"].get(name, 0)) for name in POINTS}
        weekly = {name: int(profile["weekly"].get(name, 0)) for name in POINTS}
        points = sum(metrics[name] * weight for name, weight in POINTS.items())
        weekly_points = sum(weekly[name] * weight for name, weight in POINTS.items())
        missions = [{
            **mission,
            "progress": min(int(mission["target"]), weekly.get(str(mission["metric"]), 0)),
            "completed": weekly.get(str(mission["metric"]), 0) >= int(mission["target"]),
        } for mission in WEEKLY_MISSIONS]
        items.append({
            "slug": contributor_slug(profile["display_name"]),
            "display_name": profile["display_name"],
            "rank": contributor_rank(points),
            "points": points,
            "weekly_points": weekly_points,
            "metrics": metrics,
            "weekly_metrics": weekly,
            "missions": missions,
        })

    items.sort(key=lambda row: (-int(row["points"]), -sum(row["metrics"].values()), str(row["display_name"]).casefold()))
    for position, item in enumerate(items, start=1):
        item["position"] = position

    return {
        "items": items[:limit],
        "total": len(items),
        "week": {"starts_at": week_start.isoformat(), "ends_at": week_end.isoformat()},
        "missions": list(WEEKLY_MISSIONS),
        "scoring": POINTS,
        "privacy": "Only publicly attributed, approved contributions appear on this leaderboard.",
    }
