"""Benchmark Organic4D simulation throughput, review payload cost, and LLM runtime pressure.

Uses the deterministic embedding stub by default to focus on engine cost and
provide commit-to-commit regression checks on the same machine.

The optional mock-openai mode exercises the actual HTTP-based LLM runtime path
without depending on an external provider. It is useful for comparing runtime
profiles (`balanced` vs `llm-first`) and review citation repair pressure when a
real provider is not currently connected.
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import re
import statistics
import sys
import threading
import time
import tracemalloc
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterator, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("ORGANIC4D_EMBED_BACKEND", "stub")
os.environ.setdefault("ORGANIC4D_LLM_CHAT_ENABLED", "0")

from app.core.review_payloads import (  # noqa: E402
    build_cached_session_review_payload,
    build_review_diff_payload,
    build_world_review_payload,
)
from app.core.settings import get_llm_runtime_profile  # noqa: E402
from app.core.settings import (  # noqa: E402
    get_llm_api_key,
    get_llm_base_url,
    get_llm_chat_enabled,
    get_llm_model,
    get_llm_provider,
)
from app.core.snapshot import SnapshotStore  # noqa: E402
from app.graph.time_flow import create_time_flow_graph  # noqa: E402
from app.llm.facade import llm_facade  # noqa: E402


PRESETS: dict[str, list[int]] = {
    "smoke": [100, 1000],
    "scale": [1000, 5000, 10000],
    "stress": [10000, 25000, 50000],
    "mega": [10000, 25000, 50000, 100000],
}

LLM_BENCHMARK_MODES = ("disabled", "runtime-config", "mock-openai")


def llm_runtime_preflight(*, llm_mode: str) -> dict[str, Any]:
    provider = str(get_llm_provider() or "stub")
    enabled = bool(get_llm_chat_enabled())
    model = str(get_llm_model() or "stub")
    base_url = str(get_llm_base_url() or "")
    has_api_key = bool(get_llm_api_key())
    reasons: list[str] = []
    suggestions: list[str] = []
    ready = True
    if llm_mode == "disabled":
        ready = False
        reasons.append("llm_mode=disabled")
        suggestions.append("Switch to --llm-mode runtime-config or --llm-mode mock-openai.")
    elif llm_mode == "runtime-config":
        if not enabled:
            ready = False
            reasons.append("llm_disabled")
            suggestions.append("Enable LLM runtime in Setup and save the config before running a live baseline.")
        if provider == "stub":
            ready = False
            reasons.append("provider=stub")
            suggestions.append("Choose OpenAI, OpenAI-compatible, or Ollama instead of stub.")
        if provider in ("openai", "openai-compatible") and not has_api_key:
            ready = False
            reasons.append("api_key_missing")
            suggestions.append("Add an API key for the selected provider.")
        if provider != "stub" and not base_url:
            ready = False
            reasons.append("base_url_missing")
            suggestions.append("Provide a provider base URL before running runtime-config benchmarks.")
    diagnosis = "ready" if ready else ", ".join(reasons) or "not_ready"
    return {
        "ready": ready,
        "mode": llm_mode,
        "enabled": enabled,
        "provider": provider,
        "model": model,
        "base_url": base_url,
        "has_api_key": has_api_key,
        "diagnosis": diagnosis,
        "suggestions": suggestions,
    }


@dataclass(frozen=True)
class BenchmarkCase:
    label: str
    cells: int
    steps: int
    repeat: int
    llm_profile: str = "balanced"


@dataclass(frozen=True)
class BenchmarkSample:
    label: str
    cells: int
    steps: int
    repeat_index: int
    llm_profile: str
    llm_mode: str
    final_cells: int
    snapshots: int
    elapsed_sec: float
    steps_per_sec: float
    cell_steps_per_sec: float
    peak_memory_mb: float
    review_payload_sec: float = 0.0
    review_payload_kb: float = 0.0
    review_annotation_count: int = 0
    review_graph_edges: int = 0
    review_chain_count: int = 0
    review_curve_points: int = 0
    llm_live_call_rate: float = 0.0
    llm_fallback_rate: float = 0.0
    llm_stability_score: float = 0.0
    llm_provider_error_pressure: int = 0
    llm_total_repairs: int = 0
    llm_top_reasons: dict[str, int] = field(default_factory=dict)
    llm_task_repairs: dict[str, int] = field(default_factory=dict)


class _MockOpenAIState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.call_index = 0

    def next_call(self) -> int:
        with self.lock:
            self.call_index += 1
            return self.call_index


class _MockOpenAIHandler(BaseHTTPRequestHandler):
    state = _MockOpenAIState()

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        try:
            body = json.loads(raw or "{}")
        except json.JSONDecodeError:
            self._send(400, {"error": "invalid_json"})
            return
        if self.path.rstrip("/") != "/v1/chat/completions":
            self._send(404, {"error": "not_found"})
            return
        messages = list(body.get("messages") or [])
        system = str((messages[0] or {}).get("content") or "") if messages else ""
        user = str((messages[-1] or {}).get("content") or "") if messages else ""
        task = self._extract_task(system)
        call_index = self.state.next_call()
        content = self._mock_content(task=task, user=user, call_index=call_index)
        self._send(
            200,
            {
                "id": f"mock-{call_index}",
                "object": "chat.completion",
                "choices": [
                    {
                        "index": 0,
                        "message": {"role": "assistant", "content": content},
                        "finish_reason": "stop",
                    }
                ],
            },
        )

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _send(self, status: int, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(dict(payload), ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    @staticmethod
    def _extract_task(system_text: str) -> str:
        match = re.search(r"task=([a-z_]+)", system_text)
        return str(match.group(1)) if match else "unknown"

    @staticmethod
    def _extract_json_section(user_text: str, section: str) -> Any:
        lines = user_text.splitlines()
        marker = f"[{section.upper()}]"
        collecting = False
        buffer: list[str] = []
        for line in lines:
            if line.strip() == marker:
                collecting = True
                buffer = []
                continue
            if collecting and line.startswith("[") and line.endswith("]"):
                break
            if collecting:
                buffer.append(line)
        raw = "\n".join(buffer).strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return raw

    @classmethod
    def _extract_allowed_ids(cls, user_text: str) -> list[str]:
        repair_meta = cls._extract_json_section(user_text, "repair_meta")
        if isinstance(repair_meta, dict):
            return [str(item) for item in list(repair_meta.get("allowed_anchor_ids") or []) if str(item).strip()]
        return []

    @classmethod
    def _extract_required_keys(cls, user_text: str) -> list[str]:
        repair_meta = cls._extract_json_section(user_text, "repair_meta")
        if isinstance(repair_meta, dict):
            return [str(item) for item in list(repair_meta.get("required_keys") or []) if str(item).strip()]
        return []

    @classmethod
    def _extract_broken_output(cls, user_text: str) -> dict[str, Any] | None:
        section = cls._extract_json_section(user_text, "broken_output")
        return dict(section) if isinstance(section, dict) else None

    @classmethod
    def _repair_response(cls, user_text: str) -> str:
        allowed_ids = cls._extract_allowed_ids(user_text)
        required_keys = cls._extract_required_keys(user_text)
        repair_meta = cls._extract_json_section(user_text, "repair_meta")
        citation_mode = "map"
        if isinstance(repair_meta, dict):
            citation_mode = str(repair_meta.get("citation_mode") or "map")
        broken = cls._extract_broken_output(user_text) or {
            "headline": "Repaired analyst output",
            "executive_summary": "Repair filled missing citation links.",
            "key_events": ["Repair reconstructed missing event citations."],
            "causal_analysis": ["Repair reassigned invalid anchors to allowed evidence."],
            "decision_implications": ["Repair kept meaning while restoring grounding."],
            "watch_items": ["Check repeated repair reasons."],
            "answer": "Repair restored valid citations.",
            "evidence": ["Allowed anchors were reapplied."],
            "follow_up": ["Inspect repeated repair reasons in runtime telemetry."],
            "confidence_notes": ["Repair pass only changed citation bindings."],
            "key_findings": ["Repair restored session-level citation coverage."],
            "objective_explanation": "Repair preserved the original explanation while fixing anchors.",
        }
        if citation_mode == "list":
            broken["citations"] = allowed_ids[:2] or ["fallback-anchor"]
            return json.dumps(broken, ensure_ascii=False)
        citation_map = broken.get("citations")
        if not isinstance(citation_map, dict):
            citation_map = {}
        fallback_id = allowed_ids[0] if allowed_ids else "fallback-anchor"
        for idx, key in enumerate(required_keys):
            citation_map[str(key)] = [allowed_ids[min(idx, max(0, len(allowed_ids) - 1))] if allowed_ids else fallback_id]
        broken["citations"] = citation_map
        return json.dumps(broken, ensure_ascii=False)

    @classmethod
    def _mock_content(cls, *, task: str, user: str, call_index: int) -> str:
        if task == "review_citation_repair":
            return cls._repair_response(user)
        if task == "thought":
            return f"Agent reassesses pressure path {call_index % 5} and keeps a short tactical note."
        if task == "worldview":
            return f"Agent updates long-run worldview track {call_index % 4} with a compact ideological shift."
        if task == "action":
            return json.dumps(
                {
                    "strategy_summary": f"Mock action profile {call_index % 7}",
                    "resource_bias": 0.52,
                    "risk_tolerance": 0.41,
                    "cooperation_bias": 0.58,
                    "policy_sensitivity": 0.61,
                    "mobility_bias": 0.37,
                },
                ensure_ascii=False,
            )
        if task == "policy":
            return json.dumps(
                {
                    "memory_summary": f"Policy memory record {call_index % 5}",
                    "emotion_index": 0.56,
                    "emotion_delta": 0.08,
                    "cooperation_shift": 0.04,
                    "policy_sensitivity_shift": 0.11,
                    "importance": 0.64,
                },
                ensure_ascii=False,
            )
        if task == "dialogue":
            return json.dumps(
                {
                    "summary_a": "A revised stance slightly after dialogue.",
                    "summary_b": "B notes a small trust shift.",
                    "alignment_delta": 0.06,
                    "tension_delta": -0.03,
                    "cooperation_delta": 0.05,
                    "importance": 0.62,
                },
                ensure_ascii=False,
            )
        if task == "group_deliberation":
            return json.dumps(
                {
                    "stance_summary": "Group aligns around a tentative coalition move.",
                    "cohesion_delta": 0.07,
                    "tension_delta": -0.02,
                    "coalition_signal": "forming",
                    "importance": 0.66,
                },
                ensure_ascii=False,
            )

        if task == "review_summary":
            citations = {
                "headline": ["event:policy-0"],
                "key_events.0": ["event:policy-0"],
                "causal_analysis.0": ["group:workers"],
                "decision_implications.0": ["zone:metro"],
            }
            mode = call_index % 3
            if mode == 0:
                citations.pop("decision_implications.0", None)
            elif mode == 1:
                citations["causal_analysis.0"] = ["invalid-anchor"]
            payload = {
                "headline": "Policy shock reorganized one dominant group lane.",
                "executive_summary": "Review summary highlights a policy-led transition across group and zone layers.",
                "key_events": ["A policy injection created a visible turning point."],
                "causal_analysis": ["The policy first shifted a role group, then propagated into a hotspot zone."],
                "decision_implications": ["Follow up on the affected zone and stabilize the group bridge."],
                "watch_items": ["Monitor repeated zone pressure after the policy shock."],
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        if task == "review_diff":
            citations = {
                "key_deltas.0": ["group:workers"],
                "causal_comparison.0": ["event:policy-0"],
                "decision_implications.0": ["zone:metro"],
            }
            mode = call_index % 3
            if mode == 0:
                citations["key_deltas.0"] = ["invalid-anchor"]
            elif mode == 1:
                citations.pop("causal_comparison.0", None)
            payload = {
                "headline": "Target world diverged through a stronger policy-to-group pathway.",
                "executive_summary": "Diff summary notes a sharper policy propagation and zone drift in the target world.",
                "key_deltas": ["The target world amplified group drift more than baseline."],
                "causal_comparison": ["A stronger policy bridge produced a larger downstream zone fracture."],
                "decision_implications": ["Re-run from the turning point with a stabilizing policy channel."],
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        if task == "review_query":
            citations = ["group:workers"]
            mode = call_index % 3
            if mode == 0:
                citations = []
            elif mode == 1:
                citations = ["invalid-anchor"]
            payload = {
                "answer": "The worker-aligned group moved the most in this run.",
                "evidence": ["Its cohesion and zone drift changed together after the policy event."],
                "follow_up": ["Inspect the worker group in the hotspot zone."],
                "confidence_notes": ["Confidence rises when the same pattern appears in the diff view."],
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        if task == "review_diff_query":
            citations = ["event:policy-0"]
            if call_index % 2 == 0:
                citations = ["invalid-anchor"]
            payload = {
                "answer": "The target diverged because the policy bridge hit a more fracture-prone group.",
                "evidence": ["The target showed a stronger policy-lineage bridge and larger zone gap."],
                "follow_up": ["Branch from the turning point and dampen the bridge channel."],
                "confidence_notes": ["This answer depends on the dominant policy event remaining the same."],
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        if task == "session_review":
            citations = {
                "key_findings.0": ["world:bench-a"],
                "decision_implications.0": ["world:bench-b"],
            }
            if call_index % 2 == 1:
                citations["key_findings.0"] = ["invalid-anchor"]
            payload = {
                "headline": "Session shows a repeated ideology migration pattern.",
                "executive_summary": "Across worlds, the same group transition repeats under similar policy pressure.",
                "key_findings": ["One world family repeatedly drifts toward the same regime pattern."],
                "decision_implications": ["Use the more stable branch as the next experimental baseline."],
                "objective_explanation": "The leading world suppresses split risk while preserving cohesion.",
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        if task == "session_review_query":
            citations = ["world:bench-a"]
            if call_index % 2 == 0:
                citations = []
            payload = {
                "answer": "The most stable world is the one with the lowest split-risk trend.",
                "evidence": ["Its lineage and fracture signals stay flatter than peers."],
                "follow_up": ["Compare it directly against the most volatile branch."],
                "confidence_notes": ["Session-level answers are stronger when multiple worlds share the same signal."],
                "citations": citations,
            }
            return json.dumps(payload, ensure_ascii=False)

        return json.dumps({"ok": True, "task": task, "call_index": call_index}, ensure_ascii=False)


@contextlib.contextmanager
def mock_openai_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockOpenAIHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"
    try:
        yield base_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


@contextlib.contextmanager
def temporary_llm_env(
    *,
    llm_mode: str,
    llm_profile: str,
    strict_mode: str,
    base_url: str | None = None,
) -> Iterator[None]:
    keys = [
        "ORGANIC4D_LLM_CHAT_ENABLED",
        "ORGANIC4D_LLM_PROVIDER",
        "ORGANIC4D_LLM_MODEL",
        "ORGANIC4D_LLM_BASE_URL",
        "ORGANIC4D_LLM_API_KEY",
        "ORGANIC4D_LLM_RUNTIME_PROFILE",
        "ORGANIC4D_LLM_STRICT_MODE",
        "ORGANIC4D_LLM_CYCLE_PROMPT_BUDGET",
        "ORGANIC4D_LLM_AGENT_SAMPLE_SIZE",
        "ORGANIC4D_DIALOGUE_MAX_PAIRS",
        "ORGANIC4D_GROUP_DELIBERATION_MAX_GROUPS",
    ]
    previous = {key: os.environ.get(key) for key in keys}
    try:
        os.environ["ORGANIC4D_LLM_RUNTIME_PROFILE"] = llm_profile
        os.environ["ORGANIC4D_LLM_STRICT_MODE"] = strict_mode
        if llm_mode == "disabled":
            os.environ["ORGANIC4D_LLM_CHAT_ENABLED"] = "0"
            os.environ.setdefault("ORGANIC4D_LLM_PROVIDER", "stub")
            os.environ.setdefault("ORGANIC4D_LLM_MODEL", "stub")
        elif llm_mode == "runtime-config":
            # Keep existing provider/model env if present, but force runtime profile/strict mode.
            pass
        elif llm_mode == "mock-openai":
            os.environ["ORGANIC4D_LLM_CHAT_ENABLED"] = "1"
            os.environ["ORGANIC4D_LLM_PROVIDER"] = "openai-compatible"
            os.environ["ORGANIC4D_LLM_MODEL"] = "mock-analyst"
            os.environ["ORGANIC4D_LLM_BASE_URL"] = str(base_url or "")
            os.environ["ORGANIC4D_LLM_API_KEY"] = "mock-key"
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _run_review_suite(*, entry: dict[str, Any]) -> None:
    payload = build_world_review_payload(entry)
    llm_facade.summarize_review(payload)
    llm_facade.query_review(payload, question="Which group shifted the most and why?")
    diff_payload = build_review_diff_payload(base_payload=payload, target_payload=payload)
    llm_facade.compare_reviews(diff_payload=diff_payload)
    llm_facade.query_review_diff(diff_payload, question="What changed most between the two worlds?")
    session_payload = build_cached_session_review_payload(
        {"session_id": "bench-session", "title": "Benchmark Session"},
        [entry],
        objective="balanced",
    )
    llm_facade.summarize_session_review(session_payload)
    llm_facade.query_session_review(session_payload, question="Which world is most stable and why?")


def run_sample(
    case: BenchmarkCase,
    repeat_index: int,
    *,
    include_review_payload: bool = False,
    include_review_suite: bool = False,
    llm_mode: str = "disabled",
    llm_strict_mode: str = "adaptive",
) -> BenchmarkSample:
    store = SnapshotStore(world_id=f"bench-{case.llm_profile}-{case.label}-{repeat_index}")
    graph = create_time_flow_graph()
    llm_facade.reset_stats()
    review_payload_sec = 0.0
    review_payload_kb = 0.0
    review_annotation_count = 0
    review_graph_edges = 0
    review_chain_count = 0
    review_curve_points = 0

    with contextlib.ExitStack() as stack:
        mock_base_url = None
        if llm_mode == "mock-openai":
            mock_base_url = stack.enter_context(mock_openai_server())
        stack.enter_context(
            temporary_llm_env(
                llm_mode=llm_mode,
                llm_profile=case.llm_profile,
                strict_mode=llm_strict_mode,
                base_url=mock_base_url,
            )
        )

        tracemalloc.start()
        start = time.perf_counter()
        out = graph.invoke(
            {
                "initial_cell_count": case.cells,
                "t_max": float(case.steps),
                "snapshot_store": store,
            },
            config={"recursion_limit": case.steps + 80},
        )
        elapsed = time.perf_counter() - start
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        final_cells = len(out["cells"])
        entry = {
            "world": SimpleNamespace(world_id=store.world_id, nutrients=[]),
            "snapshot_store": store,
            "genesis_prompt": f"benchmark:{case.label}",
            "persona_country": "bench",
            "config_version": "bench",
            "session_id": "bench-session",
            "role_catalog": [],
            "engine_params": {},
            "coalition_state": {},
            "coalition_history": [],
        }
        if include_review_payload:
            review_start = time.perf_counter()
            payload = build_world_review_payload(entry)
            review_payload_sec = round(time.perf_counter() - review_start, 6)
            review_payload_kb = round(len(json.dumps(payload, ensure_ascii=False).encode("utf-8")) / 1024.0, 3)
            review_annotation_count = len(list(payload.get("annotation_candidates") or []))
            review_graph_edges = len(list((payload.get("belief_graph") or {}).get("edges") or []))
            review_chain_count = len(list(payload.get("causal_chains") or []))
            review_curve_points = len(list((payload.get("emergent_dynamics") or {}).get("worldview_curve") or []))
        if include_review_suite:
            _run_review_suite(entry=entry)
        runtime_stats = llm_facade.snapshot_stats()

    repair_summary = dict(runtime_stats.get("repair_summary") or {})
    task_repairs = {
        str(item.get("task") or ""): int(item.get("repair_count") or 0)
        for item in list(repair_summary.get("task_repairs") or [])
        if str(item.get("task") or "")
    }
    top_reasons = {
        str(item.get("reason") or ""): int(item.get("count") or 0)
        for item in list(repair_summary.get("top_reasons") or [])
        if str(item.get("reason") or "")
    }
    health = dict(runtime_stats.get("health") or {})
    return BenchmarkSample(
        label=case.label,
        cells=case.cells,
        steps=case.steps,
        repeat_index=repeat_index,
        llm_profile=case.llm_profile,
        llm_mode=llm_mode,
        final_cells=final_cells,
        snapshots=len(store.list_t()),
        elapsed_sec=round(elapsed, 6),
        steps_per_sec=round(case.steps / elapsed, 4) if elapsed > 0 else 0.0,
        cell_steps_per_sec=round((case.cells * case.steps) / elapsed, 4) if elapsed > 0 else 0.0,
        peak_memory_mb=round(peak / (1024 * 1024), 4),
        review_payload_sec=review_payload_sec,
        review_payload_kb=review_payload_kb,
        review_annotation_count=review_annotation_count,
        review_graph_edges=review_graph_edges,
        review_chain_count=review_chain_count,
        review_curve_points=review_curve_points,
        llm_live_call_rate=round(float(health.get("live_call_rate") or 0.0), 4),
        llm_fallback_rate=round(float(health.get("recent_fallback_rate") or 0.0), 4),
        llm_stability_score=round(float(health.get("stability_score") or 0.0), 4),
        llm_provider_error_pressure=int((runtime_stats.get("optimizer") or {}).get("provider_error_pressure") or 0),
        llm_total_repairs=int(repair_summary.get("total_repairs") or 0),
        llm_top_reasons=top_reasons,
        llm_task_repairs=task_repairs,
    )


def build_cases(
    *,
    cells: list[int],
    steps: int,
    repeat: int,
    preset: str | None,
    llm_profiles: list[str] | None = None,
) -> list[BenchmarkCase]:
    if preset:
        cells = list(PRESETS.get(preset, cells))
    profiles = [str(item) for item in (llm_profiles or ["balanced"])]
    cases: list[BenchmarkCase] = []
    for profile in profiles:
        for cells_count in cells:
            cases.append(
                BenchmarkCase(
                    label=f"{profile}:{cells_count}c-{steps}s",
                    cells=int(cells_count),
                    steps=int(steps),
                    repeat=int(repeat),
                    llm_profile=profile,
                )
            )
    return cases


def summarize_case(case: BenchmarkCase, samples: list[BenchmarkSample]) -> dict[str, Any]:
    elapsed = [sample.elapsed_sec for sample in samples]
    throughput = [sample.cell_steps_per_sec for sample in samples]
    memory = [sample.peak_memory_mb for sample in samples]
    payload_sec = [sample.review_payload_sec for sample in samples]
    payload_kb = [sample.review_payload_kb for sample in samples]
    annotation_counts = [sample.review_annotation_count for sample in samples]
    graph_edges = [sample.review_graph_edges for sample in samples]
    chain_counts = [sample.review_chain_count for sample in samples]
    curve_points = [sample.review_curve_points for sample in samples]
    llm_live_rates = [sample.llm_live_call_rate for sample in samples]
    llm_fallback_rates = [sample.llm_fallback_rate for sample in samples]
    llm_stabilities = [sample.llm_stability_score for sample in samples]
    llm_repairs = [sample.llm_total_repairs for sample in samples]
    llm_provider_pressure = [sample.llm_provider_error_pressure for sample in samples]
    top_reasons: dict[str, int] = {}
    task_repairs: dict[str, int] = {}
    for sample in samples:
        for reason, count in dict(sample.llm_top_reasons or {}).items():
            top_reasons[str(reason)] = int(top_reasons.get(str(reason), 0)) + int(count)
        for task, count in dict(sample.llm_task_repairs or {}).items():
            task_repairs[str(task)] = int(task_repairs.get(str(task), 0)) + int(count)
    return {
        "label": case.label,
        "cells": case.cells,
        "steps": case.steps,
        "repeat": case.repeat,
        "llm_profile": case.llm_profile,
        "final_cells_last": samples[-1].final_cells if samples else case.cells,
        "snapshots_last": samples[-1].snapshots if samples else 0,
        "elapsed_sec_avg": round(statistics.fmean(elapsed), 6) if elapsed else 0.0,
        "elapsed_sec_min": round(min(elapsed), 6) if elapsed else 0.0,
        "elapsed_sec_max": round(max(elapsed), 6) if elapsed else 0.0,
        "cell_steps_per_sec_avg": round(statistics.fmean(throughput), 4) if throughput else 0.0,
        "cell_steps_per_sec_min": round(min(throughput), 4) if throughput else 0.0,
        "cell_steps_per_sec_max": round(max(throughput), 4) if throughput else 0.0,
        "peak_memory_mb_avg": round(statistics.fmean(memory), 4) if memory else 0.0,
        "peak_memory_mb_max": round(max(memory), 4) if memory else 0.0,
        "review_payload_sec_avg": round(statistics.fmean(payload_sec), 6) if payload_sec else 0.0,
        "review_payload_kb_avg": round(statistics.fmean(payload_kb), 3) if payload_kb else 0.0,
        "review_annotation_count_max": max(annotation_counts) if annotation_counts else 0,
        "review_graph_edges_max": max(graph_edges) if graph_edges else 0,
        "review_chain_count_max": max(chain_counts) if chain_counts else 0,
        "review_curve_points_max": max(curve_points) if curve_points else 0,
        "llm_live_call_rate_avg": round(statistics.fmean(llm_live_rates), 4) if llm_live_rates else 0.0,
        "llm_fallback_rate_avg": round(statistics.fmean(llm_fallback_rates), 4) if llm_fallback_rates else 0.0,
        "llm_stability_score_avg": round(statistics.fmean(llm_stabilities), 4) if llm_stabilities else 0.0,
        "llm_total_repairs_avg": round(statistics.fmean(llm_repairs), 3) if llm_repairs else 0.0,
        "llm_provider_error_pressure_max": max(llm_provider_pressure) if llm_provider_pressure else 0,
        "llm_top_reasons": [
            {"reason": str(reason), "count": int(count)}
            for reason, count in sorted(top_reasons.items(), key=lambda item: (-int(item[1]), str(item[0])))[:6]
        ],
        "llm_task_repairs": [
            {"task": str(task), "count": int(count)}
            for task, count in sorted(task_repairs.items(), key=lambda item: (-int(item[1]), str(item[0])))[:6]
        ],
    }


def _build_profile_comparison(summaries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[int, int], dict[str, dict[str, Any]]] = {}
    for summary in summaries:
        key = (int(summary.get("cells") or 0), int(summary.get("steps") or 0))
        grouped.setdefault(key, {})[str(summary.get("llm_profile") or "balanced")] = summary
    comparisons: list[dict[str, Any]] = []
    for (cells, steps), profiles in sorted(grouped.items()):
        balanced = profiles.get("balanced")
        llm_first = profiles.get("llm-first")
        if not balanced or not llm_first:
            continue
        balanced_reasons = {str(item.get("reason") or ""): int(item.get("count") or 0) for item in list(balanced.get("llm_top_reasons") or []) if str(item.get("reason") or "")}
        llm_first_reasons = {str(item.get("reason") or ""): int(item.get("count") or 0) for item in list(llm_first.get("llm_top_reasons") or []) if str(item.get("reason") or "")}
        all_reasons = sorted(set(balanced_reasons) | set(llm_first_reasons))
        comparisons.append(
            {
                "cells": cells,
                "steps": steps,
                "balanced_live_call_rate": float(balanced.get("llm_live_call_rate_avg") or 0.0),
                "llm_first_live_call_rate": float(llm_first.get("llm_live_call_rate_avg") or 0.0),
                "balanced_repairs": float(balanced.get("llm_total_repairs_avg") or 0.0),
                "llm_first_repairs": float(llm_first.get("llm_total_repairs_avg") or 0.0),
                "balanced_stability": float(balanced.get("llm_stability_score_avg") or 0.0),
                "llm_first_stability": float(llm_first.get("llm_stability_score_avg") or 0.0),
                "repair_reason_deltas": [
                    {
                        "reason": reason,
                        "balanced": int(balanced_reasons.get(reason, 0)),
                        "llm_first": int(llm_first_reasons.get(reason, 0)),
                        "delta": int(llm_first_reasons.get(reason, 0)) - int(balanced_reasons.get(reason, 0)),
                    }
                    for reason in all_reasons
                ],
            }
        )
    return comparisons


def run_benchmarks(
    cases: list[BenchmarkCase],
    *,
    include_review_payload: bool = False,
    include_review_suite: bool = False,
    llm_mode: str = "disabled",
    llm_strict_mode: str = "adaptive",
) -> dict[str, Any]:
    preflight = llm_runtime_preflight(llm_mode=llm_mode)
    if llm_mode == "runtime-config" and not preflight["ready"]:
        suggestion_text = " ".join(str(item) for item in list(preflight.get("suggestions") or []))
        raise SystemExit(
            f"runtime-config benchmark is not ready: {preflight['diagnosis']}. {suggestion_text}".strip()
        )
    all_samples: list[BenchmarkSample] = []
    summaries: list[dict[str, Any]] = []
    for case in cases:
        case_samples = [
            run_sample(
                case,
                idx + 1,
                include_review_payload=include_review_payload,
                include_review_suite=include_review_suite,
                llm_mode=llm_mode,
                llm_strict_mode=llm_strict_mode,
            )
            for idx in range(case.repeat)
        ]
        all_samples.extend(case_samples)
        summaries.append(summarize_case(case, case_samples))
    return {
        "schema_version": "benchmark-report/v3",
        "environment": {
            "embed_backend": os.getenv("ORGANIC4D_EMBED_BACKEND", ""),
            "llm_chat_enabled": os.getenv("ORGANIC4D_LLM_CHAT_ENABLED", ""),
            "llm_effective_enabled": llm_mode != "disabled",
            "snapshot_interval": os.getenv("ORGANIC4D_SNAPSHOT_INTERVAL", ""),
            "include_review_payload": include_review_payload,
            "include_review_suite": include_review_suite,
            "llm_mode": llm_mode,
            "llm_strict_mode": llm_strict_mode,
            "profiles": sorted({case.llm_profile for case in cases}),
            "llm_preflight": preflight,
        },
        "summaries": summaries,
        "samples": [asdict(sample) for sample in all_samples],
        "profile_comparison": _build_profile_comparison(summaries),
    }


def _render_text_report(report: dict[str, Any]) -> str:
    lines = []
    for summary in report["summaries"]:
        reason_text = ", ".join(
            f"{item['reason']}:{item['count']}" for item in list(summary.get("llm_top_reasons") or [])[:3]
        )
        lines.append(
            " ".join(
                [
                    f"label={summary['label']}",
                    f"cells={summary['cells']}",
                    f"steps={summary['steps']}",
                    f"repeat={summary['repeat']}",
                    f"elapsed_avg={summary['elapsed_sec_avg']}s",
                    f"cell_steps/s_avg={summary['cell_steps_per_sec_avg']}",
                    f"peak_mem_max={summary['peak_memory_mb_max']}MB",
                    f"review_payload_avg={summary['review_payload_sec_avg']}s",
                    f"review_payload_kb_avg={summary['review_payload_kb_avg']}",
                    f"review_chains_max={summary['review_chain_count_max']}",
                    f"review_curve_points_max={summary['review_curve_points_max']}",
                    f"llm_live_avg={summary['llm_live_call_rate_avg']}",
                    f"llm_fallback_avg={summary['llm_fallback_rate_avg']}",
                    f"llm_stability_avg={summary['llm_stability_score_avg']}",
                    f"llm_repairs_avg={summary['llm_total_repairs_avg']}",
                    f"llm_top_reasons={reason_text or '-'}",
                ]
            )
        )
    if report.get("profile_comparison"):
        lines.append("--- profile_comparison ---")
        for item in list(report.get("profile_comparison") or []):
            lines.append(
                " ".join(
                    [
                        f"cells={item['cells']}",
                        f"steps={item['steps']}",
                        f"balanced_live={item['balanced_live_call_rate']}",
                        f"llm_first_live={item['llm_first_live_call_rate']}",
                        f"balanced_repairs={item['balanced_repairs']}",
                        f"llm_first_repairs={item['llm_first_repairs']}",
                    ]
                )
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark simulation runs")
    parser.add_argument("--cells", type=int, nargs="+", default=[100, 1000])
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--repeat", type=int, default=3)
    parser.add_argument("--preset", choices=sorted(PRESETS.keys()))
    parser.add_argument("--snapshot-interval", type=int, default=None)
    parser.add_argument(
        "--include-review-payload",
        action="store_true",
        help="Also benchmark review payload build time/size on the latest snapshot set",
    )
    parser.add_argument(
        "--include-review-suite",
        action="store_true",
        help="Run review summary/diff/query/session tasks too, so repair/runtime stats are populated",
    )
    parser.add_argument(
        "--llm-mode",
        choices=LLM_BENCHMARK_MODES,
        default="disabled",
        help="disabled=stub/off, runtime-config=respect current env/config, mock-openai=exercise live HTTP LLM path locally",
    )
    parser.add_argument(
        "--llm-profiles",
        nargs="+",
        default=["balanced"],
        help="Runtime profiles to compare, e.g. balanced llm-first",
    )
    parser.add_argument(
        "--llm-strict-mode",
        choices=["adaptive", "llm-preferred", "fail-hard"],
        default="adaptive",
    )
    parser.add_argument("--json", action="store_true", help="Print JSON report")
    parser.add_argument("--output", type=str, default="", help="Optional path to write JSON report")
    args = parser.parse_args()

    if args.snapshot_interval is not None:
        os.environ["ORGANIC4D_SNAPSHOT_INTERVAL"] = str(max(1, int(args.snapshot_interval)))

    cases = build_cases(
        cells=list(args.cells),
        steps=args.steps,
        repeat=args.repeat,
        preset=args.preset,
        llm_profiles=list(args.llm_profiles),
    )
    report = run_benchmarks(
        cases,
        include_review_payload=args.include_review_payload,
        include_review_suite=args.include_review_suite,
        llm_mode=args.llm_mode,
        llm_strict_mode=args.llm_strict_mode,
    )

    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return

    print(_render_text_report(report))


if __name__ == "__main__":
    main()
