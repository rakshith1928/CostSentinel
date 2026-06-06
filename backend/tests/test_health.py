"""Tests for health check endpoints including /health/db."""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.mark.asyncio
async def test_health_db_connected_returns_200():
    """Healthy DB returns 200 with connected status."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        from app.routes.health import health_db
        app = FastAPI()
        app.get("/health/db")(health_db)
        with TestClient(app) as client:
            response = client.get("/health/db")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert body["database"] == "connected"


@pytest.mark.asyncio
async def test_health_db_disconnected_returns_503():
    """Unreachable DB returns 503 with error detail."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("DB unreachable"))
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        from app.routes.health import health_db
        app = FastAPI()
        app.get("/health/db")(health_db)
        with TestClient(app) as client:
            response = client.get("/health/db")

        assert response.status_code == 503
        body = response.json()
        assert body["status"] == "unhealthy"
        assert body["database"] == "disconnected"
        assert "DB unreachable" in body["error"]


@pytest.mark.asyncio
async def test_health_db_closes_session_on_success():
    """Session is closed even when query succeeds."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        from app.routes.health import health_db
        app = FastAPI()
        app.get("/health/db")(health_db)
        with TestClient(app) as client:
            client.get("/health/db")

        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_health_db_closes_session_on_failure():
    """Session is closed even when query fails."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("boom"))
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        from app.routes.health import health_db
        app = FastAPI()
        app.get("/health/db")(health_db)
        with TestClient(app) as client:
            client.get("/health/db")

        mock_session.close.assert_called_once()


@pytest.mark.asyncio
async def test_main_health_includes_database_status():
    """/health endpoint includes database field."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session, \
         patch("app.routes.health.rc") as mock_rc, \
         patch("app.routes.health.proxy") as mock_proxy, \
         patch("app.routes.health.settings") as mock_settings:

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=None)
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        mock_rc.redis.ping = AsyncMock(return_value=True)
        mock_proxy.check_ollama = AsyncMock(return_value=True)
        mock_proxy.get_ollama_models = AsyncMock(return_value=["llama3.2"])
        mock_settings.default_budget_tokens = 100000
        mock_settings.hard_limit_multiplier = 1.2
        mock_settings.downgrade_model = "tinyllama"

        from app.routes.health import health
        app = FastAPI()
        app.get("/health")(health)
        with TestClient(app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["database"] is True
        assert body["database_error"] is None


@pytest.mark.asyncio
async def test_main_health_degraded_when_db_down():
    """/health returns degraded when database unreachable."""
    with patch("app.routes.health.get_session_no_yield") as mock_get_session, \
         patch("app.routes.health.rc") as mock_rc, \
         patch("app.routes.health.proxy") as mock_proxy, \
         patch("app.routes.health.settings") as mock_settings:

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=ConnectionError("no db"))
        mock_session.close = AsyncMock()
        mock_get_session.return_value = mock_session

        mock_rc.redis.ping = AsyncMock(return_value=True)
        mock_proxy.check_ollama = AsyncMock(return_value=True)
        mock_proxy.get_ollama_models = AsyncMock(return_value=[])
        mock_settings.default_budget_tokens = 100000
        mock_settings.hard_limit_multiplier = 1.2
        mock_settings.downgrade_model = "tinyllama"

        from app.routes.health import health
        app = FastAPI()
        app.get("/health")(health)
        with TestClient(app) as client:
            response = client.get("/health")

        body = response.json()
        assert body["status"] == "degraded"
        assert body["database"] is False
        assert "no db" in body["database_error"]
