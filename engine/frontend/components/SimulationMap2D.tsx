"use client";

import { useEffect, useMemo, useRef, useState, type WheelEvent } from "react";

import {
  emotionToColorAndScale,
  type CellSnapshot,
  type ReviewGroundingItem,
  type TimelineAnnotation,
} from "@/lib/api";
import { PixiStageHost } from "@/components/center-map/pixi/PixiStageHost";
import type { PixiInteractionApi } from "@/components/center-map/pixi/PixiStageHost";
import type { PixiCameraState } from "@/components/center-map/pixi/PixiSceneController";
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
  showZoneLayer?: boolean;
  showShockLayer?: boolean;
  showAnchorLayer?: boolean;
  showDriftLayer?: boolean;
  showClusterLayer?: boolean;
  showAgentLayer?: boolean;
  annotations?: TimelineAnnotation[];
  groundingItems?: ReviewGroundingItem[];
  currentT?: number;
  renderTime?: number;
  transitionPhase?: number;
  pointerField?: PointerField;
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  cameraResetSignal?: number;
  onSelectAgent?: (cell: CellSnapshot) => void;
  onSelectZone?: (zone: SelectedZone) => void;
  onSelectBand?: (band: SelectedBand) => void;
  onClearSelection?: () => void;
  onJumpToT?: (t: number) => void;
};

type CenterMapWheelEvent = globalThis.WheelEvent & {
  __centerMapHandled?: boolean;
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
  showZoneLayer = true,
  showShockLayer = true,
  showAnchorLayer = true,
  showDriftLayer = false,
  showClusterLayer = true,
  showAgentLayer = true,
  annotations = [],
  groundingItems = [],
  currentT = 0,
  renderTime = 0,
  transitionPhase = 0,
  pointerField = { x: 0.5, y: 0.5, active: false },
  selectedAgentId = null,
  selectedZoneId = null,
  selectedBandKey = null,
  cameraResetSignal = 0,
  onSelectAgent,
  onSelectZone,
  onSelectBand,
  onClearSelection,
  onJumpToT,
}: SimulationMap2DProps) {
  const scene = useMemo(() => buildScene(cells), [cells]);
  const pixiScene = useMemo(
    () => buildCenterMapScene({ cells, selectedAgentId }),
    [cells, selectedAgentId]
  );
  const [hoveredAgentId, setHoveredAgentId] = useState<string | null>(null);
  const [hoverPosition, setHoverPosition] = useState<{
    x: number;
    y: number;
    width: number;
  } | null>(null);
  const [cameraState, setCameraState] = useState<PixiCameraState>({
    offsetX: 0,
    offsetY: 0,
    scaleX: 1,
    scaleY: 1,
    zoom: 1,
  });
  const stageRef = useRef<HTMLDivElement | null>(null);
  const pixiInteractionRef = useRef<PixiInteractionApi | null>(null);
  const lastCameraResetSignalRef = useRef(cameraResetSignal);
  const dragRef = useRef<{ active: boolean; moved: boolean; x: number; y: number }>({
    active: false,
    moved: false,
    x: 0,
    y: 0,
  });
  const cellById = useMemo(
    () => new Map(cells.map((cell) => [cell.cell_id, cell])),
    [cells]
  );
  const resolvedAnchors = useMemo(
    () => resolveOverlayAnchors(scene.nodes, scene.zoneBoxes, groundingItems, currentT),
    [scene.nodes, scene.zoneBoxes, groundingItems, currentT]
  );
  const selectedBand = selectedBandKey
    ? scene.elevationBands.find((band) => band.key === selectedBandKey) ?? null
    : null;
  const metaItems = [
    `${cells.length.toLocaleString()} visible`,
    `${totalCells.toLocaleString()} total`,
    `${scene.zoneBoxes.length} zones`,
    sampled ? "sampled" : "full",
  ];

  useEffect(() => {
    if (cameraResetSignal === lastCameraResetSignalRef.current) return;
    lastCameraResetSignalRef.current = cameraResetSignal;
    pixiInteractionRef.current?.resetCamera();
  }, [cameraResetSignal]);

  useEffect(() => {
    const stage = stageRef.current;
    if (!stage) return;

    const handleWheel = (event: globalThis.WheelEvent) => {
      event.preventDefault();
      event.stopPropagation();
      if ((event as CenterMapWheelEvent).__centerMapHandled) return;
      const rect = stage.getBoundingClientRect();
      if (rect.width <= 0 || rect.height <= 0) return;
      const factor = event.deltaY < 0 ? 1.08 : 0.92;
      pixiInteractionRef.current?.zoomAtScreen(
        factor,
        event.clientX - rect.left,
        event.clientY - rect.top
      );
    };

    stage.addEventListener("wheel", handleWheel, { passive: false });
    return () => stage.removeEventListener("wheel", handleWheel);
  }, [cells.length]);

  const handleStageWheel = (event: WheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    event.stopPropagation();
    (event.nativeEvent as CenterMapWheelEvent).__centerMapHandled = true;
    const rect = event.currentTarget.getBoundingClientRect();
    if (rect.width <= 0 || rect.height <= 0) return;
    const factor = event.deltaY < 0 ? 1.08 : 0.92;
    pixiInteractionRef.current?.zoomAtScreen(
      factor,
      event.clientX - rect.left,
      event.clientY - rect.top
    );
  };

  return (
    <div className="simulation-map">
      <div className="simulation-map__viewport">
        {cells.length === 0 ? (
          <div
            className="simulation-map__empty"
            data-testid="simulation-map-empty"
          >
            Run the simulation to populate the social field.
          </div>
        ) : (
          <div
            ref={stageRef}
            className="simulation-map__stage"
            onWheelCapture={handleStageWheel}
            onPointerDown={(event) => {
              const target = event.target as Element | null;
              if (target?.closest(".simulation-map__zone-chip, .simulation-map__anchor-pin")) {
                return;
              }
              dragRef.current = { active: true, moved: false, x: event.clientX, y: event.clientY };
            }}
            onPointerUp={() => {
              dragRef.current.active = false;
            }}
            onPointerCancel={() => {
              dragRef.current.active = false;
            }}
            onMouseMove={(event) => {
              if (dragRef.current.active) {
                const dx = event.clientX - dragRef.current.x;
                const dy = event.clientY - dragRef.current.y;
                dragRef.current = {
                  active: true,
                  moved: dragRef.current.moved || Math.abs(dx) > 1 || Math.abs(dy) > 1,
                  x: event.clientX,
                  y: event.clientY,
                };
                pixiInteractionRef.current?.panByScreen(dx, dy);
                return;
              }
              const target = event.target as Element | null;
              if (target?.closest(".simulation-map__zone-chip, .simulation-map__anchor-pin")) {
                pixiInteractionRef.current?.setHoveredAgent(null);
                setHoveredAgentId(null);
                setHoverPosition(null);
                return;
              }
              const rect = event.currentTarget.getBoundingClientRect();
              if (rect.width <= 0 || rect.height <= 0) return;
              const nextId =
                pixiInteractionRef.current?.hitTestAtScreen(
                  event.clientX - rect.left,
                  event.clientY - rect.top
                ) ?? null;
              pixiInteractionRef.current?.setHoveredAgent(nextId);
              setHoveredAgentId(nextId);
              setHoverPosition(
                nextId
                  ? {
                      x: event.clientX - rect.left,
                      y: event.clientY - rect.top,
                      width: rect.width,
                    }
                  : null
              );
            }}
            onMouseLeave={() => {
              dragRef.current.active = false;
              pixiInteractionRef.current?.setHoveredAgent(null);
              setHoveredAgentId(null);
              setHoverPosition(null);
            }}
            onClick={(event) => {
              const target = event.target as Element | null;
              if (dragRef.current.moved || target?.closest(".simulation-map__zone-chip, .simulation-map__anchor-pin")) {
                dragRef.current.moved = false;
                return;
              }
              const rect = event.currentTarget.getBoundingClientRect();
              if (rect.width <= 0 || rect.height <= 0) return;
              const selectedId =
                pixiInteractionRef.current?.hitTestAtScreen(
                  event.clientX - rect.left,
                  event.clientY - rect.top
                ) ?? null;
              if (!selectedId) {
                onClearSelection?.();
                return;
              }
              if (selectedId === selectedAgentId) {
                onClearSelection?.();
                return;
              }
              const selectedCell = cellById.get(selectedId);
              if (selectedCell) onSelectAgent?.(selectedCell);
            }}
          >
            <div className="simulation-map__hud">
              <div>
                <p className="simulation-map__eyebrow">Social Field</p>
                <h3 className="simulation-map__title">{scene.zSemantics.label}</h3>
              </div>
              <div className="simulation-map__meta">
                {metaItems.map((item) => (
                  <span key={item}>{item}</span>
                ))}
              </div>
            </div>
            <PixiStageHost
              scene={pixiScene}
              annotations={annotations}
              currentT={currentT}
              renderTime={renderTime}
              transitionPhase={transitionPhase}
              pointerField={pointerField}
              layerVisibility={{
                zones: showZoneLayer,
                agents: showAgentLayer,
                clusters: showClusterLayer,
                pressure: showPressureField,
                shocks: showShockLayer,
              }}
              onInteractionApiReady={(api) => {
                pixiInteractionRef.current = api;
              }}
              onCameraStateChange={setCameraState}
            />
            <div className="simulation-map__dom-overlay">
              <div className="simulation-map__overlay-world" style={overlayWorldStyle(cameraState)}>
                {scene.zoneBoxes.map((zone, index) => (
                  <button
                    key={zone.zoneId}
                    type="button"
                    className={`simulation-map__zone-chip${
                      selectedZoneId === zone.zoneId ? " simulation-map__zone-chip--active" : ""
                    }`}
                    style={zoneOverlayStyle(zone, index)}
                    onClick={() =>
                      onSelectZone?.({
                        zoneId: zone.zoneId,
                        label: zone.label,
                        influence: zone.influence,
                        friction: zone.friction,
                        count: zone.count,
                      })
                    }
                  >
                    <span>{zone.label}</span>
                  </button>
                ))}

                {showAnchorLayer
                  ? resolvedAnchors.map((anchor) => (
                      <button
                        key={anchor.key}
                        type="button"
                        className="simulation-map__anchor-pin"
                        style={anchorOverlayStyle(anchor)}
                        onClick={() => {
                          if (onJumpToT && anchor.t != null) onJumpToT(anchor.t);
                        }}
                        title={anchor.reason}
                      >
                        <span
                          className="simulation-map__anchor-dot"
                          style={{ background: anchor.color }}
                        />
                        <span className="simulation-map__anchor-text">{anchor.label}</span>
                      </button>
                    ))
                  : null}
              </div>
            </div>
          {hoveredAgentId && hoverPosition ? (
            <div
              className="simulation-map__hover-chip"
              style={hoverChipStyle(hoverPosition)}
            >
              {cellById.get(hoveredAgentId)?.role_label ??
                cellById.get(hoveredAgentId)?.role_key ??
                "agent"}
            </div>
          ) : null}
          </div>
        )}
      </div>

      {selectedBand && (
        <details className="simulation-map__detail-collapse group">
          <summary className="simulation-map__detail-summary">
            <div>
              <p className="simulation-map__detail-eyebrow">{scene.zSemantics.contourName}</p>
              <h4 className="simulation-map__detail-title">
                {scene.zSemantics.label} · {selectedBand.label}
              </h4>
            </div>
            <span className="simulation-map__detail-toggle">
              open
            </span>
          </summary>
          <div className="simulation-map__detail-card">
            <div className="simulation-map__detail-grid">
              <span>{selectedBand.agentCount} agents</span>
              <span>avg z {selectedBand.avgZ.toFixed(2)}</span>
              <span>avg energy {selectedBand.avgEnergy.toFixed(1)}</span>
              <span>dominant role {selectedBand.dominantRole}</span>
            </div>
          </div>
        </details>
      )}

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

type OverlayAnchor = {
  key: string;
  x: number;
  y: number;
  label: string;
  reason: string;
  t: number | null;
  color: string;
};

function resolveOverlayAnchors(
  nodes: AgentNode[],
  zones: ZoneBox[],
  items: ReviewGroundingItem[],
  currentT: number
) {
  const filtered = items
    .filter((item) => item.t == null || Math.abs(Number(item.t) - currentT) <= 12)
    .slice(0, 8);

  const fallbackNodes = [...nodes]
    .sort((a, b) => b.collectivePressure - a.collectivePressure)
    .slice(0, Math.max(1, filtered.length));

  return filtered
    .map((item, index) => {
      const color = overlayAnchorColor(item.kind);
      if (item.cell_id) {
        const node = nodes.find((candidate) => candidate.id === item.cell_id);
        if (node) {
          return {
            key: item.anchor_id || `cell-${item.cell_id}-${index}`,
            x: node.cx,
            y: node.cy,
            label: item.label,
            reason: item.reason,
            t: item.t ?? null,
            color,
          };
        }
      }
      if (item.zone_id) {
        const zone = zones.find((candidate) => candidate.zoneId === item.zone_id);
        if (zone) {
          return {
            key: item.anchor_id || `zone-${item.zone_id}-${index}`,
            x: (zone.x0 + zone.x1) / 2,
            y: (zone.y0 + zone.y1) / 2,
            label: item.label,
            reason: item.reason,
            t: item.t ?? null,
            color,
          };
        }
      }
      const fallback = fallbackNodes[index % Math.max(1, fallbackNodes.length)];
      if (!fallback) return null;
      return {
        key: item.anchor_id || `fallback-${index}`,
        x: fallback.cx,
        y: fallback.cy,
        label: item.label,
        reason: item.reason,
        t: item.t ?? null,
        color,
      };
    })
    .filter((item): item is OverlayAnchor => item !== null);
}

function zoneOverlayStyle(zone: ZoneBox, index: number) {
  const palette = [
    ["rgba(255, 255, 255, 0.72)", "rgba(2, 132, 199, 0.28)"],
    ["rgba(255, 255, 255, 0.72)", "rgba(37, 99, 235, 0.28)"],
    ["rgba(255, 255, 255, 0.72)", "rgba(234, 88, 12, 0.28)"],
    ["rgba(255, 255, 255, 0.72)", "rgba(5, 150, 105, 0.28)"],
    ["rgba(255, 255, 255, 0.72)", "rgba(219, 39, 119, 0.28)"],
  ] as const;
  const [bg, border] = palette[index % palette.length]!;
  const labelX = Math.min(zone.x1 - 24, Math.max(PADDING, zone.x0 + 8));
  const labelY = Math.min(zone.y1 - 18, Math.max(PADDING, zone.y0 + 8));
  return {
    left: `${labelX}px`,
    top: `${labelY}px`,
    background: bg,
    borderColor: border,
  };
}

function hoverChipStyle(position: { x: number; y: number; width: number }) {
  return {
    left: `${Math.min(position.x + 14, Math.max(24, position.width - 140))}px`,
    top: `${Math.max(16, position.y - 18)}px`,
  };
}

function anchorOverlayStyle(anchor: OverlayAnchor) {
  return {
    left: `${anchor.x}px`,
    top: `${anchor.y}px`,
    color: anchor.color,
  };
}

function overlayWorldStyle(camera: PixiCameraState) {
  return {
    width: `${SVG_WIDTH}px`,
    height: `${SVG_HEIGHT}px`,
    transform: `translate(${camera.offsetX}px, ${camera.offsetY}px) scale(${camera.scaleX}, ${camera.scaleY})`,
    transformOrigin: "top left",
  } as const;
}

function overlayAnchorColor(kind: string) {
  if (kind === "event") return "rgb(249, 115, 22)";
  if (kind === "group") return "rgb(99, 102, 241)";
  if (kind === "zone") return "rgb(16, 185, 129)";
  if (kind === "agent") return "rgb(244, 63, 94)";
  return "rgb(14, 165, 233)";
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
