import asyncio
import logging
from fastapi import WebSocket

from app.core.config import settings

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> bool:
        if len(self.active_connections) >= settings.ws_max_connections:
            await websocket.close(code=1008, reason="Max connections exceeded")
            return False
        
        self.active_connections.append(websocket)
        logger.debug(f"WebSocket connected. Active connections: {len(self.active_connections)}")
        return True

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.debug(f"WebSocket disconnected. Active connections: {len(self.active_connections)}")

    async def broadcast_json(self, payload: dict):
        if not self.active_connections:
            logger.debug("Broadcast skipped: 0 active connections.")
            return
            
        snapshot = list(self.active_connections)
        sends = [ws.send_json(payload) for ws in snapshot]
        results = await asyncio.gather(*sends, return_exceptions=True)
        
        for ws, result in zip(snapshot, results):
            if isinstance(result, Exception):
                logger.error(f"Error broadcasting to client, evicting: {result}")
                try:
                    await ws.close()
                except Exception:
                    pass
                self.disconnect(ws)

manager = ConnectionManager()
