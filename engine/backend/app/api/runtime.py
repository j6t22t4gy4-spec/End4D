"""Local runtime status API for packaged engine deployments."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.data_packs import local_runtime_status, sync_data_pack_manifest

router = APIRouter(prefix="/runtime", tags=["runtime"])


class RuntimePackResponse(BaseModel):
    pack_id: str
    kind: str
    country: str
    version: str
    relative_path: str = ""
    path: str = ""
    installed: bool = False
    license: str = ""
    source_url: str = ""
    dataset_id: str = ""
    updated_at: str = ""
    description: str = ""


class RuntimeLlmResponse(BaseModel):
    enabled: bool = False
    provider: str = "stub"
    model: str = "stub"
    base_url: str = ""


class LocalRuntimeStatusResponse(BaseModel):
    runtime_profile: str
    state_dir: str
    data_cache_dir: str
    manifest_path: str
    remote_manifest_url: str = ""
    llm: RuntimeLlmResponse
    installed_pack_count: int
    available_countries: List[str] = Field(default_factory=list)
    packs: List[RuntimePackResponse] = Field(default_factory=list)


class DataPackSyncRequest(BaseModel):
    remote_url: str = ""


class DataPackSyncResponse(BaseModel):
    schema_version: str
    source: str = ""
    synced: bool = False
    pack_count: int = 0
    installed_pack_count: int = 0


@router.get("/local-status", response_model=LocalRuntimeStatusResponse)
def get_local_runtime_status():
    status: Dict[str, Any] = local_runtime_status()
    return LocalRuntimeStatusResponse(
        runtime_profile=str(status.get("runtime_profile") or ""),
        state_dir=str(status.get("state_dir") or ""),
        data_cache_dir=str(status.get("data_cache_dir") or ""),
        manifest_path=str(status.get("manifest_path") or ""),
        remote_manifest_url=str(status.get("remote_manifest_url") or ""),
        llm=RuntimeLlmResponse(**dict(status.get("llm") or {})),
        installed_pack_count=int(status.get("installed_pack_count") or 0),
        available_countries=list(status.get("available_countries") or []),
        packs=[RuntimePackResponse(**pack) for pack in status.get("packs") or []],
    )


@router.post("/data-packs/sync", response_model=DataPackSyncResponse)
def sync_data_packs(req: DataPackSyncRequest = DataPackSyncRequest()):
    result = sync_data_pack_manifest(req.remote_url)
    return DataPackSyncResponse(**result)
