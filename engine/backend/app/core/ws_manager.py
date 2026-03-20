"""Organic4D Engine — WebSocket 연결 관리 (Phase 3.3).

world_id별 WebSocket 연결 등록·해제, 브로드캐스트
"""
from __future__ import annotations

from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    """world_id별 WebSocket 연결 관리."""

    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    def connect(self, world_id: str, websocket: WebSocket) -> None:
        """연결 등록."""
        if world_id not in self._connections:
            self._connections[world_id] = set()
        self._connections[world_id].add(websocket)

    def disconnect(self, world_id: str, websocket: WebSocket) -> None:
        """연결 해제."""
        if world_id in self._connections:
            self._connections[world_id].discard(websocket)
            if not self._connections[world_id]:
                del self._connections[world_id]

    async def send_to_world(self, world_id: str, message: dict) -> None:
        """해당 world_id의 모든 연결에 메시지 전송."""
        if world_id not in self._connections:
            return
        dead = set()
        for ws in self._connections[world_id]:
            try:
                await ws.send_json(message)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self._connections[world_id].discard(ws)
        if world_id in self._connections and not self._connections[world_id]:
            del self._connections[world_id]


ws_manager = ConnectionManager()
