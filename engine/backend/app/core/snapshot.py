"""Organic4D Engine — 스냅샷 저장 (Phase 2.3).

매 t (또는 N간격) 스냅샷 메모리/파일
ARCHITECTURE §2.2: World → Snapshot → Cell 계층
"""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Any, Callable, Dict, List, Optional

from app.core.settings import get_snapshot_max_in_memory
from app.models.cell import Cell
from app.models.world import Snapshot


class SnapshotStore:
    """메모리 내 스냅샷 저장소."""

    def __init__(self, world_id: str = "", on_change: Optional[Callable[[], None]] = None):
        self.world_id = world_id
        self._snapshots: Dict[float, Snapshot] = {}
        self._index: Dict[float, Dict[str, Any]] = {}
        self._archived_t: List[float] = []
        self._on_change = on_change

    def _notify(self) -> None:
        if self._on_change is not None:
            self._on_change()

    def _build_index_entry(self, snap: Snapshot) -> Dict[str, Any]:
        digest = sha256(
            "|".join(
                f"{cell.cell_id}:{cell.energy:.4f}:{cell.x:.3f}:{cell.y:.3f}:{cell.zone_id}"
                for cell in snap.cells
            ).encode("utf-8")
        ).hexdigest()[:16]
        return {
            "t": float(snap.t),
            "cell_count": len(snap.cells),
            "total_energy": float(sum(float(cell.energy) for cell in snap.cells)),
            "created_at": (snap.created_at or datetime.now(timezone.utc)).isoformat(),
            "digest": digest,
        }

    def _archive_t(self, t: float) -> None:
        value = float(t)
        if value not in self._archived_t:
            self._archived_t.append(value)
            self._archived_t.sort()

    def _trim(self) -> None:
        limit = get_snapshot_max_in_memory()
        if len(self._snapshots) <= limit:
            return
        keep = set(sorted(self._snapshots.keys())[-limit:])
        to_archive = [t for t in self._snapshots.keys() if t not in keep]
        self._snapshots = {t: snap for t, snap in self._snapshots.items() if t in keep}
        for t in to_archive:
            self._archive_t(t)

    def save(self, t: float, cells: List[Cell]) -> Snapshot:
        """t 시점 스냅샷 저장."""
        snap = Snapshot(world_id=self.world_id, t=t, cells=list(cells))
        self._snapshots[t] = snap
        self._index[float(t)] = self._build_index_entry(snap)
        self._trim()
        self._notify()
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
        for t in self._snapshots.keys():
            self._archive_t(t)
        self._snapshots.clear()
        self._notify()

    def clear_after(self, t_keep: float, eps: float = 1e-9) -> int:
        """t_keep 초과인 스냅샷만 제거 (주입 후 t>t_keep 재계산용). 제거 개수 반환."""
        to_del = [k for k in self._snapshots if k > t_keep + eps]
        for k in to_del:
            del self._snapshots[k]
            self._archive_t(k)
        if to_del:
            self._notify()
        return len(to_del)

    def load_snapshots(
        self,
        snapshots: List[Snapshot],
        *,
        snapshot_index: Optional[List[Dict[str, Any]]] = None,
        archived_t: Optional[List[float]] = None,
    ) -> None:
        """Load persisted snapshots into memory."""
        self._snapshots = {float(snap.t): snap for snap in snapshots}
        self._index = {
            float(item.get("t", 0.0)): dict(item)
            for item in (snapshot_index or [])
            if isinstance(item, dict)
        }
        for snap in snapshots:
            self._index.setdefault(float(snap.t), self._build_index_entry(snap))
        self._archived_t = sorted({float(t) for t in (archived_t or [])})
        self._trim()

    def snapshot_index(self) -> List[Dict[str, Any]]:
        return [dict(self._index[t]) for t in sorted(self._index.keys())]

    def archive_summary(self) -> Dict[str, Any]:
        return {
            "archived_count": len(self._archived_t),
            "archived_t": list(self._archived_t),
        }
