"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneInteraction,
  CenterMapSceneZone,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

export class PressureLayerPixi {
  readonly container = new Container();

  private readonly field = new Graphics();
  private readonly flash = new Graphics();
  private zones: CenterMapSceneZone[] = [];
  private sceneFlashes: Array<{ id: string; x: number; y: number; intensity: number; type: CenterMapSceneInteraction["type"]; pressureDelta: number; bornAt: number }> = [];

  constructor() {
    this.container.addChild(this.field);
    this.container.addChild(this.flash);
  }

  updateZones(zones: CenterMapSceneZone[]) {
    this.zones = zones
      .filter((zone) => zone.avgPressure > 0.01 || zone.fractureSignals > 0)
      .sort((a, b) => b.avgPressure - a.avgPressure)
      .slice(0, 80);
    this.redrawField();
  }

  updateInteractions(interactions: CenterMapSceneInteraction[], renderTime: number) {
    const existing = new Set(this.sceneFlashes.map((flash) => flash.id));
    const additions = interactions
      .filter((interaction) => interaction.fresh && Math.abs(interaction.pressureDelta ?? 0) > 0.01 && !existing.has(interaction.id))
      .slice(0, 18)
      .map((interaction) => ({
        id: interaction.id,
        x: (interaction.x0 + interaction.x1) / 2,
        y: (interaction.y0 + interaction.y1) / 2,
        intensity: Math.max(0.25, Math.min(1, interaction.intensity + Math.abs(interaction.pressureDelta ?? 0) * 2)),
        type: interaction.type,
        pressureDelta: Number(interaction.pressureDelta ?? 0),
        bornAt: renderTime,
      }));
    if (additions.length) {
      this.sceneFlashes = [...additions, ...this.sceneFlashes].slice(0, 32);
    }
  }

  animate(renderTime: number, pointerField: PointerField) {
    void pointerField;
    this.flash.clear();
    if (!this.sceneFlashes.length) return;
    this.sceneFlashes = this.sceneFlashes.filter((item) => renderTime - item.bornAt < 1300);
    for (const item of this.sceneFlashes) {
      const age = Math.max(0, Math.min(1, (renderTime - item.bornAt) / 1300));
      const alpha = (1 - age) * (0.18 + item.intensity * 0.18);
      const radius = 18 + age * 44 + item.intensity * 20;
      this.flash.beginFill(fieldColor(Math.abs(item.pressureDelta) * 4 + item.intensity * 0.55), alpha * 0.12);
      this.flash.drawRoundedRect(item.x - radius * 0.72, item.y - radius * 0.42, radius * 1.44, radius * 0.84, 16);
      this.flash.endFill();
      this.flash.lineStyle(1, colorForType(item.type), alpha * 0.78);
      this.flash.drawEllipse(item.x, item.y, radius * 0.66, radius * 0.38);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
  }

  private redrawField() {
    this.field.clear();
    if (this.zones.length === 0) return;

    const cellSize = 18;
    const gap = 1.5;

    for (let y = 62; y <= 574; y += cellSize) {
      for (let x = 62; x <= 898; x += cellSize) {
        const intensity = this.zones.reduce((sum, zone) => {
          const radiusX = Math.max(42, zone.width * 0.56);
          const radiusY = Math.max(34, zone.height * 0.6);
          const dx = Math.abs(x - zone.centerX) / radiusX;
          const dy = Math.abs(y - zone.centerY) / radiusY;
          const falloff = Math.max(0, 1 - Math.sqrt(dx * dx + dy * dy));
          const pressure = zone.avgPressure + Math.min(0.24, zone.fractureSignals * 0.045);
          return sum + pressure * falloff;
        }, 0);

        if (intensity < 0.055) continue;

        const normalized = Math.min(1, intensity);
        const fill = fieldColor(normalized);
        const alpha = Math.min(0.24, 0.035 + normalized * 0.16);
        this.field.beginFill(fill, alpha);
        this.field.drawRoundedRect(
          x - cellSize / 2 + gap,
          y - cellSize / 2 + gap,
          cellSize - gap * 2,
          cellSize - gap * 2,
          4
        );
        this.field.endFill();
        if (normalized >= 0.36) {
          this.field.lineStyle(0.6, fill, Math.min(0.22, normalized * 0.18));
          this.field.drawRoundedRect(
            x - cellSize / 2 + gap,
            y - cellSize / 2 + gap,
            cellSize - gap * 2,
            cellSize - gap * 2,
            4
          );
        }
      }
    }
  }
}

function fieldColor(intensity: number) {
  if (intensity >= 0.58) return 0xe11d48;
  if (intensity >= 0.36) return 0xf97316;
  if (intensity >= 0.2) return 0xf59e0b;
  return 0x38bdf8;
}

function colorForType(type: CenterMapSceneInteraction["type"]) {
  if (type === "positive") return 0x16a34a;
  if (type === "negative") return 0xf59e0b;
  if (type === "hostile") return 0xdc2626;
  return 0x0284c7;
}
