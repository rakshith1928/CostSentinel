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


def test_to_dict_conversion():
    """Test conversion to dictionary for database insertion."""
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

    data_dict = history.to_dict()

    assert data_dict["id"] == "req_test_002"
    assert data_dict["user_id"] == "user_789"
    assert data_dict["team"] == "team_abc"
    assert data_dict["blocked"] is True
    assert data_dict["block_reason"] == "budget_exceeded"


def test_from_dict_conversion():
    """Test reconstruction from database row data."""
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
    
    history = RequestHistory.from_dict(firestore_data)
    
    assert history.id == "req_test_003"
    assert history.user_id == "user_999"
    assert history.team == "team_xyz"
    assert history.downgraded is True
    assert history.blocked is False


def test_expires_at_default_90_days():
    """Test that expires_at is set to 90 days from now by default."""
    now = datetime.utcnow()
    history = RequestHistory.from_request_context(
        request_id="req_ttl_001",
        timestamp=now,
        user_id="ttl_user",
        team=None,
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        blocked=False,
        downgraded=False,
        block_reason=None,
        latency_ms=100,
    )

    expected_expiry = now + timedelta(days=90)
    time_diff = abs((history.expires_at - expected_expiry).total_seconds())

    # Allow 5 second tolerance for test execution time
    assert time_diff < 5, f"expires_at should be ~90 days from now, got {time_diff}s difference"


def test_expires_at_custom_ttl():
    """Test that custom TTL days is respected."""
    now = datetime.utcnow()
    history = RequestHistory.from_request_context(
        request_id="req_ttl_002",
        timestamp=now,
        user_id="ttl_user",
        team=None,
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        blocked=False,
        downgraded=False,
        block_reason=None,
        latency_ms=100,
        ttl_days=30,
    )

    expected_expiry = now + timedelta(days=30)
    time_diff = abs((history.expires_at - expected_expiry).total_seconds())

    assert time_diff < 5, f"expires_at should be ~30 days from now, got {time_diff}s difference"


def test_expires_at_is_future():
    """Test that expires_at is always in the future."""
    history = RequestHistory.from_request_context(
        request_id="req_ttl_003",
        timestamp=datetime.utcnow(),
        user_id="ttl_user",
        team=None,
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        blocked=False,
        downgraded=False,
        block_reason=None,
        latency_ms=100,
    )

    assert history.expires_at > datetime.utcnow()
    assert history.expires_at > history.timestamp


def test_expires_at_in_to_dict():
    """Test that expires_at is included in serialized output."""
    history = RequestHistory.from_request_context(
        request_id="req_ttl_004",
        timestamp=datetime.utcnow(),
        user_id="ttl_user",
        team=None,
        model="ollama/llama2",
        original_model="ollama/llama2",
        input_tokens=10,
        output_tokens=20,
        total_tokens=30,
        blocked=False,
        downgraded=False,
        block_reason=None,
        latency_ms=100,
    )

    data = history.to_dict()
    assert "expires_at" in data
    assert isinstance(data["expires_at"], datetime)
    assert data["expires_at"] > datetime.utcnow()
