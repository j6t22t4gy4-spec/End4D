"""Organic4D Engine — WebSocket 엔드포인트 (Phase 3.3).

GET /worlds/{id}/ws — 시뮬레이션 스트리밍
연결 시 t, 세포 수, 스냅샷 델타 수신
"""
from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.store import world_store
from app.core.ws_manager import ws_manager


router = APIRouter(prefix="/worlds", tags=["ws"])


@router.websocket("/{world_id}/ws")
async def websocket_endpoint(websocket: WebSocket, world_id: str):
    """월드 시뮬레이션 WebSocket 스트리밍."""
    entry = world_store.get(world_id)
    if entry is None:
        await websocket.close(code=4000, reason="World not found")
        return

    await websocket.accept()
    ws_manager.connect(world_id, websocket)

    try:
        while True:
            data = await websocket.receive_text()
            # 클라이언트 메시지 처리 (필요 시 ping/pong, run 트리거 등)
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        ws_manager.disconnect(world_id, websocket)
