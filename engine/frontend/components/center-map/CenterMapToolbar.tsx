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
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white/70 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-slate-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-white">
          {mode}
        </span>
        <span className="rounded-md bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">
          t={currentT}
        </span>
        {(Object.keys(visibleLayers) as Array<keyof CenterMapVisibleLayers>).map((key) => (
          <button
            key={key}
            type="button"
            className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
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
        {onClearSelection ? (
          <button
            type="button"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
            onClick={onClearSelection}
          >
            Clear
          </button>
        ) : null}
      </div>
    </div>
  );
}
