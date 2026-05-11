"use client";

/**
 * t별 세포 수·에너지 합 (Phase 7.4, Recharts)
 */
import { useState, useEffect, useMemo } from "react";
import {
  BarChart,
  Bar,
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
import { type UiLocale } from "@/lib/ui-language";

type ScenarioTimelineProps = {
  locale?: UiLocale;
  worldId: string | null;
  refreshKey: number;
  annotations?: TimelineAnnotation[];
  emergentCurve?: Array<{ t: number; avg_z: number; cell_count: number }>;
  onJumpToT?: (t: number) => void;
};

export function ScenarioTimeline({
  locale = "ko",
  worldId,
  refreshKey,
  annotations = [],
  emergentCurve = [],
  onJumpToT,
}: ScenarioTimelineProps) {
  const isKo = locale === "ko";
  const [points, setPoints] = useState<TimelinePoint[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"both" | "cells" | "energy" | "events" | "worldview">("both");

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

  const eventIndex = useMemo(
    () =>
      Object.fromEntries(
        annotations.map((item) => [
          String(item.t),
          {
            label: item.label,
            severity: item.severity,
            score: severityScore(item.severity),
          },
        ])
      ),
    [annotations]
  );

  const chartData = useMemo(
    () =>
      points.map((p) => {
        const matched = eventIndex[String(p.t)];
        return {
          t: p.t,
          cells: p.cell_count,
          energy: Math.round(p.total_energy * 10) / 10,
          eventLoad: matched?.score ?? 0,
          eventLabel: matched?.label ?? "",
        };
      }),
    [eventIndex, points]
  );

  const latestAnnotations = annotations.slice().sort((left, right) => right.t - left.t).slice(0, 4);

  return (
    <AppPanel
      title={isKo ? "타임라인" : "Timeline"}
      subtitle={isKo ? "실행 추세, 에너지 흐름, 주요 이벤트 압력" : "Run trend, energy flow, and key event pressure"}
      bodyClassName="space-y-2"
      testId="scenario-timeline"
    >
      <div className="flex flex-wrap gap-2">
        {[
          ["both", isKo ? "개요" : "Overview"],
          ["cells", isKo ? "세포" : "Cells"],
          ["energy", isKo ? "에너지" : "Energy"],
          ["events", isKo ? "이벤트" : "Events"],
          ["worldview", isKo ? "세계관" : "Worldview"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            className={`app-button ${mode === value ? "app-button--primary" : "app-button--ghost"}`}
            onClick={() => setMode(value as "both" | "cells" | "energy" | "events" | "worldview")}
          >
            {label}
          </button>
        ))}
      </div>
      {err && (
        <p className="text-xs text-rose-700" role="alert">
          {err}
        </p>
      )}
      {!err && chartData.length === 0 && (
        <p className="text-xs text-slate-500">시뮬 실행 후 데이터가 표시됩니다.</p>
      )}
      {chartData.length > 0 && (
        <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_280px]">
          <div className="h-72 w-full min-w-0 xl:h-[20rem]">
            <ResponsiveContainer width="100%" height="100%">
              {mode === "events" ? (
                <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <XAxis dataKey="t" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip
                    contentStyle={tooltipStyle}
                    formatter={(value) => [`${value}`, "event pressure"]}
                    labelFormatter={(label) => `t=${label}`}
                  />
                  <Bar dataKey="eventLoad" fill="#f59e0b" radius={[8, 8, 0, 0]} />
                </BarChart>
              ) : mode === "worldview" ? (
                <LineChart
                  data={emergentCurve.map((item) => ({
                    t: item.t,
                    avgZ: Math.round(item.avg_z * 100) / 100,
                    cells: item.cell_count,
                  }))}
                  margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                >
                  <XAxis dataKey="t" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="avgZ"
                    name="Avg social elevation"
                    stroke="#0f766e"
                    dot={false}
                    strokeWidth={2.5}
                  />
                  <Line
                    type="monotone"
                    dataKey="cells"
                    name="Tracked cells"
                    stroke="#1d4ed8"
                    dot={false}
                    strokeWidth={1.5}
                  />
                </LineChart>
              ) : (
                <LineChart
                  data={chartData}
                  margin={{ top: 8, right: 8, left: 0, bottom: 0 }}
                >
                  <XAxis dataKey="t" stroke="#94a3b8" fontSize={11} />
                  <YAxis stroke="#94a3b8" fontSize={11} />
                  <Tooltip contentStyle={tooltipStyle} />
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
                  {(mode === "both" || mode === "cells") && (
                    <Line
                      type="monotone"
                      dataKey="cells"
                      name="세포 수"
                      stroke="#22d3ee"
                      dot={false}
                      strokeWidth={2}
                    />
                  )}
                  {(mode === "both" || mode === "energy") && (
                    <Line
                      type="monotone"
                      dataKey="energy"
                      name="에너지 합"
                      stroke="#a78bfa"
                      dot={false}
                      strokeWidth={2}
                    />
                  )}
                </LineChart>
              )}
            </ResponsiveContainer>
          </div>
          <div className="grid gap-2">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isKo ? "분석 메모" : "Analysis Notes"}
              </p>
              <p className="mt-2 text-sm leading-6 text-slate-600">
                {isKo
                  ? "`Overview`는 전체 추세, `Events`는 annotation이 집중된 시점, `Worldview`는 사회적 고도와 장기 emergent dynamics를 따로 읽기 위한 레이어입니다."
                  : "`Overview` shows total trends, `Events` isolates annotation pressure, and `Worldview` tracks long-run social elevation dynamics."}
              </p>
            </div>
            {latestAnnotations.length ? (
              <div className="grid gap-2">
                {latestAnnotations.map((item) => (
                  <button
                    key={`${item.t}-${item.label}-summary`}
                    type="button"
                    className="session-thread-card text-left"
                    onClick={() => onJumpToT?.(item.t)}
                  >
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">{item.label}</p>
                      <span className="session-thread-card__meta">t={item.t}</span>
                    </div>
                    <p className="session-thread-card__prompt">{item.reason}</p>
                  </button>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-500">{isKo ? "아직 자동 annotation이 없습니다." : "No automatic annotations yet."}</p>
            )}
          </div>
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

function severityScore(severity: string) {
  if (severity === "high") return 3;
  if (severity === "medium") return 2;
  return 1;
}

const tooltipStyle = {
  background: "#ffffff",
  border: "1px solid #cbd5e1",
  borderRadius: "16px",
  boxShadow: "0 12px 32px rgba(15, 23, 42, 0.08)",
};
