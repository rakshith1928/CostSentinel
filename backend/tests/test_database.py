"""Tests for PostgreSQL database client."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.database import (
    init_database,
    close_database,
    get_engine,
    get_session_no_yield,
)


@pytest.mark.asyncio
async def test_database_client_init():
    """Test database engine initialization."""
    with patch("app.database.create_async_engine") as mock_engine:
        await init_database()
        
        mock_engine.assert_called_once()


@pytest.mark.asyncio
async def test_database_client_close():
    """Test database engine cleanup."""
    mock_engine = MagicMock()
    mock_engine.dispose = AsyncMock()
    
    with patch("app.database._engine", mock_engine):
        await close_database()
        
        mock_engine.dispose.assert_called_once()


def test_database_not_initialized():
    """Test that get_engine() raises when not initialized."""
    with patch("app.database._engine", None):
        with pytest.raises(RuntimeError, match="not initialized"):
            get_engine()


@pytest.mark.asyncio
async def test_get_session_no_yield():
    """Test session retrieval without yield."""
    mock_factory = MagicMock()
    mock_session = AsyncMock()
    mock_factory.return_value = mock_session
    
    with patch("app.database._session_factory", mock_factory):
        result = await get_session_no_yield()
        
        assert result == mock_session
