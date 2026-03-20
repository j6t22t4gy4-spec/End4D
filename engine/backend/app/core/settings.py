"""엔진 전역 설정·기능 분기 (Phase 6 후속 / Phase 7).

LLM 채팅 API·DB 영속화는 아직 미구현이며, 환경 변수로만 분기해 두고
추후 `ORGANIC4D_LLM_CHAT_ENABLED=1`, `ORGANIC4D_DATABASE_URL=...` 등으로 연동한다.
"""
from __future__ import annotations

import os
from typing import Literal, Optional


def get_llm_chat_enabled() -> bool:
    """True면 (후속) Ollama 등 대화형 LLM으로 Thought/Worldview 문장 생성."""
    return os.getenv("ORGANIC4D_LLM_CHAT_ENABLED", "").strip().lower() in (
        "1",
        "true",
        "yes",
        "on",
    )


def get_persistence_backend() -> Literal["memory", "postgres", "redis"]:
    """저장소 백엔드. memory만 구현됨; postgres/redis는 후속."""
    v = os.getenv("ORGANIC4D_PERSISTENCE_BACKEND", "memory").strip().lower()
    if v in ("postgres", "postgresql", "pg"):
        return "postgres"
    if v in ("redis",):
        return "redis"
    return "memory"


def get_database_url() -> Optional[str]:
    """PostgreSQL 등 연결 URL. 미설정 시 인메모리만 사용."""
    u = os.getenv("ORGANIC4D_DATABASE_URL", "").strip()
    return u or None


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
