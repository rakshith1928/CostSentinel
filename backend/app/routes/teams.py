from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from app.config import settings
from app import team_client as tc

router = APIRouter(prefix="/v1/sentinel/teams")

def _check_key(x_api_key: Optional[str]):
    if settings.sentinel_api_key and x_api_key != settings.sentinel_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

# ── List all teams ─────────────────────────────────────────────────────────────

@router.get("")
async def list_teams(x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    return {"teams": await tc.list_teams()}

# ── Get one team ───────────────────────────────────────────────────────────────

@router.get("/{team}")
async def get_team(team: str, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    return await tc.get_team_status(team)

# ── Create / update team budget ────────────────────────────────────────────────

@router.put("/{team}/budget")
async def set_team_budget(team: str, payload: dict, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    tokens = payload.get("tokens")
    if tokens is None:
        raise HTTPException(status_code=422, detail="tokens field required")
    try:
        await tc.set_team_budget(team, int(tokens))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"team": team, "budget_tokens": int(tokens)}

# ── Add member ─────────────────────────────────────────────────────────────────

@router.post("/{team}/members")
async def add_member(
    team: str,
    payload: dict,
    x_api_key: Optional[str] = Header(default=None),
):
    _check_key(x_api_key)
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=422, detail="user_id required")
    await tc.add_team_member(team, user_id)
    return {"team": team, "user_id": user_id, "action": "added"}

# ── Remove member ──────────────────────────────────────────────────────────────

@router.delete("/{team}/members/{user_id}")
async def remove_member(
    team: str,
    user_id: str,
    x_api_key: Optional[str] = Header(default=None),
):
    _check_key(x_api_key)
    await tc.remove_team_member(team, user_id)
    return {"team": team, "user_id": user_id, "action": "removed"}

# ── Reset team usage ───────────────────────────────────────────────────────────

@router.delete("/{team}/reset")
async def reset_team(
    team: str,
    x_api_key: Optional[str] = Header(default=None),
):
    _check_key(x_api_key)
    await tc.reset_team_usage(team)
    return {"team": team, "reset": True}