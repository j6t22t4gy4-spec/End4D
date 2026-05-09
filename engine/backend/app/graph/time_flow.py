"""Organic4D Engine — LangGraph 시간 흐름 그래프 (Phase 2.1).

노드: init → step_loop → (성장→분열→사멸→융합→돌연변이)
ARCHITECTURE_CHECKLIST 5.1: 입력 → 4D세계 → 에이전트 풀 → 시간 흐름 엔진
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, START, END

from app.models.cell import Cell
from app.core.memory_store import seed_memory_from_text
from app.core.snapshot import SnapshotStore
from app.graph.nodes import step_loop_node


def _create_initial_cells(
    count: int = 5,
    t: float = 0.0,
    role_catalog: Optional[List[str]] = None,
    persona_catalog: Optional[List[dict]] = None,
) -> List[Cell]:
    """초기 세포 생성. 페르소나가 있으면 역할·메모리 seed로 사용."""
    import numpy as np

    roles = role_catalog if role_catalog else ["agent"]
    if not roles:
        roles = ["agent"]
    personas = persona_catalog or []

    cells = []
    for i in range(count):
        persona = personas[i % len(personas)] if personas else {}
        rk = str(persona.get("role_key") or roles[i % len(roles)])
        label = str(persona.get("role_label") or rk)
        persona_text = str(persona.get("persona_text") or "")
        cell = Cell(
                x=float(i * 2),
                y=0.0,
                z=0.0,
                t=t,
                energy=50.0,
                gene_vec=np.random.randn(32).astype(np.float32) * 0.1,
                emotion_vec=np.random.randn(8).astype(np.float32) * 0.1,
                thought_vec=np.random.randn(256).astype(np.float32) * 0.1,
                worldview_vec=np.random.randn(384).astype(np.float32) * 0.1,
                role_key=rk,
                role_label=label,
                persona_id=str(persona.get("persona_id") or ""),
                persona_text=persona_text,
                persona_country=str(persona.get("country") or ""),
                persona_attrs=dict(persona.get("attrs") or {}),
            )
        if persona_text:
            cell = seed_memory_from_text(cell, persona_text)
        cells.append(cell)
    return cells


# State: TypedDict 대신 dict 사용 (Cell 직렬화 이슈 회피)
SimulationState = Dict[str, Any]


def _init_node(state: SimulationState) -> SimulationState:
    """초기화: initial_cells가 있으면 사용, 없으면 기본 생성."""
    cells = state.get("initial_cells")
    if cells is None:
        cells = _create_initial_cells(
            count=state.get("initial_cell_count", 5),
            t=0.0,
            role_catalog=state.get("role_catalog"),
            persona_catalog=state.get("persona_catalog"),
        )
    out: SimulationState = {
        "cells": cells,
        "current_t": 0.0,
    }
    if "t_max" in state:
        out["t_max"] = state["t_max"]
    if "nutrient_per_step" in state:
        out["nutrient_per_step"] = state["nutrient_per_step"]
    if "snapshot_store" in state:
        out["snapshot_store"] = state["snapshot_store"]
    store = state.get("snapshot_store")
    if store is not None:
        store.save(0.0, cells)
    return out


def _should_continue(state: SimulationState) -> str:
    """t < t_max이면 step_loop, 아니면 종료."""
    if state["current_t"] < state["t_max"]:
        return "step"
    return "done"


def create_time_flow_graph():
    """시간 흐름 LangGraph 생성 및 컴파일."""
    graph = StateGraph(SimulationState)

    graph.add_node("init", _init_node)
    graph.add_node("step_loop", step_loop_node)

    graph.add_edge(START, "init")
    graph.add_conditional_edges(
        "init",
        lambda s: "step" if s["current_t"] < s["t_max"] else "done",
        {"step": "step_loop", "done": END},
    )
    graph.add_conditional_edges(
        "step_loop",
        _should_continue,
        {"step": "step_loop", "done": END},
    )

    return graph.compile()


def create_resume_time_flow_graph():
    """주입 후 t_inject→t_max만 재계산 (init 생략, START→step_loop).

    state 필수 키: cells, current_t, t_max, snapshot_store
    선택: nutrient_per_step
    """
    graph = StateGraph(SimulationState)
    graph.add_node("step_loop", step_loop_node)
    graph.add_edge(START, "step_loop")
    graph.add_conditional_edges(
        "step_loop",
        _should_continue,
        {"step": "step_loop", "done": END},
    )
    return graph.compile()
