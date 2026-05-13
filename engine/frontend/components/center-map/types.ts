"use client";

import type {
  CellSnapshot,
  CollectiveDynamicsSummary,
  ReviewGroundingItem,
  ReviewSummaryResponse,
  TimelineAnnotation,
} from "@/lib/api";
import type { UiLocale } from "@/lib/ui-language";
import type { SelectedBand, SelectedZone } from "@/components/SimulationInspectorPanel";

export type CenterMapMode = "precision" | "swarm";

export type CenterMapVisibleLayers = {
  zones: boolean;
  agents: boolean;
  heat: boolean;
  shock: boolean;
  drift: boolean;
  anchors: boolean;
  labels: boolean;
  clusters: boolean;
};

export type CenterMapShellProps = {
  mode: CenterMapMode;
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  currentT: number;
  annotations?: TimelineAnnotation[];
  groundingItems?: ReviewGroundingItem[];
  collectiveSummary: CollectiveDynamicsSummary | null;
  reviewSummary: ReviewSummaryResponse | null;
  locale?: UiLocale;
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  onSelectAgent?: (cell: CellSnapshot) => void;
  onSelectZone?: (zone: SelectedZone) => void;
  onSelectBand?: (band: SelectedBand) => void;
  onClearSelection?: () => void;
  onJumpToT?: (t: number) => void;
};
