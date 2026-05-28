import pytest
from fastapi import HTTPException, status, Depends
from unittest.mock import patch, MagicMock
from app.security import (
    require_admin_auth,
    require_scope,
    check_admin_user,
    validate_admin_list,
    get_api_key,
)
def test_get_api_key():
    """Test API key extraction from header."""
    result = get_api_key(x_api_key="test-key-123")
    assert result == "test-key-123"
def test_get_api_key_missing():
    """Test missing API key returns None."""
    result = get_api_key(x_api_key=None)
    assert result is None
def test_require_admin_auth_missing_key():
    """Test fail-closed: missing key raises 401."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.history_api_admin_key = "history-key"
        mock_settings.is_admin.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            require_admin_auth(x_api_key=None)
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Missing API key" in str(exc_info.value.detail)
def test_require_admin_auth_invalid_key():
    """Test fail-closed: invalid key raises 401."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.history_api_admin_key = "history-key"
        mock_settings.is_admin.return_value = False
        
        with pytest.raises(HTTPException) as exc_info:
            require_admin_auth(x_api_key="wrong-key")
        
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid API key" in str(exc_info.value.detail)
def test_require_admin_auth_non_admin():
    """Test fail-closed: non-admin user raises 403."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.history_api_admin_key = ""  # Skip key validation
        mock_settings.is_admin.return_value = False
        
        with patch("app.security.verify_token") as mock_verify:
            mock_verify.return_value = {"user_id": "regular_user", "role": "member"}
            
            with pytest.raises(HTTPException) as exc_info:
                require_admin_auth(x_api_key="valid-key")
            
            assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
            assert "Admin access required" in str(exc_info.value.detail)
def test_require_admin_auth_valid_admin():
    """Test valid admin returns context."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.history_api_admin_key = ""  # Skip key validation
        mock_settings.is_admin.return_value = True
        
        with patch("app.security.verify_token") as mock_verify:
            mock_verify.return_value = {"user_id": "admin_user", "role": "admin"}
            
            result = require_admin_auth(x_api_key="valid-key")
            
            assert result["user_id"] == "admin_user"
            assert result["role"] == "admin"
            assert result["scope"] == "admin:history:read"
def test_require_scope_insufficient():
    """Test scope check fails with insufficient scope."""
    mock_admin_context = {"scope": "admin:users:read"}
    
    # Create scope checker and call it directly with mocked context
    scope_checker = require_scope("admin:history:read")
    
    with pytest.raises(HTTPException) as exc_info:
        # Bypass FastAPI's Depends by calling with direct argument
        scope_checker.__call__(mock_admin_context)
    
    assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
    assert "Insufficient scope" in str(exc_info.value.detail)


def test_require_scope_sufficient():
    """Test scope check passes with correct scope."""
    mock_admin_context = {"scope": "admin:history:read"}
    
    scope_checker = require_scope("admin:history:read")
    
    # Call with valid scope - should not raise
    result = scope_checker.__call__(mock_admin_context)
    
    assert result == mock_admin_context
def test_check_admin_user():
    """Test admin user check."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.is_admin.return_value = True
        assert check_admin_user("alice") is True
        
        mock_settings.is_admin.return_value = False
        assert check_admin_user("bob") is False
def test_validate_admin_list():
    """Test admin list validation."""
    with patch("app.security.settings") as mock_settings:
        mock_settings.admin_users = "alice,bob,charlie"
        admins = validate_admin_list()
        assert admins == ["alice", "bob", "charlie"]
        
        mock_settings.admin_users = ""
        admins = validate_admin_list()
        assert admins == []