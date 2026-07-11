from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def canonical_hash(record: dict[str, Any], keys: Iterable[str]) -> str:
    normalized = {key: str(record.get(key, "") or "").strip() for key in keys}
    payload = json.dumps(normalized, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def fingerprint(value: dict[str, Any]) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
