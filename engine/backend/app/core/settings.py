"""엔진 전역 설정·기능 분기 (Phase 6 후속 / Phase 7).

LLM 채팅 API·DB 영속화는 아직 미구현이며, 환경 변수로만 분기해 두고
추후 `ORGANIC4D_LLM_CHAT_ENABLED=1`, `ORGANIC4D_DATABASE_URL=...` 등으로 연동한다.
"""
from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Literal, Optional

LLM_TASK_NAMES = (
    "genesis",
    "thought",
    "worldview",
    "action",
    "policy",
    "dialogue",
    "group_deliberation",
    "review_summary",
    "timeline_annotation",
    "review_diff",
    "review_query",
    "review_diff_query",
    "session_review",
    "session_review_query",
    "agent_interview",
    "agent_interview_diff",
)

LLM_RUNTIME_PROFILES = ("rules-first", "balanced", "llm-first")
LLM_STRICT_MODES = ("adaptive", "llm-preferred", "fail-hard")

_TASK_PRIORITY_DEFAULTS = {
    "genesis": 0,
    "policy": 0,
    "action": 1,
    "thought": 1,
    "dialogue": 2,
    "group_deliberation": 3,
    "worldview": 4,
    "review_summary": 1,
    "timeline_annotation": 2,
    "review_diff": 1,
    "review_query": 1,
    "review_diff_query": 1,
    "session_review": 1,
    "session_review_query": 1,
    "agent_interview": 1,
    "agent_interview_diff": 1,
}


def _runtime_llm_config_path() -> Path:
    return get_state_dir().parent / "runtime" / "llm_config.json"


def _load_runtime_llm_config() -> dict[str, str]:
    path = _runtime_llm_config_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): str(value) for key, value in data.items() if value is not None}


def _write_runtime_llm_config(config: dict[str, str]) -> None:
    path = _runtime_llm_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def _get_runtime_llm_value(key: str, default: str = "") -> str:
    env_value = os.getenv(key, "").strip()
    if env_value:
        return env_value
    return str(_load_runtime_llm_config().get(key, default)).strip()


def set_runtime_llm_config(
    *,
    enabled: bool,
    provider: str,
    model: str,
    base_url: str = "",
    api_key: str = "",
    temperature: float = 0.2,
    timeout_s: float = 20.0,
    runtime_profile: str = "balanced",
    strict_mode: str = "adaptive",
    cycle_prompt_budget: int | None = None,
    agent_sample_size: int | None = None,
    dialogue_max_pairs: int | None = None,
    group_deliberation_max_groups: int | None = None,
    task_budgets: dict[str, int] | None = None,
    task_priorities: dict[str, int] | None = None,
) -> dict[str, str]:
    runtime_profile = runtime_profile.strip() if runtime_profile.strip() in LLM_RUNTIME_PROFILES else "balanced"
    strict_mode = strict_mode.strip() if strict_mode.strip() in LLM_STRICT_MODES else "adaptive"
    existing = _load_runtime_llm_config()
    config = {
        "ORGANIC4D_LLM_CHAT_ENABLED": "1" if enabled else "0",
        "ORGANIC4D_LLM_PROVIDER": provider.strip(),
        "ORGANIC4D_LLM_MODEL": model.strip(),
        "ORGANIC4D_LLM_BASE_URL": base_url.strip(),
        "ORGANIC4D_LLM_API_KEY": api_key.strip(),
        "ORGANIC4D_LLM_TEMPERATURE": str(float(temperature)),
        "ORGANIC4D_LLM_TIMEOUT_S": str(float(timeout_s)),
        "ORGANIC4D_LLM_RUNTIME_PROFILE": runtime_profile,
        "ORGANIC4D_LLM_STRICT_MODE": strict_mode,
    }
    if cycle_prompt_budget is not None:
        config["ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET"] = str(int(cycle_prompt_budget))
    elif "ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET" in existing:
        config["ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET"] = existing["ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET"]
    if agent_sample_size is not None:
        config["ORGANIC4D_LLM_AGENT_SAMPLE_SIZE"] = str(int(agent_sample_size))
    elif "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE" in existing:
        config["ORGANIC4D_LLM_AGENT_SAMPLE_SIZE"] = existing["ORGANIC4D_LLM_AGENT_SAMPLE_SIZE"]
    if dialogue_max_pairs is not None:
        config["ORGANIC4D_DIALOGUE_MAX_PAIRS"] = str(int(dialogue_max_pairs))
    elif "ORGANIC4D_DIALOGUE_MAX_PAIRS" in existing:
        config["ORGANIC4D_DIALOGUE_MAX_PAIRS"] = existing["ORGANIC4D_DIALOGUE_MAX_PAIRS"]
    if group_deliberation_max_groups is not None:
        config["ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS"] = str(int(group_deliberation_max_groups))
    elif "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS" in existing:
        config["ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS"] = existing["ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS"]
    normalized_task_budgets = dict(existing)
    normalized_task_priorities = dict(existing)
    for task in LLM_TASK_NAMES:
        budget_key = f"ORGANIC4D_LLM_BUDGET_{task.upper()}"
        priority_key = f"ORGANIC4D_LLM_PRIORITY_{task.upper()}"
        if task_budgets and task in task_budgets:
            config[budget_key] = str(int(task_budgets[task]))
        elif budget_key in normalized_task_budgets:
            config[budget_key] = normalized_task_budgets[budget_key]
        if task_priorities and task in task_priorities:
            config[priority_key] = str(int(task_priorities[task]))
        elif priority_key in normalized_task_priorities:
            config[priority_key] = normalized_task_priorities[priority_key]
    _write_runtime_llm_config(config)
    for key, value in config.items():
        os.environ[key] = value
    return config


def get_llm_chat_enabled() -> bool:
    """True면 (후속) Ollama 등 대화형 LLM으로 Thought/Worldview 문장 생성."""
    return _get_runtime_llm_value("ORGANIC4D_LLM_CHAT_ENABLED", "").lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_llm_provider() -> Literal["stub", "openai", "openai-compatible", "ollama"]:
    """LLM chat backend for Thought/Worldview text generation."""
    v = _get_runtime_llm_value("ORGANIC4D_LLM_PROVIDER", "stub").lower()
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
    return _get_runtime_llm_value("ORGANIC4D_LLM_MODEL", default_model) or default_model


def get_llm_base_url() -> Optional[str]:
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_BASE_URL", "")
    if raw:
        return raw.rstrip("/")
    provider = get_llm_provider()
    if provider == "openai":
        return "https://api.openai.com/v1"
    if provider == "ollama":
        return "http://127.0.0.1:11434"
    return None


def get_llm_api_key() -> Optional[str]:
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_API_KEY", "")
    if raw:
        return raw
    raw = os.getenv("OPENAI_API_KEY", "").strip()
    return raw or None


def get_llm_timeout_s() -> float:
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_TIMEOUT_S", "20")
    try:
        return max(1.0, min(120.0, float(raw)))
    except ValueError:
        return 20.0


def get_llm_temperature() -> float:
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_TEMPERATURE", "0.2")
    try:
        return max(0.0, min(2.0, float(raw)))
    except ValueError:
        return 0.2


def get_llm_runtime_profile() -> str:
    profile = _get_runtime_llm_value("ORGANIC4D_LLM_RUNTIME_PROFILE", "balanced")
    return profile if profile in LLM_RUNTIME_PROFILES else "balanced"


def get_llm_strict_mode() -> str:
    mode = _get_runtime_llm_value("ORGANIC4D_LLM_STRICT_MODE", "adaptive")
    return mode if mode in LLM_STRICT_MODES else "adaptive"


def get_llm_max_prompts_per_task() -> int:
    """Hard cap for one LLM task batch to keep long runs predictable."""
    raw = os.getenv("ORGANIC4D_LLM_MAX_PROMPTS_PER_TASK", "64").strip()
    try:
        return max(1, min(2048, int(raw)))
    except ValueError:
        profile = get_llm_runtime_profile()
        if profile == "llm-first":
            return 512
        if profile == "rules-first":
            return 32
        return 64


def get_llm_task_budget(task: str) -> int:
    """Per-task prompt cap, falling back to the global max."""
    env_key = f"ORGANIC4D_LLM_BUDGET_{str(task).upper()}"
    raw = _get_runtime_llm_value(env_key, "")
    if not raw:
        return get_llm_max_prompts_per_task()
    try:
        return max(1, min(2048, int(raw)))
    except ValueError:
        return get_llm_max_prompts_per_task()


def get_llm_task_budgets() -> dict[str, int]:
    return {task: get_llm_task_budget(task) for task in LLM_TASK_NAMES}


def get_llm_cycle_prompt_budget() -> int:
    """Total prompts the engine may send in one simulation cycle."""
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET", "160")
    try:
        return max(1, min(50000, int(raw)))
    except ValueError:
        profile = get_llm_runtime_profile()
        if profile == "llm-first":
            return 1200
        if profile == "rules-first":
            return 96
        return 160


def get_llm_task_priority(task: str) -> int:
    env_key = f"ORGANIC4D_LLM_PRIORITY_{str(task).upper()}"
    raw = _get_runtime_llm_value(env_key, "")
    if raw:
        try:
            return max(0, min(9, int(raw)))
        except ValueError:
            pass
    return int(_TASK_PRIORITY_DEFAULTS.get(task, 5))


def get_llm_task_priorities() -> dict[str, int]:
    return {task: get_llm_task_priority(task) for task in LLM_TASK_NAMES}


def get_llm_agent_sample_size() -> int:
    """Max agents selected for expensive LLM cognition in one simulation tick."""
    raw = _get_runtime_llm_value("ORGANIC4D_LLM_AGENT_SAMPLE_SIZE", "256")
    try:
        return max(1, min(10000, int(raw)))
    except ValueError:
        profile = get_llm_runtime_profile()
        if profile == "llm-first":
            return 2048
        if profile == "rules-first":
            return 96
        return 256


def get_thought_refresh_interval() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_THOUGHT_INTERVAL", "")
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 6
    if profile == "rules-first":
        return 24
    return 20


def get_action_refresh_interval() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_ACTION_INTERVAL", "")
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 2
    if profile == "rules-first":
        return 12
    return 10


def get_worldview_refresh_interval() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_WORLDVIEW_INTERVAL", "")
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 12
    if profile == "rules-first":
        return 48
    return 40


def get_worldview_memory_threshold() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_WORLDVIEW_MEMORY_THRESHOLD", "")
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 48
    return 100


def get_worldview_t_threshold() -> float:
    raw = _get_runtime_llm_value("ORGANIC4D_WORLDVIEW_T_THRESHOLD", "")
    if raw:
        try:
            return max(0.0, min(100000.0, float(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 80.0
    return 200.0


def get_group_representative_limit(group_count: int) -> int:
    profile = get_llm_runtime_profile()
    base_sample = get_llm_agent_sample_size()
    if profile == "llm-first":
        return max(8, min(64, base_sample // max(1, group_count)))
    if profile == "rules-first":
        return max(3, min(12, base_sample // max(2, group_count * 2)))
    return max(4, min(24, base_sample // max(1, group_count)))


def get_dialogue_interval() -> int:
    raw = os.getenv("ORGANIC4D_DIALOGUE_INTERVAL", "").strip()
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 6
    if profile == "rules-first":
        return 30
    return 25


def get_dialogue_max_pairs() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_DIALOGUE_MAX_PAIRS", "64")
    try:
        return max(1, min(5000, int(raw)))
    except ValueError:
        profile = get_llm_runtime_profile()
        if profile == "llm-first":
            return 320
        return 64


def get_group_deliberation_interval() -> int:
    raw = os.getenv("ORGANIC4D_GROUP_DELIBERATION_INTERVAL", "").strip()
    if raw:
        try:
            return max(1, min(10000, int(raw)))
        except ValueError:
            pass
    profile = get_llm_runtime_profile()
    if profile == "llm-first":
        return 12
    if profile == "rules-first":
        return 60
    return 50


def get_group_deliberation_max_groups() -> int:
    raw = _get_runtime_llm_value("ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS", "12")
    try:
        return max(1, min(256, int(raw)))
    except ValueError:
        profile = get_llm_runtime_profile()
        if profile == "llm-first":
            return 40
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
