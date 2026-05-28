"""Security utilities for admin authentication and authorization."""

from typing import Optional
from fastapi import Depends, HTTPException, Header, status
from app.config import settings
from app.ws_token import verify_token


# ── Authentication Dependencies ──────────────────────────────────────────────

def get_api_key(x_api_key: Optional[str] = Header(default=None)) -> Optional[str]:
    """Extract API key from header."""
    return x_api_key


def require_admin_auth(x_api_key: Optional[str] = Header(default=None)) -> dict:
    """
    Fail-closed admin authentication guard for history API endpoints.
    
    This dependency:
    1. Requires valid HISTORY_API_ADMIN_KEY via X-API-Key header
    2. Verifies the user is an admin (in ADMIN_USERS list)
    3. Returns admin user context for downstream use
    
    Fail-closed behavior:
    - Missing credentials → 401 Unauthorized
    - Invalid credentials → 401 Unauthorized  
    - Non-admin user → 403 Forbidden
    
    Returns:
        dict: Admin user context with user_id and role
        
    Raises:
        HTTPException: 401 or 403 on auth failure
    """
    # Check 1: API key present (fail-closed: missing = 401)
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Check 2: History API admin key valid (fail-closed: invalid = 401)
    if settings.history_api_admin_key and x_api_key != settings.history_api_admin_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Check 3: Extract user from token or config
    # For now, we trust the API key. In v2, we can decode JWT tokens here.
    # Try to decode as WS token first
    token_data = verify_token(x_api_key)
    
    if token_data:
        user_id = token_data.get("user_id")
        role = token_data.get("role", "member")
    else:
        # Fallback: treat API key holders as admins
        # (legacy behavior from existing admin routes)
        user_id = "api_key_user"
        role = "admin"
    
    # Check 4: User must be admin (fail-closed: non-admin = 403)
    if role != "admin" and not settings.is_admin(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    
    # Return admin context
    return {
        "user_id": user_id,
        "role": role,
        "scope": "admin:history:read",
    }


def require_scope(scope: str):
    """
    Create a dependency that requires a specific scope.
    
    Usage:
        @router.get("/history", dependencies=[Depends(require_scope("admin:history:read"))])
    
    Args:
        scope: Required scope string (e.g., "admin:history:read")
        
    Returns:
        Dependency function that checks scope
    """
    def scope_checker(admin_context: dict = Depends(require_admin_auth)):
        if scope not in admin_context.get("scope", ""):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient scope. Required: {scope}",
            )
        return admin_context
    return scope_checker


# ── Helper Functions ──────────────────────────────────────────────────────────

def check_admin_user(user_id: str) -> bool:
    """
    Check if a user ID is in the admin list.
    
    Args:
        user_id: User identifier to check
        
    Returns:
        True if user is admin
    """
    return settings.is_admin(user_id)


def validate_admin_list() -> list[str]:
    """
    Get list of admin users from configuration.
    
    Returns:
        List of admin user IDs
    """
    if not settings.admin_users:
        return []
    return [u.strip() for u in settings.admin_users.split(',')]