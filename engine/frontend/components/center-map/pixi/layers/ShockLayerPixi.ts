"use client";

import { Container, Graphics } from "pixi.js";

import type { TimelineAnnotation } from "@/lib/api";
import type { CenterMapSceneAgent } from "@/components/center-map/scene/sceneTypes";

type ShockVisual = {
  id: string;
  container: Container;
  glow: Graphics;
  outer: Graphics;
  middle: Graphics;
  core: Graphics;
  x: number;
  y: number;
  severity: string;
  emphasis: number;
  phase: number;
};

export class ShockLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, ShockVisual>();

  getFlashLevel(renderTime: number) {
    let maxFlash = 0;
    for (const visual of this.visuals.values()) {
      const pulse = ((Math.sin(renderTime * (3.2 + visual.phase * 0.7) + visual.phase * 9) + 1) / 2);
      maxFlash = Math.max(maxFlash, (0.03 + visual.emphasis * 0.08) * pulse);
    }
    return maxFlash;
  }

  updateAnnotations(
    annotations: TimelineAnnotation[],
    currentT: number,
    agents: CenterMapSceneAgent[]
  ) {
    const activeAnnotations = annotations
      .filter((item) => Math.abs(Number(item.t ?? 0) - currentT) <= 6)
      .slice(0, 4);

    const anchorAgents = [...agents]
      .sort((a, b) => {
        const fractureDelta = Number(b.fractureSignal) - Number(a.fractureSignal);
        if (fractureDelta !== 0) return fractureDelta;
        return b.pressure - a.pressure;
      })
      .slice(0, Math.max(1, activeAnnotations.length));

    const nextIds = new Set<string>();

    activeAnnotations.forEach((annotation, index) => {
      const anchor = anchorAgents[index % anchorAgents.length];
      if (!anchor) return;

      const id = `${annotation.t}-${annotation.label}-${index}`;
      nextIds.add(id);
      const emphasis = Math.max(0.18, anchor.pressure + (anchor.fractureSignal ? 0.18 : 0));
      const existing = this.visuals.get(id);

      if (!existing) {
        const visual = this.createVisual(id, anchor.x, anchor.y, String(annotation.severity ?? "medium"), emphasis);
        this.visuals.set(id, visual);
        this.container.addChild(visual.container);
        return;
      }

      existing.x = anchor.x;
      existing.y = anchor.y;
      existing.severity = String(annotation.severity ?? "medium");
      existing.emphasis = emphasis;
      this.redrawVisual(existing);
    });

    for (const [id, visual] of this.visuals) {
      if (nextIds.has(id)) continue;
      this.container.removeChild(visual.container);
      visual.container.destroy({ children: true });
      this.visuals.delete(id);
    }
  }

  animate(renderTime: number) {
    for (const visual of this.visuals.values()) {
      visual.container.position.set(visual.x, visual.y);

      const baseGlow = 0.96 + ((Math.sin(renderTime * (1.3 + visual.phase * 0.18)) + 1) / 2) * 0.28;
      const baseOuter = 0.74 + ((renderTime * (0.36 + visual.phase * 0.08)) % 1) * 0.56;
      const baseMiddle = 0.82 + ((renderTime * (0.44 + visual.phase * 0.09)) % 1) * 0.34;
      const corePulse = 0.99 + ((Math.sin(renderTime * (2.8 + visual.phase)) + 1) / 2) * 0.14;

      visual.glow.scale.set(baseGlow);
      visual.outer.scale.set(baseOuter);
      visual.middle.scale.set(baseMiddle);
      visual.core.scale.set(corePulse);

      visual.glow.alpha = Math.min(0.18, 0.06 + visual.emphasis * 0.1);
      visual.outer.alpha = Math.max(0, 0.34 - (baseOuter - 0.74) * 0.42) * (0.72 + visual.emphasis * 0.18);
      visual.middle.alpha = Math.max(0, 0.28 - (baseMiddle - 0.82) * 0.38) * (0.68 + visual.emphasis * 0.14);
      visual.core.alpha = Math.min(0.24, 0.1 + visual.emphasis * 0.12);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(id: string, x: number, y: number, severity: string, emphasis: number) {
    const container = new Container();
    const glow = new Graphics();
    const outer = new Graphics();
    const middle = new Graphics();
    const core = new Graphics();
    container.addChild(glow);
    container.addChild(outer);
    container.addChild(middle);
    container.addChild(core);

    const visual: ShockVisual = {
      id,
      container,
      glow,
      outer,
      middle,
      core,
      x,
      y,
      severity,
      emphasis,
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(x, y);
    return visual;
  }

  private redrawVisual(visual: ShockVisual) {
    const color = shockColor(visual.severity);
    const glowRadius = 16 + visual.emphasis * 24;
    const outerRadius = 28 + visual.emphasis * 28;
    const middleRadius = 18 + visual.emphasis * 16;
    const coreRadius = 8 + visual.emphasis * 8;

    visual.glow.clear();
    visual.glow.beginFill(color, 0.1);
    visual.glow.drawCircle(0, 0, glowRadius);
    visual.glow.endFill();

    visual.outer.clear();
    visual.outer.lineStyle(2, color, 0.38);
    visual.outer.drawCircle(0, 0, outerRadius);

    visual.middle.clear();
    visual.middle.lineStyle(1.5, color, 0.42);
    visual.middle.drawCircle(0, 0, middleRadius);

    visual.core.clear();
    visual.core.beginFill(color, 0.16);
    visual.core.drawCircle(0, 0, coreRadius);
    visual.core.endFill();
  }
}

function shockColor(severity: string) {
  if (severity === "high") return 0xf43f5e;
  if (severity === "medium") return 0xf97316;
  return 0x38bdf8;
}
