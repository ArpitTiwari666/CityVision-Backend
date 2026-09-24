import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket


class ConnectionManager:
    """
    Tracks WebSocket clients per logical channel (e.g. 'alerts', 'feed:CAM-014')
    and broadcasts JSON-serialisable payloads to everyone on that channel.
    """

    def __init__(self):
        self._channels: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._channels.setdefault(channel, set()).add(ws)

    async def disconnect(self, channel: str, ws: WebSocket):
        async with self._lock:
            conns = self._channels.get(channel)
            if conns and ws in conns:
                conns.remove(ws)
                if not conns:
                    self._channels.pop(channel, None)

    async def broadcast(self, channel: str, payload: dict):
        conns = list(self._channels.get(channel, []))
        dead = []
        message = json.dumps(payload, default=str)
        for ws in conns:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        if dead:
            async with self._lock:
                for ws in dead:
                    self._channels.get(channel, set()).discard(ws)


manager = ConnectionManager()
