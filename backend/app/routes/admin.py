from typing import Optional
from fastapi import APIRouter, HTTPException, Header
from app.config import settings
from app import redis_client as rc

router = APIRouter(prefix="/v1/sentinel")

def _check_key(x_api_key: Optional[str]):
    if settings.sentinel_api_key and x_api_key != settings.sentinel_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

@router.get("/users")
async def list_users(x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    return {"users": await rc.list_users()}

@router.get("/usage/{user_id}")
async def get_usage(user_id: str, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    return await rc.get_user_detail(user_id)

@router.put("/budget/{user_id}")
async def set_budget(user_id: str, payload: dict, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    tokens = payload.get("tokens")
    if tokens is None:
        raise HTTPException(status_code=422, detail="tokens field required")
    tokens = int(tokens)
    if tokens <= 0:
        raise HTTPException(status_code=422, detail="Budget must be positive")
    await rc.set_budget(user_id, tokens)
    return {"user_id": user_id, "budget_tokens": tokens}

@router.delete("/usage/{user_id}/reset")
async def reset_usage(user_id: str, x_api_key: Optional[str] = Header(default=None)):
    _check_key(x_api_key)
    await rc.reset_usage(user_id)
    return {"user_id": user_id, "reset": True}