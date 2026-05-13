"use client";

import { Container, Graphics } from "pixi.js";

import type { TimelineAnnotation } from "@/lib/api";
import type { CenterMapSceneAgent } from "@/components/center-map/scene/sceneTypes";

type ShockVisual = {
  id: string;
  container: Container;
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

      const baseOuter = 0.74 + ((renderTime * (0.42 + visual.phase * 0.08)) % 1) * 0.62;
      const baseMiddle = 0.82 + ((renderTime * (0.55 + visual.phase * 0.09)) % 1) * 0.38;
      const corePulse = 0.92 + ((Math.sin(renderTime * (3.2 + visual.phase)) + 1) / 2) * 0.22;

      visual.outer.scale.set(baseOuter);
      visual.middle.scale.set(baseMiddle);
      visual.core.scale.set(corePulse);

      visual.outer.alpha = Math.max(0, 0.46 - (baseOuter - 0.74) * 0.64) * (0.72 + visual.emphasis * 0.3);
      visual.middle.alpha = Math.max(0, 0.42 - (baseMiddle - 0.82) * 0.54) * (0.68 + visual.emphasis * 0.26);
      visual.core.alpha = Math.min(0.38, 0.14 + visual.emphasis * 0.2);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(id: string, x: number, y: number, severity: string, emphasis: number) {
    const container = new Container();
    const outer = new Graphics();
    const middle = new Graphics();
    const core = new Graphics();
    container.addChild(outer);
    container.addChild(middle);
    container.addChild(core);

    const visual: ShockVisual = {
      id,
      container,
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
    const outerRadius = 28 + visual.emphasis * 30;
    const middleRadius = 18 + visual.emphasis * 18;
    const coreRadius = 8 + visual.emphasis * 10;

    visual.outer.clear();
    visual.outer.lineStyle(2, color, 0.5);
    visual.outer.drawCircle(0, 0, outerRadius);

    visual.middle.clear();
    visual.middle.lineStyle(2, color, 0.62);
    visual.middle.drawCircle(0, 0, middleRadius);

    visual.core.clear();
    visual.core.beginFill(color, 0.2);
    visual.core.drawCircle(0, 0, coreRadius);
    visual.core.endFill();
  }
}

function shockColor(severity: string) {
  if (severity === "high") return 0xf43f5e;
  if (severity === "medium") return 0xf97316;
  return 0x38bdf8;
}
