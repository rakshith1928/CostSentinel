import time
import hashlib
import json
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

def make_request_id(user_id: str, model: str, messages: list) -> str:
    """
    Generate deterministic request ID for idempotent retries.
    
    Format: req_{timestamp}_{hash}
    timestamp = first 12 chars of content hash (deterministic)
    hash = last 8 chars of content hash
    
    Same request content produces same ID on retry.
    """
    messages_json = json.dumps(messages, sort_keys=True, separators=(",", ":"))
    content = f"{user_id}|{model}|{messages_json}"
    full_hash = hashlib.md5(content.encode()).hexdigest()
    timestamp_part = full_hash[:12]
    hash_suffix = full_hash[12:20]
    return f"req_{timestamp_part}_{hash_suffix}"

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