"use client";

import type { CenterMapMode, CenterMapVisibleLayers } from "@/components/center-map/types";

type CenterMapToolbarProps = {
  mode: CenterMapMode;
  currentT: number;
  visibleLayers: CenterMapVisibleLayers;
  onToggleLayer: (key: keyof CenterMapVisibleLayers) => void;
  onClearSelection?: () => void;
};

const LAYER_LABELS: Record<keyof CenterMapVisibleLayers, string> = {
  agents: "Agents",
  heat: "Heat",
  shock: "Shock",
  drift: "Drift",
  anchors: "Anchors",
  labels: "Labels",
  clusters: "Clusters",
};

export function CenterMapToolbar({
  mode,
  currentT,
  visibleLayers,
  onToggleLayer,
  onClearSelection,
}: CenterMapToolbarProps) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
          {mode}
        </span>
        <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-600">
          t={currentT}
        </span>
        {(Object.keys(visibleLayers) as Array<keyof CenterMapVisibleLayers>).map((key) => (
          <button
            key={key}
            type="button"
            className={`rounded-full border px-3 py-1.5 text-xs font-medium transition ${
              visibleLayers[key]
                ? "border-sky-300 bg-sky-50 text-sky-900"
                : "border-slate-200 bg-white text-slate-500"
            }`}
            onClick={() => onToggleLayer(key)}
          >
            {LAYER_LABELS[key]}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <p className="text-xs text-slate-500">
          {mode === "precision" ? "Micro-visible analysis layers" : "Meso-visible swarm layers"}
        </p>
        {onClearSelection ? (
          <button
            type="button"
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-600"
            onClick={onClearSelection}
          >
            Clear Focus
          </button>
        ) : null}
      </div>
    </div>
  );
}
