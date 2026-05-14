"use client";

import type { CenterMapMode, CenterMapVisibleLayers } from "@/components/center-map/types";
import type { UiLocale } from "@/lib/ui-language";

type CenterMapToolbarProps = {
  mode: CenterMapMode;
  currentT: number;
  locale?: UiLocale;
  visibleLayers: CenterMapVisibleLayers;
  onToggleLayer: (key: keyof CenterMapVisibleLayers) => void;
  onClearSelection?: () => void;
  onResetCamera?: () => void;
};

const TOOLBAR_COPY = {
  en: {
    guide: "Guide",
    guideTitle: "Layer guide",
    layersTitle: "Layers",
    colorsTitle: "Colors",
    fit: "Fit",
    clear: "Clear",
    layerLabels: {
      zones: "Zones",
      agents: "Agents",
      interactions: "Relations",
      pressure: "Pressure",
      heat: "Agent heat",
      shock: "Shock",
      drift: "Drift",
      anchors: "Anchors",
      labels: "Labels",
      clusters: "Clusters",
    },
    layerDescriptions: {
      zones: "Zone terrain. Shows the underlying regions that organize agents and group pressure.",
      agents: "Individual agents. Hover or click to inspect a local social neighborhood.",
      interactions: "Live intra-t relationship lines. Green is cooperative, amber is negative, red is hostile.",
      pressure: "Collective pressure grid. Aggregates tension/policy pressure separately from individual agent colors.",
      heat: "Agent distribution heatmap. Shows density/activity, not collective pressure.",
      shock: "Event ripples from timeline annotations and policy shocks.",
      drift: "Directional movement of zones and groups across the field.",
      anchors: "Review grounding pins tied to evidence, events, or specific agents.",
      labels: "Text labels for map entities. Keep off when scanning dense fields.",
      clusters: "Group mass contours. Best for swarm or bloc-level reading.",
    },
    colors: [
      ["Blue", "low pressure, stable signal, or baseline social field"],
      ["Amber", "rising pressure or moderate collective tension"],
      ["Orange", "high pressure and stronger policy/group response"],
      ["Red", "fracture, shock, or elevated risk"],
      ["Teal", "drift or movement-oriented group change"],
    ],
  },
  ko: {
    guide: "설명",
    guideTitle: "레이어 설명",
    layersTitle: "레이어",
    colorsTitle: "색상 의미",
    fit: "맞춤",
    clear: "해제",
    layerLabels: {
      zones: "Zone",
      agents: "에이전트",
      interactions: "관계선",
      pressure: "압력",
      heat: "에이전트 Heat",
      shock: "충격",
      drift: "이동",
      anchors: "근거",
      labels: "라벨",
      clusters: "클러스터",
    },
    layerDescriptions: {
      zones: "Zone 지형입니다. 에이전트와 집단 압력이 놓이는 기본 지역 구조를 보여줍니다.",
      agents: "개별 에이전트입니다. 마우스를 올리거나 클릭하면 주변 사회 상태를 확인할 수 있습니다.",
      interactions: "t 내부 관계선입니다. 긍정은 초록, 부정은 주황, 적대는 빨강으로 표시합니다.",
      pressure: "집단 압력 그리드입니다. 에이전트 색상과 분리해 긴장/정책 압력이 모이는 위치를 보여줍니다.",
      heat: "에이전트 분포 히트맵입니다. 밀도/활동량을 보여주며 집단 압력과는 별개입니다.",
      shock: "타임라인 이벤트나 정책 충격이 퍼지는 파동입니다.",
      drift: "zone과 group이 어느 방향으로 이동하거나 흔들리는지 보여줍니다.",
      anchors: "리뷰 근거, 이벤트, 특정 에이전트와 연결된 위치 표시입니다.",
      labels: "맵 요소의 텍스트 라벨입니다. 밀도가 높을 때는 끄는 편이 읽기 좋습니다.",
      clusters: "집단/블록의 질량 분포입니다. Swarm이나 bloc 단위 해석에 적합합니다.",
    },
    colors: [
      ["파랑", "낮은 압력, 안정 신호, 기본 사회장"],
      ["노랑", "상승 중인 압력 또는 중간 수준의 집단 긴장"],
      ["주황", "높은 압력과 강한 정책/집단 반응"],
      ["빨강", "분열, 충격, 상승한 위험"],
      ["청록", "이동, drift, 방향성 있는 집단 변화"],
    ],
  },
} satisfies Record<
  UiLocale,
  {
    guide: string;
    guideTitle: string;
    layersTitle: string;
    colorsTitle: string;
    fit: string;
    clear: string;
    layerLabels: Record<keyof CenterMapVisibleLayers, string>;
    layerDescriptions: Record<keyof CenterMapVisibleLayers, string>;
    colors: Array<readonly [string, string]>;
  }
>;

export function CenterMapToolbar({
  mode,
  currentT,
  locale = "ko",
  visibleLayers,
  onToggleLayer,
  onClearSelection,
  onResetCamera,
}: CenterMapToolbarProps) {
  const copy = TOOLBAR_COPY[locale];
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 bg-white/70 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-md bg-slate-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.1em] text-white">
          {mode}
        </span>
        <span className="rounded-md bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-600">
          t={currentT}
        </span>
        <span className="center-map-toolbar__info">
          <button
            type="button"
            className="center-map-toolbar__guide-button"
            aria-describedby="center-map-layer-guide"
          >
            {copy.guide}
          </button>
          <span id="center-map-layer-guide" role="tooltip" className="center-map-toolbar__popover">
            <strong>{copy.guideTitle}</strong>
            <span className="center-map-toolbar__section-title">{copy.layersTitle}</span>
            {(Object.keys(copy.layerDescriptions) as Array<keyof CenterMapVisibleLayers>).map((key) => (
              <span key={key} className="center-map-toolbar__guide-row">
                <b>{copy.layerLabels[key]}</b>
                <span>{copy.layerDescriptions[key]}</span>
              </span>
            ))}
            <span className="center-map-toolbar__section-title">{copy.colorsTitle}</span>
            {copy.colors.map(([label, description]) => (
              <span key={label} className="center-map-toolbar__guide-row">
                <b>{label}</b>
                <span>{description}</span>
              </span>
            ))}
          </span>
        </span>
        {(Object.keys(visibleLayers) as Array<keyof CenterMapVisibleLayers>).map((key) => (
          <span key={key} className="center-map-toolbar__layer">
            <button
            type="button"
            title={copy.layerDescriptions[key]}
            className={`rounded-md border px-2.5 py-1 text-xs font-medium transition ${
              visibleLayers[key]
                ? "border-sky-300 bg-sky-50 text-sky-900"
                : "border-slate-200 bg-white text-slate-500"
            }`}
            onClick={() => onToggleLayer(key)}
          >
            {copy.layerLabels[key]}
          </button>
          </span>
        ))}
      </div>
      <div className="flex items-center gap-2">
        {onResetCamera ? (
          <button
            type="button"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600 transition hover:border-sky-300 hover:text-sky-800"
            onClick={onResetCamera}
          >
            {copy.fit}
          </button>
        ) : null}
        {onClearSelection ? (
          <button
            type="button"
            className="rounded-md border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
            onClick={onClearSelection}
          >
            {copy.clear}
          </button>
        ) : null}
      </div>
    </div>
  );
}
