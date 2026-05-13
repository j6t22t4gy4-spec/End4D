"use client";

import type { AgentNode, ZoneBox } from "@/components/SimulationMap2D";
import type { ReviewGroundingItem } from "@/lib/api";

type AnchorLayerProps = {
  nodes: AgentNode[];
  zones: ZoneBox[];
  items: ReviewGroundingItem[];
  currentT: number;
  onJumpToT?: (t: number) => void;
};

type ResolvedAnchor = {
  key: string;
  x: number;
  y: number;
  label: string;
  reason: string;
  t: number | null;
  color: string;
};

export function AnchorLayer({
  nodes,
  zones,
  items,
  currentT,
  onJumpToT,
}: AnchorLayerProps) {
  const filtered = items
    .filter((item) => item.t == null || Math.abs(Number(item.t) - currentT) <= 12)
    .slice(0, 8);

  if (!filtered.length) return null;

  const fallbackNodes = [...nodes]
    .sort((a, b) => b.collectivePressure - a.collectivePressure)
    .slice(0, Math.max(1, filtered.length));

  const resolved: ResolvedAnchor[] = filtered
    .map((item, index) => resolveAnchor(item, index, nodes, zones, fallbackNodes))
    .filter((item): item is ResolvedAnchor => item !== null);

  return (
    <g className="simulation-map__anchor-layer">
      {resolved.map((anchor) => (
        <g
          key={anchor.key}
          className="simulation-map__anchor-pin"
          onClick={() => {
            if (onJumpToT && anchor.t != null) onJumpToT(anchor.t);
          }}
          style={{ cursor: anchor.t != null && onJumpToT ? "pointer" : "default" }}
        >
          <circle
            cx={anchor.x}
            cy={anchor.y}
            r="9"
            fill="white"
            fillOpacity="0.96"
            stroke={anchor.color}
            strokeWidth="2"
          />
          <circle
            cx={anchor.x}
            cy={anchor.y}
            r="3.5"
            fill={anchor.color}
            stroke="none"
          />
          <line
            x1={anchor.x + 7}
            y1={anchor.y - 7}
            x2={anchor.x + 16}
            y2={anchor.y - 16}
            stroke={anchor.color}
            strokeWidth="1.5"
            strokeOpacity="0.8"
          />
          <text
            x={anchor.x + 20}
            y={anchor.y - 18}
            className="simulation-map__zone-label simulation-map__anchor-label"
            fill={anchor.color}
          >
            {anchor.label}
          </text>
          <title>{anchor.reason}</title>
        </g>
      ))}
    </g>
  );
}

function resolveAnchor(
  item: ReviewGroundingItem,
  index: number,
  nodes: AgentNode[],
  zones: ZoneBox[],
  fallbackNodes: AgentNode[]
): ResolvedAnchor | null {
  const color = anchorColor(item.kind);
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
}

function anchorColor(kind: string) {
  if (kind === "event") return "rgb(249, 115, 22)";
  if (kind === "group") return "rgb(99, 102, 241)";
  if (kind === "zone") return "rgb(16, 185, 129)";
  if (kind === "agent") return "rgb(244, 63, 94)";
  return "rgb(14, 165, 233)";
}
