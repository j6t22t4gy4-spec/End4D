"use client";

import { useEffect, useMemo, useState } from "react";

import { CenterMapToolbar } from "@/components/center-map/CenterMapToolbar";
import { CenterMapViewport } from "@/components/center-map/CenterMapViewport";
import type { CenterMapShellProps, CenterMapVisibleLayers } from "@/components/center-map/types";

const LAYER_STATUS_LABELS: Record<keyof CenterMapVisibleLayers, string> = {
  zones: "zones",
  agents: "agents",
  heat: "pressure",
  shock: "shock",
  drift: "drift",
  anchors: "anchors",
  labels: "labels",
  clusters: "clusters",
};

function defaultVisibleLayers(mode: CenterMapShellProps["mode"]): CenterMapVisibleLayers {
  if (mode === "swarm") {
    return {
      zones: true,
      agents: false,
      heat: true,
      shock: true,
      drift: true,
      anchors: false,
      labels: false,
      clusters: true,
    };
  }
  return {
    zones: true,
    agents: true,
    heat: true,
    shock: false,
    drift: false,
    anchors: false,
    labels: false,
    clusters: false,
  };
}

export function CenterMapShell({
  mode,
  cells,
  totalCells,
  sampled,
  currentT,
  annotations = [],
  groundingItems = [],
  collectiveSummary,
  reviewSummary,
  locale = "ko",
  selectedAgentId = null,
  selectedZoneId = null,
  selectedBandKey = null,
  onSelectAgent,
  onSelectZone,
  onSelectBand,
  onClearSelection,
  onJumpToT,
}: CenterMapShellProps) {
  const [visibleLayers, setVisibleLayers] = useState<CenterMapVisibleLayers>(() => defaultVisibleLayers(mode));
  const [cameraResetSignal, setCameraResetSignal] = useState(0);

  useEffect(() => {
    setVisibleLayers(defaultVisibleLayers(mode));
  }, [mode]);

  const focusSummary = useMemo(() => {
    const roleFracture = Math.round((collectiveSummary?.role?.avg_fracture_risk ?? 0) * 100);
    const zoneDrift = Math.round((collectiveSummary?.zone?.avg_drift_velocity ?? 0) * 100);
    const avgPressure =
      cells.length > 0
        ? Math.round(
            (cells.reduce((sum, cell) => sum + Number(cell.action_state?.collective_pressure ?? 0), 0) /
              cells.length) *
              100
          )
        : 0;
    const validationConfidence = String(
      (reviewSummary?.validation_readout as Record<string, unknown> | undefined)?.current_confidence ?? "n/a"
    );
    return { roleFracture, zoneDrift, avgPressure, validationConfidence };
  }, [cells, collectiveSummary, reviewSummary]);

  return (
    <div className="center-map-shell flex min-h-0 flex-1 flex-col gap-3">
      <CenterMapToolbar
        mode={mode}
        currentT={currentT}
        locale={locale}
        visibleLayers={visibleLayers}
        onToggleLayer={(key) =>
          setVisibleLayers((prev) => ({
            ...prev,
            [key]: !prev[key],
          }))
        }
        onClearSelection={onClearSelection}
        onResetCamera={() => setCameraResetSignal((signal) => signal + 1)}
      />

      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <div className="min-h-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
          <CenterMapViewport
            mode={mode}
            cells={cells}
            totalCells={totalCells}
            sampled={sampled}
            currentT={currentT}
            annotations={annotations}
            groundingItems={groundingItems}
            selectedAgentId={selectedAgentId}
            selectedZoneId={selectedZoneId}
            selectedBandKey={selectedBandKey}
            cameraResetSignal={cameraResetSignal}
            visibleLayers={visibleLayers}
            onSelectAgent={onSelectAgent}
            onSelectZone={onSelectZone}
            onSelectBand={onSelectBand}
            onClearSelection={onClearSelection}
            onJumpToT={onJumpToT}
          />
        </div>

        <div className="shrink-0 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white/70 px-3 py-2 text-xs text-slate-600">
          <div className="flex flex-wrap items-center gap-3">
            <span>pressure {focusSummary.avgPressure}%</span>
            <span>fracture {focusSummary.roleFracture}%</span>
            <span>drift {focusSummary.zoneDrift}%</span>
            <span>confidence {focusSummary.validationConfidence}</span>
          </div>
          <div className="flex flex-wrap gap-1.5">
              {Object.entries(visibleLayers)
                .filter(([, enabled]) => enabled)
                .map(([key]) => (
                  <span
                    key={key}
                    className="rounded-md bg-sky-50 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-sky-700"
                  >
                    {LAYER_STATUS_LABELS[key as keyof CenterMapVisibleLayers]}
                  </span>
                ))}
          </div>
        </div>
      </div>
    </div>
  );
}
