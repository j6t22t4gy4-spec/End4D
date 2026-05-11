"""Post-simulation LLM review helpers."""
from __future__ import annotations

import json
from typing import Any, Mapping

from app.llm.prompt_registry import build_prompt_contract


def build_review_summary_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "review_summary",
        [
            ("world_meta", _compact(payload.get("world_meta") or {})),
            ("timeline", _compact(payload.get("timeline") or {})),
            ("metrics", _compact(payload.get("metrics") or {})),
            ("stance_summary", _compact(payload.get("stance_summary") or {})),
            ("zone_z_summary", _compact_list(payload.get("zone_z_summary") or [], limit=4)),
            ("policy_events", _compact_list(payload.get("policy_events") or [], limit=4)),
            ("highlights", " | ".join(str(item) for item in list(payload.get("highlights") or [])[:6])),
        ],
    )


def build_timeline_annotation_prompt(payload: Mapping[str, Any]) -> str:
    return build_prompt_contract(
        "timeline_annotation",
        [
            ("timeline", _compact(payload.get("timeline") or {})),
            (
                "annotation_candidates",
                _compact_list(payload.get("annotation_candidates") or [], limit=6),
            ),
            ("highlights", " | ".join(str(item) for item in list(payload.get("highlights") or [])[:6])),
        ],
    )


def heuristic_review_summary(payload: Mapping[str, Any]) -> str:
    metrics = dict(payload.get("metrics") or {})
    timeline = dict(payload.get("timeline") or {})
    stance = dict(payload.get("stance_summary") or {})
    groups = list(stance.get("groups") or [])
    top_group = groups[0] if groups else {}
    events = list(payload.get("policy_events") or [])
    parts = [
        (
            f"t={timeline.get('first_t', 0)}에서 t={timeline.get('last_t', 0)}까지 진행된 시뮬레이션에서 "
            f"세포 수는 {metrics.get('initial_cell_count', 0)}에서 {metrics.get('final_cell_count', 0)}로 변했고 "
            f"총 에너지는 {metrics.get('energy_delta', 0):+.2f} 변화했습니다."
        ),
        (
            f"집단 신호는 {stance.get('overall_signal', 'diffuse')} 상태이며, "
            f"가장 큰 역할 집단은 {top_group.get('role_label', 'n/a')}이고 "
            f"stance={top_group.get('stance', 'n/a')} cohesion={float(top_group.get('cohesion_score', 0.0)):.2f}입니다."
        ),
        (
            f"사회적 고도 z 평균은 {metrics.get('z_delta', 0):+.2f} 이동했고, "
            f"주요 정책 이벤트는 {len(events)}건 기록되었습니다."
        ),
    ]
    return " ".join(part for part in parts if part).strip()


def heuristic_timeline_annotations(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for item in list(payload.get("annotation_candidates") or [])[:4]:
        annotations.append(
            {
                "t": float(item.get("t", 0.0)),
                "label": str(item.get("label") or "timeline shift"),
                "reason": str(item.get("reason") or ""),
                "severity": _severity(float(item.get("score", 0.0))),
            }
        )
    return annotations


def parse_timeline_annotations(raw_text: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    text = str(raw_text or "").strip()
    if not text:
        return heuristic_timeline_annotations(payload)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return heuristic_timeline_annotations(payload)
    rows = list(parsed.get("annotations") or [])
    out: list[dict[str, Any]] = []
    for item in rows[:6]:
        out.append(
            {
                "t": float(item.get("t", 0.0)),
                "label": str(item.get("label") or "timeline shift"),
                "reason": str(item.get("reason") or ""),
                "severity": str(item.get("severity") or "medium"),
            }
        )
    return out or heuristic_timeline_annotations(payload)


def _compact(mapping: Mapping[str, Any]) -> str:
    return "; ".join(f"{key}={value}" for key, value in mapping.items())[:1600]


def _compact_list(items: list[Any], *, limit: int) -> str:
    sliced = items[:limit]
    return " | ".join(_compact(item) if isinstance(item, Mapping) else str(item) for item in sliced)[:1600]


def _severity(score: float) -> str:
    if score >= 1.45:
        return "high"
    if score >= 0.9:
        return "medium"
    return "low"
