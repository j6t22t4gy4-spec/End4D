"use client";

import type { AgentNode } from "@/components/SimulationMap2D";
import type { TimelineAnnotation } from "@/lib/api";

type ShockLayerProps = {
  nodes: AgentNode[];
  annotations: TimelineAnnotation[];
  currentT: number;
  renderTime: number;
};

export function ShockLayer({
  nodes,
  annotations,
  currentT,
  renderTime,
}: ShockLayerProps) {
  const activeAnnotations = annotations
    .filter((item) => Math.abs(Number(item.t ?? 0) - currentT) <= 6)
    .slice(0, 4);

  if (!activeAnnotations.length || !nodes.length) return null;

  const anchorNodes = [...nodes]
    .sort((a, b) => {
      const left = Number(b.fractureSignal) - Number(a.fractureSignal);
      if (left !== 0) return left;
      return b.collectivePressure - a.collectivePressure;
    })
    .slice(0, activeAnnotations.length);

  return (
    <g className="simulation-map__shock-layer">
      {activeAnnotations.map((annotation, index) => {
        const anchor = anchorNodes[index % anchorNodes.length];
        if (!anchor) return null;
        const isNearCurrent = Math.abs(Number(annotation.t ?? 0) - currentT) <= 2;
        const outer = 28 + index * 8 + (isNearCurrent ? 10 : 0);
        const middle = outer * 0.72;
        const inner = Math.max(10, outer * 0.26);
        const color = shockColor(String(annotation.severity ?? "medium"));
        const phase = (renderTime * (1.3 + index * 0.18)) % 1;
        const midPhase = (renderTime * (1.8 + index * 0.2)) % 1;
        const corePhase = (Math.sin(renderTime * 4 + index) + 1) / 2;
        return (
          <g key={`shock-${index}-${annotation.t}-${annotation.label}`}>
            <circle
              cx={anchor.cx}
              cy={anchor.cy}
              r={outer * (0.68 + phase * 0.5)}
              fill="none"
              stroke={color}
              strokeOpacity={0.5 - phase * 0.46}
              strokeWidth="2"
              strokeDasharray="6 8"
              className="simulation-map__shock-ring simulation-map__shock-ring--outer"
            />
            <circle
              cx={anchor.cx}
              cy={anchor.cy}
              r={middle * (0.78 + midPhase * 0.34)}
              fill="none"
              stroke={color}
              strokeOpacity={0.58 - midPhase * 0.42}
              strokeWidth="2"
              className="simulation-map__shock-ring simulation-map__shock-ring--middle"
            />
            <circle
              cx={anchor.cx}
              cy={anchor.cy}
              r={inner * (0.9 + corePhase * 0.32)}
              fill={color}
              fillOpacity={0.12 + corePhase * 0.22}
              stroke={color}
              strokeOpacity={0.6}
              strokeWidth="1.5"
              className="simulation-map__shock-core"
            />
            <text
              x={anchor.cx + 12}
              y={anchor.cy - 10}
              className="simulation-map__zone-label simulation-map__shock-label"
              fill={color}
            >
              {annotation.label}
            </text>
          </g>
        );
      })}
    </g>
  );
}

function shockColor(severity: string) {
  if (severity === "high") return "rgb(244, 63, 94)";
  if (severity === "medium") return "rgb(249, 115, 22)";
  return "rgb(56, 189, 248)";
}
