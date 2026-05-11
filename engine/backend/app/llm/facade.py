"""Convenient, task-oriented LLM entrypoints for the simulation engine."""
from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Any, Iterable, Mapping, Sequence

from app.core.settings import (
    get_dialogue_max_pairs,
    get_group_deliberation_max_groups,
    get_llm_api_key,
    get_llm_agent_sample_size,
    get_llm_chat_enabled,
    get_llm_cycle_prompt_budget,
    get_llm_model,
    get_llm_provider,
    get_llm_strict_mode,
    get_llm_task_budget,
    get_llm_task_budgets,
    get_llm_task_priorities,
    get_llm_task_priority,
)
from app.llm.chat_runtime import generate_reasoning_batch
from app.llm.prompt_engineering import (
    build_action_prompt,
    build_dialogue_prompt,
    build_group_deliberation_prompt,
    build_policy_prompt,
    build_thought_prompt,
    build_worldview_prompt,
)
from app.llm.prompt_registry import get_prompt_meta, get_prompt_version
from app.llm.review import (
    build_agent_interview_prompt,
    build_agent_interview_diff_prompt,
    build_review_diff_prompt,
    build_review_diff_query_prompt,
    build_review_query_prompt,
    build_review_summary_prompt,
    build_session_review_prompt,
    build_session_review_query_prompt,
    build_timeline_annotation_prompt,
    heuristic_review_diff,
    heuristic_review_diff_query,
    heuristic_review_query,
    heuristic_review_summary,
    heuristic_agent_interview,
    heuristic_agent_interview_diff,
    heuristic_session_review,
    heuristic_session_review_query,
    parse_review_diff,
    parse_review_diff_query,
    parse_review_query,
    parse_agent_interview,
    parse_agent_interview_diff,
    parse_review_summary,
    parse_session_review,
    parse_session_review_query,
    parse_timeline_annotations,
    heuristic_timeline_annotations,
)
from app.models.cell import Cell


class LLMFacade:
    """High-level engine-facing LLM interface.

    Engine modules should call these task-specific methods instead of stitching
    prompt construction and provider invocation together on their own.
    """

    def __init__(self):
        self._lock = Lock()
        self._recent_runs: deque[dict[str, Any]] = deque(maxlen=32)
        self._task_totals: dict[str, dict[str, int]] = {}
        self._scheduler: dict[str, Any] = {
            "cycle_key": "default",
            "cycle_budget_total": get_llm_cycle_prompt_budget(),
            "cycle_budget_remaining": get_llm_cycle_prompt_budget(),
            "context": {},
        }

    def begin_cycle(self, cycle_key: str, *, context: Mapping[str, Any] | None = None) -> None:
        payload = dict(context or {})
        with self._lock:
            if self._scheduler.get("cycle_key") == cycle_key:
                self._scheduler["context"] = payload
                return
            total = get_llm_cycle_prompt_budget()
            self._scheduler = {
                "cycle_key": cycle_key,
                "cycle_budget_total": total,
                "cycle_budget_remaining": total,
                "context": payload,
            }

    def think(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_thought_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="thought")

    def update_worldviews(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_worldview_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="worldview")

    def decide_actions(self, cells: Sequence[Cell]) -> list[str]:
        prompts = [build_action_prompt(cell) for cell in cells]
        return self._run_task(prompts, task="action")

    def interpret_policy(
        self,
        cells: Sequence[Cell],
        *,
        event_type: str,
        payload: Mapping,
    ) -> list[str]:
        prompts = [build_policy_prompt(cell, event_type, dict(payload)) for cell in cells]
        return self._run_task(prompts, task="policy")

    def run_dialogues(
        self,
        pairs: Sequence[tuple[Cell, Cell]],
        *,
        current_t: float,
    ) -> list[str]:
        prompts = [
            build_dialogue_prompt(a, b, current_t=current_t)
            for a, b in pairs
        ]
        return self._run_task(prompts, task="dialogue")

    def deliberate_groups(
        self,
        groups: Mapping[str, Sequence[Cell]],
        *,
        current_t: float,
    ) -> list[str]:
        prompts = [
            build_group_deliberation_prompt(role, list(cells), current_t=current_t)
            for role, cells in groups.items()
        ]
        return self._run_task(prompts, task="group_deliberation")

    def plan_genesis(self, prompt_text: str, heuristic_payload: Mapping) -> str:
        prompt = (
            f"prompt_version={get_prompt_version('genesis')}\n"
            f"user_prompt={prompt_text}\n"
            "Heuristic baseline:\n"
            f"{heuristic_payload}\n"
            "Return JSON only."
        )
        out = self._run_task([prompt], task="genesis")
        return out[0] if out else prompt

    def summarize_review(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        prompt = build_review_summary_prompt(payload)
        texts, meta = self._run_task_with_meta([prompt], task="review_summary")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        summary = (
            heuristic_review_summary(payload)
            if used_heuristic
            else parse_review_summary(text, payload)
        )
        return {
            "summary": summary,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("review_summary"),
            "prompt_meta": get_prompt_meta("review_summary"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def annotate_timeline(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        prompt = build_timeline_annotation_prompt(payload)
        texts, meta = self._run_task_with_meta([prompt], task="timeline_annotation")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        annotations = (
            heuristic_timeline_annotations(payload)
            if used_heuristic
            else parse_timeline_annotations(text, payload)
        )
        return {
            "annotations": annotations,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("timeline_annotation"),
            "prompt_meta": get_prompt_meta("timeline_annotation"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def compare_reviews(
        self,
        *,
        diff_payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        prompt = build_review_diff_prompt(diff_payload)
        texts, meta = self._run_task_with_meta([prompt], task="review_diff")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        summary = (
            heuristic_review_diff(diff_payload)
            if used_heuristic
            else parse_review_diff(text, diff_payload)
        )
        return {
            "diff": summary,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("review_diff"),
            "prompt_meta": get_prompt_meta("review_diff"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def query_review(
        self,
        payload: Mapping[str, Any],
        *,
        question: str,
    ) -> dict[str, Any]:
        prompt = build_review_query_prompt(payload, question)
        texts, meta = self._run_task_with_meta([prompt], task="review_query")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        answer = (
            heuristic_review_query(payload, question)
            if used_heuristic
            else parse_review_query(text, payload, question)
        )
        return {
            "query": answer,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("review_query"),
            "prompt_meta": get_prompt_meta("review_query"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def query_review_diff(
        self,
        diff_payload: Mapping[str, Any],
        *,
        question: str,
    ) -> dict[str, Any]:
        prompt = build_review_diff_query_prompt(diff_payload, question)
        texts, meta = self._run_task_with_meta([prompt], task="review_diff_query")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        answer = (
            heuristic_review_diff_query(diff_payload, question)
            if used_heuristic
            else parse_review_diff_query(text, diff_payload, question)
        )
        return {
            "query": answer,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("review_diff_query"),
            "prompt_meta": get_prompt_meta("review_diff_query"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def summarize_session_review(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        prompt = build_session_review_prompt(payload)
        texts, meta = self._run_task_with_meta([prompt], task="session_review")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        summary = (
            heuristic_session_review(payload)
            if used_heuristic
            else parse_session_review(text, payload)
        )
        return {
            "summary": summary,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("session_review"),
            "prompt_meta": get_prompt_meta("session_review"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def interview_agent(
        self,
        *,
        cell: Cell,
        question: str,
        grounding: Mapping[str, Any],
    ) -> dict[str, Any]:
        prompt = build_agent_interview_prompt(cell=cell, question=question, grounding=grounding)
        texts, meta = self._run_task_with_meta([prompt], task="agent_interview")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        answer = (
            heuristic_agent_interview(cell=cell, question=question, grounding=grounding)
            if used_heuristic
            else parse_agent_interview(text, cell=cell, question=question, grounding=grounding)
        )
        return {
            "query": answer,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("agent_interview"),
            "prompt_meta": get_prompt_meta("agent_interview"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def interview_agent_diff(
        self,
        *,
        current_cell: Cell,
        base_cell: Cell,
        question: str,
        grounding: Mapping[str, Any],
    ) -> dict[str, Any]:
        prompt = build_agent_interview_diff_prompt(
            current_cell=current_cell,
            base_cell=base_cell,
            question=question,
            grounding=grounding,
        )
        texts, meta = self._run_task_with_meta([prompt], task="agent_interview_diff")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        answer = (
            heuristic_agent_interview_diff(
                current_cell=current_cell,
                base_cell=base_cell,
                question=question,
                grounding=grounding,
            )
            if used_heuristic
            else parse_agent_interview_diff(
                text,
                current_cell=current_cell,
                base_cell=base_cell,
                question=question,
                grounding=grounding,
            )
        )
        return {
            "query": answer,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("agent_interview_diff"),
            "prompt_meta": get_prompt_meta("agent_interview_diff"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def query_session_review(
        self,
        payload: Mapping[str, Any],
        *,
        question: str,
    ) -> dict[str, Any]:
        prompt = build_session_review_query_prompt(payload, question)
        texts, meta = self._run_task_with_meta([prompt], task="session_review_query")
        text = str(texts[0] if texts else "").strip()
        used_heuristic = (not text) or text == prompt or text.startswith("[PROMPT_CONTRACT]")
        answer = (
            heuristic_session_review_query(payload, question)
            if used_heuristic
            else parse_session_review_query(text, payload, question)
        )
        return {
            "query": answer,
            "mode": "heuristic" if used_heuristic else "llm",
            "prompt_version": get_prompt_version("session_review_query"),
            "prompt_meta": get_prompt_meta("session_review_query"),
            "provider": str(meta.get("provider") or get_llm_provider()),
            "model": str(meta.get("model") or get_llm_model()),
            "fallback_reason": str(meta.get("fallback_reason") or ""),
        }

    def snapshot_stats(self) -> dict[str, Any]:
        with self._lock:
            recent_runs = [dict(item) for item in self._recent_runs]
            fallback_runs = [item for item in recent_runs if bool(item.get("used_fallback"))]
            recent_count = len(recent_runs)
            fallback_rate = (len(fallback_runs) / recent_count) if recent_count else 0.0
            last_fallback_reason = str(fallback_runs[-1].get("fallback_reason") or "") if fallback_runs else ""
            provider = get_llm_provider()
            enabled = get_llm_chat_enabled()
            has_api_key = bool(get_llm_api_key())
            if not enabled:
                health_status = "disabled"
                health_reason = "llm_disabled"
            elif provider in ("openai", "openai-compatible") and not has_api_key:
                health_status = "auth-missing"
                health_reason = "api_key_missing"
            elif recent_count == 0:
                health_status = "ready"
                health_reason = "awaiting_calls"
            elif fallback_rate >= 0.6:
                health_status = "degraded"
                health_reason = last_fallback_reason or "fallback_pressure"
            elif fallback_rate > 0.0:
                health_status = "warning"
                health_reason = last_fallback_reason or "partial_fallbacks"
            else:
                health_status = "healthy"
                health_reason = "live_llm_calls_dominant"
            return {
                "provider": provider,
                "model": get_llm_model(),
                "strict_mode": get_llm_strict_mode(),
                "cycle_prompt_budget": get_llm_cycle_prompt_budget(),
                "agent_sample_size": get_llm_agent_sample_size(),
                "dialogue_max_pairs": get_dialogue_max_pairs(),
                "group_deliberation_max_groups": get_group_deliberation_max_groups(),
                "task_budgets": get_llm_task_budgets(),
                "task_priorities": get_llm_task_priorities(),
                "scheduler": dict(self._scheduler),
                "recent_runs": recent_runs,
                "task_totals": {
                    key: dict(value)
                    for key, value in self._task_totals.items()
                },
                "health": {
                    "status": health_status,
                    "reason": health_reason,
                    "recent_call_count": recent_count,
                    "recent_fallback_count": len(fallback_runs),
                    "recent_fallback_rate": round(fallback_rate, 4),
                    "last_fallback_reason": last_fallback_reason,
                },
            }

    def reset_stats(self) -> None:
        with self._lock:
            self._recent_runs.clear()
            self._task_totals.clear()
            total = get_llm_cycle_prompt_budget()
            self._scheduler = {
                "cycle_key": "default",
                "cycle_budget_total": total,
                "cycle_budget_remaining": total,
                "context": {},
            }

    def _run_task(self, prompts: Iterable[str], *, task: str) -> list[str]:
        texts, _ = self._run_task_with_meta(prompts, task=task)
        return texts

    def _run_task_with_meta(self, prompts: Iterable[str], *, task: str) -> tuple[list[str], dict[str, Any]]:
        items = [str(prompt) for prompt in prompts]
        if not items:
            return [], {
                "task": task,
                "provider": get_llm_provider(),
                "model": get_llm_model(),
                "prompt_count_in": 0,
                "prompt_count_sent": 0,
            }
        task_budget = get_llm_task_budget(task)
        scheduler = self._reserve_prompts(task=task, requested=len(items), task_budget=task_budget)
        active_budget = int(scheduler["allowed"])
        active_items = items[:active_budget]
        skipped_by_scheduler = items[active_budget:]
        batch = generate_reasoning_batch(active_items, task=task)
        texts = list(batch.get("texts") or []) + skipped_by_scheduler
        meta = dict(batch.get("meta") or {})
        meta.update(
            {
                "task": task,
                "prompt_version": get_prompt_version(task),
                "prompt_meta": dict(meta.get("prompt_meta") or get_prompt_meta(task)),
                "provider": str(meta.get("provider") or get_llm_provider()),
                "model": str(meta.get("model") or get_llm_model()),
                "task_budget": int(task_budget),
                "task_priority": int(get_llm_task_priority(task)),
                "prompt_count_in": len(items),
                "prompt_count_sent": int(meta.get("prompt_count_sent", len(active_items))),
                "prompt_count_skipped_by_task_budget": int(scheduler["skipped_by_task_budget"]),
                "prompt_count_skipped_by_cycle_budget": int(scheduler["skipped_by_cycle_budget"]),
                "cycle_key": str(scheduler["cycle_key"]),
                "cycle_budget_total": int(scheduler["cycle_budget_total"]),
                "cycle_budget_remaining_before": int(scheduler["cycle_budget_remaining_before"]),
                "cycle_budget_remaining_after": int(scheduler["cycle_budget_remaining_after"]),
            }
        )
        if skipped_by_scheduler:
            meta["used_fallback"] = True
            fallback_reason = str(meta.get("fallback_reason") or "")
            reasons: list[str] = [part for part in fallback_reason.split("|") if part]
            if int(scheduler["skipped_by_task_budget"]) > 0:
                reasons.append("task_budget_cap")
            if int(scheduler["skipped_by_cycle_budget"]) > 0:
                reasons.append("cycle_budget_cap")
            if int(scheduler["adaptive_skip"]) > 0:
                reasons.append("adaptive_priority_skip")
            meta["fallback_reason"] = "|".join(dict.fromkeys(reasons))
        self._record_run(meta)
        return texts, meta

    def _reserve_prompts(self, *, task: str, requested: int, task_budget: int) -> dict[str, Any]:
        with self._lock:
            cycle_key = str(self._scheduler.get("cycle_key") or "default")
            total = int(self._scheduler.get("cycle_budget_total", get_llm_cycle_prompt_budget()))
            remaining_before = int(self._scheduler.get("cycle_budget_remaining", total))
            priority = int(get_llm_task_priority(task))
            capped_by_task = min(requested, task_budget)
            adaptive_cap = self._adaptive_cap(
                priority=priority,
                remaining=remaining_before,
                total=total,
                requested=capped_by_task,
            )
            allowed = min(capped_by_task, remaining_before, adaptive_cap)
            allowed = max(0, allowed)
            remaining_after = max(0, remaining_before - allowed)
            self._scheduler["cycle_budget_remaining"] = remaining_after
            skipped_by_task_budget = max(0, requested - min(requested, task_budget))
            skipped_after_task = max(0, requested - min(requested, task_budget))
            skipped_by_cycle_budget = max(0, capped_by_task - allowed)
            adaptive_skip = max(0, capped_by_task - min(capped_by_task, remaining_before) if adaptive_cap < min(capped_by_task, remaining_before) else 0)
            return {
                "allowed": allowed,
                "cycle_key": cycle_key,
                "cycle_budget_total": total,
                "cycle_budget_remaining_before": remaining_before,
                "cycle_budget_remaining_after": remaining_after,
                "skipped_by_task_budget": skipped_by_task_budget,
                "skipped_by_cycle_budget": skipped_by_cycle_budget,
                "adaptive_skip": adaptive_skip,
                "skipped_after_task": skipped_after_task,
            }

    def _adaptive_cap(self, *, priority: int, remaining: int, total: int, requested: int) -> int:
        if total <= 0:
            return 0
        ratio = remaining / total
        if ratio <= 0.10 and priority >= 2:
            return 0
        if ratio <= 0.20 and priority >= 1:
            return max(0, min(requested, 1))
        if ratio <= 0.35 and priority >= 3:
            return max(0, min(requested, requested // 2))
        if ratio <= 0.50 and priority >= 4:
            return max(0, min(requested, requested // 2))
        return requested

    def _record_run(self, meta: Mapping[str, Any]) -> None:
        task = str(meta.get("task") or "unknown")
        prompt_count_in = int(meta.get("prompt_count_in", 0) or 0)
        prompt_count_sent = int(meta.get("prompt_count_sent", 0) or 0)
        skipped = int(meta.get("prompt_count_skipped_by_task_budget", 0) or 0)
        skipped_by_cycle = int(meta.get("prompt_count_skipped_by_cycle_budget", 0) or 0)
        used_fallback = 1 if bool(meta.get("used_fallback")) else 0
        with self._lock:
            totals = self._task_totals.setdefault(
                task,
                {
                    "calls": 0,
                    "prompt_count_in": 0,
                    "prompt_count_sent": 0,
                    "prompt_count_skipped_by_task_budget": 0,
                    "prompt_count_skipped_by_cycle_budget": 0,
                    "fallback_calls": 0,
                },
            )
            totals["calls"] += 1
            totals["prompt_count_in"] += prompt_count_in
            totals["prompt_count_sent"] += prompt_count_sent
            totals["prompt_count_skipped_by_task_budget"] += skipped
            totals["prompt_count_skipped_by_cycle_budget"] += skipped_by_cycle
            totals["fallback_calls"] += used_fallback
            self._recent_runs.append(
                {
                    "task": task,
                    "provider": str(meta.get("provider") or ""),
                    "model": str(meta.get("model") or ""),
                    "prompt_version": str(meta.get("prompt_version") or ""),
                    "prompt_output_mode": str((meta.get("prompt_meta") or {}).get("output_mode") or ""),
                    "prompt_expected_keys": list((meta.get("prompt_meta") or {}).get("expected_keys") or []),
                    "prompt_count_in": prompt_count_in,
                    "prompt_count_sent": prompt_count_sent,
                    "prompt_count_skipped_by_task_budget": skipped,
                    "prompt_count_skipped_by_cycle_budget": skipped_by_cycle,
                    "task_budget": int(meta.get("task_budget", 0) or 0),
                    "task_priority": int(meta.get("task_priority", 0) or 0),
                    "cycle_key": str(meta.get("cycle_key") or ""),
                    "cycle_budget_total": int(meta.get("cycle_budget_total", 0) or 0),
                    "cycle_budget_remaining_before": int(meta.get("cycle_budget_remaining_before", 0) or 0),
                    "cycle_budget_remaining_after": int(meta.get("cycle_budget_remaining_after", 0) or 0),
                    "used_fallback": bool(meta.get("used_fallback")),
                    "fallback_reason": str(meta.get("fallback_reason") or ""),
                }
            )


llm_facade = LLMFacade()
