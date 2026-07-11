from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any, TypeVar

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")

# Keep each PostgreSQL statement well below the driver's 65,535 bind-parameter
# ceiling. A 500-row chunk remains safe even for the widest Wonder Codex rows.
DEFAULT_CHUNK_SIZE = 500


def chunks(rows: Sequence[dict[str, Any]], size: int = DEFAULT_CHUNK_SIZE) -> Iterable[Sequence[dict[str, Any]]]:
    if size < 1:
        raise ValueError("Chunk size must be at least 1.")
    for start in range(0, len(rows), size):
        yield rows[start:start + size]


def insert_conflict_safe(
    session: Session,
    model: type[ModelT],
    rows: Sequence[dict[str, Any]],
    *,
    conflict_columns: list[str],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Insert rows in safe chunks and return the number actually inserted."""
    inserted = 0
    for batch in chunks(rows, chunk_size):
        statement = (
            insert(model)
            .values(list(batch))
            .on_conflict_do_nothing(index_elements=conflict_columns)
            .returning(model.id)
        )
        result = session.execute(statement)
        inserted += len(result.scalars().all())
    return inserted


def insert_plain(
    session: Session,
    model: type[ModelT],
    rows: Sequence[dict[str, Any]],
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> int:
    """Insert non-deduplicated rows in safe chunks and return rows submitted."""
    inserted = 0
    for batch in chunks(rows, chunk_size):
        session.execute(insert(model).values(list(batch)))
        inserted += len(batch)
    return inserted
