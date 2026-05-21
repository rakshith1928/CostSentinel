"""Tests for RequestHistory model."""

from datetime import datetime, timedelta
from app.models.request_history import RequestHistory


def test_request_history_creation():
    """Test basic RequestHistory creation."""
    history = RequestHistory(
        id="req_1234567890_abc123",
        timestamp=datetime.utcnow(),
        user_id="user_123",
        team="team_456",
        model="ollama/llama2",
        original_model="ollama/mistral",
        input_tokens=150,
        output_tokens=300,
        total_tokens=450,
        blocked=False,
        downgraded=True,
        block_reason=None,
        latency_ms=234,
        expires_at=datetime.utcnow() + timedelta(days=90),
    )
    
    assert history.id == "req_1234567890_abc123"
    assert history.user_id == "user_123"
    assert history.team == "team_456"
    assert history.total_tokens == 450
    assert history.downgraded is True
    assert history.blocked is False


def test_from_request_context():
    """Test factory function creates valid instance."""
    now = datetime.utcnow()
    history = RequestHistory.from_request_context(
        request_id="req_test_001",
        timestamp=now,
        user_id="test_user",
        team=None,
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=100,
        output_tokens=200,
        total_tokens=300,
        blocked=False,
        downgraded=False,
        block_reason=None,
        latency_ms=150,
        ttl_days=90,
    )
    
    assert history.id == "req_test_001"
    assert history.user_id == "test_user"
    assert history.team is None
    assert history.input_tokens == 100
    assert history.output_tokens == 200
    assert history.total_tokens == 300
    assert history.latency_ms == 150
    assert history.expires_at > now
    assert history.expires_at.day == (now + timedelta(days=90)).day


def test_to_firestore_conversion():
    """Test conversion to Firestore dictionary."""
    history = RequestHistory.from_request_context(
        request_id="req_test_002",
        timestamp=datetime.utcnow(),
        user_id="user_789",
        team="team_abc",
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=50,
        output_tokens=100,
        total_tokens=150,
        blocked=True,
        downgraded=False,
        block_reason="budget_exceeded",
        latency_ms=100,
        ttl_days=90,
    )
    
    firestore_dict = history.to_firestore()
    
    assert firestore_dict["id"] == "req_test_002"
    assert firestore_dict["user_id"] == "user_789"
    assert firestore_dict["team"] == "team_abc"
    assert firestore_dict["blocked"] is True
    assert firestore_dict["block_reason"] == "budget_exceeded"


def test_from_firestore_conversion():
    """Test reconstruction from Firestore data."""
    now = datetime.utcnow()
    firestore_data = {
        "id": "req_test_003",
        "timestamp": now,
        "user_id": "user_999",
        "team": "team_xyz",
        "model": "ollama/tinyllama",
        "original_model": "ollama/llama2",
        "input_tokens": 75,
        "output_tokens": 125,
        "total_tokens": 200,
        "blocked": False,
        "downgraded": True,
        "block_reason": None,
        "latency_ms": 180,
        "expires_at": now + timedelta(days=90),
    }
    
    history = RequestHistory.from_firestore(firestore_data)
    
    assert history.id == "req_test_003"
    assert history.user_id == "user_999"
    assert history.team == "team_xyz"
    assert history.downgraded is True
    assert history.blocked is False
