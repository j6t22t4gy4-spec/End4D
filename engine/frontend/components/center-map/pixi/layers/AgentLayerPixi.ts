"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type AgentVisual = {
  container: Container;
  halo: Graphics;
  hoverGlow: Graphics;
  fractureAura: Graphics;
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
  hovered: boolean;
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
      const lerpGain = visual.selected ? 0.24 : visual.hovered ? 0.21 : 0.18;
      visual.x += (visual.targetX - visual.x) * lerpGain;
      visual.y += (visual.targetY - visual.y) * lerpGain;

      const driftWeight = 0.08 + visual.pressure * 0.14 + (visual.hovered ? 0.04 : 0);
      const floatX =
        Math.sin(renderTime * (0.9 + visual.phase * 0.25) + visual.phase * 6) *
        (2.8 + visual.pressure * 3.6 + (visual.hovered ? 1.2 : 0) + (visual.selected ? 1.6 : 0));
      const floatY =
        Math.cos(renderTime * (1.1 + visual.phase * 0.22) + visual.phase * 7) *
        (2.4 + visual.pressure * 3.2 + (visual.hovered ? 1.1 : 0) + (visual.selected ? 1.5 : 0));

      visual.container.position.set(
        visual.x + floatX + pointerPushX * driftWeight,
        visual.y + floatY + pointerPushY * driftWeight
      );

      const haloPulse =
        0.98 + ((Math.sin(renderTime * (1.8 + visual.phase) + visual.phase * 10) + 1) / 2) * 0.24;
      visual.halo.scale.set(haloPulse);
      visual.halo.alpha = Math.min(
        0.42,
        0.08 +
          visual.observerScore * 0.28 +
          visual.pressure * 0.1 +
          (visual.hovered ? 0.08 : 0) +
          (visual.selected ? 0.12 : 0)
      );

      const hoverGlowPulse =
        1.04 + ((Math.cos(renderTime * (2.6 + visual.phase * 0.5) + visual.phase * 9) + 1) / 2) * 0.28;
      visual.hoverGlow.scale.set(hoverGlowPulse);
      visual.hoverGlow.alpha = visual.hovered
        ? 0.54 + ((Math.sin(renderTime * 5.2 + visual.phase * 10) + 1) / 2) * 0.18
        : visual.selected
          ? 0.34
          : 0;

      const fracturePulse =
        1.02 + ((Math.sin(renderTime * (4.4 + visual.phase * 0.7) + visual.phase * 8) + 1) / 2) * 0.34;
      visual.fractureAura.scale.set(fracturePulse);
      visual.fractureAura.alpha = visual.fractureSignal
        ? 0.26 + ((Math.sin(renderTime * 6.2 + visual.phase * 11) + 1) / 2) * 0.22
        : 0;

      const corePulse =
        1 +
        ((Math.cos(renderTime * (2.2 + visual.phase * 0.7)) + 1) / 2) *
          (visual.hovered ? 0.18 : visual.selected ? 0.22 : 0.1);
      visual.core.scale.set(corePulse);

      const ringPulse =
        1 +
        ((Math.sin(renderTime * (3.1 + visual.phase * 0.5) + visual.phase * 8) + 1) / 2) *
          (visual.selected ? 0.28 : visual.hovered ? 0.22 : 0.18);
      visual.ring.scale.set(ringPulse);
      visual.ring.alpha = visual.selected || visual.hovered || visual.fractureSignal ? 0.9 : 0.0;
    }
  }

  setHoveredAgent(agentId: string | null) {
    for (const [id, visual] of this.visuals) {
      const nextHovered = id === agentId;
      if (visual.hovered === nextHovered) continue;
      visual.hovered = nextHovered;
      this.redrawVisual(visual);
    }
  }

  hitTest(x: number, y: number) {
    let bestId: string | null = null;
    let bestDistance = Number.POSITIVE_INFINITY;

    for (const [id, visual] of this.visuals) {
      const dx = x - visual.container.position.x;
      const dy = y - visual.container.position.y;
      const distance = Math.hypot(dx, dy);
      const threshold = visual.radius + 10;
      if (distance > threshold) continue;
      if (distance >= bestDistance) continue;
      bestDistance = distance;
      bestId = id;
    }

    return bestId;
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(agent: CenterMapSceneAgent) {
    const container = new Container();
    const halo = new Graphics();
    const hoverGlow = new Graphics();
    const fractureAura = new Graphics();
    const ring = new Graphics();
    const core = new Graphics();

    container.addChild(halo);
    container.addChild(hoverGlow);
    container.addChild(fractureAura);
    container.addChild(ring);
    container.addChild(core);

    const visual: AgentVisual = {
      container,
      halo,
      hoverGlow,
      fractureAura,
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
      hovered: false,
      fractureSignal: agent.fractureSignal,
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(agent.x, agent.y);
    return visual;
  }

  private redrawVisual(visual: AgentVisual) {
    visual.halo.clear();
    visual.halo.beginFill(
      visual.color,
      Math.min(0.34, 0.08 + visual.observerScore * 0.18 + visual.pressure * 0.08)
    );
    visual.halo.drawCircle(0, 0, visual.radius + 9 + visual.pressure * 10);
    visual.halo.endFill();

    visual.hoverGlow.clear();
    visual.hoverGlow.beginFill(0x7dd3fc, 0.24);
    visual.hoverGlow.drawCircle(0, 0, visual.radius + 13 + visual.pressure * 7);
    visual.hoverGlow.endFill();

    visual.fractureAura.clear();
    visual.fractureAura.beginFill(0xfb7185, 0.2);
    visual.fractureAura.drawCircle(0, 0, visual.radius + 16 + visual.pressure * 8);
    visual.fractureAura.endFill();

    visual.ring.clear();
    if (visual.selected || visual.hovered || visual.fractureSignal) {
      visual.ring.lineStyle(
        2 + (visual.selected ? 1.2 : visual.hovered ? 0.8 : 0.4),
        visual.selected ? 0xf8fafc : visual.hovered ? 0x7dd3fc : 0xfb7185,
        0.88
      );
      visual.ring.drawCircle(0, 0, visual.radius + 11 + visual.pressure * 6);
    }

    visual.core.clear();
    visual.core.beginFill(visual.color, 0.96);
    visual.core.drawCircle(0, 0, visual.radius + (visual.hovered ? 1.4 : visual.selected ? 1.9 : 0));
    visual.core.endFill();
    visual.core.lineStyle(
      1.3 + visual.observerScore * 1.8 + (visual.hovered ? 0.8 : 0) + (visual.selected ? 1 : 0),
      0xffffff,
      0.3 + visual.observerScore * 0.28
    );
    visual.core.drawCircle(
      0,
      0,
      Math.max(1.2, visual.radius - 0.2 + (visual.hovered ? 0.8 : 0) + (visual.selected ? 1.1 : 0))
    );
  }
}
