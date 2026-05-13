"use client";

import { useMemo, useState } from "react";

import { CenterMapToolbar } from "@/components/center-map/CenterMapToolbar";
import { CenterMapViewport } from "@/components/center-map/CenterMapViewport";
import type { CenterMapShellProps, CenterMapVisibleLayers } from "@/components/center-map/types";

function defaultVisibleLayers(mode: CenterMapShellProps["mode"]): CenterMapVisibleLayers {
  if (mode === "swarm") {
    return {
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
    agents: true,
    heat: true,
    shock: true,
    drift: true,
    anchors: true,
    labels: true,
    clusters: true,
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
    <div className="grid gap-4">
      <CenterMapToolbar
        mode={mode}
        currentT={currentT}
        visibleLayers={visibleLayers}
        onToggleLayer={(key) =>
          setVisibleLayers((prev) => ({
            ...prev,
            [key]: !prev[key],
          }))
        }
        onClearSelection={onClearSelection}
      />

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_280px]">
        <div className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm min-h-[480px]">
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
            visibleLayers={visibleLayers}
            onSelectAgent={onSelectAgent}
            onSelectZone={onSelectZone}
            onSelectBand={onSelectBand}
            onJumpToT={onJumpToT}
          />
        </div>

        <div className="grid gap-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Center Map Readout
            </p>
            <div className="mt-3 grid gap-2">
              <p className="text-sm text-slate-700">avg pressure {focusSummary.avgPressure}%</p>
              <p className="text-sm text-slate-700">role fracture {focusSummary.roleFracture}%</p>
              <p className="text-sm text-slate-700">zone drift {focusSummary.zoneDrift}%</p>
              <p className="text-sm text-slate-700">
                validation confidence {focusSummary.validationConfidence}
              </p>
            </div>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
              Layer Status
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(visibleLayers)
                .filter(([, enabled]) => enabled)
                .map(([key]) => (
                  <span
                    key={key}
                    className="rounded-full bg-sky-50 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-700"
                  >
                    {key}
                  </span>
                ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
