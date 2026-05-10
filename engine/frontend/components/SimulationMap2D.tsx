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

type ElevationBand = {
  key: string;
  d: string;
  label: string;
  alpha: number;
};

type ZSemantics = {
  mode: string;
  label: string;
  subtitle: string;
  rangeLabel: string;
  contourName: string;
  fills: string[];
  strokes: string[];
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
          <p className="simulation-map__subtitle">
            {scene.zSemantics.subtitle}
          </p>
        </div>
        <div className="simulation-map__meta">
          <span>{cells.length.toLocaleString()} visible</span>
          <span>{totalCells.toLocaleString()} total</span>
          <span>{scene.zoneBoxes.length} zones</span>
          <span>{scene.zSemantics.rangeLabel} {scene.zRange.min.toFixed(1)}-{scene.zRange.max.toFixed(1)}</span>
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

            {scene.elevationBands.map((band, index) => (
              <path
                key={band.key}
                d={band.d}
                className="simulation-map__contour-band"
                style={{
                  fill: contourFill(scene.zSemantics, index, band.alpha),
                  stroke: contourStroke(scene.zSemantics, index),
                }}
              >
                <title>{band.label}</title>
              </path>
            ))}

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
        <div className="simulation-map__legend-item simulation-map__legend-item--elevation">
          <span
            className="simulation-map__legend-contour"
            style={{
              background: contourLegendFill(scene.zSemantics),
              borderColor: contourStroke(scene.zSemantics, 1),
            }}
          />
          <div>
            <strong>{scene.zLabel}</strong>
            <span>
              {scene.zSemantics.contourName} {scene.zRange.min.toFixed(1)} to {scene.zRange.max.toFixed(1)}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

function buildScene(cells: CellSnapshot[]) {
  if (cells.length === 0) {
    return {
      nodes: [],
      zoneBoxes: [] as ZoneBox[],
      elevationBands: [] as ElevationBand[],
      zRange: { min: 0, max: 0 },
      zLabel: "social elevation",
      zSemantics: zSemanticsForMode("hybrid"),
    };
  }

  const xs = cells.map((cell) => cell.x);
  const ys = cells.map((cell) => cell.y);
  const zs = cells.map((cell) => cell.z ?? 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const minZ = Math.min(...zs);
  const maxZ = Math.max(...zs);
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

  const elevationBands = buildElevationBands({
    cells,
    projectX,
    projectY,
    minZ,
    maxZ,
  });
  const zMode = inferZMode(cells);
  const zSemantics = zSemanticsForMode(zMode);

  return {
    nodes,
    zoneBoxes,
    elevationBands,
    zRange: { min: minZ, max: maxZ },
    zLabel: zSemantics.label,
    zSemantics,
  };
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

function contourFill(semantics: ZSemantics, index: number, alpha: number) {
  const color = semantics.fills[index % semantics.fills.length]!;
  return color.replace("__ALPHA__", alpha.toFixed(3));
}

function contourStroke(semantics: ZSemantics, index: number) {
  return semantics.strokes[index % semantics.strokes.length]!;
}

function buildElevationBands({
  cells,
  projectX,
  projectY,
  minZ,
  maxZ,
}: {
  cells: CellSnapshot[];
  projectX: (x: number) => number;
  projectY: (y: number) => number;
  minZ: number;
  maxZ: number;
}) {
  const bandCount = 4;
  const spanZ = Math.max(0.001, maxZ - minZ);
  const bands: ElevationBand[] = [];

  for (let index = 0; index < bandCount; index += 1) {
    const lower = minZ + (spanZ * index) / bandCount;
    const upper = minZ + (spanZ * (index + 1)) / bandCount;
    const selected = cells.filter((cell) => {
      const z = cell.z ?? 0;
      if (index === bandCount - 1) return z >= lower && z <= upper;
      return z >= lower && z < upper;
    });
    if (selected.length < 2) continue;

    const xs = selected.map((cell) => projectX(cell.x));
    const ys = selected.map((cell) => projectY(cell.y));
    const x0 = Math.max(PADDING - 8, Math.min(...xs) - 20);
    const x1 = Math.min(SVG_WIDTH - PADDING + 8, Math.max(...xs) + 20);
    const y0 = Math.max(PADDING - 8, Math.min(...ys) - 20);
    const y1 = Math.min(SVG_HEIGHT - PADDING + 8, Math.max(...ys) + 20);
    const d = roundedRectPath(x0, y0, Math.max(22, x1 - x0), Math.max(22, y1 - y0), 28);
    bands.push({
      key: `band-${index}`,
      d,
      label: `elevation ${lower.toFixed(1)}-${upper.toFixed(1)}`,
      alpha: 0.08 + index * 0.035,
    });
  }
  return bands;
}

function roundedRectPath(x: number, y: number, width: number, height: number, radius: number) {
  const r = Math.min(radius, width / 2, height / 2);
  return [
    `M ${x + r} ${y}`,
    `H ${x + width - r}`,
    `Q ${x + width} ${y} ${x + width} ${y + r}`,
    `V ${y + height - r}`,
    `Q ${x + width} ${y + height} ${x + width - r} ${y + height}`,
    `H ${x + r}`,
    `Q ${x} ${y + height} ${x} ${y + height - r}`,
    `V ${y + r}`,
    `Q ${x} ${y} ${x + r} ${y}`,
    "Z",
  ].join(" ");
}

function contourLegendFill(semantics: ZSemantics) {
  const top = semantics.fills[1]?.replace("__ALPHA__", "0.180") ?? "rgba(14, 165, 233, 0.18)";
  const bottom = semantics.fills[2]?.replace("__ALPHA__", "0.080") ?? "rgba(59, 130, 246, 0.08)";
  return `linear-gradient(180deg, ${top}, ${bottom}), #ffffff`;
}

function inferZMode(cells: CellSnapshot[]) {
  const mode = cells[0]?.action_state?.z_mode;
  return typeof mode === "string" && mode.trim() ? mode.trim() : "hybrid";
}

function zSemanticsForMode(mode: string): ZSemantics {
  switch (mode) {
    case "wealth":
      return {
        mode,
        label: "wealth elevation",
        subtitle: "Contour bands track resource concentration and accumulated economic height.",
        rangeLabel: "wealth z",
        contourName: "wealth bands",
        fills: [
          "rgba(245, 158, 11, __ALPHA__)",
          "rgba(251, 191, 36, __ALPHA__)",
          "rgba(249, 115, 22, __ALPHA__)",
          "rgba(234, 88, 12, __ALPHA__)",
        ],
        strokes: [
          "rgba(180, 83, 9, 0.34)",
          "rgba(202, 138, 4, 0.34)",
          "rgba(234, 88, 12, 0.34)",
          "rgba(194, 65, 12, 0.34)",
        ],
      };
    case "influence":
      return {
        mode,
        label: "influence elevation",
        subtitle: "Contour bands highlight social leverage, coordination reach, and institutional pull.",
        rangeLabel: "influence z",
        contourName: "influence bands",
        fills: [
          "rgba(99, 102, 241, __ALPHA__)",
          "rgba(129, 140, 248, __ALPHA__)",
          "rgba(59, 130, 246, __ALPHA__)",
          "rgba(79, 70, 229, __ALPHA__)",
        ],
        strokes: [
          "rgba(67, 56, 202, 0.34)",
          "rgba(79, 70, 229, 0.34)",
          "rgba(37, 99, 235, 0.34)",
          "rgba(55, 48, 163, 0.34)",
        ],
      };
    case "policy":
      return {
        mode,
        label: "policy sensitivity elevation",
        subtitle: "Contour bands show which areas are structurally more reactive to policy signals.",
        rangeLabel: "policy z",
        contourName: "policy bands",
        fills: [
          "rgba(16, 185, 129, __ALPHA__)",
          "rgba(52, 211, 153, __ALPHA__)",
          "rgba(13, 148, 136, __ALPHA__)",
          "rgba(5, 150, 105, __ALPHA__)",
        ],
        strokes: [
          "rgba(5, 150, 105, 0.34)",
          "rgba(4, 120, 87, 0.34)",
          "rgba(13, 148, 136, 0.34)",
          "rgba(6, 95, 70, 0.34)",
        ],
      };
    case "memory":
      return {
        mode,
        label: "memory elevation",
        subtitle: "Contour bands reflect accumulated long-memory and repeated social imprint.",
        rangeLabel: "memory z",
        contourName: "memory bands",
        fills: [
          "rgba(236, 72, 153, __ALPHA__)",
          "rgba(244, 114, 182, __ALPHA__)",
          "rgba(217, 70, 239, __ALPHA__)",
          "rgba(219, 39, 119, __ALPHA__)",
        ],
        strokes: [
          "rgba(190, 24, 93, 0.34)",
          "rgba(219, 39, 119, 0.34)",
          "rgba(168, 85, 247, 0.34)",
          "rgba(157, 23, 77, 0.34)",
        ],
      };
    case "flat":
      return {
        mode,
        label: "flat elevation",
        subtitle: "Elevation is flattened, so contour overlays collapse toward the communication plane.",
        rangeLabel: "flat z",
        contourName: "flat bands",
        fills: [
          "rgba(148, 163, 184, __ALPHA__)",
          "rgba(203, 213, 225, __ALPHA__)",
          "rgba(148, 163, 184, __ALPHA__)",
          "rgba(226, 232, 240, __ALPHA__)",
        ],
        strokes: [
          "rgba(100, 116, 139, 0.34)",
          "rgba(148, 163, 184, 0.34)",
          "rgba(100, 116, 139, 0.34)",
          "rgba(148, 163, 184, 0.34)",
        ],
      };
    default:
      return {
        mode: "hybrid",
        label: "social elevation",
        subtitle: "Contour bands blend wealth, influence, memory, and policy sensitivity over the flat communication plane.",
        rangeLabel: "social z",
        contourName: "hybrid bands",
        fills: [
          "rgba(14, 165, 233, __ALPHA__)",
          "rgba(59, 130, 246, __ALPHA__)",
          "rgba(99, 102, 241, __ALPHA__)",
          "rgba(251, 191, 36, __ALPHA__)",
        ],
        strokes: [
          "rgba(2, 132, 199, 0.34)",
          "rgba(37, 99, 235, 0.34)",
          "rgba(79, 70, 229, 0.34)",
          "rgba(202, 138, 4, 0.34)",
        ],
      };
  }
}
