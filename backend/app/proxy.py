import time
import hashlib
import httpx
import tiktoken
from datetime import datetime, timezone
from app.config import settings

enc = tiktoken.get_encoding("cl100k_base")

def count_tokens(text: str) -> int:
    try:
        return len(enc.encode(text))
    except Exception:
        return len(text) // 4

def resolve_user(request) -> str:
    return request.headers.get("X-User-ID") or request.client.host or "anonymous"

def make_request_id() -> str:
    return hashlib.md5(str(time.time()).encode()).hexdigest()[:8]

async def call_ollama(model: str, messages: list, options: dict = None) -> dict:
    body = {"model": model, "messages": messages, "stream": False}
    if options:
        body["options"] = options
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(f"{settings.ollama_url}/api/chat", json=body)
        resp.raise_for_status()
        return resp.json()

async def get_ollama_models() -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{settings.ollama_url}/api/tags")
            return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []

async def check_ollama() -> bool:
    try:
        async with httpx.AsyncClient(timeout=3) as c:
            r = await c.get(f"{settings.ollama_url}/api/tags")
            return r.status_code == 200
    except Exception:
        return False