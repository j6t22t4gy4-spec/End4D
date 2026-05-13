"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type AgentVisual = {
  container: Container;
  halo: Graphics;
  core: Graphics;
  ring: Graphics;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  radius: number;
  color: number;
  pressure: number;
  observerScore: number;
  selected: boolean;
  fractureSignal: boolean;
  phase: number;
};

export class AgentLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, AgentVisual>();

  updateAgents(agents: CenterMapSceneAgent[]) {
    const nextIds = new Set(agents.map((agent) => agent.id));

    for (const [id, visual] of this.visuals) {
      if (nextIds.has(id)) continue;
      this.container.removeChild(visual.container);
      visual.container.destroy({ children: true });
      this.visuals.delete(id);
    }

    for (const agent of agents) {
      const existing = this.visuals.get(agent.id);
      if (!existing) {
        const visual = this.createVisual(agent);
        this.visuals.set(agent.id, visual);
        this.container.addChild(visual.container);
        continue;
      }

      existing.targetX = agent.x;
      existing.targetY = agent.y;
      const needsRedraw =
        existing.radius !== agent.radius ||
        existing.color !== agent.color ||
        existing.pressure !== agent.pressure ||
        existing.observerScore !== agent.observerScore ||
        existing.selected !== agent.selected ||
        existing.fractureSignal !== agent.fractureSignal;

      existing.radius = agent.radius;
      existing.color = agent.color;
      existing.pressure = agent.pressure;
      existing.observerScore = agent.observerScore;
      existing.selected = agent.selected;
      existing.fractureSignal = agent.fractureSignal;

      if (needsRedraw) this.redrawVisual(existing);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 14 : 5);
    const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 12 : 4);

    for (const visual of this.visuals.values()) {
      visual.x += (visual.targetX - visual.x) * 0.14;
      visual.y += (visual.targetY - visual.y) * 0.14;

      const driftWeight = 0.05 + visual.pressure * 0.1;
      const floatX =
        Math.sin(renderTime * (0.9 + visual.phase * 0.25) + visual.phase * 6) *
        (1.8 + visual.pressure * 2.4);
      const floatY =
        Math.cos(renderTime * (1.1 + visual.phase * 0.22) + visual.phase * 7) *
        (1.6 + visual.pressure * 2);

      visual.container.position.set(
        visual.x + floatX + pointerPushX * driftWeight,
        visual.y + floatY + pointerPushY * driftWeight
      );

      const haloPulse =
        0.96 + ((Math.sin(renderTime * (1.8 + visual.phase) + visual.phase * 10) + 1) / 2) * 0.18;
      visual.halo.scale.set(haloPulse);
      visual.halo.alpha = Math.min(
        0.34,
        0.06 + visual.observerScore * 0.24 + visual.pressure * 0.08
      );

      const corePulse =
        0.98 + ((Math.cos(renderTime * (2.2 + visual.phase * 0.7)) + 1) / 2) * 0.08;
      visual.core.scale.set(corePulse);

      const ringPulse =
        1 + ((Math.sin(renderTime * (3.1 + visual.phase * 0.5) + visual.phase * 8) + 1) / 2) * 0.14;
      visual.ring.scale.set(ringPulse);
      visual.ring.alpha = visual.selected || visual.fractureSignal ? 0.88 : 0.0;
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(agent: CenterMapSceneAgent) {
    const container = new Container();
    const halo = new Graphics();
    const ring = new Graphics();
    const core = new Graphics();

    container.addChild(halo);
    container.addChild(ring);
    container.addChild(core);

    const visual: AgentVisual = {
      container,
      halo,
      ring,
      core,
      x: agent.x,
      y: agent.y,
      targetX: agent.x,
      targetY: agent.y,
      radius: agent.radius,
      color: agent.color,
      pressure: agent.pressure,
      observerScore: agent.observerScore,
      selected: agent.selected,
      fractureSignal: agent.fractureSignal,
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(agent.x, agent.y);
    return visual;
  }

  private redrawVisual(visual: AgentVisual) {
    visual.halo.clear();
    visual.halo.beginFill(visual.color, Math.min(0.28, 0.05 + visual.observerScore * 0.18 + visual.pressure * 0.08));
    visual.halo.drawCircle(0, 0, visual.radius + 7 + visual.pressure * 9);
    visual.halo.endFill();

    visual.ring.clear();
    if (visual.selected || visual.fractureSignal) {
      visual.ring.lineStyle(
        1.5 + (visual.selected ? 0.9 : 0),
        visual.selected ? 0xf8fafc : 0xfb7185,
        0.88
      );
      visual.ring.drawCircle(0, 0, visual.radius + 9 + visual.pressure * 5);
    }

    visual.core.clear();
    visual.core.beginFill(visual.color, 0.96);
    visual.core.drawCircle(0, 0, visual.radius);
    visual.core.endFill();
    visual.core.lineStyle(1 + visual.observerScore * 1.6, 0xffffff, 0.26 + visual.observerScore * 0.28);
    visual.core.drawCircle(0, 0, Math.max(1.2, visual.radius - 0.4));
  }
}
