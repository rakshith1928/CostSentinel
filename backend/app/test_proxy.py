"""Tests for proxy utilities including deterministic request ID generation."""

import pytest
from app import proxy


def test_make_request_id_deterministic():
    """Same request content produces identical ID on retry."""
    user_id = "user_123"
    model = "llama3.2"
    messages = [{"role": "user", "content": "Hello"}]

    id1 = proxy.make_request_id(user_id, model, messages)
    id2 = proxy.make_request_id(user_id, model, messages)

    assert id1 == id2


def test_make_request_id_different_user():
    """Different user_id produces different ID."""
    model = "llama3.2"
    messages = [{"role": "user", "content": "Hello"}]

    id1 = proxy.make_request_id("user_1", model, messages)
    id2 = proxy.make_request_id("user_2", model, messages)

    assert id1 != id2


def test_make_request_id_different_model():
    """Different model produces different ID."""
    user_id = "user_123"
    messages = [{"role": "user", "content": "Hello"}]

    id1 = proxy.make_request_id(user_id, "llama3.2", messages)
    id2 = proxy.make_request_id(user_id, "tinyllama", messages)

    assert id1 != id2


def test_make_request_id_different_messages():
    """Different messages produces different ID."""
    user_id = "user_123"
    model = "llama3.2"

    id1 = proxy.make_request_id(user_id, model, [{"role": "user", "content": "Hello"}])
    id2 = proxy.make_request_id(user_id, model, [{"role": "user", "content": "World"}])

    assert id1 != id2


def test_make_request_id_format():
    """ID follows req_{hash_timestamp}_{hash} format (both hex)."""
    user_id = "user_123"
    model = "llama3.2"
    messages = [{"role": "user", "content": "Hello"}]

    request_id = proxy.make_request_id(user_id, model, messages)

    assert request_id.startswith("req_")
    parts = request_id.split("_")
    assert len(parts) == 3
    assert parts[0] == "req"
    assert len(parts[1]) == 12  # 12-char hex timestamp portion
    assert len(parts[2]) == 8   # 8-char hash suffix
    # Both parts should be valid hex
    int(parts[1], 16)
    int(parts[2], 16)


def test_make_request_id_message_order_matters():
    """Different message order produces different ID (order matters for conversation)."""
    user_id = "user_123"
    model = "llama3.2"

    messages1 = [{"role": "user", "content": "A"}, {"role": "assistant", "content": "B"}]
    messages2 = [{"role": "assistant", "content": "B"}, {"role": "user", "content": "A"}]

    id1 = proxy.make_request_id(user_id, model, messages1)
    id2 = proxy.make_request_id(user_id, model, messages2)

    # Different order = different conversation = different ID
    assert id1 != id2