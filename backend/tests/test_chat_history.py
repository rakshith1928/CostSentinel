"""Tests for chat completion history persistence integration."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _setup_chat_mocks(mock_proxy, mock_rc, mock_tc, mock_settings,
                      *, used=0, budget=1000, team=None,
                      team_used=0, team_budget=10000):
    """Configure mocks so the endpoint runs without auth or DB."""
    mock_settings.sentinel_api_key = ""
    mock_settings.hard_limit_multiplier = 1.2
    mock_settings.default_budget_tokens = budget
    mock_settings.downgrade_model = "tinyllama"
    mock_settings.cors_origins = "*"

    mock_proxy.resolve_user.return_value = "user_1"
    mock_proxy.count_tokens.return_value = 10
    mock_proxy.make_request_id.return_value = "req_test_abc"
    mock_proxy.call_ollama = AsyncMock(return_value={"message": {"content": "OK"}})

    mock_rc.get_budget = AsyncMock(return_value=budget)
    mock_rc.get_used = AsyncMock(return_value=used)
    mock_rc.log_request = AsyncMock()
    mock_rc.increment_usage = AsyncMock()

    mock_tc.get_user_team = AsyncMock(return_value=team)
    mock_tc.get_team_budget = AsyncMock(return_value=team_budget)
    mock_tc.get_team_used = AsyncMock(return_value=team_used)
    mock_tc.increment_team_usage = AsyncMock()


def _build_app_and_post(chat_completions, payload):
    """Wire chat_completions onto a fresh app and POST."""
    app = FastAPI()
    app.post("/test")(chat_completions)
    with TestClient(app) as client:
        return client.post("/test", json=payload)


@pytest.mark.asyncio
async def test_user_block_persists_history():
    """User budget block path queues history persistence."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history") as mock_persist, \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(
            mock_proxy, mock_rc, mock_tc, mock_settings,
            used=200, budget=100,
        )
        mock_proxy.make_request_id.return_value = "req_user_block_abc"

        from app.routes.chat import chat_completions
        response = _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        assert response.status_code == 429
        mock_persist.assert_called_once()
        history_data = mock_persist.call_args.args[0]
        assert history_data["user_id"] == "user_1"
        assert history_data["blocked"] is True
        assert history_data["block_reason"] == "user_budget_exceeded"
        assert history_data["request_id" if False else "id"] == "req_user_block_abc"


@pytest.mark.asyncio
async def test_team_block_persists_history():
    """Team budget block path queues history persistence."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history") as mock_persist, \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(
            mock_proxy, mock_rc, mock_tc, mock_settings,
            used=0, budget=10000,
            team="team_a", team_used=700, team_budget=500,
        )
        mock_proxy.make_request_id.return_value = "req_team_block_abc"

        from app.routes.chat import chat_completions
        response = _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        assert response.status_code == 429
        mock_persist.assert_called_once()
        history_data = mock_persist.call_args.args[0]
        assert history_data["team"] == "team_a"
        assert history_data["blocked"] is True
        assert history_data["block_reason"] == "team_budget_exceeded"


@pytest.mark.asyncio
async def test_success_path_persists_history():
    """Successful completion path queues history persistence."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history") as mock_persist, \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(mock_proxy, mock_rc, mock_tc, mock_settings,
                          used=0, budget=1000)
        mock_proxy.count_tokens.side_effect = [10, 20]
        mock_proxy.make_request_id.return_value = "req_success_abc"

        from app.routes.chat import chat_completions
        response = _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        assert response.status_code == 200
        mock_persist.assert_called_once()
        history_data = mock_persist.call_args.args[0]
        assert history_data["user_id"] == "user_1"
        assert history_data["blocked"] is False
        assert history_data["downgraded"] is False
        assert history_data["input_tokens"] == 10
        assert history_data["output_tokens"] == 20
        assert history_data["total_tokens"] == 30
        assert history_data["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_downgraded_success_persists_with_flag():
    """Downgraded success path persists with downgraded=True."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history") as mock_persist, \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(mock_proxy, mock_rc, mock_tc, mock_settings,
                          used=100, budget=100)
        mock_proxy.count_tokens.side_effect = [10, 20]
        mock_proxy.make_request_id.return_value = "req_downgrade_abc"

        from app.routes.chat import chat_completions
        response = _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        assert response.status_code == 200
        mock_persist.assert_called_once()
        history_data = mock_persist.call_args.args[0]
        assert history_data["downgraded"] is True
        assert history_data["model"] == "tinyllama"
        assert history_data["original_model"] == "llama3.2"


@pytest.mark.asyncio
async def test_request_id_in_response_sentinel():
    """request_id is included in response sentinel object."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history"), \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(mock_proxy, mock_rc, mock_tc, mock_settings,
                          used=0, budget=1000)
        mock_proxy.count_tokens.side_effect = [5, 10]
        mock_proxy.make_request_id.return_value = "req_deterministic_xyz"

        from app.routes.chat import chat_completions
        response = _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        assert response.status_code == 200
        body = response.json()
        assert body["sentinel"]["request_id"] == "req_deterministic_xyz"


@pytest.mark.asyncio
async def test_history_data_includes_ttl_field():
    """Persisted history includes expires_at (TTL) field."""
    with patch("app.routes.chat.proxy") as mock_proxy, \
         patch("app.routes.chat.rc") as mock_rc, \
         patch("app.routes.chat.tc") as mock_tc, \
         patch("app.routes.chat.persist_request_history") as mock_persist, \
         patch("app.routes.chat.manager"), \
         patch("app.routes.chat.settings") as mock_settings:

        _setup_chat_mocks(mock_proxy, mock_rc, mock_tc, mock_settings,
                          used=0, budget=1000)
        mock_proxy.count_tokens.side_effect = [5, 10]
        mock_proxy.make_request_id.return_value = "req_ttl_test"

        from app.routes.chat import chat_completions
        _build_app_and_post(chat_completions, {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Hi"}],
        })

        mock_persist.assert_called_once()
        history_data = mock_persist.call_args.args[0]
        assert "expires_at" in history_data
        assert "timestamp" in history_data

        ts = history_data["timestamp"]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        exp = history_data["expires_at"]
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        # Force both naive so subtraction works regardless of tz mix
        if ts.tzinfo is not None:
            ts = ts.replace(tzinfo=None)
        if exp.tzinfo is not None:
            exp = exp.replace(tzinfo=None)
        delta = exp - ts
        assert delta >= timedelta(days=89)
        assert delta <= timedelta(days=91)
