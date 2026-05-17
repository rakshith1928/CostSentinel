import json
import asyncio
from dataclasses import dataclass, field
from fastapi import WebSocket

@dataclass
class Connection:
    ws:      WebSocket
    user_id: str
    role:    str          # "admin" or "member"
    team:    str | None

class ConnectionManager:
    def __init__(self):
        self._connections: list[Connection] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, user_id: str,
                      role: str, team: str | None):
        await ws.accept()
        async with self._lock:
            self._connections.append(Connection(ws, user_id, role, team))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections = [c for c in self._connections if c.ws is not ws]

    def _should_receive(self, conn: Connection, payload: dict) -> bool:
        """Admin sees everything. Members see only their own events."""
        if conn.role == 'admin':
            return True
        event_user = payload.get('user_id')
        # snapshot and system events go to everyone
        if payload.get('type') in ('snapshot', 'system'):
            return True
        return event_user == conn.user_id

    async def broadcast(self, payload: dict):
        if not self._connections:
            return
        async with self._lock:
            live = list(self._connections)
        dead = []
        for conn in live:
            if not self._should_receive(conn, payload):
                continue
            try:
                await conn.ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(conn.ws)
        for ws in dead:
            await self.disconnect(ws)

    async def broadcast_all(self, payload: dict):
        """Send to every connection regardless of scope — for system events."""
        async with self._lock:
            live = list(self._connections)
        dead = []
        for conn in live:
            try:
                await conn.ws.send_text(json.dumps(payload))
            except Exception:
                dead.append(conn.ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def count(self) -> int:
        return len(self._connections)

manager = ConnectionManager()