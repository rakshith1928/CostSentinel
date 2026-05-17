from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from app.config import settings
from app.ws_token import issue_token
from app import team_client as tc

router = APIRouter(prefix="/v1/sentinel")

def _check_key(x_api_key: Optional[str]):
    if settings.sentinel_api_key and x_api_key != settings.sentinel_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.post("/auth/ws-token")
async def get_ws_token(
    payload: dict,
    x_api_key: Optional[str] = Header(default=None),
):
    """
    Issue a short-lived WS token for a user.
    Call this from your app before opening the WebSocket.

    Body: { "user_id": "priya" }
    Returns: { "token": "...", "expires_in": 60 }
    """
    _check_key(x_api_key)
    user_id = payload.get("user_id", "").strip()
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id required")

    role = "admin" if settings.is_admin(user_id) else "member"
    team = await tc.get_user_team(user_id)

    token = issue_token(user_id, role, team)
    return {
        "token":      token,
        "user_id":    user_id,
        "role":       role,
        "team":       team,
        "expires_in": 60,
    }