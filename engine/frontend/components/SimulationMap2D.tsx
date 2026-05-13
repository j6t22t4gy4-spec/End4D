"use client";

import { useMemo, useState } from "react";

import {
  emotionToColorAndScale,
  type CellSnapshot,
  type ReviewGroundingItem,
  type TimelineAnnotation,
} from "@/lib/api";
import { AgentLayer } from "@/components/center-map/layers/AgentLayer";
import { AnchorLayer } from "@/components/center-map/layers/AnchorLayer";
import { ClusterLayer } from "@/components/center-map/layers/ClusterLayer";
import { DriftLayer } from "@/components/center-map/layers/DriftLayer";
import { PressureFieldLayer } from "@/components/center-map/layers/PressureFieldLayer";
import { ShockLayer } from "@/components/center-map/layers/ShockLayer";
import { ZoneLayer } from "@/components/center-map/layers/ZoneLayer";
import { PixiStageHost } from "@/components/center-map/pixi/PixiStageHost";
import { buildCenterMapScene } from "@/components/center-map/scene/buildCenterMapScene";
import type { PointerField } from "@/components/center-map/scene/sceneTypes";
import type {
  SelectedBand,
  SelectedZone,
} from "@/components/SimulationInspectorPanel";

type SimulationMap2DProps = {
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  showPressureField?: boolean;
  showShockLayer?: boolean;
  showAnchorLayer?: boolean;
  showDriftLayer?: boolean;
  showClusterLayer?: boolean;
  annotations?: TimelineAnnotation[];
  groundingItems?: ReviewGroundingItem[];
  currentT?: number;
  renderTime?: number;
  transitionPhase?: number;
  pointerField?: PointerField;
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  onSelectAgent?: (cell: CellSnapshot) => void;
  onSelectZone?: (zone: SelectedZone) => void;
  onSelectBand?: (band: SelectedBand) => void;
  onJumpToT?: (t: number) => void;
};

export type ZoneBox = {
  zoneId: string;
  label: string;
  influence: number;
  friction: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  count: number;
  avgDrift: number;
  avgPressure: number;
  fractureSignals: number;
};

type ElevationBand = {
  key: string;
  d: string;
  label: string;
  alpha: number;
  lower: number;
  upper: number;
  agentCount: number;
  avgEnergy: number;
  avgZ: number;
  dominantRole: string;
};

export type ObserverSemantics = {
  focus: string;
  score: number;
  ring: string;
  halo: string;
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

export type AgentNode = {
  id: string;
  cell: CellSnapshot;
  cx: number;
  cy: number;
  r: number;
  fill: string;
  observer: ObserverSemantics;
  title: string;
  collectivePressure: number;
  pressureBucket: string;
  fractureSignal: boolean;
};

const SVG_WIDTH = 960;
const SVG_HEIGHT = 640;
const PADDING = 56;

export default function SimulationMap2D({
  cells,
  totalCells,
  sampled,
  showPressureField = true,
  showShockLayer = true,
  showAnchorLayer = true,
  showDriftLayer = false,
  showClusterLayer = true,
  annotations = [],
  groundingItems = [],
  currentT = 0,
  renderTime = 0,
  transitionPhase = 0,
  pointerField = { x: 0.5, y: 0.5, active: false },
  selectedAgentId = null,
  selectedZoneId = null,
  selectedBandKey = null,
  onSelectAgent,
  onSelectZone,
  onSelectBand,
  onJumpToT,
}: SimulationMap2DProps) {
  const scene = useMemo(() => buildScene(cells), [cells]);
  const pixiScene = useMemo(
    () => buildCenterMapScene({ cells, selectedAgentId }),
    [cells, selectedAgentId]
  );
  const usePixiLiveField = true;
  const [hoveredBandKey, setHoveredBandKey] = useState<string | null>(null);
  const pointerX = PADDING + pointerField.x * (SVG_WIDTH - PADDING * 2);
  const pointerY = PADDING + pointerField.y * (SVG_HEIGHT - PADDING * 2);
  const pointerDriftX = (pointerField.x - 0.5) * (pointerField.active ? 26 : 10);
  const pointerDriftY = (pointerField.y - 0.5) * (pointerField.active ? 24 : 8);
  const activeBand =
    scene.elevationBands.find((band) => band.key === hoveredBandKey) ??
    scene.elevationBands.find((band) => band.key === selectedBandKey) ??
    scene.elevationBands[scene.elevationBands.length - 1] ??
    null;

  return (
    <div className="simulation-map">
      <div className="simulation-map__header">
        <div>
          <p className="simulation-map__eyebrow">2D Social Field</p>
          <h3 className="simulation-map__title">Zone-aware agent communication surface</h3>
          <p className="simulation-map__subtitle">
            {scene.zSemantics.subtitle}
          </p>
          <p className="simulation-map__subtitle">
            Derived from live agent `z` values refreshed by energy, zone influence, policy sensitivity, memory, and relationship state.
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
          <>
            <PixiStageHost
              scene={pixiScene}
              annotations={annotations}
              currentT={currentT}
              renderTime={renderTime}
              transitionPhase={transitionPhase}
              pointerField={pointerField}
            />
            <svg
              className="simulation-map__svg"
              viewBox={`0 0 ${SVG_WIDTH} ${SVG_HEIGHT}`}
              role="img"
              aria-label="2D social field simulation map"
            >
              <defs>
                <radialGradient id="map-ambient-glow" cx="50%" cy="42%" r="68%">
                  <stop offset="0%" stopColor="rgba(56, 189, 248, 0.18)" />
                  <stop offset="38%" stopColor="rgba(99, 102, 241, 0.10)" />
                  <stop offset="100%" stopColor="rgba(15, 23, 42, 0)" />
                </radialGradient>
                <radialGradient id="map-core-field" cx="50%" cy="50%" r="72%">
                  <stop offset="0%" stopColor="rgba(30, 41, 59, 0.0)" />
                  <stop offset="100%" stopColor="rgba(15, 23, 42, 0.32)" />
                </radialGradient>
                <filter id="map-glow-soft" x="-50%" y="-50%" width="200%" height="200%">
                  <feGaussianBlur stdDeviation="8" result="blurred" />
                  <feMerge>
                    <feMergeNode in="blurred" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
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
              <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="#07111f" />
              <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#map-ambient-glow)" />
              <rect width={SVG_WIDTH} height={SVG_HEIGHT} fill="url(#map-core-field)" />
              <g opacity="0.56">
                <circle
                  cx={SVG_WIDTH * 0.22 + Math.sin(renderTime * 0.23) * 28 + pointerDriftX * 0.35}
                  cy={SVG_HEIGHT * 0.24 + Math.cos(renderTime * 0.19) * 18 + pointerDriftY * 0.35}
                  r={146 + Math.sin(renderTime * 0.41) * 12}
                  fill="rgba(56, 189, 248, 0.05)"
                  filter="url(#map-glow-soft)"
                />
                <circle
                  cx={SVG_WIDTH * 0.78 + Math.cos(renderTime * 0.21) * 22 - pointerDriftX * 0.28}
                  cy={SVG_HEIGHT * 0.68 + Math.sin(renderTime * 0.27) * 16 - pointerDriftY * 0.24}
                  r={128 + Math.cos(renderTime * 0.36) * 10}
                  fill="rgba(99, 102, 241, 0.05)"
                  filter="url(#map-glow-soft)"
                />
              </g>
              <g opacity={pointerField.active ? 0.48 : 0.32}>
                <ellipse
                  cx={pointerX}
                  cy={pointerY}
                  rx={110 + Math.sin(renderTime * 1.2) * 12}
                  ry={86 + Math.cos(renderTime * 1.05) * 10}
                  fill="rgba(125, 211, 252, 0.05)"
                  filter="url(#map-glow-soft)"
                />
                <ellipse
                  cx={pointerX}
                  cy={pointerY}
                  rx={48 + Math.sin(renderTime * 1.8) * 6}
                  ry={36 + Math.cos(renderTime * 1.52) * 5}
                  fill="rgba(255,255,255,0.035)"
                />
              </g>
              <rect
                x={PADDING}
                y={PADDING}
                width={SVG_WIDTH - PADDING * 2}
                height={SVG_HEIGHT - PADDING * 2}
                rx="28"
                fill="url(#map-grid)"
              />
              <g opacity="0.24" transform={`translate(${Math.sin(renderTime * 0.4) * 10} ${Math.cos(renderTime * 0.33) * 8})`}>
                <rect
                  x={PADDING - 120 + ((renderTime * 92) % (SVG_WIDTH + 240))}
                  y={PADDING - 30}
                  width="96"
                  height={SVG_HEIGHT - PADDING * 2 + 60}
                  rx="28"
                  fill="rgba(255,255,255,0.02)"
                  transform={`rotate(-12 ${SVG_WIDTH / 2} ${SVG_HEIGHT / 2})`}
                />
                <rect
                  x={PADDING - 180 + ((renderTime * 64) % (SVG_WIDTH + 320))}
                  y={PADDING - 20}
                  width="42"
                  height={SVG_HEIGHT - PADDING * 2 + 40}
                  rx="24"
                  fill="rgba(125,211,252,0.015)"
                  transform={`rotate(-12 ${SVG_WIDTH / 2} ${SVG_HEIGHT / 2})`}
                />
              </g>
              {transitionPhase > 0.001 ? (
                <rect
                  x={PADDING}
                  y={PADDING}
                  width={SVG_WIDTH - PADDING * 2}
                  height={SVG_HEIGHT - PADDING * 2}
                  rx="28"
                  fill="rgba(255,255,255,0.05)"
                  opacity={transitionPhase * 0.4}
                />
              ) : null}

            {scene.elevationBands.map((band, index) => (
              <path
                key={band.key}
                d={band.d}
                className="simulation-map__contour-band"
                style={{
                  fill: contourFill(scene.zSemantics, index, band.alpha),
                  stroke: contourStroke(scene.zSemantics, index),
                  opacity:
                    !activeBand || activeBand.key === band.key || selectedBandKey === band.key
                      ? 1
                      : 0.58,
                }}
                onMouseEnter={() => setHoveredBandKey(band.key)}
                onMouseLeave={() => setHoveredBandKey(null)}
                onClick={() =>
                  onSelectBand?.({
                    key: band.key,
                    label: band.label,
                    lower: band.lower,
                    upper: band.upper,
                    agentCount: band.agentCount,
                    avgEnergy: band.avgEnergy,
                    avgZ: band.avgZ,
                    dominantRole: band.dominantRole,
                    modeLabel: scene.zSemantics.label,
                  })
                }
              >
                <title>{band.label}</title>
              </path>
            ))}

            {!usePixiLiveField && showClusterLayer ? (
              <ClusterLayer
                zones={scene.zoneBoxes}
                renderTime={renderTime}
                pointerField={pointerField}
              />
            ) : null}
            {!usePixiLiveField && showPressureField ? (
              <PressureFieldLayer
                nodes={scene.nodes}
                renderTime={renderTime}
                pointerField={pointerField}
              />
            ) : null}
            {!usePixiLiveField && showShockLayer ? (
              <ShockLayer
                nodes={scene.nodes}
                annotations={annotations}
                currentT={currentT}
                renderTime={renderTime}
              />
            ) : null}
            {showDriftLayer ? (
              <DriftLayer
                zones={scene.zoneBoxes}
                mapCenter={{ x: SVG_WIDTH / 2, y: SVG_HEIGHT / 2 }}
                renderTime={renderTime}
              />
            ) : null}

            <ZoneLayer
              zones={scene.zoneBoxes}
              selectedZoneId={selectedZoneId}
              onSelectZone={onSelectZone}
            />

            {showAnchorLayer ? (
              <AnchorLayer
                nodes={scene.nodes}
                zones={scene.zoneBoxes}
                items={groundingItems}
                currentT={currentT}
                onJumpToT={onJumpToT}
              />
            ) : null}

            {!usePixiLiveField ? (
              <AgentLayer
                nodes={scene.nodes}
                renderTime={renderTime}
                selectedAgentId={selectedAgentId}
                onSelectAgent={onSelectAgent}
              />
            ) : null}
          </svg>
          </>
        )}
      </div>

      {activeBand && (
        <details className="simulation-map__detail-collapse group">
          <summary className="simulation-map__detail-summary">
            <div>
              <p className="simulation-map__detail-eyebrow">{scene.zSemantics.contourName}</p>
              <h4 className="simulation-map__detail-title">
                {scene.zSemantics.label} · {activeBand.label}
              </h4>
            </div>
            <span className="simulation-map__detail-toggle">
              open
            </span>
          </summary>
          <div className="simulation-map__detail-card">
            <div className="simulation-map__detail-grid">
              <span>{activeBand.agentCount} agents</span>
              <span>avg z {activeBand.avgZ.toFixed(2)}</span>
              <span>avg energy {activeBand.avgEnergy.toFixed(1)}</span>
              <span>dominant role {activeBand.dominantRole}</span>
            </div>
          </div>
        </details>
      )}

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
        <div className="simulation-map__legend-item simulation-map__legend-item--elevation">
          <span
            className="simulation-map__legend-contour"
            style={{
              background:
                "linear-gradient(180deg, rgba(124, 58, 237, 0.24), rgba(14, 165, 233, 0.16)), #ffffff",
              borderColor: "rgba(124, 58, 237, 0.48)",
            }}
          />
          <div>
            <strong>observer signal</strong>
            <span>focus halo + ring intensity mark live observer importance</span>
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
    const observer = observerSemantics(cell);
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
      avgDrift: 0,
      avgPressure: 0,
      fractureSignals: 0,
    };
    box.x0 = Math.min(box.x0, cx);
    box.x1 = Math.max(box.x1, cx);
    box.y0 = Math.min(box.y0, cy);
    box.y1 = Math.max(box.y1, cy);
    box.count += 1;
    box.avgDrift += Number(cell.action_state?.zone_group_drift_velocity ?? 0);
    box.avgPressure += Number(cell.action_state?.collective_pressure ?? 0);
    box.fractureSignals += Number(Boolean(cell.action_state?.fracture_signal_received));
    zoneAcc.set(zoneId, box);

    return {
      id: cell.cell_id,
      cell,
      cx,
      cy,
      r: 4 + scale * 5 + observer.score * 1.5,
      fill,
      observer,
      title: `${cell.role_label ?? cell.role_key ?? "agent"} · ${
        zoneLabel
      } · pressure ${Number(cell.action_state?.collective_pressure ?? 0).toFixed(2)} · energy ${cell.energy.toFixed(1)} · observer ${observer.focus} ${observer.score.toFixed(2)}`,
      collectivePressure: Math.max(0, Math.min(1, Number(cell.action_state?.collective_pressure ?? 0))),
      pressureBucket: String(cell.action_state?.collective_pressure_bucket ?? "low"),
      fractureSignal: Boolean(cell.action_state?.fracture_signal_received),
    };
  });

  const zoneBoxes = Array.from(zoneAcc.values())
    .map((zone) => ({
      ...zone,
      x0: Math.max(PADDING - 6, zone.x0 - 18),
      x1: Math.min(SVG_WIDTH - PADDING + 6, zone.x1 + 18),
      y0: Math.max(PADDING - 6, zone.y0 - 18),
      y1: Math.min(SVG_HEIGHT - PADDING + 6, zone.y1 + 18),
      avgDrift: zone.count ? zone.avgDrift / zone.count : 0,
      avgPressure: zone.count ? zone.avgPressure / zone.count : 0,
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

function observerSemantics(cell: CellSnapshot): ObserverSemantics {
  const focus = String(cell.action_state?.observer_focus ?? "field");
  const score = Math.max(0, Math.min(1, Number(cell.action_state?.observer_score ?? 0)));
  if (focus === "thought") {
    return {
      focus,
      score,
      ring: "rgba(124, 58, 237, 0.88)",
      halo: "rgba(167, 139, 250, 0.95)",
    };
  }
  if (focus === "mover") {
    return {
      focus,
      score,
      ring: "rgba(14, 165, 233, 0.88)",
      halo: "rgba(125, 211, 252, 0.9)",
    };
  }
  if (focus === "zone") {
    return {
      focus,
      score,
      ring: "rgba(245, 158, 11, 0.88)",
      halo: "rgba(253, 230, 138, 0.9)",
    };
  }
  return {
    focus,
    score,
    ring: "rgba(148, 163, 184, 0.8)",
    halo: "rgba(203, 213, 225, 0.8)",
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
  const buckets = Array.from({ length: bandCount }, (_, index) => ({
    index,
    lower: minZ + (spanZ * index) / bandCount,
    upper: minZ + (spanZ * (index + 1)) / bandCount,
    points: [] as Array<{ x: number; y: number }>,
    energySum: 0,
    zSum: 0,
    roleCounts: new Map<string, number>(),
  }));

  for (const cell of cells) {
    const z = cell.z ?? 0;
    const rawIndex = Math.floor(((z - minZ) / spanZ) * bandCount);
    const index = Math.max(0, Math.min(bandCount - 1, rawIndex));
    const bucket = buckets[index]!;
    bucket.points.push({ x: projectX(cell.x), y: projectY(cell.y) });
    bucket.energySum += cell.energy;
    bucket.zSum += z;
    const role = cell.role_label ?? cell.role_key ?? "agent";
    bucket.roleCounts.set(role, (bucket.roleCounts.get(role) ?? 0) + 1);
  }

  return buckets.flatMap((bucket) => {
    if (bucket.points.length < 3) {
      return [];
    }
    const hull = convexHull(bucket.points);
    if (hull.length < 3) {
      return [];
    }
    const expanded = expandPolygon(hull, 16);
    const d = smoothClosedPath(expanded);
    const dominantRole =
      [...bucket.roleCounts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))[0]?.[0] ?? "agent";
    return [
      {
        key: `band-${bucket.index}`,
        d,
        label: `elevation ${bucket.lower.toFixed(1)}-${bucket.upper.toFixed(1)}`,
        alpha: 0.08 + bucket.index * 0.035,
        lower: bucket.lower,
        upper: bucket.upper,
        agentCount: bucket.points.length,
        avgEnergy: bucket.energySum / bucket.points.length,
        avgZ: bucket.zSum / bucket.points.length,
        dominantRole,
      },
    ];
  });
}

function contourLegendFill(semantics: ZSemantics) {
  const top = semantics.fills[1]?.replace("__ALPHA__", "0.180") ?? "rgba(14, 165, 233, 0.18)";
  const bottom = semantics.fills[2]?.replace("__ALPHA__", "0.080") ?? "rgba(59, 130, 246, 0.08)";
  return `linear-gradient(180deg, ${top}, ${bottom}), #ffffff`;
}

function convexHull(points: Array<{ x: number; y: number }>) {
  const unique = Array.from(
    new Map(points.map((point) => [`${point.x.toFixed(2)}:${point.y.toFixed(2)}`, point])).values()
  ).sort((a, b) => a.x - b.x || a.y - b.y);
  if (unique.length <= 3) return unique;

  const lower: Array<{ x: number; y: number }> = [];
  for (const point of unique) {
    while (lower.length >= 2 && cross(lower[lower.length - 2]!, lower[lower.length - 1]!, point) <= 0) {
      lower.pop();
    }
    lower.push(point);
  }
  const upper: Array<{ x: number; y: number }> = [];
  for (let index = unique.length - 1; index >= 0; index -= 1) {
    const point = unique[index]!;
    while (upper.length >= 2 && cross(upper[upper.length - 2]!, upper[upper.length - 1]!, point) <= 0) {
      upper.pop();
    }
    upper.push(point);
  }
  lower.pop();
  upper.pop();
  return [...lower, ...upper];
}

function expandPolygon(points: Array<{ x: number; y: number }>, padding: number) {
  const centroid = points.reduce(
    (acc, point) => ({ x: acc.x + point.x, y: acc.y + point.y }),
    { x: 0, y: 0 }
  );
  centroid.x /= points.length;
  centroid.y /= points.length;
  return points.map((point) => {
    const dx = point.x - centroid.x;
    const dy = point.y - centroid.y;
    const length = Math.hypot(dx, dy) || 1;
    return {
      x: clamp(point.x + (dx / length) * padding, PADDING - 8, SVG_WIDTH - PADDING + 8),
      y: clamp(point.y + (dy / length) * padding, PADDING - 8, SVG_HEIGHT - PADDING + 8),
    };
  });
}

function smoothClosedPath(points: Array<{ x: number; y: number }>) {
  if (points.length < 3) return "";
  const path = [];
  const firstMid = midpoint(points[0]!, points[1]!);
  path.push(`M ${firstMid.x.toFixed(1)} ${firstMid.y.toFixed(1)}`);
  for (let index = 1; index <= points.length; index += 1) {
    const current = points[index % points.length]!;
    const next = points[(index + 1) % points.length]!;
    const mid = midpoint(current, next);
    path.push(
      `Q ${current.x.toFixed(1)} ${current.y.toFixed(1)} ${mid.x.toFixed(1)} ${mid.y.toFixed(1)}`
    );
  }
  path.push("Z");
  return path.join(" ");
}

function midpoint(a: { x: number; y: number }, b: { x: number; y: number }) {
  return { x: (a.x + b.x) / 2, y: (a.y + b.y) / 2 };
}

function cross(a: { x: number; y: number }, b: { x: number; y: number }, c: { x: number; y: number }) {
  return (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x);
}

function clamp(value: number, min: number, max: number) {
  return Math.max(min, Math.min(max, value));
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
