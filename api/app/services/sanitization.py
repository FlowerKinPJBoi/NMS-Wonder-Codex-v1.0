from __future__ import annotations

import math
from typing import Any


def safe_text(value: Any) -> str:
    """Return UTF-8-safe text that PostgreSQL text/JSONB can store."""
    text = str(value or "").replace("\x00", "")
    # Game saves can occasionally contain lone UTF-16 surrogate code points.
    # Replace them rather than allowing psycopg's UTF-8 encoder to fail.
    return text.encode("utf-8", "replace").decode("utf-8")


def clean_json(value: Any) -> Any:
    """Recursively clean browser JSON for PostgreSQL JSONB storage."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, str):
        return safe_text(value)
    if isinstance(value, list):
        return [clean_json(item) for item in value]
    if isinstance(value, tuple):
        return [clean_json(item) for item in value]
    if isinstance(value, dict):
        return {safe_text(key): clean_json(item) for key, item in value.items()}
    return safe_text(value)
