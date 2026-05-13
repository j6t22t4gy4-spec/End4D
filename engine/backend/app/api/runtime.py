"""Local runtime status API for packaged engine deployments."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.data_packs import (
    diff_data_pack_history,
    install_data_pack,
    local_runtime_status,
    pin_data_pack,
    rollback_data_pack,
    sync_data_pack_manifest,
    validate_data_pack,
    verify_data_pack,
)
from app.core.settings import get_ui_language, set_runtime_llm_config, set_runtime_ui_language
from app.llm.chat_runtime import generate_reasoning_batch

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
    verification: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    description: str = ""


class RuntimeLlmResponse(BaseModel):
    enabled: bool = False
    provider: str = "stub"
    model: str = "stub"
    base_url: str = ""
    has_api_key: bool = False
    configured_via: str = "default"
    runtime_profile: str = "balanced"
    strict_mode: str = "adaptive"
    ui_language: str = "ko"


class RuntimeLlmRunResponse(BaseModel):
    task: str
    provider: str = ""
    model: str = ""
    prompt_version: str = ""
    prompt_count_in: int = 0
    prompt_count_sent: int = 0
    prompt_count_skipped_by_task_budget: int = 0
    prompt_count_skipped_by_cycle_budget: int = 0
    task_budget: int = 0
    task_priority: int = 0
    cycle_key: str = ""
    cycle_budget_total: int = 0
    cycle_budget_remaining_before: int = 0
    cycle_budget_remaining_after: int = 0
    used_fallback: bool = False
    fallback_reason: str = ""


class RuntimeLlmTotalsResponse(BaseModel):
    calls: int = 0
    prompt_count_in: int = 0
    prompt_count_sent: int = 0
    prompt_count_skipped_by_task_budget: int = 0
    prompt_count_skipped_by_cycle_budget: int = 0
    fallback_calls: int = 0


class RuntimeLlmHealthResponse(BaseModel):
    status: str = "disabled"
    reason: str = ""
    recent_call_count: int = 0
    live_call_count: int = 0
    live_call_rate: float = 0.0
    recent_fallback_count: int = 0
    recent_fallback_rate: float = 0.0
    last_fallback_reason: str = ""
    dominant_failure_reason: str = ""
    live_streak: int = 0
    fallback_streak: int = 0
    stability_score: float = 0.0


class RuntimeLlmReasonCountResponse(BaseModel):
    reason: str
    count: int = 0


class RuntimeLlmTaskInsightResponse(BaseModel):
    task: str
    calls: int = 0
    live_calls: int = 0
    fallback_calls: int = 0
    live_call_rate: float = 0.0
    prompt_live_rate: float = 0.0
    status: str = "idle"
    recommendation: str = ""
    top_fallback_reasons: List[RuntimeLlmReasonCountResponse] = Field(default_factory=list)


class RuntimeLlmRepairTaskResponse(BaseModel):
    task: str
    repair_count: int = 0
    top_reasons: List[RuntimeLlmReasonCountResponse] = Field(default_factory=list)


class RuntimeLlmRepairSummaryResponse(BaseModel):
    total_repairs: int = 0
    task_repairs: List[RuntimeLlmRepairTaskResponse] = Field(default_factory=list)
    top_reasons: List[RuntimeLlmReasonCountResponse] = Field(default_factory=list)


class RuntimeLlmRuntimeResponse(BaseModel):
    provider: str = "stub"
    model: str = "stub"
    strict_mode: str = "adaptive"
    density_profile: str = "balanced"
    cycle_prompt_budget: int = 0
    agent_sample_size: int = 0
    dialogue_max_pairs: int = 0
    group_deliberation_max_groups: int = 0
    task_priorities: Dict[str, int] = Field(default_factory=dict)
    task_budgets: Dict[str, int] = Field(default_factory=dict)
    task_live_floors: Dict[str, int] = Field(default_factory=dict)
    scheduler: Dict[str, Any] = Field(default_factory=dict)
    health: RuntimeLlmHealthResponse = Field(default_factory=RuntimeLlmHealthResponse)
    recent_runs: List[RuntimeLlmRunResponse] = Field(default_factory=list)
    task_totals: Dict[str, RuntimeLlmTotalsResponse] = Field(default_factory=dict)
    task_insights: List[RuntimeLlmTaskInsightResponse] = Field(default_factory=list)
    degraded_tasks: List[str] = Field(default_factory=list)
    fallback_reason_counts: Dict[str, int] = Field(default_factory=dict)
    recommended_actions: List[str] = Field(default_factory=list)
    repair_summary: RuntimeLlmRepairSummaryResponse = Field(default_factory=RuntimeLlmRepairSummaryResponse)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    optimizer: Dict[str, Any] = Field(default_factory=dict)


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


class DataPackVerifyRequest(BaseModel):
    pack_id: str


class DataPackVerifyResponse(BaseModel):
    pack_id: str
    exists: bool = False
    dataset_id: str = ""
    version: str = ""
    verified_at: str = ""
    schema_health: str = ""
    field_coverage: Dict[str, Any] = Field(default_factory=dict)
    sample_roles: List[str] = Field(default_factory=list)
    sample_regions: List[str] = Field(default_factory=list)
    country_consistency: float = 0.0
    ready_for_genesis: bool = False


class DataPackRollbackRequest(BaseModel):
    pack_id: str
    history_index: int


class DataPackRollbackResponse(BaseModel):
    pack_id: str
    rolled_back: bool = False
    version: str = ""
    history_index: int = 0
    updated_at: str = ""


class DataPackDiffRequest(BaseModel):
    pack_id: str
    history_index: int


class DataPackDiffResponse(BaseModel):
    pack_id: str
    history_index: int
    selected_action: str = ""
    selected_at: str = ""
    changes: List[Dict[str, Any]] = Field(default_factory=list)
    verification_changes: List[Dict[str, Any]] = Field(default_factory=list)


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


class RuntimeLlmConfigRequest(BaseModel):
    enabled: bool = False
    provider: str = "stub"
    model: str = "stub"
    base_url: str = ""
    api_key: str = ""
    temperature: float = 0.2
    timeout_s: float = 20.0
    runtime_profile: str = "balanced"
    strict_mode: str = "adaptive"
    cycle_prompt_budget: Optional[int] = None
    agent_sample_size: Optional[int] = None
    dialogue_max_pairs: Optional[int] = None
    group_deliberation_max_groups: Optional[int] = None
    task_budgets: Dict[str, int] = Field(default_factory=dict)
    task_priorities: Dict[str, int] = Field(default_factory=dict)
    ui_language: Optional[str] = None


class RuntimeLlmConfigResponse(BaseModel):
    enabled: bool = False
    provider: str = "stub"
    model: str = "stub"
    base_url: str = ""
    has_api_key: bool = False
    temperature: float = 0.2
    timeout_s: float = 20.0
    configured_via: str = "runtime-ui"
    runtime_profile: str = "balanced"
    strict_mode: str = "adaptive"
    cycle_prompt_budget: int = 0
    agent_sample_size: int = 0
    dialogue_max_pairs: int = 0
    group_deliberation_max_groups: int = 0
    task_budgets: Dict[str, int] = Field(default_factory=dict)
    task_priorities: Dict[str, int] = Field(default_factory=dict)
    ui_language: str = "ko"


class RuntimeUiLanguageRequest(BaseModel):
    language: str = "ko"


class RuntimeUiLanguageResponse(BaseModel):
    language: str = "ko"


class RuntimeLlmTestResponse(BaseModel):
    ok: bool = False
    mode: str = "stub"
    provider: str = "stub"
    model: str = "stub"
    used_fallback: bool = False
    fallback_reason: str = ""
    preview: str = ""
    diagnosis: str = ""
    suggestions: List[str] = Field(default_factory=list)


@router.get("/local-status", response_model=LocalRuntimeStatusResponse)
def get_local_runtime_status():
    status: Dict[str, Any] = local_runtime_status()
    return LocalRuntimeStatusResponse(
        runtime_profile=str(status.get("runtime_profile") or ""),
        state_dir=str(status.get("state_dir") or ""),
        data_cache_dir=str(status.get("data_cache_dir") or ""),
        manifest_path=str(status.get("manifest_path") or ""),
        remote_manifest_url=str(status.get("remote_manifest_url") or ""),
        llm=RuntimeLlmResponse(
            **{
                **dict(status.get("llm") or {}),
                "ui_language": get_ui_language(),
            }
        ),
        llm_runtime=RuntimeLlmRuntimeResponse(
            provider=str((status.get("llm_runtime") or {}).get("provider") or "stub"),
            model=str((status.get("llm_runtime") or {}).get("model") or "stub"),
            strict_mode=str((status.get("llm_runtime") or {}).get("strict_mode") or "adaptive"),
            density_profile=str((status.get("llm_runtime") or {}).get("density_profile") or "balanced"),
            cycle_prompt_budget=int((status.get("llm_runtime") or {}).get("cycle_prompt_budget") or 0),
            agent_sample_size=int((status.get("llm_runtime") or {}).get("agent_sample_size") or 0),
            dialogue_max_pairs=int((status.get("llm_runtime") or {}).get("dialogue_max_pairs") or 0),
            group_deliberation_max_groups=int((status.get("llm_runtime") or {}).get("group_deliberation_max_groups") or 0),
            task_priorities=dict((status.get("llm_runtime") or {}).get("task_priorities") or {}),
            task_budgets=dict((status.get("llm_runtime") or {}).get("task_budgets") or {}),
            task_live_floors=dict((status.get("llm_runtime") or {}).get("task_live_floors") or {}),
            scheduler=dict((status.get("llm_runtime") or {}).get("scheduler") or {}),
            health=RuntimeLlmHealthResponse(**dict((status.get("llm_runtime") or {}).get("health") or {})),
            recent_runs=[
                RuntimeLlmRunResponse(**item)
                for item in (status.get("llm_runtime") or {}).get("recent_runs") or []
            ],
            task_totals={
                key: RuntimeLlmTotalsResponse(**value)
                for key, value in dict((status.get("llm_runtime") or {}).get("task_totals") or {}).items()
            },
            task_insights=[
                RuntimeLlmTaskInsightResponse(**item)
                for item in (status.get("llm_runtime") or {}).get("task_insights") or []
            ],
            degraded_tasks=list((status.get("llm_runtime") or {}).get("degraded_tasks") or []),
            fallback_reason_counts=dict((status.get("llm_runtime") or {}).get("fallback_reason_counts") or {}),
            recommended_actions=list((status.get("llm_runtime") or {}).get("recommended_actions") or []),
            repair_summary=RuntimeLlmRepairSummaryResponse(
                total_repairs=int(((status.get("llm_runtime") or {}).get("repair_summary") or {}).get("total_repairs") or 0),
                task_repairs=[
                    RuntimeLlmRepairTaskResponse(
                        task=str((item or {}).get("task") or ""),
                        repair_count=int((item or {}).get("repair_count") or 0),
                        top_reasons=[
                            RuntimeLlmReasonCountResponse(**dict(reason or {}))
                            for reason in list((item or {}).get("top_reasons") or [])
                        ],
                    )
                    for item in list(((status.get("llm_runtime") or {}).get("repair_summary") or {}).get("task_repairs") or [])
                ],
                top_reasons=[
                    RuntimeLlmReasonCountResponse(**dict(item or {}))
                    for item in list(((status.get("llm_runtime") or {}).get("repair_summary") or {}).get("top_reasons") or [])
                ],
            ),
            diagnostics=dict((status.get("llm_runtime") or {}).get("diagnostics") or {}),
            optimizer=dict((status.get("llm_runtime") or {}).get("optimizer") or {}),
        ),
        installed_pack_count=int(status.get("installed_pack_count") or 0),
        available_countries=list(status.get("available_countries") or []),
        packs=[RuntimePackResponse(**pack) for pack in status.get("packs") or []],
    )


@router.post("/llm-config", response_model=RuntimeLlmConfigResponse)
def update_runtime_llm_config(req: RuntimeLlmConfigRequest):
    config = set_runtime_llm_config(
        enabled=req.enabled,
        provider=req.provider,
        model=req.model,
        base_url=req.base_url,
        api_key=req.api_key,
        temperature=req.temperature,
        timeout_s=req.timeout_s,
        runtime_profile=req.runtime_profile,
        strict_mode=req.strict_mode,
        cycle_prompt_budget=req.cycle_prompt_budget,
        agent_sample_size=req.agent_sample_size,
        dialogue_max_pairs=req.dialogue_max_pairs,
        group_deliberation_max_groups=req.group_deliberation_max_groups,
        task_budgets=dict(req.task_budgets or {}),
        task_priorities=dict(req.task_priorities or {}),
        ui_language=req.ui_language,
    )
    return RuntimeLlmConfigResponse(
        enabled=config["ORGANIC4D_LLM_CHAT_ENABLED"] == "1",
        provider=str(config["ORGANIC4D_LLM_PROVIDER"] or "stub"),
        model=str(config["ORGANIC4D_LLM_MODEL"] or "stub"),
        base_url=str(config["ORGANIC4D_LLM_BASE_URL"] or ""),
        has_api_key=bool(config["ORGANIC4D_LLM_API_KEY"]),
        temperature=float(config["ORGANIC4D_LLM_TEMPERATURE"]),
        timeout_s=float(config["ORGANIC4D_LLM_TIMEOUT_S"]),
        configured_via="runtime-ui",
        runtime_profile=str(config.get("ORGANIC4D_LLM_RUNTIME_PROFILE") or "balanced"),
        strict_mode=str(config.get("ORGANIC4D_LLM_STRICT_MODE") or "adaptive"),
        cycle_prompt_budget=int(config.get("ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET") or 0),
        agent_sample_size=int(config.get("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE") or 0),
        dialogue_max_pairs=int(config.get("ORGANIC4D_DIALOGUE_MAX_PAIRS") or 0),
        group_deliberation_max_groups=int(config.get("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS") or 0),
        task_budgets={
            key.removeprefix("ORGANIC4D_LLM_BUDGET_").lower(): int(value)
            for key, value in config.items()
            if key.startswith("ORGANIC4D_LLM_BUDGET_")
        },
        task_priorities={
            key.removeprefix("ORGANIC4D_LLM_PRIORITY_").lower(): int(value)
            for key, value in config.items()
            if key.startswith("ORGANIC4D_LLM_PRIORITY_")
        },
        ui_language=str(config.get("ORGANIC4D_UI_LANGUAGE") or get_ui_language()),
    )


@router.post("/ui-language", response_model=RuntimeUiLanguageResponse)
def update_runtime_ui_language(req: RuntimeUiLanguageRequest):
    return RuntimeUiLanguageResponse(language=set_runtime_ui_language(req.language))


@router.post("/llm-config/test", response_model=RuntimeLlmTestResponse)
def test_runtime_llm_config():
    try:
        result = generate_reasoning_batch(
            ["Respond in one short sentence confirming that runtime cognition is connected."],
            task="thought",
        )
        texts = list(result.get("texts") or [])
        meta = dict(result.get("meta") or {})
        preview = str(texts[0] if texts else "").strip()
        ok = bool(preview) and not (
            bool(meta.get("used_fallback")) and str(meta.get("fallback_reason") or "") == "llm_disabled"
        )
        return RuntimeLlmTestResponse(
            ok=ok,
            mode="llm" if bool(meta.get("enabled")) and not bool(meta.get("used_fallback")) else "fallback",
            provider=str(meta.get("provider") or "stub"),
            model=str(meta.get("model") or "stub"),
            used_fallback=bool(meta.get("used_fallback")),
            fallback_reason=str(meta.get("fallback_reason") or ""),
            preview=preview[:240],
            diagnosis="connected" if ok else "provider returned fallback or empty output",
            suggestions=[] if ok else [
                "Verify provider/model/base_url values",
                "Check API key or local server availability",
                "Retry after confirming runtime strict mode and budget settings",
            ],
        )
    except Exception as exc:
        return RuntimeLlmTestResponse(
            ok=False,
            mode="error",
            provider="unknown",
            model="unknown",
            used_fallback=False,
            fallback_reason=str(exc),
            preview="",
            diagnosis="provider request failed",
            suggestions=[
                "Check network reachability or local provider health",
                "Confirm API key, base URL, and model name",
                "Provider errors do not auto-fallback anymore; fix the connection and test again",
            ],
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


@router.post("/data-packs/verify", response_model=DataPackVerifyResponse)
def verify_runtime_data_pack(req: DataPackVerifyRequest):
    return DataPackVerifyResponse(**verify_data_pack(req.pack_id))


@router.post("/data-packs/rollback", response_model=DataPackRollbackResponse)
def rollback_runtime_data_pack(req: DataPackRollbackRequest):
    return DataPackRollbackResponse(**rollback_data_pack(req.pack_id, history_index=req.history_index))


@router.post("/data-packs/diff", response_model=DataPackDiffResponse)
def diff_runtime_data_pack(req: DataPackDiffRequest):
    return DataPackDiffResponse(**diff_data_pack_history(req.pack_id, history_index=req.history_index))
