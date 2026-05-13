"use client";

import type { CellSnapshot } from "@/lib/api";
import type { AgentNode } from "@/components/SimulationMap2D";

type AgentLayerProps = {
  nodes: AgentNode[];
  renderTime: number;
  selectedAgentId?: string | null;
  onSelectAgent?: (cell: CellSnapshot) => void;
};

export function AgentLayer({
  nodes,
  renderTime,
  selectedAgentId = null,
  onSelectAgent,
}: AgentLayerProps) {
  return (
    <>
      {nodes.map((node, index) => (
        <g
          key={node.id}
          className="simulation-map__agent-group"
          transform={`translate(${Math.sin(renderTime * (0.7 + (index % 5) * 0.11) + index) * (1.5 + (index % 4))} ${Math.cos(renderTime * (0.9 + (index % 7) * 0.08) + index * 0.7) * (1.2 + (index % 3))})`}
        >
          {node.observer.score > 0 ? (
            <circle
              cx={node.cx}
              cy={node.cy}
              r={node.r + 5 + node.observer.score * 6}
              fill={node.observer.halo}
              fillOpacity={0.2 + node.observer.score * 0.16 + Math.sin(renderTime * 1.8 + index) * 0.06}
              stroke="none"
              className="simulation-map__agent-observer-halo"
            />
          ) : null}
          {selectedAgentId === node.id ? (
            <circle
              cx={node.cx}
              cy={node.cy}
              r={node.r + 9 + Math.sin(renderTime * 3.2) * 2.4}
              fill="none"
              stroke="rgba(255,255,255,0.9)"
              strokeWidth="1.2"
              strokeOpacity={0.62 + Math.sin(renderTime * 3.2) * 0.18}
              className="simulation-map__agent-focus-ring"
            />
          ) : null}
          <circle
            cx={node.cx}
            cy={node.cy}
            r={node.r * (1 + Math.sin(renderTime * (1.6 + (index % 6) * 0.12) + index * 0.4) * 0.06)}
            fill={node.fill}
            fillOpacity="0.92"
            stroke={selectedAgentId === node.id ? "#0f172a" : node.observer.ring}
            strokeWidth={selectedAgentId === node.id ? "2.5" : 1.5 + node.observer.score * 1.8}
            className="simulation-map__agent-node"
            onClick={() => onSelectAgent?.(node.cell)}
          />
          <title>{node.title}</title>
        </g>
      ))}
    </>
  );
}
