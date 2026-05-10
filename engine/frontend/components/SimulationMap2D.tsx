"use client";

import { useMemo } from "react";

import {
  emotionToColorAndScale,
  type CellSnapshot,
} from "@/lib/api";

type SimulationMap2DProps = {
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
};

type ZoneBox = {
  zoneId: string;
  label: string;
  influence: number;
  friction: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  count: number;
};

const SVG_WIDTH = 960;
const SVG_HEIGHT = 640;
const PADDING = 56;

export default function SimulationMap2D({
  cells,
  totalCells,
  sampled,
}: SimulationMap2DProps) {
  const scene = useMemo(() => buildScene(cells), [cells]);

  return (
    <div className="simulation-map">
      <div className="simulation-map__header">
        <div>
          <p className="simulation-map__eyebrow">2D Social Field</p>
          <h3 className="simulation-map__title">Zone-aware agent communication surface</h3>
        </div>
        <div className="simulation-map__meta">
          <span>{cells.length.toLocaleString()} visible</span>
          <span>{totalCells.toLocaleString()} total</span>
          <span>{scene.zoneBoxes.length} zones</span>
          {sampled ? <span>sampled</span> : <span>full</span>}
        </div>
      </div>

      <div className="simulation-map__viewport">
        {cells.length === 0 ? (
          <div
            className="simulation-map__empty"
            data-testid="simulation-map-empty"
          >
            Run the simulation to populate the social field.
          </div>
        ) : (
          <svg
            className="simulation-map__svg"
            viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
            role="img"
            aria-label="2D social field simulation map"
          >
            <defs>
              <pattern
                id="map-grid"
                width="48"
                height="48"
                patternUnits="userSpaceOnUse"
              >
                <path
                  d="M 48 0 L 0 0 0 48"
                  fill="none"
                  stroke="rgba(148,163,184,0.18)"
                  strokeWidth="1"
                />
              </pattern>
            </defs>
            <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#f8fbfd" />
            <rect
              x={PADDING}
              y={PADDING}
              width={SVG_WIDTH - PADDING * 2}
              height={SVG_HEIGHT - PADDING * 2}
              rx="28"
              fill="url(#map-grid)"
            />

            {scene.zoneBoxes.map((zone, index) => (
              <g key={zone.zoneId}>
                <rect
                  x={zone.x0}
                  y={zone.y0}
                  width={Math.max(24, zone.x1 - zone.x0)}
                  height={Math.max(24, zone.y1 - zone.y0)}
                  rx="24"
                  fill={zoneBackground(index)}
                  stroke={zoneStroke(index)}
                  strokeWidth="1.5"
                />
                <text
                  x={zone.x0 + 14}
                  y={zone.y0 + 20}
                  className="simulation-map__zone-label"
                >
                  {zone.label} · {zone.count}
                </text>
              </g>
            ))}

            {scene.nodes.map((node) => (
              <g key={node.id}>
                <circle
                  cx={node.cx}
                  cy={node.cy}
                  r={node.r}
                  fill={node.fill}
                  fillOpacity="0.92"
                  stroke="#ffffff"
                  strokeWidth="1.5"
                />
                <title>{node.title}</title>
              </g>
            ))}
          </svg>
        )}
      </div>

      <div className="simulation-map__legend">
        {scene.zoneBoxes.slice(0, 5).map((zone, index) => (
          <div key={zone.zoneId} className="simulation-map__legend-item">
            <span
              className="simulation-map__legend-swatch"
              style={{ background: zoneBackground(index) }}
            />
            <div>
              <strong>{zone.label}</strong>
              <span>
                influence {zone.influence.toFixed(2)} · friction{" "}
                {zone.friction.toFixed(2)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function buildScene(cells: CellSnapshot[]) {
  if (cells.length === 0) {
    return { nodes: [], zoneBoxes: [] as ZoneBox[] };
  }

  const xs = cells.map((cell) => cell.x);
  const ys = cells.map((cell) => cell.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const innerWidth = SVG_WIDTH - PADDING * 2;
  const innerHeight = SVG_HEIGHT - PADDING * 2;

  const projectX = (x: number) => PADDING + ((x - minX) / spanX) * innerWidth;
  const projectY = (y: number) => PADDING + (1 - (y - minY) / spanY) * innerHeight;

  const zoneAcc = new Map<string, ZoneBox>();
  const nodes = cells.map((cell) => {
    const cx = projectX(cell.x);
    const cy = projectY(cell.y);
    const { rgb, scale } = emotionToColorAndScale(cell.emotion_vec);
    const fill = rgbToCss(rgb);
    const zoneId = cell.zone_id ?? "zone-0";
    const zoneLabel = cell.zone_label ?? zoneId;
    const box = zoneAcc.get(zoneId) ?? {
      zoneId,
      label: zoneLabel,
      influence: cell.zone_influence ?? 1,
      friction: cell.zone_friction ?? 0,
      x0: cx,
      x1: cx,
      y0: cy,
      y1: cy,
      count: 0,
    };
    box.x0 = Math.min(box.x0, cx);
    box.x1 = Math.max(box.x1, cx);
    box.y0 = Math.min(box.y0, cy);
    box.y1 = Math.max(box.y1, cy);
    box.count += 1;
    zoneAcc.set(zoneId, box);

    return {
      id: cell.cell_id,
      cx,
      cy,
      r: 4 + scale * 5,
      fill,
      title: `${cell.role_label ?? cell.role_key ?? "agent"} · ${
        zoneLabel
      } · energy ${cell.energy.toFixed(1)}`,
    };
  });

  const zoneBoxes = Array.from(zoneAcc.values())
    .map((zone) => ({
      ...zone,
      x0: Math.max(PADDING - 6, zone.x0 - 18),
      x1: Math.min(SVG_WIDTH - PADDING + 6, zone.x1 + 18),
      y0: Math.max(PADDING - 6, zone.y0 - 18),
      y1: Math.min(SVG_HEIGHT - PADDING + 6, zone.y1 + 18),
    }))
    .sort((a, b) => b.count - a.count);

  return { nodes, zoneBoxes };
}

function rgbToCss(rgb: [number, number, number]) {
  return `rgb(${Math.round(rgb[0] * 255)}, ${Math.round(
    rgb[1] * 255
  )}, ${Math.round(rgb[2] * 255)})`;
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
