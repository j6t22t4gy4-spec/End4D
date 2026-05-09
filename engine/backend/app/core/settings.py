"""엔진 전역 설정·기능 분기 (Phase 6 후속 / Phase 7).

LLM 채팅 API·DB 영속화는 아직 미구현이며, 환경 변수로만 분기해 두고
추후 `ORGANIC4D_LLM_CHAT_ENABLED=1`, `ORGANIC4D_DATABASE_URL=...` 등으로 연동한다.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, Optional


def get_llm_chat_enabled() -> bool:
    """True면 (후속) Ollama 등 대화형 LLM으로 Thought/Worldview 문장 생성."""
    return os.getenv("ORGANIC4D_LLM_CHAT_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_llm_provider() -> Literal["stub", "openai", "openai-compatible", "ollama"]:
    """LLM chat backend for Thought/Worldview text generation."""
    v = os.getenv("ORGANIC4D_LLM_PROVIDER", "stub").strip().lower()
    if v in ("openai",):
        return "openai"
    if v in ("openai-compatible", "openai_compatible", "openai-compatible-local"):
        return "openai-compatible"
    if v in ("ollama", "local", "ollama-local"):
        return "ollama"
    return "stub"


def get_llm_model() -> str:
    provider = get_llm_provider()
    default_model = {
        "openai": "gpt-4.1-mini",
        "openai-compatible": "gpt-4.1-mini",
        "ollama": "llama3.1",
        "stub": "stub",
    }[provider]
    return os.getenv("ORGANIC4D_LLM_MODEL", default_model).strip() or default_model


def get_llm_base_url() -> Optional[str]:
    raw = os.getenv("ORGANIC4D_LLM_BASE_URL", "").strip()
    if raw:
        return raw.rstrip("/")
    provider = get_llm_provider()
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "ollama":
        return "http://127.0.0.1:11434"
    return None


def get_llm_api_key() -> Optional[str]:
    raw = os.getenv("ORGANIC4D_LLM_API_KEY", "").strip()
    if raw:
        return raw
    raw = os.getenv("OPENAI_API_KEY", "").strip()
    return raw or None


def get_llm_timeout_s() -> float:
    raw = os.getenv("ORGANIC4D_LLM_TIMEOUT_S", "20").strip()
    try:
        return max(1.0, min(120.0, float(raw)))
    except ValueError:
        return 20.0


def get_llm_temperature() -> float:
    raw = os.getenv("ORGANIC4D_LLM_TEMPERATURE", "0.2").strip()
    try:
        return max(0.0, min(2.0, float(raw)))
    except ValueError:
        return 0.2


def get_llm_max_prompts_per_task() -> int:
    """Hard cap for one LLM task batch to keep long runs predictable."""
    raw = os.getenv("ORGANIC4D_LLM_MAX_PROMPTS_PER_TASK", "64").strip()
    try:
        return max(1, min(2048, int(raw)))
    except ValueError:
        return 64


def get_llm_agent_sample_size() -> int:
    """Max agents selected for expensive LLM cognition in one simulation tick."""
    raw = os.getenv("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE", "256").strip()
    try:
        return max(1, min(10000, int(raw)))
    except ValueError:
        return 256


def get_dialogue_interval() -> int:
    raw = os.getenv("ORGANIC4D_DIALOGUE_INTERVAL", "25").strip()
    try:
        return max(1, min(10000, int(raw)))
    except ValueError:
        return 25


def get_dialogue_max_pairs() -> int:
    raw = os.getenv("ORGANIC4D_DIALOGUE_MAX_PAIRS", "64").strip()
    try:
        return max(1, min(5000, int(raw)))
    except ValueError:
        return 64


def get_group_deliberation_interval() -> int:
    raw = os.getenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", "50").strip()
    try:
        return max(1, min(10000, int(raw)))
    except ValueError:
        return 50


def get_group_deliberation_max_groups() -> int:
    raw = os.getenv("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS", "12").strip()
    try:
        return max(1, min(256, int(raw)))
    except ValueError:
        return 12


def get_snapshot_interval() -> int:
    """Persist every N ticks. Default 1 preserves current reproducibility behavior."""
    raw = os.getenv("ORGANIC4D_SNAPSHOT_INTERVAL", "1").strip()
    try:
        return max(1, min(100000, int(raw)))
    except ValueError:
        return 1


def get_snapshot_max_in_memory() -> int:
    """Cap retained snapshots per world to protect long local runs."""
    raw = os.getenv("ORGANIC4D_SNAPSHOT_MAX_IN_MEMORY", "1000").strip()
    try:
        return max(2, min(100000, int(raw)))
    except ValueError:
        return 1000


def get_persistence_backend() -> Literal["memory", "disk", "postgres", "redis"]:
    """저장소 백엔드. 기본은 disk, postgres/redis는 후속."""
    v = os.getenv("ORGANIC4D_PERSISTENCE_BACKEND", "disk").strip().lower()
    if v in ("disk", "file", "json"):
        return "disk"
    if v in ("postgres", "postgresql", "pg"):
        return "postgres"
    if v in ("redis",):
        return "redis"
    return "memory"


def get_database_url() -> Optional[str]:
    """PostgreSQL 등 연결 URL. 미설정 시 인메모리만 사용."""
    u = os.getenv("ORGANIC4D_DATABASE_URL", "").strip()
    return u or None


def get_state_dir() -> Path:
    """File persistence base directory."""
    raw = os.getenv("ORGANIC4D_STATE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "worlds"


def get_data_cache_dir() -> Path:
    """Local cache directory for cloud-delivered data packs."""
    raw = os.getenv("ORGANIC4D_DATA_CACHE_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path(__file__).resolve().parents[2] / "data" / "packs"


def get_data_pack_remote_manifest_url() -> str:
    """Cloud manifest URL or local file path for data-pack sync."""
    return os.getenv("ORGANIC4D_DATA_PACK_REMOTE_MANIFEST_URL", "").strip()


def get_runtime_profile() -> str:
    """Human-readable runtime profile label for local engine packaging."""
    return os.getenv("ORGANIC4D_RUNTIME_PROFILE", "local-pro").strip() or "local-pro"


def get_cors_origins() -> list[str]:
    """브라우저 CORS 허용 출처. 기본 localhost + ORGANIC4D_CORS_ORIGINS(쉼표) 추가."""
    defaults = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    raw = os.getenv("ORGANIC4D_CORS_ORIGINS", "").strip()
    if not raw:
        return defaults
    extra = [x.strip() for x in raw.split(",") if x.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for o in defaults + extra:
        if o not in seen:
            seen.add(o)
            out.append(o)
    return out
