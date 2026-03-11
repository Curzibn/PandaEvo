from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

router = APIRouter()

_connections: list[WebSocket] = []
_lock = asyncio.Lock()


async def _broadcast(message: dict[str, Any]) -> None:
    async with _lock:
        dead: list[WebSocket] = []
        for ws in _connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            _connections.remove(ws)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    async with _lock:
        _connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        async with _lock:
            if websocket in _connections:
                _connections.remove(websocket)


@router.post("/internal/reload")
async def internal_reload() -> JSONResponse:
    await _broadcast({"type": "reload"})
    return JSONResponse({"ok": True, "clients": len(_connections)})
