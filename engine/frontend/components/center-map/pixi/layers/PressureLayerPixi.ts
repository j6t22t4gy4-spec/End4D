"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type PressureVisual = {
  container: Container;
  outer: Graphics;
  core: Graphics;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  pressure: number;
  fractureSignal: boolean;
  radius: number;
  phase: number;
};

export class PressureLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, PressureVisual>();

  updateAgents(agents: CenterMapSceneAgent[]) {
    const pressureAgents = agents
      .filter((agent) => agent.pressure > 0.03)
      .sort((a, b) => b.pressure - a.pressure)
      .slice(0, 52);

    const nextIds = new Set(pressureAgents.map((agent) => agent.id));

    for (const [id, visual] of this.visuals) {
      if (nextIds.has(id)) continue;
      this.container.removeChild(visual.container);
      visual.container.destroy({ children: true });
      this.visuals.delete(id);
    }

    for (const agent of pressureAgents) {
      const existing = this.visuals.get(agent.id);
      if (!existing) {
        const visual = this.createVisual(agent);
        this.visuals.set(agent.id, visual);
        this.container.addChild(visual.container);
        continue;
      }

      existing.targetX = agent.x;
      existing.targetY = agent.y;
      const nextRadius = 18 + agent.pressure * 68 + (agent.fractureSignal ? 16 : 0);
      const needsRedraw =
        existing.pressure !== agent.pressure ||
        existing.fractureSignal !== agent.fractureSignal ||
        existing.radius !== nextRadius;

      existing.pressure = agent.pressure;
      existing.fractureSignal = agent.fractureSignal;
      existing.radius = nextRadius;

      if (needsRedraw) this.redrawVisual(existing);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 16 : 6);
    const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 14 : 6);

    for (const visual of this.visuals.values()) {
      visual.x += (visual.targetX - visual.x) * 0.1;
      visual.y += (visual.targetY - visual.y) * 0.1;

      const wobbleX =
        Math.sin(renderTime * (0.64 + visual.phase * 0.3) + visual.phase * 9) *
        (3 + visual.pressure * 5);
      const wobbleY =
        Math.cos(renderTime * (0.58 + visual.phase * 0.24) + visual.phase * 8) *
        (2.5 + visual.pressure * 4);
      const driftWeight = 0.18 + visual.pressure * 0.34;

      visual.container.position.set(
        visual.x + wobbleX + pointerPushX * driftWeight,
        visual.y + wobbleY + pointerPushY * driftWeight
      );

      const outerPulse =
        0.96 + ((Math.sin(renderTime * (1.2 + visual.phase * 0.2) + visual.phase * 5) + 1) / 2) * 0.24;
      const corePulse =
        0.88 + ((Math.cos(renderTime * (1.7 + visual.phase * 0.25) + visual.phase * 6) + 1) / 2) * 0.18;

      visual.outer.scale.set(outerPulse);
      visual.core.scale.set(corePulse);
      visual.outer.alpha = Math.min(
        0.34,
        0.08 + visual.pressure * 0.24 + (visual.fractureSignal ? 0.08 : 0)
      );
      visual.core.alpha = Math.min(
        0.2,
        0.05 + visual.pressure * 0.12 + (visual.fractureSignal ? 0.04 : 0)
      );
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(agent: CenterMapSceneAgent) {
    const container = new Container();
    const outer = new Graphics();
    const core = new Graphics();
    container.addChild(outer);
    container.addChild(core);

    const visual: PressureVisual = {
      container,
      outer,
      core,
      x: agent.x,
      y: agent.y,
      targetX: agent.x,
      targetY: agent.y,
      pressure: agent.pressure,
      fractureSignal: agent.fractureSignal,
      radius: 18 + agent.pressure * 68 + (agent.fractureSignal ? 16 : 0),
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(agent.x, agent.y);
    return visual;
  }

  private redrawVisual(visual: PressureVisual) {
    const fill = pressureColor(visual.pressure, visual.fractureSignal);

    visual.outer.clear();
    visual.outer.beginFill(fill, 0.18);
    visual.outer.drawEllipse(0, 0, visual.radius * 1.08, visual.radius * 0.82);
    visual.outer.endFill();

    visual.core.clear();
    visual.core.beginFill(fill, 0.14);
    visual.core.drawEllipse(0, 0, visual.radius * 0.54, visual.radius * 0.42);
    visual.core.endFill();
  }
}

function pressureColor(pressure: number, fractureSignal: boolean) {
  if (fractureSignal || pressure >= 0.55) return 0xf43f5e;
  if (pressure >= 0.35) return 0xfb923c;
  if (pressure >= 0.18) return 0xfacc15;
  return 0x38bdf8;
}
