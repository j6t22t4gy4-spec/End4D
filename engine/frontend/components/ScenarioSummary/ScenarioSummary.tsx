"use client";

import { useEffect, useState } from "react";
import { getTimelineSummary, type TimelineSummaryResponse } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";

type ScenarioSummaryProps = {
  worldId: string | null;
  refreshKey: number;
};

const OUTCOME_LABELS: Record<string, string> = {
  extinct: "Extinct",
  expanding: "Expanding",
  contracting: "Contracting",
  energy_accumulating: "Energy accumulating",
  energy_depleted: "Energy depleted",
  stable: "Stable",
  not_started: "Not started",
};

export function ScenarioSummary({ worldId, refreshKey }: ScenarioSummaryProps) {
  const [summary, setSummary] = useState<TimelineSummaryResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!worldId) {
      setSummary(null);
      setErr(null);
      return;
    }
    let cancelled = false;
    setErr(null);
    getTimelineSummary(worldId)
      .then((r) => {
        if (!cancelled) setSummary(r);
      })
      .catch((e) => {
        if (!cancelled) {
          setSummary(null);
          setErr((e as Error).message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [worldId, refreshKey]);

  if (!worldId) return null;

  return (
    <AppPanel
      title="Scenario Summary"
      subtitle="Outcome and trajectory snapshot"
      bodyClassName="space-y-3"
    >
      {err && (
        <p className="text-xs text-slate-500">
          시뮬 실행 후 요약이 표시됩니다.
        </p>
      )}
      {summary && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          <Metric label="outcome" value={OUTCOME_LABELS[summary.outcome] ?? summary.outcome} />
          <Metric label="cells" value={`${summary.initial_cell_count} -> ${summary.final_cell_count}`} />
          <Metric label="energy delta" value={formatDelta(summary.energy_delta)} />
          <Metric label="peak energy" value={formatNumber(summary.peak_total_energy)} />
        </div>
      )}
    </AppPanel>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] uppercase tracking-wide text-slate-500">{label}</p>
      <p className="mt-1 truncate text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}

function formatDelta(v: number): string {
  const sign = v > 0 ? "+" : "";
  return `${sign}${formatNumber(v)}`;
}

function formatNumber(v: number): string {
  return Math.round(v * 10).toLocaleString(undefined, {
    maximumFractionDigits: 1,
  });
}
