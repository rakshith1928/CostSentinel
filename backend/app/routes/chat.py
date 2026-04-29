import time
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse
from app.config import settings
from app import redis_client as rc
from app import proxy

router = APIRouter()

def _check_key(x_api_key: Optional[str]):
    if settings.sentinel_api_key and x_api_key != settings.sentinel_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")