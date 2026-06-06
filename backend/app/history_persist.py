"""Background history persistence worker.

Persists request history to PostgreSQL + TimescaleDB asynchronously
from FastAPI BackgroundTasks. Provides:

- Idempotent inserts (duplicate PK handled silently)
- Bounded retry with exponential backoff (3 attempts)
- Structured failure logging for operator troubleshooting
"""

import asyncio
import logging
from typing import Any
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from sqlalchemy import insert as sql_insert

from app.database import get_session_no_yield
from app.models.request_history_sqla import request_history


logger = logging.getLogger("costsentinel.history")


MAX_RETRIES = 3
BASE_BACKOFF_SECONDS = 0.5


async def _insert_once(data: dict) -> bool:
    """Attempt a single insert. Returns True on success, False on duplicate, raises on transient."""
    session = await get_session_no_yield()
    try:
        stmt = sql_insert(request_history).values(**data)
        await session.execute(stmt)
        await session.commit()
        return True
    except IntegrityError as e:
        await session.rollback()
        # Duplicate primary key = idempotent retry, not an error
        if "duplicate key" in str(e).lower() or "unique constraint" in str(e).lower():
            logger.info(
                "history.duplicate_skipped",
                extra={"request_id": data.get("id")},
            )
            return False
        raise
    except (OperationalError, SQLAlchemyError):
        await session.rollback()
        raise
    finally:
        await session.close()


async def persist_request_history(data: dict[str, Any]) -> bool:
    """
    Persist a request history record with bounded retry.

    Args:
        data: Dictionary matching request_history table columns.
              Must include 'id', 'timestamp', 'user_id', 'model',
              'original_model', 'expires_at'.

    Returns:
        True if inserted, False if duplicate (idempotent skip).

    Logs and surfaces failure after MAX_RETRIES exhausted.
    """
    request_id = data.get("id", "<unknown>")
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await _insert_once(data)
        except (OperationalError, SQLAlchemyError) as e:
            last_exc = e
            backoff = BASE_BACKOFF_SECONDS * (2 ** (attempt - 1))
            logger.warning(
                "history.persist_retry",
                extra={
                    "request_id": request_id,
                    "attempt": attempt,
                    "max_attempts": MAX_RETRIES,
                    "backoff_seconds": backoff,
                    "error": str(e),
                },
            )
            if attempt < MAX_RETRIES:
                await asyncio.sleep(backoff)

    logger.error(
        "history.persist_failed",
        extra={
            "request_id": request_id,
            "attempts": MAX_RETRIES,
            "error": str(last_exc) if last_exc else "unknown",
        },
    )
    return False
