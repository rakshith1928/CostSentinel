from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from app.config import settings
from app import redis_client as rc
from app import proxy
from app.database import get_session_no_yield

router = APIRouter()


async def _check_database() -> tuple[bool, str | None]:
    """Attempt SELECT 1 against the database. Returns (ok, error_message)."""
    session = await get_session_no_yield()
    try:
        await session.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        await session.close()


@router.get("/health/db")
async def health_db():
    """Database connectivity health check (operator monitoring surface)."""
    db_ok, db_error = await _check_database()
    if db_ok:
        return JSONResponse(status_code=200, content={
            "status": "healthy",
            "database": "connected",
        })
    return JSONResponse(status_code=503, content={
        "status": "unhealthy",
        "database": "disconnected",
        "error": db_error,
    })


@router.get("/health")
async def health():
    redis_ok  = False
    try:
        await rc.redis.ping()
        redis_ok = True
    except Exception:
        pass

    ollama_ok = await proxy.check_ollama()
    models    = await proxy.get_ollama_models()
    db_ok, db_error = await _check_database()

    return {
        "status": "ok" if redis_ok and ollama_ok and db_ok else "degraded",
        "redis": redis_ok,
        "ollama": ollama_ok,
        "database": db_ok,
        "database_error": db_error,
        "available_models": models,
        "config": {
            "default_budget_tokens": settings.default_budget_tokens,
            "hard_limit_multiplier": settings.hard_limit_multiplier,
            "downgrade_model": settings.downgrade_model,
        },
    }