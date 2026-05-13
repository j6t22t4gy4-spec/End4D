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
  onClearSelection?: () => void;
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
  onClearSelection,
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

  void mode;

  return (
    <div className="h-full min-h-[640px]">
      <div
        className="h-full min-h-[640px]"
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
          showAgentLayer={visibleLayers.agents}
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
          onClearSelection={onClearSelection}
          onJumpToT={onJumpToT}
        />
      </div>
    </div>
  );
}
