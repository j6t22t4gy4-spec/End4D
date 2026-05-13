"use client";

import type { ZoneBox } from "@/components/SimulationMap2D";

type ClusterLayerProps = {
  zones: ZoneBox[];
  renderTime: number;
  pointerField: {
    x: number;
    y: number;
    active: boolean;
  };
};

export function ClusterLayer({ zones, renderTime, pointerField }: ClusterLayerProps) {
  const activeZones = zones
    .filter((zone) => zone.count >= 2)
    .sort((a, b) => (b.avgPressure + b.avgDrift * 0.7) - (a.avgPressure + a.avgDrift * 0.7))
    .slice(0, 5);
  const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 34 : 12);
  const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 28 : 10);

  return (
    <g className="simulation-map__cluster-layer" aria-hidden="true">
      {activeZones.map((zone, index) => {
        const cx = (zone.x0 + zone.x1) / 2;
        const cy = (zone.y0 + zone.y1) / 2;
        const width = Math.max(80, (zone.x1 - zone.x0) * (1.2 + zone.avgPressure * 0.8));
        const height = Math.max(54, (zone.y1 - zone.y0) * (1.18 + zone.avgDrift * 0.9));
        const wobbleX = Math.sin(renderTime * (0.32 + index * 0.07) + index) * (8 + index * 2);
        const wobbleY = Math.cos(renderTime * (0.26 + index * 0.05) + index * 1.2) * (6 + index * 1.5);
        const pulse = 0.94 + ((Math.sin(renderTime * (0.8 + index * 0.11) + index) + 1) / 2) * 0.18;
        const fieldPullX = pointerPushX * (0.18 + zone.avgPressure * 0.28);
        const fieldPullY = pointerPushY * (0.16 + zone.avgDrift * 0.32);
        const rx = (width / 2) * pulse;
        const ry = (height / 2) * pulse;
        const opacity = Math.min(
          0.34,
          0.1 + zone.avgPressure * 0.22 + zone.avgDrift * 0.16 + (pointerField.active ? 0.03 : 0)
        );
        const fill = clusterFill(zone.avgPressure, zone.avgDrift, index);
        return (
          <g key={`cluster-${zone.zoneId}`}>
            <ellipse
              cx={cx + wobbleX + fieldPullX}
              cy={cy + wobbleY + fieldPullY}
              rx={rx * 1.14}
              ry={ry * 1.1}
              fill={fill}
              fillOpacity={opacity * 0.45}
              stroke="none"
              filter="url(#map-glow-soft)"
            />
            <ellipse
              cx={cx + wobbleX * 0.82 + fieldPullX}
              cy={cy + wobbleY * 0.82 + fieldPullY}
              rx={rx}
              ry={ry}
              fill={fill}
              fillOpacity={opacity}
              stroke="rgba(255,255,255,0.06)"
              strokeWidth="1"
              filter="url(#map-glow-soft)"
            />
          </g>
        );
      })}
    </g>
  );
}

function clusterFill(avgPressure: number, avgDrift: number, index: number) {
  if (avgPressure >= 0.45) return "rgb(251, 113, 133)";
  if (avgDrift >= 0.24) return "rgb(45, 212, 191)";
  const palette = [
    "rgb(56, 189, 248)",
    "rgb(99, 102, 241)",
    "rgb(168, 85, 247)",
    "rgb(34, 197, 94)",
  ];
  return palette[index % palette.length]!;
}
