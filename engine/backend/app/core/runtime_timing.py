"""Small runtime timing helper for simulation phases."""
from __future__ import annotations

from contextlib import contextmanager
import time
from typing import Callable, Iterator


class RuntimeTimer:
    """Collect low-overhead phase timings for one simulation step."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or time.perf_counter
        self._started_at = self._clock()
        self._phase_ms: dict[str, float] = {}
        self._phase_counts: dict[str, int] = {}

    @contextmanager
    def phase(self, name: str) -> Iterator[None]:
        started = self._clock()
        try:
            yield
        finally:
            elapsed_ms = max(0.0, (self._clock() - started) * 1000.0)
            key = str(name or "unknown")
            self._phase_ms[key] = self._phase_ms.get(key, 0.0) + elapsed_ms
            self._phase_counts[key] = self._phase_counts.get(key, 0) + 1

    def snapshot(self) -> dict:
        total_ms = max(0.0, (self._clock() - self._started_at) * 1000.0)
        phases = {
            name: {
                "ms": round(value, 3),
                "count": int(self._phase_counts.get(name, 0)),
            }
            for name, value in sorted(self._phase_ms.items())
        }
        dominant = max(self._phase_ms.items(), key=lambda item: item[1])[0] if self._phase_ms else ""
        return {
            "total_ms": round(total_ms, 3),
            "dominant_phase": dominant,
            "phases": phases,
        }
