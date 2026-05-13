"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneZone,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type ClusterVisual = {
  id: string;
  container: Container;
  mass: Graphics;
  contour: Graphics;
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
    void renderTime;

    const pointerPushX = pointerField.active ? (pointerField.x - 0.5) * 4 : 0;
    const pointerPushY = pointerField.active ? (pointerField.y - 0.5) * 3.5 : 0;

    for (const visual of this.visuals.values()) {
      const driftWeight = 0.03 + visual.avgPressure * 0.04 + visual.avgDrift * 0.03;

      visual.container.position.set(
        visual.centerX + pointerPushX * driftWeight,
        visual.centerY + pointerPushY * driftWeight
      );

      visual.contour.scale.set(1);
      visual.mass.scale.set(1);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private createVisual(zone: CenterMapSceneZone) {
    const container = new Container();
    const mass = new Graphics();
    const contour = new Graphics();
    container.addChild(mass);
    container.addChild(contour);

    const visual: ClusterVisual = {
      id: zone.id,
      container,
      mass,
      contour,
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
    const outerW = visual.width * (1.1 + visual.avgPressure * 0.22);
    const outerH = visual.height * (1.04 + visual.avgDrift * 0.24);
    const coreW = visual.width * (0.84 + visual.avgPressure * 0.16);
    const coreH = visual.height * (0.78 + visual.avgDrift * 0.16);

    visual.mass.clear();
    visual.mass.beginFill(fill, Math.min(0.26, 0.11 + visual.avgPressure * 0.12 + opacityBoost));
    drawClusterPatch(visual.mass, coreW, coreH, visual.phase, 1.1);
    visual.mass.endFill();

    visual.contour.clear();
    visual.contour.beginFill(fill, Math.min(0.12, 0.04 + visual.avgPressure * 0.06 + opacityBoost));
    drawClusterPatch(visual.contour, outerW, outerH, visual.phase, 0);
    visual.contour.endFill();
    visual.contour.lineStyle(1.4, fill, 0.34 + visual.avgPressure * 0.18);
    drawClusterPatch(visual.contour, outerW, outerH, visual.phase, 0);
    visual.contour.lineStyle(1, fill, 0.22 + visual.avgPressure * 0.1);
    drawClusterPatch(visual.contour, outerW * 0.72, outerH * 0.68, visual.phase, 2.2);
  }
}

function drawClusterPatch(graphics: Graphics, width: number, height: number, phase: number, offset: number) {
  const points = 20;
  for (let i = 0; i <= points; i += 1) {
    const angle = (Math.PI * 2 * i) / points;
    const ripple =
      1 +
      Math.sin(angle * 2 + phase * 7 + offset) * 0.09 +
      Math.cos(angle * 4 + phase * 5 + offset) * 0.055;
    const x = Math.cos(angle) * width * 0.5 * ripple;
    const y = Math.sin(angle) * height * 0.5 * ripple;
    if (i === 0) graphics.moveTo(x, y);
    else graphics.lineTo(x, y);
  }
  graphics.closePath();
}

function clusterColor(avgPressure: number, avgDrift: number, fractured: boolean) {
  if (fractured || avgPressure >= 0.45) return 0xe11d48;
  if (avgDrift >= 0.24) return 0x0f766e;
  if (avgPressure >= 0.22) return 0x4f46e5;
  return 0x0369a1;
}
