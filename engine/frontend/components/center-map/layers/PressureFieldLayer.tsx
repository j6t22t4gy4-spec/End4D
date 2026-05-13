"use client";

import type { AgentNode } from "@/components/SimulationMap2D";

type PressureFieldLayerProps = {
  nodes: AgentNode[];
  renderTime: number;
  pointerField: {
    x: number;
    y: number;
    active: boolean;
  };
};

export function PressureFieldLayer({ nodes, renderTime, pointerField }: PressureFieldLayerProps) {
  const pressureNodes = nodes
    .filter((node) => node.collectivePressure > 0.02)
    .sort((a, b) => b.collectivePressure - a.collectivePressure)
    .slice(0, 48);
  const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 12 : 4);
  const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 10 : 4);

  return (
    <g className="simulation-map__pressure-field" aria-hidden="true">
      {pressureNodes.map((node, index) => {
        const pressure = node.collectivePressure;
        const baseRadius = 18 + pressure * 54;
        const alertBoost = node.fractureSignal ? 14 : 0;
        const radius = baseRadius + alertBoost;
        const fill = pressureFill(pressure, node.fractureSignal);
        const opacity = Math.min(0.34, 0.08 + pressure * 0.3 + (node.fractureSignal ? 0.08 : 0));
        const bloom = 0.88 + ((Math.sin(renderTime * (1.2 + (index % 5) * 0.17) + index * 0.4) + 1) / 2) * 0.26;
        const coreBloom = 0.82 + ((Math.cos(renderTime * (1.6 + (index % 4) * 0.13) + index * 0.3) + 1) / 2) * 0.22;
        const fieldOffsetX = pointerPushX * (0.25 + pressure * 0.4);
        const fieldOffsetY = pointerPushY * (0.2 + pressure * 0.36);
        return (
          <g key={`pressure-${node.id}`}>
            <circle
              cx={node.cx + fieldOffsetX}
              cy={node.cy + fieldOffsetY}
              r={radius * bloom}
              fill={fill}
              fillOpacity={Math.max(0.06, opacity * (0.72 + (bloom - 0.88)))}
              stroke="none"
              className="simulation-map__pressure-pulse"
            />
            <circle
              cx={node.cx + fieldOffsetX * 0.55}
              cy={node.cy + fieldOffsetY * 0.55}
              r={Math.max(10, radius * 0.58 * coreBloom)}
              fill={fill}
              fillOpacity={Math.min(0.22, opacity * (0.54 + (coreBloom - 0.82)))}
              stroke="none"
              className="simulation-map__pressure-core"
            />
          </g>
        );
      })}
    </g>
  );
}

function pressureFill(pressure: number, fractureSignal: boolean) {
  if (fractureSignal || pressure >= 0.55) return "rgb(244, 63, 94)";
  if (pressure >= 0.35) return "rgb(251, 146, 60)";
  if (pressure >= 0.18) return "rgb(250, 204, 21)";
  return "rgb(56, 189, 248)";
}
