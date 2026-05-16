"use client";

import { useEffect, useState } from "react";

import SocialFieldStage from "@/components/SocialFieldStage";
import type { CellSnapshot, IntraTSceneEvent, ReviewGroundingItem, TimelineAnnotation } from "@/lib/api";
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
  sceneEvents?: IntraTSceneEvent[];
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  cameraResetSignal?: number;
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
  sceneEvents = [],
  selectedAgentId = null,
  selectedZoneId = null,
  selectedBandKey = null,
  cameraResetSignal = 0,
  visibleLayers,
  onSelectAgent,
  onSelectZone,
  onSelectBand,
  onClearSelection,
  onJumpToT,
}: CenterMapViewportProps) {
  const [transitionPhase, setTransitionPhase] = useState(0);
  const latestStreamKey = latestSceneStreamKey(sceneEvents);
  const [pointerField, setPointerField] = useState({
    x: 0.5,
    y: 0.5,
    active: false,
  });

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
  }, [currentT, latestStreamKey]);

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
        <SocialFieldStage
          cells={cells}
          totalCells={totalCells}
          sampled={sampled}
          showZoneLayer={visibleLayers.zones}
          showPressureField={visibleLayers.pressure}
          showHeatmapLayer={visibleLayers.heat}
          showInteractionLayer={visibleLayers.interactions}
          showShockLayer={visibleLayers.shock}
          showAnchorLayer={visibleLayers.anchors}
          showDriftLayer={visibleLayers.drift}
          showClusterLayer={visibleLayers.clusters}
          showAgentLayer={visibleLayers.agents}
          annotations={annotations}
          groundingItems={groundingItems}
          sceneEvents={sceneEvents}
          currentT={currentT}
          transitionPhase={transitionPhase}
          pointerField={pointerField}
          selectedAgentId={selectedAgentId}
          selectedZoneId={selectedZoneId}
          selectedBandKey={selectedBandKey}
          cameraResetSignal={cameraResetSignal}
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

function latestSceneStreamKey(sceneEvents: IntraTSceneEvent[]) {
  const latest = sceneEvents[sceneEvents.length - 1];
  if (!latest) return "none";
  return [
    latest.stream_episode_id ?? latest.stream_session_id ?? latest.t ?? "t",
    latest.stream_round_index ?? latest.session_index ?? latest.scene_index ?? "round",
    latest.session_event_index ?? latest.stream_event_index ?? latest.scene_id ?? "event",
  ].join(":");
}
