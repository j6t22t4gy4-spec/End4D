"""Organic4D Engine — 월드 저장소 (Phase 3.1.1).

world_id → {World, SnapshotStore, 실행 상태} 매핑
ARCHITECTURE_CHECKLIST 1.3: 엔진 격리는 world_id 기준
"""
from __future__ import annotations

from typing import Dict, Optional
import uuid

from app.core.config_versions import build_simulation_config, simulation_config_version
from app.core.persistence import DiskWorldPersistence, WorldPersistenceBackend
from app.core.session_store import session_store
from app.core.settings import get_persistence_backend, get_state_dir
from app.core.snapshot import SnapshotStore
from app.models.world import World


class WorldStore:
    """월드 저장소. 기본은 disk+memory cache."""

    def __init__(self):
        self._worlds: Dict[str, dict] = {}
        backend = get_persistence_backend()
        self._persistence: Optional[WorldPersistenceBackend] = (
            DiskWorldPersistence(get_state_dir()) if backend == "disk" else None
        )
        self._preload()

    def _preload(self) -> None:
        if self._persistence is None:
            return
        for world_id in self._persistence.list_world_ids():
            self._load_from_persistence(world_id)

    def _make_snapshot_store(self, world_id: str) -> SnapshotStore:
        return SnapshotStore(
            world_id=world_id,
            on_change=lambda wid=world_id: self._persist(wid),
        )

    def _persist(self, world_id: str) -> None:
        if self._persistence is None:
            return
        entry = self._worlds.get(world_id)
        if entry is None:
            return
        self._persistence.save(world_id, entry)

    def _load_from_persistence(self, world_id: str) -> Optional[dict]:
        if self._persistence is None:
            return None
        payload = self._persistence.load(world_id)
        if payload is None:
            return None
        store = self._make_snapshot_store(world_id)
        store.load_snapshots(payload.pop("snapshots", []))
        entry = {**payload, "snapshot_store": store}
        self._worlds[world_id] = entry
        return entry

    def create(
        self,
        t_max: float,
        initial_cell_count: int = 5,
        world_id: Optional[str] = None,
        genesis_prompt: Optional[str] = None,
        genesis_rationale: Optional[str] = None,
        role_catalog: Optional[list] = None,
        t_step_semantic: str = "1 스텝 ≈ 1일 (기본)",
        t_step_unit: str = "day",
        nutrient_per_step: float = 1.0,
        persona_country: str = "",
        persona_source: str = "",
        persona_catalog: Optional[list] = None,
        engine_params: Optional[dict] = None,
        simulation_config: Optional[dict] = None,
        config_version: str = "",
        comparison_meta: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> str:
        """월드 생성. world_id 반환."""
        wid = world_id or str(uuid.uuid4())
        store = self._make_snapshot_store(wid)
        world = World(
            world_id=wid,
            t_max=t_max,
            initial_cells=[],  # cells는 run 시 생성
            nutrients=[],
            t_step_semantic=t_step_semantic,
            t_step_unit=t_step_unit,
            nutrient_per_step=float(nutrient_per_step),
        )
        params = dict(engine_params or {})
        config = simulation_config or build_simulation_config(
            t_max=float(t_max),
            initial_cell_count=int(initial_cell_count),
            role_catalog=list(role_catalog) if role_catalog else ["agent"],
            t_step_semantic=t_step_semantic,
            t_step_unit=t_step_unit,
            nutrient_per_step=float(nutrient_per_step),
            persona_country=persona_country,
            persona_source=persona_source,
            engine_params=params,
            comparison_meta=dict(comparison_meta or {}),
        )
        version = config_version or simulation_config_version(config)
        session = session_store.ensure(
            session_id,
            title=(genesis_prompt or "").strip()[:80],
        )
        self._worlds[wid] = {
            "world": world,
            "snapshot_store": store,
            "status": "idle",
            "initial_cell_count": initial_cell_count,
            "genesis_prompt": genesis_prompt,
            "genesis_rationale": genesis_rationale,
            "role_catalog": list(role_catalog) if role_catalog else ["agent"],
            "persona_country": persona_country,
            "persona_source": persona_source,
            "persona_catalog": list(persona_catalog or []),
            "engine_params": params,
            "simulation_config": dict(config),
            "config_version": version,
            "comparison_meta": dict(comparison_meta or {}),
            "session_id": str(session.get("session_id") or ""),
        }
        session_store.attach_world(str(session.get("session_id") or ""), wid)
        self._persist(wid)
        return wid

    def get(self, world_id: str) -> Optional[dict]:
        """월드 정보 조회."""
        if world_id not in self._worlds:
            self._load_from_persistence(world_id)
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
            self._persist(world_id)

    def get_initial_cell_count(self, world_id: str) -> int:
        """초기 세포 수."""
        entry = self._worlds.get(world_id)
        return entry.get("initial_cell_count", 5) if entry else 5

    def get_role_catalog(self, world_id: str) -> list:
        """세계별 역할 카탈로그 (초기 세포에 순환 부여)."""
        entry = self._worlds.get(world_id)
        if not entry:
            return ["agent"]
        return list(entry.get("role_catalog") or ["agent"])

    def get_nutrient_per_step(self, world_id: str) -> float:
        """Genesis가 정한 스텝당 영양 유입 (성장·에너지)."""
        w = self.get_world(world_id)
        if w is None:
            return 1.0
        return float(w.nutrient_per_step)

    def get_persona_catalog(self, world_id: str) -> list:
        """세계별 초기 페르소나 seed 목록."""
        entry = self._worlds.get(world_id)
        if not entry:
            return []
        return list(entry.get("persona_catalog") or [])

    def get_engine_params(self, world_id: str) -> dict:
        entry = self._worlds.get(world_id)
        if not entry:
            return {}
        params = entry.get("engine_params")
        if params is not None:
            return dict(params)
        config = dict(entry.get("simulation_config") or {})
        return dict(config.get("engine_params") or {})

    def clone_from_snapshot(
        self,
        source_world_id: str,
        *,
        snapshot_t: float,
        world_id: Optional[str] = None,
    ) -> Optional[str]:
        """Create a new world entry that starts from a stored snapshot."""
        source = self.get(source_world_id)
        if source is None:
            return None
        source_store = source["snapshot_store"]
        snap = source_store.get(snapshot_t)
        if snap is None:
            return None

        new_world_id = self.create(
            t_max=float(source["world"].t_max),
            initial_cell_count=len(snap.cells),
            world_id=world_id,
            genesis_prompt=source.get("genesis_prompt"),
            genesis_rationale=source.get("genesis_rationale"),
            role_catalog=list(source.get("role_catalog") or []),
            t_step_semantic=source["world"].t_step_semantic,
            t_step_unit=source["world"].t_step_unit,
            nutrient_per_step=float(source["world"].nutrient_per_step),
            persona_country=str(source.get("persona_country") or ""),
            persona_source=str(source.get("persona_source") or ""),
            persona_catalog=list(source.get("persona_catalog") or []),
            engine_params=dict(source.get("engine_params") or {}),
            simulation_config=dict(source.get("simulation_config") or {}),
            config_version=str(source.get("config_version") or ""),
            comparison_meta={
                "parent_world_id": source_world_id,
                "restored_from_t": float(snapshot_t),
                "mode": "fork",
                "baseline_config_version": str(source.get("config_version") or ""),
            },
            session_id=str(source.get("session_id") or ""),
        )
        new_entry = self.get(new_world_id)
        if new_entry is None:
            return None
        new_entry["snapshot_store"].save(float(snapshot_t), [c.copy() for c in snap.cells])
        self._persist(new_world_id)
        return new_world_id


# 전역 싱글톤 (엔진 격리는 world_id로)
world_store = WorldStore()
