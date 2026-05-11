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
  ReferenceDot,
} from "recharts";
import { getTimeline, type TimelineAnnotation, type TimelinePoint } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";

type ScenarioTimelineProps = {
  worldId: string | null;
  refreshKey: number;
  annotations?: TimelineAnnotation[];
  onJumpToT?: (t: number) => void;
};

export function ScenarioTimeline({
  worldId,
  refreshKey,
  annotations = [],
  onJumpToT,
}: ScenarioTimelineProps) {
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
    <AppPanel
      title="Timeline"
      subtitle="Cells and energy over time"
      bodyClassName="space-y-2"
      testId="scenario-timeline"
    >
      {err && (
        <p className="text-xs text-rose-700" role="alert">
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
                  background: "#ffffff",
                  border: "1px solid #cbd5e1",
                  borderRadius: "16px",
                  boxShadow: "0 12px 32px rgba(15, 23, 42, 0.08)",
                }}
              />
              <Legend />
              {annotations.map((item) => {
                const matched = chartData.find((point) => point.t === item.t) ?? chartData[0];
                return (
                  <ReferenceDot
                    key={`${item.t}-${item.label}`}
                    x={item.t}
                    y={matched?.cells ?? 0}
                    r={5}
                    fill={annotationColor(item.severity)}
                    stroke="#ffffff"
                    strokeWidth={1.5}
                    ifOverflow="extendDomain"
                    onClick={() => onJumpToT?.(item.t)}
                  />
                );
              })}
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
    </AppPanel>
  );
}

function annotationColor(severity: string) {
  if (severity === "high") return "#dc2626";
  if (severity === "medium") return "#ea580c";
  return "#0284c7";
}
