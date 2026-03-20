"""Organic4D Engine — 인메모리 월드 저장소 (Phase 3.1.1).

world_id → {World, SnapshotStore, 실행 상태} 매핑
ARCHITECTURE_CHECKLIST 1.3: 엔진 격리는 world_id 기준
"""
from __future__ import annotations

from typing import Dict, Optional
import uuid

from app.models.world import World
from app.core.snapshot import SnapshotStore


class WorldStore:
    """인메모리 월드 저장소."""

    def __init__(self):
        self._worlds: Dict[str, dict] = {}

    def create(
        self,
        t_max: float,
        initial_cell_count: int = 5,
        world_id: Optional[str] = None,
    ) -> str:
        """월드 생성. world_id 반환."""
        wid = world_id or str(uuid.uuid4())
        store = SnapshotStore(world_id=wid)
        world = World(
            world_id=wid,
            t_max=t_max,
            initial_cells=[],  # cells는 run 시 생성
            nutrients=[],
        )
        self._worlds[wid] = {
            "world": world,
            "snapshot_store": store,
            "status": "idle",
            "initial_cell_count": initial_cell_count,
        }
        return wid

    def get(self, world_id: str) -> Optional[dict]:
        """월드 정보 조회."""
        return self._worlds.get(world_id)

    def get_world(self, world_id: str) -> Optional[World]:
        """World 객체 조회."""
        entry = self._worlds.get(world_id)
        return entry["world"] if entry else None

    def get_snapshot_store(self, world_id: str) -> Optional[SnapshotStore]:
        """SnapshotStore 조회."""
        entry = self._worlds.get(world_id)
        return entry["snapshot_store"] if entry else None

    def set_status(self, world_id: str, status: str) -> None:
        """실행 상태 설정 (idle, running, done)."""
        if world_id in self._worlds:
            self._worlds[world_id]["status"] = status

    def get_initial_cell_count(self, world_id: str) -> int:
        """초기 세포 수."""
        entry = self._worlds.get(world_id)
        return entry.get("initial_cell_count", 5) if entry else 5


# 전역 싱글톤 (엔진 격리는 world_id로)
world_store = WorldStore()
