"""WebSocket connection manager for live updates (currency rates, etc.)."""
import asyncio
import json
from typing import Any

from fastapi import WebSocket


class ConnectionManager:
    """Tracks active WebSocket connections per company and broadcasts messages."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, company_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections.setdefault(company_id, set()).add(websocket)

    async def disconnect(self, company_id: str, websocket: WebSocket) -> None:
        async with self._lock:
            conns = self._connections.get(company_id)
            if conns:
                conns.discard(websocket)
                if not conns:
                    self._connections.pop(company_id, None)

    async def broadcast(self, company_id: str, event: str, payload: Any) -> None:
        """Send a JSON message to every socket of a company (best-effort)."""
        message = json.dumps({"event": event, "data": payload}, default=str)
        async with self._lock:
            conns = list(self._connections.get(company_id, set()))
        dead: list[WebSocket] = []
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections.get(company_id, set()).discard(ws)


manager = ConnectionManager()
