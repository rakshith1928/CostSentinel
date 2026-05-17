import hmac
import hashlib
import time
import json
import base64
from app.config import settings

# Tokens expire after 60 seconds — enough time to open the dashboard
# but too short to be reused if intercepted
TOKEN_TTL = 60

def _sign(payload: dict) -> str:
    body = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(',', ':')).encode()
    ).decode()
    sig = hmac.new(
        settings.ws_token_secret.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{sig}"

def _verify(token: str) -> dict | None:
    try:
        body, sig = token.rsplit('.', 1)
        expected = hmac.new(
            settings.ws_token_secret.encode(),
            body.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(sig, expected):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body))
        if time.time() > payload.get('exp', 0):
            return None
        return payload
    except Exception:
        return None

def issue_token(user_id: str, role: str, team: str | None = None) -> str:
    return _sign({
        'user_id': user_id,
        'role':    role,
        'team':    team,
        'exp':     int(time.time()) + TOKEN_TTL,
    })

def verify_token(token: str) -> dict | None:
    return _verify(token)