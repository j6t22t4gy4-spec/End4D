"use client";

import { useMemo } from "react";
import type { RuntimeTiming } from "@/lib/api";

type RuntimeTimingCardProps = {
  timing: RuntimeTiming | null;
  isKo: boolean;
};

export function RuntimeTimingCard({ timing, isKo }: RuntimeTimingCardProps) {
  const phaseRows = useMemo(() => {
    const phases = timing?.phases ?? {};
    return Object.entries(phases)
      .map(([phase, payload]) => ({
        phase,
        ms: Number(payload?.ms ?? 0),
        count: Number(payload?.count ?? 0),
      }))
      .sort((a, b) => b.ms - a.ms)
      .slice(0, 5);
  }, [timing]);
  const totalMs = Number(timing?.total_ms ?? 0);
  const dominant = String(timing?.dominant_phase ?? "");

  return (
    <section className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
            {isKo ? "엔진 타이밍" : "Engine Timing"}
          </p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {isKo ? "최근 step의 실제 backend phase 시간입니다." : "Backend phase timings from the latest step."}
          </p>
        </div>
        <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
          {totalMs > 0 ? formatMs(totalMs) : "pending"}
        </span>
      </div>
      {phaseRows.length ? (
        <div className="mt-3 space-y-2">
          {dominant ? (
            <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {isKo ? "현재 병목" : "Dominant"} · {formatPhaseName(dominant)} ·{" "}
              {formatMs(phaseRows.find((row) => row.phase === dominant)?.ms ?? 0)}
            </div>
          ) : null}
          {phaseRows.map((row) => {
            const ratio = totalMs > 0 ? Math.min(1, row.ms / totalMs) : 0;
            return (
              <div key={row.phase} className="space-y-1">
                <div className="flex items-center justify-between gap-3 text-xs">
                  <span className="truncate font-medium text-slate-700">{formatPhaseName(row.phase)}</span>
                  <span className="shrink-0 text-slate-500">
                    {formatMs(row.ms)}
                    {row.count > 1 ? ` · x${row.count}` : ""}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className={`h-full rounded-full ${row.phase === dominant ? "bg-amber-500" : "bg-sky-500"}`}
                    style={{ width: `${Math.max(4, Math.round(ratio * 100))}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 rounded-2xl border border-dashed border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-500">
          {isKo ? "아직 완료된 step timing이 없습니다." : "No completed step timing yet."}
        </p>
      )}
    </section>
  );
}

function formatMs(value: number): string {
  if (!Number.isFinite(value) || value <= 0) return "0ms";
  if (value >= 1000) return `${(value / 1000).toFixed(value >= 10_000 ? 1 : 2)}s`;
  return `${Math.round(value)}ms`;
}

function formatPhaseName(value: string): string {
  return String(value || "unknown").replaceAll("_", " ");
}
