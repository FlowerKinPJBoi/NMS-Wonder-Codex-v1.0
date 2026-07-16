from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlsplit

from ..config import get_settings


BOT_MARKERS = (
    "bot", "crawler", "spider", "slurp", "bingpreview", "facebookexternalhit",
    "discordbot", "embedly", "quora link preview", "whatsapp", "telegrambot",
)

TEXT_PROPERTIES: dict[str, int] = {
    "page_kind": 32,
    "entity_type": 40,
    "entity_id": 80,
    "catalog_lane": 40,
    "discovery_type": 40,
    "fauna_family": 120,
    "location_status": 30,
    "image_status": 30,
    "query_kind": 20,
    "map_galaxy": 3,
    "map_lane": 40,
    "map_quality": 30,
    "evidence_type": 30,
    "download_type": 40,
}
INTEGER_PROPERTIES = {"query_length", "result_count"}
BOOLEAN_PROPERTIES = {"has_query", "public_attribution"}


def session_hash(session_id: str) -> str:
    settings = get_settings()
    return hashlib.sha256(
        f"analytics:{settings.ip_hash_salt}:{session_id}".encode("utf-8")
    ).hexdigest()


def normalize_path(value: str) -> str | None:
    raw = (value or "/").strip()
    try:
        path = urlsplit(raw).path if "://" in raw else raw.split("?", 1)[0].split("#", 1)[0]
    except ValueError:
        path = "/"
    path = re.sub(r"/{2,}", "/", path or "/")
    if not path.startswith("/"):
        path = "/" + path
    lowered = path.casefold()
    if lowered.startswith("/admin") or lowered.startswith("/api"):
        return None
    return path[:300]


def clean_referrer(value: str) -> str:
    if not value:
        return "Direct"
    try:
        hostname = (urlsplit(value).hostname or "").casefold().strip(".")
    except ValueError:
        return "Direct"
    if not hostname:
        return "Direct"
    if hostname in {"wondercodex.com", "www.wondercodex.com"}:
        return "Internal"
    return hostname[:255]


def classify_user_agent(user_agent: str) -> dict[str, str | bool]:
    ua = (user_agent or "").casefold()
    is_bot = any(marker in ua for marker in BOT_MARKERS)

    if "ipad" in ua or "tablet" in ua:
        device = "Tablet"
    elif "mobile" in ua or "iphone" in ua or "android" in ua:
        device = "Mobile"
    else:
        device = "Desktop"

    if "edg/" in ua or "edge/" in ua:
        browser = "Edge"
    elif "firefox/" in ua or "fxios/" in ua:
        browser = "Firefox"
    elif "chrome/" in ua or "crios/" in ua:
        browser = "Chrome"
    elif "safari/" in ua:
        browser = "Safari"
    else:
        browser = "Other"

    if "windows" in ua:
        operating_system = "Windows"
    elif "iphone" in ua or "ipad" in ua or "ios" in ua:
        operating_system = "iOS"
    elif "android" in ua:
        operating_system = "Android"
    elif "mac os" in ua or "macintosh" in ua:
        operating_system = "macOS"
    elif "linux" in ua:
        operating_system = "Linux"
    else:
        operating_system = "Other"

    return {
        "is_bot": is_bot,
        "device_class": device,
        "browser_family": browser,
        "os_family": operating_system,
    }


def sanitize_properties(values: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key, maximum in TEXT_PROPERTIES.items():
        if key not in values:
            continue
        value = " ".join(str(values[key] or "").strip().split())
        if value:
            cleaned[key] = value[:maximum]
    for key in INTEGER_PROPERTIES:
        if key not in values:
            continue
        try:
            cleaned[key] = max(0, min(int(values[key]), 1_000_000))
        except (TypeError, ValueError):
            continue
    for key in BOOLEAN_PROPERTIES:
        if key in values and isinstance(values[key], bool):
            cleaned[key] = values[key]
    return cleaned
