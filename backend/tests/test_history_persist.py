"""Tests for history persistence worker."""

import pytest
from unittest.mock import patch, AsyncMock
from sqlalchemy.exc import OperationalError
from app.history_persist import persist_request_history, MAX_RETRIES


def _sample_data(request_id: str = "req_test_abc123") -> dict:
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    return {
        "id": request_id,
        "timestamp": now,
        "user_id": "user_1",
        "team": None,
        "model": "llama3.2",
        "original_model": "llama3.2",
        "input_tokens": 10,
        "output_tokens": 20,
        "total_tokens": 30,
        "blocked": False,
        "downgraded": False,
        "block_reason": None,
        "latency_ms": 150,
        "expires_at": now + timedelta(days=90),
    }


@pytest.mark.asyncio
async def test_persist_success():
    """Successful insert returns True."""
    data = _sample_data()
    with patch("app.history_persist._insert_once", new=AsyncMock(return_value=True)):
        result = await persist_request_history(data)
    assert result is True


@pytest.mark.asyncio
async def test_persist_duplicate_skipped():
    """Duplicate PK returns False (idempotent)."""
    data = _sample_data()
    with patch("app.history_persist._insert_once", new=AsyncMock(return_value=False)):
        result = await persist_request_history(data)
    assert result is False


@pytest.mark.asyncio
async def test_persist_retries_transient_failure():
    """Transient OperationalError triggers retry; success on attempt 2 returns True."""
    data = _sample_data()
    op_err = OperationalError("stmt", {}, Exception("connection lost"))
    mock_insert = AsyncMock(side_effect=[op_err, True])
    with patch("app.history_persist._insert_once", new=mock_insert):
        with patch("app.history_persist.asyncio.sleep", new=AsyncMock()):
            result = await persist_request_history(data)
    assert result is True
    assert mock_insert.call_count == 2


@pytest.mark.asyncio
async def test_persist_exhausts_retries_returns_false():
    """All retries fail -> returns False and logs error."""
    data = _sample_data()
    op_err = OperationalError("stmt", {}, Exception("db down"))
    mock_insert = AsyncMock(side_effect=op_err)
    with patch("app.history_persist._insert_once", new=mock_insert):
        with patch("app.history_persist.asyncio.sleep", new=AsyncMock()):
            result = await persist_request_history(data)
    assert result is False
    assert mock_insert.call_count == MAX_RETRIES


@pytest.mark.asyncio
async def test_persist_integrity_error_not_retried():
    """IntegrityError is not a transient failure; should be caught by _insert_once (not retry)."""
    data = _sample_data()
    mock_insert = AsyncMock(return_value=False)  # duplicate path returns False
    with patch("app.history_persist._insert_once", new=mock_insert):
        result = await persist_request_history(data)
    assert result is False
    assert mock_insert.call_count == 1


@pytest.mark.asyncio
async def test_persist_exponential_backoff():
    """Retry backoff uses exponential progression: 0.5s, 1.0s, 2.0s."""
    data = _sample_data()
    op_err = OperationalError("stmt", {}, Exception("transient"))
    mock_insert = AsyncMock(side_effect=op_err)
    sleep_mock = AsyncMock()
    with patch("app.history_persist._insert_once", new=mock_insert):
        with patch("app.history_persist.asyncio.sleep", new=sleep_mock):
            await persist_request_history(data)
    # 2 sleeps for 3 attempts (no sleep after final failure)
    assert sleep_mock.call_count == MAX_RETRIES - 1
    # Verify backoff values
    call_args_list = [call.args[0] for call in sleep_mock.call_args_list]
    assert call_args_list == [0.5, 1.0]


@pytest.mark.asyncio
async def test_persist_logs_failure_after_exhaustion():
    """Failure after max retries is logged at error level."""
    data = _sample_data()
    op_err = OperationalError("stmt", {}, Exception("permanent failure"))
    mock_insert = AsyncMock(side_effect=op_err)
    with patch("app.history_persist._insert_once", new=mock_insert):
        with patch("app.history_persist.asyncio.sleep", new=AsyncMock()):
            with patch("app.history_persist.logger") as mock_logger:
                result = await persist_request_history(data)
    assert result is False
    mock_logger.error.assert_called()
    error_call = mock_logger.error.call_args
    assert error_call[0][0] == "history.persist_failed"
