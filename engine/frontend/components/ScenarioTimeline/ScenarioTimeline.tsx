"use client";

/**
 * t별 세포 수·에너지 합 (Phase 7.4, Recharts)
 */
import { useState, useEffect } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { getTimeline, type TimelinePoint } from "@/lib/api";

type ScenarioTimelineProps = {
  worldId: string | null;
  refreshKey: number;
};

export function ScenarioTimeline({ worldId, refreshKey }: ScenarioTimelineProps) {
  const [points, setPoints] = useState<TimelinePoint[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!worldId) {
      setPoints([]);
      setErr(null);
      return;
    }
    let cancelled = false;
    setErr(null);
    getTimeline(worldId)
      .then((r) => {
        if (!cancelled) setPoints(r.points);
      })
      .catch((e) => {
        if (!cancelled) setErr((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [worldId, refreshKey]);

  if (!worldId) {
    return null;
  }

  const chartData = points.map((p) => ({
    t: p.t,
    cells: p.cell_count,
    energy: Math.round(p.total_energy * 10) / 10,
  }));

  return (
    <section
      className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-2"
      data-testid="scenario-timeline"
    >
      <h2 className="text-sm font-medium text-slate-300">
        5. 시나리오 타임라인 (t별 세포 수·에너지 합)
      </h2>
      {err && (
        <p className="text-xs text-red-300" role="alert">
          {err}
        </p>
      )}
      {!err && chartData.length === 0 && (
        <p className="text-xs text-slate-500">시뮬 실행 후 데이터가 표시됩니다.</p>
      )}
      {chartData.length > 0 && (
        <div className="h-52 w-full min-w-0">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart
              data={chartData}
              margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
            >
              <XAxis dataKey="t" stroke="#94a3b8" fontSize={11} />
              <YAxis stroke="#94a3b8" fontSize={11} />
              <Tooltip
                contentStyle={{
                  background: "#0f172a",
                  border: "1px solid #334155",
                }}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="cells"
                name="세포 수"
                stroke="#22d3ee"
                dot={false}
                strokeWidth={2}
              />
              <Line
                type="monotone"
                dataKey="energy"
                name="에너지 합"
                stroke="#a78bfa"
                dot={false}
                strokeWidth={2}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </section>
  );
}
