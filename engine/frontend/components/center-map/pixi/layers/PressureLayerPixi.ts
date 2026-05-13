"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type PressureVisual = {
  container: Container;
  contour: Graphics;
  crest: Graphics;
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  pressure: number;
  fractureSignal: boolean;
  selected: boolean;
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
      const nextRadius = 26 + agent.pressure * 92 + (agent.fractureSignal ? 24 : 0);
      const needsRedraw =
        existing.pressure !== agent.pressure ||
      existing.fractureSignal !== agent.fractureSignal ||
        existing.selected !== agent.selected ||
        existing.radius !== nextRadius;

      existing.pressure = agent.pressure;
      existing.fractureSignal = agent.fractureSignal;
      existing.selected = agent.selected;
      existing.radius = nextRadius;

      if (needsRedraw) this.redrawVisual(existing);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 10 : 4);
    const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 9 : 4);
    const selectedVisual = Array.from(this.visuals.values()).find((visual) => visual.selected);

    for (const visual of this.visuals.values()) {
      const isolationWeight = selectedVisual
        ? Math.max(0.22, 1 - Math.hypot(visual.x - selectedVisual.x, visual.y - selectedVisual.y) / 240)
        : 1;
      visual.x += (visual.targetX - visual.x) * 0.08;
      visual.y += (visual.targetY - visual.y) * 0.08;

      const wobbleX =
        Math.sin(renderTime * (0.64 + visual.phase * 0.3) + visual.phase * 9) *
        (2.2 + visual.pressure * 3.2);
      const wobbleY =
        Math.cos(renderTime * (0.58 + visual.phase * 0.24) + visual.phase * 8) *
        (1.8 + visual.pressure * 2.8);
      const driftWeight = 0.12 + visual.pressure * 0.18;

      visual.container.position.set(
        visual.x + wobbleX + pointerPushX * driftWeight,
        visual.y + wobbleY + pointerPushY * driftWeight
      );

      const contourPulse =
        1 + ((Math.sin(renderTime * (0.46 + visual.phase * 0.1) + visual.phase * 5) + 1) / 2) * 0.025;

      visual.contour.scale.set(contourPulse);
      visual.crest.scale.set(1);
      visual.contour.alpha = Math.min(
        0.72,
        0.34 + visual.pressure * 0.34 + (visual.fractureSignal ? 0.1 : 0)
      ) * isolationWeight;
      visual.crest.alpha = Math.min(
        0.6,
        0.28 + visual.pressure * 0.28 + (visual.fractureSignal ? 0.08 : 0)
      ) * isolationWeight;
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(agent: CenterMapSceneAgent) {
    const container = new Container();
    const contour = new Graphics();
    const crest = new Graphics();
    container.addChild(crest);
    container.addChild(contour);

    const visual: PressureVisual = {
      container,
      contour,
      crest,
      x: agent.x,
      y: agent.y,
      targetX: agent.x,
      targetY: agent.y,
      pressure: agent.pressure,
      fractureSignal: agent.fractureSignal,
      selected: agent.selected,
      radius: 26 + agent.pressure * 92 + (agent.fractureSignal ? 24 : 0),
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(agent.x, agent.y);
    return visual;
  }

  private redrawVisual(visual: PressureVisual) {
    const fill = pressureColor(visual.pressure, visual.fractureSignal);
    const width = visual.radius * 2.2;
    const height = visual.radius * 1.08;

    visual.crest.clear();
    visual.crest.beginFill(fill, 0.24);
    drawContourPatch(visual.crest, width * 0.92, height * 0.8, visual.phase, 0.8);
    visual.crest.endFill();

    visual.contour.clear();
    visual.contour.beginFill(fill, 0.12);
    drawContourPatch(visual.contour, width, height, visual.phase, 0);
    visual.contour.endFill();
    visual.contour.lineStyle(1.8, fill, 0.58);
    drawContourPatch(visual.contour, width, height, visual.phase, 0);
    visual.contour.lineStyle(1.3, fill, 0.42);
    drawContourPatch(visual.contour, width * 0.72, height * 0.66, visual.phase, 1.7);
    visual.contour.lineStyle(1, fill, 0.28);
    drawContourPatch(visual.contour, width * 0.48, height * 0.44, visual.phase, 2.9);
  }
}

function drawContourPatch(graphics: Graphics, width: number, height: number, phase: number, offset: number) {
  const points = 18;
  for (let i = 0; i <= points; i += 1) {
    const angle = (Math.PI * 2 * i) / points;
    const ripple =
      1 +
      Math.sin(angle * 3 + phase * 8 + offset) * 0.08 +
      Math.cos(angle * 5 + offset) * 0.04;
    const x = Math.cos(angle) * width * 0.5 * ripple;
    const y = Math.sin(angle) * height * 0.5 * ripple;
    if (i === 0) graphics.moveTo(x, y);
    else graphics.lineTo(x, y);
  }
  graphics.closePath();
}

function pressureColor(pressure: number, fractureSignal: boolean) {
  if (fractureSignal || pressure >= 0.55) return 0xe11d48;
  if (pressure >= 0.35) return 0xea580c;
  if (pressure >= 0.18) return 0xca8a04;
  return 0x0284c7;
}
