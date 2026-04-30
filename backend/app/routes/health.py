from fastapi import APIRouter
from app.config import settings
from app import redis_client as rc
from app import proxy

router = APIRouter()

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

    return {
        "status": "ok" if redis_ok and ollama_ok else "degraded",
        "redis": redis_ok,
        "ollama": ollama_ok,
        "available_models": models,
        "config": {
            "default_budget_tokens": settings.default_budget_tokens,
            "hard_limit_multiplier": settings.hard_limit_multiplier,
            "downgrade_model": settings.downgrade_model,
        },
    }