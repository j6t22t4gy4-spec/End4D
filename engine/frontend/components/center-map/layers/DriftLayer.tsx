"use client";

import type { ZoneBox } from "@/components/SimulationMap2D";

type DriftLayerProps = {
  zones: ZoneBox[];
  mapCenter: { x: number; y: number };
  renderTime: number;
};

export function DriftLayer({ zones, mapCenter, renderTime }: DriftLayerProps) {
  const driftingZones = zones
    .filter((zone) => zone.avgDrift > 0.04)
    .sort((a, b) => b.avgDrift - a.avgDrift)
    .slice(0, 6);

  return (
    <g className="simulation-map__drift-layer" aria-hidden="true">
      {driftingZones.map((zone) => {
        const cx = (zone.x0 + zone.x1) / 2;
        const cy = (zone.y0 + zone.y1) / 2;
        const dx = cx - mapCenter.x;
        const dy = cy - mapCenter.y;
        const length = Math.hypot(dx, dy) || 1;
        const ux = dx / length;
        const uy = dy / length;
        const driftScale = 18 + zone.avgDrift * 54;
        const x2 = cx + ux * driftScale;
        const y2 = cy + uy * driftScale;
        const pathId = `drift-path-${zone.zoneId}`;
        const arrowLeftX = x2 - ux * 8 - uy * 5;
        const arrowLeftY = y2 - uy * 8 + ux * 5;
        const arrowRightX = x2 - ux * 8 + uy * 5;
        const arrowRightY = y2 - uy * 8 - ux * 5;
        const opacity = Math.min(0.72, 0.22 + zone.avgDrift * 0.7);
        return (
          <g key={`drift-${zone.zoneId}`}>
            <path
              id={pathId}
              d={`M ${cx.toFixed(1)} ${cy.toFixed(1)} L ${x2.toFixed(1)} ${y2.toFixed(1)}`}
              fill="none"
              stroke="none"
            />
            <circle
              cx={cx}
              cy={cy}
              r={12 + zone.avgDrift * 18 + Math.sin(renderTime * 1.8 + cx * 0.01) * 1.2}
              fill="rgb(16, 185, 129)"
              fillOpacity={Math.min(0.18, opacity * 0.32)}
              stroke="none"
            />
            <line
              x1={cx}
              y1={cy}
              x2={x2}
              y2={y2}
              stroke="rgb(5, 150, 105)"
              strokeOpacity={opacity}
              strokeWidth={1.5 + zone.avgDrift * 2.4}
              strokeLinecap="round"
              strokeDasharray="5 8"
              className="simulation-map__drift-stream"
            />
            <circle
              cx={cx + (x2 - cx) * (((renderTime * (0.22 + zone.avgDrift * 0.34)) + (cx % 17) * 0.03) % 1)}
              cy={cy + (y2 - cy) * (((renderTime * (0.22 + zone.avgDrift * 0.34)) + (cx % 17) * 0.03) % 1)}
              r="3.2"
              fill="rgba(167, 243, 208, 0.95)"
              opacity={0.45 + Math.sin(renderTime * 4 + cx * 0.01) * 0.25}
            />
            <path
              d={`M ${arrowLeftX.toFixed(1)} ${arrowLeftY.toFixed(1)} L ${x2.toFixed(1)} ${y2.toFixed(1)} L ${arrowRightX.toFixed(1)} ${arrowRightY.toFixed(1)}`}
              fill="none"
              stroke="rgb(5, 150, 105)"
              strokeOpacity={opacity}
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
              className="simulation-map__drift-arrow"
            />
          </g>
        );
      })}
    </g>
  );
}
