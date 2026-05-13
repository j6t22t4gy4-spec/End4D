"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneZone,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type ClusterVisual = {
  id: string;
  container: Container;
  outer: Graphics;
  core: Graphics;
  centerX: number;
  centerY: number;
  width: number;
  height: number;
  avgPressure: number;
  avgDrift: number;
  count: number;
  fractureSignals: number;
  phase: number;
};

export class ClusterLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, ClusterVisual>();

  updateZones(zones: CenterMapSceneZone[]) {
    const activeZones = [...zones]
      .filter((zone) => zone.count >= 2)
      .sort((a, b) => (b.avgPressure + b.avgDrift * 0.7) - (a.avgPressure + a.avgDrift * 0.7))
      .slice(0, 6);

    const nextIds = new Set(activeZones.map((zone) => zone.id));

    for (const [id, visual] of this.visuals) {
      if (nextIds.has(id)) continue;
      this.container.removeChild(visual.container);
      visual.container.destroy({ children: true });
      this.visuals.delete(id);
    }

    for (const zone of activeZones) {
      const existing = this.visuals.get(zone.id);
      if (!existing) {
        const visual = this.createVisual(zone);
        this.visuals.set(zone.id, visual);
        this.container.addChild(visual.container);
        continue;
      }

      existing.centerX = zone.centerX;
      existing.centerY = zone.centerY;
      existing.width = zone.width;
      existing.height = zone.height;
      existing.avgPressure = zone.avgPressure;
      existing.avgDrift = zone.avgDrift;
      existing.count = zone.count;
      existing.fractureSignals = zone.fractureSignals;
      this.redrawVisual(existing);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    const pointerPushX = (pointerField.x - 0.5) * (pointerField.active ? 32 : 12);
    const pointerPushY = (pointerField.y - 0.5) * (pointerField.active ? 28 : 10);

    for (const visual of this.visuals.values()) {
      const wobbleX =
        Math.sin(renderTime * (0.28 + visual.phase * 0.08) + visual.phase * 8) *
        (8 + visual.avgPressure * 14);
      const wobbleY =
        Math.cos(renderTime * (0.24 + visual.phase * 0.06) + visual.phase * 7) *
        (6 + visual.avgDrift * 12);
      const driftWeight = 0.16 + visual.avgPressure * 0.26 + visual.avgDrift * 0.2;

      visual.container.position.set(
        visual.centerX + wobbleX + pointerPushX * driftWeight,
        visual.centerY + wobbleY + pointerPushY * driftWeight
      );

      const outerPulse =
        0.94 + ((Math.sin(renderTime * (0.9 + visual.phase * 0.22)) + 1) / 2) * 0.18;
      const corePulse =
        0.96 + ((Math.cos(renderTime * (1.15 + visual.phase * 0.28)) + 1) / 2) * 0.12;
      visual.outer.scale.set(outerPulse);
      visual.core.scale.set(corePulse);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(zone: CenterMapSceneZone) {
    const container = new Container();
    const outer = new Graphics();
    const core = new Graphics();
    container.addChild(outer);
    container.addChild(core);

    const visual: ClusterVisual = {
      id: zone.id,
      container,
      outer,
      core,
      centerX: zone.centerX,
      centerY: zone.centerY,
      width: zone.width,
      height: zone.height,
      avgPressure: zone.avgPressure,
      avgDrift: zone.avgDrift,
      count: zone.count,
      fractureSignals: zone.fractureSignals,
      phase: Math.random(),
    };
    this.redrawVisual(visual);
    container.position.set(zone.centerX, zone.centerY);
    return visual;
  }

  private redrawVisual(visual: ClusterVisual) {
    const fill = clusterColor(visual.avgPressure, visual.avgDrift, visual.fractureSignals > 0);
    const opacityBoost = visual.fractureSignals > 0 ? 0.06 : 0;
    const outerW = visual.width * (1.18 + visual.avgPressure * 0.34);
    const outerH = visual.height * (1.12 + visual.avgDrift * 0.42);
    const coreW = visual.width * (0.88 + visual.avgPressure * 0.24);
    const coreH = visual.height * (0.82 + visual.avgDrift * 0.3);

    visual.outer.clear();
    visual.outer.beginFill(fill, Math.min(0.22, 0.08 + visual.avgPressure * 0.12 + opacityBoost));
    visual.outer.drawEllipse(0, 0, outerW / 2, outerH / 2);
    visual.outer.endFill();

    visual.core.clear();
    visual.core.beginFill(fill, Math.min(0.28, 0.1 + visual.avgPressure * 0.14 + opacityBoost));
    visual.core.drawEllipse(0, 0, coreW / 2, coreH / 2);
    visual.core.endFill();
  }
}

function clusterColor(avgPressure: number, avgDrift: number, fractured: boolean) {
  if (fractured || avgPressure >= 0.45) return 0xfb7185;
  if (avgDrift >= 0.24) return 0x2dd4bf;
  if (avgPressure >= 0.22) return 0x818cf8;
  return 0x38bdf8;
}
