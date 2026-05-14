"use client";

import { Container, Graphics } from "pixi.js";

import type { CenterMapSceneAgent } from "@/components/center-map/scene/sceneTypes";

export class AgentHeatLayerPixi {
  readonly container = new Container();

  private readonly grid = new Graphics();
  private agents: CenterMapSceneAgent[] = [];

  constructor() {
    this.container.addChild(this.grid);
  }

  updateAgents(agents: CenterMapSceneAgent[]) {
    this.agents = agents
      .filter((agent) => agent.heat > 0.01)
      .sort((a, b) => b.heat - a.heat)
      .slice(0, 1200);
    this.redraw();
  }

  animate() {
    // Agent heat is intentionally static between scene updates. Motion belongs
    // to interactions; this layer is only a readable density/activity grid.
  }

  destroy() {
    this.container.destroy({ children: true });
  }

  private redraw() {
    this.grid.clear();
    if (!this.agents.length) return;

    const cellSize = 16;
    const gap = 1;
    const sigma = 42;
    const sigma2 = sigma * sigma * 2;

    for (let y = 64; y <= 576; y += cellSize) {
      for (let x = 64; x <= 896; x += cellSize) {
        let intensity = 0;
        for (const agent of this.agents) {
          const dx = x - agent.x;
          const dy = y - agent.y;
          if (Math.abs(dx) > sigma * 2.2 || Math.abs(dy) > sigma * 2.2) continue;
          intensity += Math.max(0.08, agent.heat) * Math.exp(-(dx * dx + dy * dy) / sigma2);
        }
        if (intensity < 0.055) continue;
        const normalized = Math.min(1, intensity * 0.74);
        this.grid.beginFill(heatColor(normalized), Math.min(0.28, 0.04 + normalized * 0.22));
        this.grid.drawRect(
          x - cellSize / 2 + gap,
          y - cellSize / 2 + gap,
          cellSize - gap * 2,
          cellSize - gap * 2
        );
        this.grid.endFill();
      }
    }
  }
}

function heatColor(intensity: number) {
  if (intensity >= 0.62) return 0x0f766e;
  if (intensity >= 0.36) return 0x14b8a6;
  if (intensity >= 0.18) return 0x67e8f9;
  return 0xbae6fd;
}
