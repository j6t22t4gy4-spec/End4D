"use client";

import { useEffect, useState } from "react";

import SimulationMap2D from "@/components/SimulationMap2D";
import type { CellSnapshot, ReviewGroundingItem, TimelineAnnotation } from "@/lib/api";
import type { SelectedBand, SelectedZone } from "@/components/SimulationInspectorPanel";
import type { CenterMapMode, CenterMapVisibleLayers } from "@/components/center-map/types";

type CenterMapViewportProps = {
  mode: CenterMapMode;
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  currentT: number;
  annotations?: TimelineAnnotation[];
  groundingItems?: ReviewGroundingItem[];
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  visibleLayers: CenterMapVisibleLayers;
  onSelectAgent?: (cell: CellSnapshot) => void;
  onSelectZone?: (zone: SelectedZone) => void;
  onSelectBand?: (band: SelectedBand) => void;
  onJumpToT?: (t: number) => void;
};

export function CenterMapViewport({
  mode,
  cells,
  totalCells,
  sampled,
  currentT,
  annotations = [],
  groundingItems = [],
  selectedAgentId = null,
  selectedZoneId = null,
  selectedBandKey = null,
  visibleLayers,
  onSelectAgent,
  onSelectZone,
  onSelectBand,
  onJumpToT,
}: CenterMapViewportProps) {
  const [renderTime, setRenderTime] = useState(0);
  const [transitionPhase, setTransitionPhase] = useState(0);
  const [pointerField, setPointerField] = useState({
    x: 0.5,
    y: 0.5,
    active: false,
  });

  useEffect(() => {
    let frame = 0;
    let start = 0;
    const tick = (ts: number) => {
      if (!start) start = ts;
      setRenderTime((ts - start) / 1000);
      frame = window.requestAnimationFrame(tick);
    };
    frame = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    let frame = 0;
    let start = 0;
    const animate = (ts: number) => {
      if (!start) start = ts;
      const elapsed = (ts - start) / 1000;
      const next = Math.max(0, 1 - elapsed / 0.55);
      setTransitionPhase(next);
      if (next > 0) frame = window.requestAnimationFrame(animate);
    };
    setTransitionPhase(1);
    frame = window.requestAnimationFrame(animate);
    return () => window.cancelAnimationFrame(frame);
  }, [currentT]);

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 px-1">
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          {mode === "precision" ? "Focus: agents + anchors" : "Focus: blocs + flow"}
        </span>
        {visibleLayers.heat ? (
          <span className="rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-700">
            Pressure field on
          </span>
        ) : null}
        {visibleLayers.shock ? (
          <span className="rounded-full bg-rose-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-rose-700">
            Shock layer staged
          </span>
        ) : null}
        {visibleLayers.drift ? (
          <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-700">
            Drift layer staged
          </span>
        ) : null}
      </div>
      <div
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          if (rect.width <= 0 || rect.height <= 0) return;
          setPointerField({
            x: Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)),
            y: Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height)),
            active: true,
          });
        }}
        onMouseLeave={() =>
          setPointerField({
            x: 0.5,
            y: 0.5,
            active: false,
          })
        }
      >
        <SimulationMap2D
          cells={cells}
          totalCells={totalCells}
          sampled={sampled}
          showPressureField={visibleLayers.heat}
          showShockLayer={visibleLayers.shock}
          showAnchorLayer={visibleLayers.anchors}
          showDriftLayer={visibleLayers.drift}
          showClusterLayer={visibleLayers.clusters}
          annotations={annotations}
          groundingItems={groundingItems}
          currentT={currentT}
          renderTime={renderTime}
          transitionPhase={transitionPhase}
          pointerField={pointerField}
          selectedAgentId={selectedAgentId}
          selectedZoneId={selectedZoneId}
          selectedBandKey={selectedBandKey}
          onSelectAgent={onSelectAgent}
          onSelectZone={onSelectZone}
          onSelectBand={onSelectBand}
          onJumpToT={onJumpToT}
        />
      </div>
    </div>
  );
}
