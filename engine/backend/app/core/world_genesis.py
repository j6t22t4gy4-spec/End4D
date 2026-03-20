"""프롬프트 기반 세계 제안 (World Genesis).

사용자 질의만으로 t_max·초기 개체 수·역할 목록 등을 제안.
후속: 외부 LLM API로 대체. 현재는 휴리스틱 스텁 (코드·프롬프트는 자체 작성).
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import List


# 기본 역할 풀 — 시나리오가 구체적이지 않을 때
_DEFAULT_ROLES = [
    "생산자",
    "분배자",
    "규제자",
    "소비자",
    "관측자",
]

_KEYWORD_ROLES = [
    (r"정책|규제|법|정부", "규제자"),
    (r"시장|거래|금융|투자", "시장참여자"),
    (r"기업|회사|스타트업", "기업"),
    (r"시민|소비|여론", "시민"),
    (r"기후|환경|에너지", "환경행위자"),
    (r"기술|AI|데이터", "기술주체"),
]


@dataclass
class GenesisPlan:
    """AI(또는 스텁)가 제안하는 단일 세계 초기 조건."""

    t_max: float
    initial_cell_count: int
    role_catalog: List[str]
    rationale: str
    # 한 스텝 t가 달력에서 의미하는 바 (시/일/년 …) — 사용자가 고르지 않음
    t_step_semantic: str
    t_step_unit: str
    # apply_growth에 쓰는 영양 유입 강도 (시간 스케일에 비례해 스텁에서 가중)
    nutrient_per_step: float


def _stable_extra_cells(prompt: str) -> int:
    h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
    return int(h[:4], 16) % 12


def _infer_time_step_and_nutrient(text: str) -> tuple[str, str, float]:
    """질의에서 스텝의 시간 단위 추정 → 영양(에너지 유입) 스케일.

    후속: LLM이 동일 필드를 JSON으로 채움. 큰 스텝(년)일수록 한 번에 유입되는
    «기간 합산» 자원을 크게 두는 단순 모델(튜닝 가능).
    """
    if re.search(
        r"10\s*년|십\s*년|수십\s*년|decade|세\s*기|장기\s*예측",
        text,
        re.I,
    ):
        return (
            "decade_scale",
            "1 스텝 ≈ 다년·장기 정책 주기 (스텁: 연 단위 흐름에 맞춘 합산)",
            120.0,
        )
    if re.search(
        r"연간|년\s*단위|1\s*년|한\s*해|per\s*year|annual|yoy|매\s*년",
        text,
        re.I,
    ):
        return "year", "1 스텝 ≈ 1년", 52.0
    if re.search(r"월|분기|month|quarterly", text, re.I):
        return "month", "1 스텝 ≈ 1개월", 4.5
    if re.search(
        r"시간|시간당|실시간|intraday|hourly|매\s*시",
        text,
        re.I,
    ):
        return "hour", "1 스텝 ≈ 1시간", 0.06
    if re.search(r"일일|매\s*일|하루|daily|per\s*day", text, re.I):
        return "day", "1 스텝 ≈ 1일", 1.0
    return "day", "1 스텝 ≈ 1일 (질의에서 단위 힌트 없음, 기본)", 1.0


def propose_world_from_prompt(prompt: str) -> GenesisPlan:
    """
    프롬프트에서 예측·탐색 목적에 맞는 초기 세계를 제안.
    (후속: 동일 계약으로 LLM JSON 출력 연동)
    """
    text = prompt.strip()
    if not text:
        text = "일반 복잡계 시나리오"

    # 시간 범위: 질문 길이·키워드로 거칠게 스케일
    t_max = 80.0
    if len(text) > 200:
        t_max = 160.0
    if re.search(r"장기|10년|수십\s*년|예측", text, re.I):
        t_max = 280.0
    if re.search(r"단기|즉시|몇\s*주", text, re.I):
        t_max = 48.0

    base_cells = 8
    n_extra = _stable_extra_cells(text)
    initial_cell_count = min(48, max(6, base_cells + n_extra))

    roles: List[str] = []
    for pattern, label in _KEYWORD_ROLES:
        if re.search(pattern, text) and label not in roles:
            roles.append(label)
    if len(roles) < 3:
        for r in _DEFAULT_ROLES:
            if r not in roles:
                roles.append(r)
            if len(roles) >= 5:
                break

    t_unit, t_semantic, nutrient = _infer_time_step_and_nutrient(text)

    rationale = (
        f"질의 길이·키워드 기반 스텁 제안입니다. "
        f"시간 의미: {t_semantic} (unit={t_unit}), "
        f"스텝당 영양 유입 nutrient_per_step≈{nutrient:.3f}. "
        f"t_max≈{int(t_max)}, 초기 에이전트≈{initial_cell_count}, "
        f"역할 풀: {', '.join(roles[:6])}. "
        f"LLM 연동 시 동일 필드로 최적화된 세계를 채웁니다."
    )

    return GenesisPlan(
        t_max=t_max,
        initial_cell_count=initial_cell_count,
        role_catalog=roles[:8],
        rationale=rationale,
        t_step_semantic=t_semantic,
        t_step_unit=t_unit,
        nutrient_per_step=nutrient,
    )
