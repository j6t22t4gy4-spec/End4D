"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  CenterMapSceneInteraction,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type AgentVisual = {
  container: Container;
  transitionTrail: Graphics;
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
  transitionEnergy: number;
  interactionX: number;
  interactionY: number;
  interactionEnergy: number;
};

export class AgentLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, AgentVisual>();

  updateInteractions(interactions: CenterMapSceneInteraction[]) {
    for (const interaction of interactions.slice(0, 80)) {
      if (!interaction.fresh) continue;
      const source = this.visuals.get(interaction.sourceId);
      const target = this.visuals.get(interaction.targetId);
      if (!source || !target) continue;
      const dx = target.targetX - source.targetX;
      const dy = target.targetY - source.targetY;
      const len = Math.max(1, Math.hypot(dx, dy));
      const ux = dx / len;
      const uy = dy / len;
      const sign = interaction.type === "positive" || interaction.type === "dialogue" ? 1 : -1;
      const lateral = interaction.type === "hostile" ? 0.55 : interaction.type === "negative" ? 0.3 : 0.12;
      const force = Math.min(
        8.5,
        2.6 + interaction.intensity * 6.4 + Math.abs(interaction.pressureDelta ?? 0) * 10
      );
      nudge(source, ux * sign * force + -uy * lateral * force, uy * sign * force + ux * lateral * force, interaction.intensity);
      nudge(target, -ux * sign * force + uy * lateral * force, -uy * sign * force + -ux * lateral * force, interaction.intensity);
    }
  }

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

      const targetShift = Math.hypot(agent.x - existing.targetX, agent.y - existing.targetY);
      existing.targetX = agent.x;
      existing.targetY = agent.y;
      if (targetShift > 0.35) {
        existing.transitionEnergy = Math.min(1, existing.transitionEnergy + Math.min(1, targetShift / 42));
      }
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

  animate(renderTime: number, pointerField: PointerField, transitionPhase = 0) {
    const pointerPushX = pointerField.active ? (pointerField.x - 0.5) * 3.5 : 0;
    const pointerPushY = pointerField.active ? (pointerField.y - 0.5) * 3 : 0;
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
      const targetDistance = Math.hypot(visual.targetX - visual.x, visual.targetY - visual.y);
      const transitionBoost = Math.max(transitionPhase, visual.transitionEnergy);
      const lerpGain = Math.min(
        0.42,
        (visual.selected ? 0.21 : visual.hovered ? 0.19 : 0.16) +
          transitionBoost * 0.16 +
          Math.min(0.08, targetDistance / 900)
      );
      visual.x += (visual.targetX - visual.x) * lerpGain;
      visual.y += (visual.targetY - visual.y) * lerpGain;
      visual.transitionEnergy = Math.max(0, visual.transitionEnergy * 0.9 - 0.012);

      const driftWeight = visual.hovered || visual.selected ? 0.08 : 0.025;

      visual.container.position.set(
        visual.x + visual.interactionX + pointerPushX * driftWeight,
        visual.y + visual.interactionY + pointerPushY * driftWeight
      );
      visual.container.scale.set(
        1 +
          (visual.hovered ? 0.1 : 0) +
          (visual.selected ? 0.08 : 0) +
          neighborFocus * 0.12 +
          visual.interactionEnergy * 0.08
      );
      visual.container.alpha = isolationDim;

      visual.halo.scale.set(1);
      visual.halo.alpha = Math.min(
        0.34,
        0.08 +
          visual.observerScore * 0.2 +
          visual.pressure * 0.06 +
          neighborFocus * 0.18 +
          visual.interactionEnergy * 0.12 +
          (visual.hovered ? 0.06 : 0) +
          (visual.selected ? 0.09 : 0)
      );

      visual.hoverGlow.scale.set(visual.hovered ? 1.08 : 1);
      visual.hoverGlow.alpha = visual.hovered
        ? 0.36
        : visual.selected
          ? 0.22
          : 0;

      visual.fractureAura.scale.set(1.08);
      visual.fractureAura.alpha = visual.fractureSignal
        ? 0.22
        : 0;

      visual.core.scale.set(1 + (visual.hovered ? 0.08 : visual.selected ? 0.1 : 0));
      visual.core.alpha = hoveredVisual && !visual.hovered && !visual.selected
        ? 0.68 + neighborFocus * 0.32
        : isolationDim;

      visual.ring.scale.set(visual.selected ? 1.12 : visual.hovered ? 1.08 : 1);
      visual.ring.alpha = visual.selected || visual.hovered || visual.fractureSignal ? 0.78 : 0.0;

      this.drawTransitionTrail(visual, renderTime, transitionBoost, targetDistance);
      visual.interactionX *= 0.84;
      visual.interactionY *= 0.84;
      visual.interactionEnergy = Math.max(0, visual.interactionEnergy * 0.86 - 0.01);
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
    const transitionTrail = new Graphics();
    const halo = new Graphics();
    const hoverGlow = new Graphics();
    const fractureAura = new Graphics();
    const ring = new Graphics();
    const core = new Graphics();

    container.addChild(transitionTrail);
    container.addChild(halo);
    container.addChild(hoverGlow);
    container.addChild(fractureAura);
    container.addChild(ring);
    container.addChild(core);

    const visual: AgentVisual = {
      container,
      transitionTrail,
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
      transitionEnergy: 0,
      interactionX: 0,
      interactionY: 0,
      interactionEnergy: 0,
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

  private drawTransitionTrail(
    visual: AgentVisual,
    renderTime: number,
    transitionBoost: number,
    targetDistance: number
  ) {
    visual.transitionTrail.clear();
    if (transitionBoost <= 0.02 || targetDistance <= 0.6) return;
    const dx = visual.targetX - visual.x;
    const dy = visual.targetY - visual.y;
    const len = Math.max(1, Math.hypot(dx, dy));
    const ux = dx / len;
    const uy = dy / len;
    const tail = Math.min(28, 8 + targetDistance * 0.38);
    const shimmer = 0.65 + 0.35 * Math.sin(renderTime * 0.018 + visual.phase * 6.28);
    visual.transitionTrail.lineStyle(
      Math.min(1.6, 0.65 + transitionBoost * 0.85),
      visual.color,
      Math.min(0.34, transitionBoost * 0.28 * shimmer)
    );
    visual.transitionTrail.moveTo(-ux * tail, -uy * tail);
    visual.transitionTrail.lineTo(-ux * (visual.radius + 2), -uy * (visual.radius + 2));
  }
}

function nudge(visual: AgentVisual, dx: number, dy: number, energy: number) {
  visual.interactionX = Math.max(-16, Math.min(16, visual.interactionX + dx));
  visual.interactionY = Math.max(-16, Math.min(16, visual.interactionY + dy));
  visual.interactionEnergy = Math.min(1, visual.interactionEnergy + 0.28 + energy * 0.42);
}
