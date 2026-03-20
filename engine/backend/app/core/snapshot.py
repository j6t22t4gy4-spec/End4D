"""Organic4D Engine — 스냅샷 저장 (Phase 2.3).

매 t (또는 N간격) 스냅샷 메모리/파일
ARCHITECTURE §2.2: World → Snapshot → Cell 계층
"""
from __future__ import annotations

from typing import Dict, List, Optional

from app.models.cell import Cell
from app.models.world import Snapshot


class SnapshotStore:
    """메모리 내 스냅샷 저장소."""

    def __init__(self, world_id: str = ""):
        self.world_id = world_id
        self._snapshots: Dict[float, Snapshot] = {}

    def save(self, t: float, cells: List[Cell]) -> Snapshot:
        """t 시점 스냅샷 저장."""
        snap = Snapshot(world_id=self.world_id, t=t, cells=list(cells))
        self._snapshots[t] = snap
        return snap

    def get(self, t: float) -> Optional[Snapshot]:
        """t 시점 스냅샷 조회."""
        return self._snapshots.get(t)

    def get_nearest(self, t: float) -> Optional[Snapshot]:
        """t에 가장 가까운 스냅샷 조회."""
        if not self._snapshots:
            return None
        best = min(self._snapshots.keys(), key=lambda k: abs(k - t))
        return self._snapshots[best]

    def list_t(self) -> List[float]:
        """저장된 t 목록 (정렬)."""
        return sorted(self._snapshots.keys())

    def clear(self) -> None:
        """전체 삭제."""
        self._snapshots.clear()
