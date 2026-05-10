"""Local runtime status API for packaged engine deployments."""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.data_packs import (
    install_data_pack,
    local_runtime_status,
    pin_data_pack,
    sync_data_pack_manifest,
    validate_data_pack,
)

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
    installed_at: str = ""
    pinned: bool = False
    pinned_version: str = ""
    validated_at: str = ""
    validation: Dict[str, Any] = Field(default_factory=dict)
    description: str = ""


class RuntimeLlmResponse(BaseModel):
    enabled: bool = False
    provider: str = "stub"
    model: str = "stub"
    base_url: str = ""


class RuntimeLlmRunResponse(BaseModel):
    task: str
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    prompt_count_in: int = 0
    prompt_count_sent: int = 0
    prompt_count_skipped_by_task_budget: int = 0
    task_budget: int = 0
    used_fallback: bool = False
    fallback_reason: str = ""


class RuntimeLlmTotalsResponse(BaseModel):
    calls: int = 0
    prompt_count_in: int = 0
    prompt_count_sent: int = 0
    prompt_count_skipped_by_task_budget: int = 0
    fallback_calls: int = 0


class RuntimeLlmRuntimeResponse(BaseModel):
    provider: str = "stub"
    model: str = "stub"
    task_budgets: Dict[str, int] = Field(default_factory=dict)
    recent_runs: List[RuntimeLlmRunResponse] = Field(default_factory=list)
    task_totals: Dict[str, RuntimeLlmTotalsResponse] = Field(default_factory=dict)


class DataPackInstallRequest(BaseModel):
    pack_id: str
    source_path: str
    version: str = ""
    dataset_id: str = ""
    source_url: str = ""


class DataPackInstallResponse(BaseModel):
    pack_id: str
    installed: bool = False
    exists: bool = False
    row_count_estimate: int = 0
    sample_error: str = ""
    validated_at: str = ""
    version: str = ""


class DataPackValidateRequest(BaseModel):
    pack_id: str


class DataPackValidateResponse(BaseModel):
    pack_id: str
    exists: bool = False
    row_count_estimate: int = 0
    sample_error: str = ""
    validated_at: str = ""
    version: str = ""


class DataPackPinRequest(BaseModel):
    pack_id: str
    pinned_version: str


class DataPackPinResponse(BaseModel):
    pack_id: str
    pinned: bool = False
    pinned_version: str = ""
    pinned_at: str = ""


class LocalRuntimeStatusResponse(BaseModel):
    runtime_profile: str
    state_dir: str
    data_cache_dir: str
    manifest_path: str
    remote_manifest_url: str = ""
    llm: RuntimeLlmResponse
    llm_runtime: RuntimeLlmRuntimeResponse
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
        llm_runtime=RuntimeLlmRuntimeResponse(
            provider=str((status.get("llm_runtime") or {}).get("provider") or "stub"),
            model=str((status.get("llm_runtime") or {}).get("model") or "stub"),
            task_budgets=dict((status.get("llm_runtime") or {}).get("task_budgets") or {}),
            recent_runs=[
                RuntimeLlmRunResponse(**item)
                for item in (status.get("llm_runtime") or {}).get("recent_runs") or []
            ],
            task_totals={
                key: RuntimeLlmTotalsResponse(**value)
                for key, value in dict((status.get("llm_runtime") or {}).get("task_totals") or {}).items()
            },
        ),
        installed_pack_count=int(status.get("installed_pack_count") or 0),
        available_countries=list(status.get("available_countries") or []),
        packs=[RuntimePackResponse(**pack) for pack in status.get("packs") or []],
    )


@router.post("/data-packs/sync", response_model=DataPackSyncResponse)
def sync_data_packs(req: DataPackSyncRequest = DataPackSyncRequest()):
    result = sync_data_pack_manifest(req.remote_url)
    return DataPackSyncResponse(**result)


@router.post("/data-packs/install", response_model=DataPackInstallResponse)
def install_runtime_data_pack(req: DataPackInstallRequest):
    return DataPackInstallResponse(
        **install_data_pack(
            pack_id=req.pack_id,
            source_path=req.source_path,
            version=req.version,
            dataset_id=req.dataset_id,
            source_url=req.source_url,
        )
    )


@router.post("/data-packs/validate", response_model=DataPackValidateResponse)
def validate_runtime_data_pack(req: DataPackValidateRequest):
    return DataPackValidateResponse(**validate_data_pack(req.pack_id))


@router.post("/data-packs/pin", response_model=DataPackPinResponse)
def pin_runtime_data_pack(req: DataPackPinRequest):
    return DataPackPinResponse(**pin_data_pack(req.pack_id, pinned_version=req.pinned_version))
