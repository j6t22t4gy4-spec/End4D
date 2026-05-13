"use client";

import type { SelectedZone } from "@/components/SimulationInspectorPanel";
import type { ZoneBox } from "@/components/SimulationMap2D";

type ZoneLayerProps = {
  zones: ZoneBox[];
  selectedZoneId?: string | null;
  onSelectZone?: (zone: SelectedZone) => void;
};

export function ZoneLayer({
  zones,
  selectedZoneId = null,
  onSelectZone,
}: ZoneLayerProps) {
  return (
    <>
      {zones.map((zone, index) => (
        <g key={zone.zoneId}>
          <rect
            x={zone.x0}
            y={zone.y0}
            width={Math.max(24, zone.x1 - zone.x0)}
            height={Math.max(24, zone.y1 - zone.y0)}
            rx="24"
            fill={zoneBackground(index)}
            stroke={zoneStroke(index)}
            strokeWidth={selectedZoneId === zone.zoneId ? "3" : "1.5"}
            className="simulation-map__zone-rect"
            onClick={() =>
              onSelectZone?.({
                zoneId: zone.zoneId,
                label: zone.label,
                influence: zone.influence,
                friction: zone.friction,
                count: zone.count,
              })
            }
          />
          <text x={zone.x0 + 14} y={zone.y0 + 20} className="simulation-map__zone-label">
            {zone.label} · {zone.count}
          </text>
        </g>
      ))}
    </>
  );
}

function zoneBackground(index: number) {
  const palette = [
    "rgba(14, 165, 233, 0.10)",
    "rgba(59, 130, 246, 0.10)",
    "rgba(249, 115, 22, 0.10)",
    "rgba(16, 185, 129, 0.10)",
    "rgba(244, 114, 182, 0.10)",
  ];
  return palette[index % palette.length]!;
}

function zoneStroke(index: number) {
  const palette = [
    "rgba(2, 132, 199, 0.36)",
    "rgba(37, 99, 235, 0.36)",
    "rgba(234, 88, 12, 0.36)",
    "rgba(5, 150, 105, 0.36)",
    "rgba(219, 39, 119, 0.36)",
  ];
  return palette[index % palette.length]!;
}
