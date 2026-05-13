"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

export class PressureLayerPixi {
  readonly container = new Container();

  private readonly field = new Graphics();
  private fieldAgents: CenterMapSceneAgent[] = [];

  constructor() {
    this.container.addChild(this.field);
  }

  updateAgents(agents: CenterMapSceneAgent[]) {
    const pressureAgents = agents
      .filter((agent) => agent.pressure > 0.003 || agent.fractureSignal)
      .sort((a, b) => b.pressure - a.pressure)
      .slice(0, 220);
    this.fieldAgents = pressureAgents;
    this.redrawField();
  }

  animate(renderTime: number, pointerField: PointerField) {
    void renderTime;
    void pointerField;
  }

  destroy() {
    this.container.destroy({ children: true });
  }

  private redrawField() {
    this.field.clear();
    if (this.fieldAgents.length === 0) return;

    const cellSize = 24;
    const gap = 2;
    const sigma = 78;
    const sigma2 = sigma * sigma * 2;

    for (let y = 62; y <= 574; y += cellSize) {
      for (let x = 62; x <= 898; x += cellSize) {
        const intensity = this.fieldAgents.reduce((sum, agent) => {
          const dx = x - agent.x;
          const dy = y - agent.y;
          const pressure = agent.pressure + (agent.fractureSignal ? 0.16 : 0);
          return sum + pressure * Math.exp(-(dx * dx + dy * dy) / sigma2);
        }, 0);

        if (intensity < 0.06) continue;

        const normalized = Math.min(1, intensity);
        const fill = fieldColor(normalized);
        const alpha = Math.min(0.42, 0.08 + normalized * 0.24);
        this.field.beginFill(fill, alpha);
        this.field.drawRect(
          x - cellSize / 2 + gap,
          y - cellSize / 2 + gap,
          cellSize - gap * 2,
          cellSize - gap * 2
        );
        this.field.endFill();
      }
    }
  }
}

function fieldColor(intensity: number) {
  if (intensity >= 0.58) return 0xe11d48;
  if (intensity >= 0.36) return 0xf97316;
  if (intensity >= 0.2) return 0xf59e0b;
  return 0x38bdf8;
}
