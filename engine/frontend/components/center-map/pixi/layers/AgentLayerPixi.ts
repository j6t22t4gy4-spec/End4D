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
      if (existing.selected) this.container.addChild(existing.container);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 8 : 3);
    const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 7 : 2.5);
    const hoveredVisual = Array.from(this.visuals.values()).find((visual) => visual.hovered);
    const selectedVisual = Array.from(this.visuals.values()).find((visual) => visual.selected);
    const anchorVisual = hoveredVisual ?? selectedVisual;
    const selectedIsolation = Boolean(selectedVisual && !hoveredVisual);

    for (const visual of this.visuals.values()) {
      const focusDistance = anchorVisual
        ? Math.hypot(visual.x - anchorVisual.x, visual.y - anchorVisual.y)
        : Number.POSITIVE_INFINITY;
      const neighborFocus =
        anchorVisual && visual !== anchorVisual
          ? Math.max(0, 1 - focusDistance / (selectedIsolation ? 170 : 118)) * (selectedIsolation ? 0.52 : 0.42)
          : 0;
      const isolationDim =
        selectedIsolation && !visual.selected
          ? 0.42 + neighborFocus * 0.7
          : 1;
      const lerpGain = visual.selected ? 0.21 : visual.hovered ? 0.19 : 0.16;
      visual.x += (visual.targetX - visual.x) * lerpGain;
      visual.y += (visual.targetY - visual.y) * lerpGain;

      const driftWeight = 0.04 + visual.pressure * 0.08 + (visual.hovered ? 0.03 : 0);
      const floatX =
        Math.sin(renderTime * (0.9 + visual.phase * 0.25) + visual.phase * 6) *
        (1.1 + visual.pressure * 1.8 + (visual.hovered ? 0.6 : 0) + (visual.selected ? 0.8 : 0));
      const floatY =
        Math.cos(renderTime * (1.1 + visual.phase * 0.22) + visual.phase * 7) *
        (0.9 + visual.pressure * 1.5 + (visual.hovered ? 0.5 : 0) + (visual.selected ? 0.7 : 0));

      visual.container.position.set(
        visual.x + floatX + pointerPushX * driftWeight,
        visual.y + floatY + pointerPushY * driftWeight
      );
      visual.container.scale.set(
        1 + (visual.hovered ? 0.1 : 0) + (visual.selected ? 0.08 : 0) + neighborFocus * 0.12
      );
      visual.container.alpha = isolationDim;

      const haloPulse =
        0.99 + ((Math.sin(renderTime * (1.3 + visual.phase) + visual.phase * 10) + 1) / 2) * 0.12;
      visual.halo.scale.set(haloPulse);
      visual.halo.alpha = Math.min(
        0.34,
        0.08 +
          visual.observerScore * 0.2 +
          visual.pressure * 0.06 +
          neighborFocus * 0.18 +
          (visual.hovered ? 0.06 : 0) +
          (visual.selected ? 0.09 : 0)
      );

      const hoverGlowPulse =
        1.02 + ((Math.cos(renderTime * (2 + visual.phase * 0.5) + visual.phase * 9) + 1) / 2) * 0.14;
      visual.hoverGlow.scale.set(hoverGlowPulse);
      visual.hoverGlow.alpha = visual.hovered
        ? 0.34 + ((Math.sin(renderTime * 4.1 + visual.phase * 10) + 1) / 2) * 0.12
        : visual.selected
          ? 0.22
          : 0;

      const fracturePulse =
        1.01 + ((Math.sin(renderTime * (3.2 + visual.phase * 0.7) + visual.phase * 8) + 1) / 2) * 0.18;
      visual.fractureAura.scale.set(fracturePulse);
      visual.fractureAura.alpha = visual.fractureSignal
        ? 0.18 + ((Math.sin(renderTime * 4.6 + visual.phase * 11) + 1) / 2) * 0.12
        : 0;

      const corePulse =
        1 +
        ((Math.cos(renderTime * (2.2 + visual.phase * 0.7)) + 1) / 2) *
          (visual.hovered ? 0.18 : visual.selected ? 0.22 : 0.1);
      visual.core.scale.set(corePulse);
      visual.core.alpha = hoveredVisual && !visual.hovered && !visual.selected
        ? 0.68 + neighborFocus * 0.32
        : isolationDim;

      const ringPulse =
        1 +
        ((Math.sin(renderTime * (3.1 + visual.phase * 0.5) + visual.phase * 8) + 1) / 2) *
          (visual.selected ? 0.28 : visual.hovered ? 0.22 : 0.18);
      visual.ring.scale.set(ringPulse);
      visual.ring.alpha = visual.selected || visual.hovered || visual.fractureSignal ? 0.78 : 0.0;
    }
  }

  setHoveredAgent(agentId: string | null) {
    for (const [id, visual] of this.visuals) {
      const nextHovered = id === agentId;
      if (visual.hovered === nextHovered) continue;
      visual.hovered = nextHovered;
      if (nextHovered) this.container.addChild(visual.container);
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
    if (agent.selected) this.container.addChild(container);
    return visual;
  }

  private redrawVisual(visual: AgentVisual) {
    visual.halo.clear();
    visual.halo.beginFill(
      visual.color,
      Math.min(0.24, 0.05 + visual.observerScore * 0.14 + visual.pressure * 0.05)
    );
    visual.halo.drawCircle(0, 0, visual.radius + 6 + visual.pressure * 6);
    visual.halo.endFill();

    visual.hoverGlow.clear();
    visual.hoverGlow.beginFill(0x38bdf8, 0.2);
    visual.hoverGlow.drawCircle(0, 0, visual.radius + 9 + visual.pressure * 5);
    visual.hoverGlow.endFill();

    visual.fractureAura.clear();
    visual.fractureAura.beginFill(0xf43f5e, 0.16);
    visual.fractureAura.drawCircle(0, 0, visual.radius + 10 + visual.pressure * 6);
    visual.fractureAura.endFill();

    visual.ring.clear();
    if (visual.selected || visual.hovered || visual.fractureSignal) {
      visual.ring.lineStyle(
        1.6 + (visual.selected ? 1 : visual.hovered ? 0.6 : 0.3),
        visual.selected ? 0xf8fafc : visual.hovered ? 0x7dd3fc : 0xfb7185,
        0.82
      );
      visual.ring.drawCircle(0, 0, visual.radius + 7 + visual.pressure * 4);
    }

    visual.core.clear();
    visual.core.beginFill(visual.color, 0.96);
    visual.core.drawCircle(0, 0, visual.radius + (visual.hovered ? 1.4 : visual.selected ? 1.9 : 0));
    visual.core.endFill();
  }
}
