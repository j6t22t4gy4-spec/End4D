"use client";

import { Container, Graphics } from "pixi.js";

import type { CenterMapSceneZone } from "@/components/center-map/scene/sceneTypes";

type ZoneRegionVisual = {
  id: string;
  body: Graphics;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  avgPressure: number;
  avgDrift: number;
  fractureSignals: number;
  phase: number;
};

export class ZoneRegionLayerPixi {
  readonly container = new Container();

  private visuals = new Map<string, ZoneRegionVisual>();

  updateZones(zones: CenterMapSceneZone[]) {
    const nextIds = new Set(zones.map((zone) => zone.id));

    for (const [id, visual] of this.visuals) {
      if (nextIds.has(id)) continue;
      this.container.removeChild(visual.body);
      visual.body.destroy();
      this.visuals.delete(id);
    }

    zones.forEach((zone, index) => {
      const existing = this.visuals.get(zone.id);
      if (!existing) {
        const visual: ZoneRegionVisual = {
          id: zone.id,
          body: new Graphics(),
          x0: zone.x0,
          x1: zone.x1,
          y0: zone.y0,
          y1: zone.y1,
          avgPressure: zone.avgPressure,
          avgDrift: zone.avgDrift,
          fractureSignals: zone.fractureSignals,
          phase: seededPhase(zone.id),
        };
        this.visuals.set(zone.id, visual);
        this.container.addChild(visual.body);
        this.redrawVisual(visual, index);
        return;
      }

      existing.x0 = zone.x0;
      existing.x1 = zone.x1;
      existing.y0 = zone.y0;
      existing.y1 = zone.y1;
      existing.avgPressure = zone.avgPressure;
      existing.avgDrift = zone.avgDrift;
      existing.fractureSignals = zone.fractureSignals;
      this.redrawVisual(existing, index);
    });
  }

  destroy() {
    this.container.destroy({ children: true });
    this.visuals.clear();
  }

  private redrawVisual(visual: ZoneRegionVisual, index: number) {
    const color = zoneColor(index, visual.avgPressure, visual.avgDrift, visual.fractureSignals > 0);
    const width = Math.max(20, visual.x1 - visual.x0);
    const height = Math.max(20, visual.y1 - visual.y0);
    const alpha = Math.min(0.12, 0.035 + visual.avgPressure * 0.06 + (visual.fractureSignals > 0 ? 0.025 : 0));
    const cx = (visual.x0 + visual.x1) / 2;
    const cy = (visual.y0 + visual.y1) / 2;

    visual.body.clear();
    visual.body.lineStyle(1.1, color, 0.12 + visual.avgPressure * 0.12);
    visual.body.beginFill(color, alpha);
    drawRegionContour(visual.body, cx, cy, width, height, visual.phase, 0);
    visual.body.endFill();

    visual.body.lineStyle(1, color, 0.08);
    drawRegionContour(visual.body, cx, cy, width * 0.9, height * 0.86, visual.phase, 1.9);
  }
}

function drawRegionContour(
  graphics: Graphics,
  cx: number,
  cy: number,
  width: number,
  height: number,
  phase: number,
  offset: number
) {
  const points = 22;
  for (let i = 0; i <= points; i += 1) {
    const angle = (Math.PI * 2 * i) / points;
    const cornerFlatten = 0.86 + 0.14 * Math.max(Math.abs(Math.cos(angle)), Math.abs(Math.sin(angle)));
    const ripple =
      1 +
      Math.sin(angle * 2 + phase * 6 + offset) * 0.07 +
      Math.cos(angle * 5 + phase * 3 + offset) * 0.045;
    const x = cx + Math.cos(angle) * width * 0.5 * cornerFlatten * ripple;
    const y = cy + Math.sin(angle) * height * 0.5 * cornerFlatten * ripple;
    if (i === 0) graphics.moveTo(x, y);
    else graphics.lineTo(x, y);
  }
  graphics.closePath();
}

function seededPhase(id: string) {
  let hash = 0;
  for (let i = 0; i < id.length; i += 1) {
    hash = (hash * 31 + id.charCodeAt(i)) % 9973;
  }
  return hash / 9973;
}

function zoneColor(index: number, avgPressure: number, avgDrift: number, fractured: boolean) {
  if (fractured || avgPressure >= 0.45) return 0xfb7185;
  if (avgDrift >= 0.24) return 0x14b8a6;
  const palette = [0x0ea5e9, 0x2563eb, 0xf97316, 0x10b981, 0xec4899];
  return palette[index % palette.length]!;
}
