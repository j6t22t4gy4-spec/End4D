"use client";

import { Container, Graphics } from "pixi.js";

import type {
  CenterMapSceneAgent,
  CenterMapSceneInteraction,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

export class PressureLayerPixi {
  readonly container = new Container();

  private readonly field = new Graphics();
  private readonly flash = new Graphics();
  private fieldAgents: CenterMapSceneAgent[] = [];
  private sceneFlashes: Array<{ id: string; x: number; y: number; intensity: number; type: CenterMapSceneInteraction["type"]; pressureDelta: number; bornAt: number }> = [];

  constructor() {
    this.container.addChild(this.field);
    this.container.addChild(this.flash);
  }

  updateAgents(agents: CenterMapSceneAgent[]) {
    const pressureAgents = agents
      .filter((agent) => agent.pressure > 0.003 || agent.fractureSignal)
      .sort((a, b) => b.pressure - a.pressure)
      .slice(0, 220);
    this.fieldAgents = pressureAgents;
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
      const alpha = (1 - age) * (0.24 + item.intensity * 0.22);
      const radius = 20 + age * 52 + item.intensity * 26;
      this.flash.beginFill(fieldColor(Math.abs(item.pressureDelta) * 4 + item.intensity * 0.55), alpha * 0.22);
      this.flash.drawRect(item.x - radius * 0.7, item.y - radius * 0.42, radius * 1.4, radius * 0.84);
      this.flash.endFill();
      this.flash.lineStyle(1, colorForType(item.type), alpha);
      this.flash.drawRect(item.x - radius * 0.62, item.y - radius * 0.36, radius * 1.24, radius * 0.72);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
  }

  private redrawField() {
    this.field.clear();
    if (this.fieldAgents.length === 0) return;

    const cellSize = 24;
    const gap = 2;
    const sigma = 78;
    const sigma2 = sigma * sigma * 2;

    for (let y = 62; y <= 574; y += cellSize) {
      for (let x = 62; x <= 898; x += cellSize) {
        const intensity = this.fieldAgents.reduce((sum, agent) => {
          const dx = x - agent.x;
          const dy = y - agent.y;
          const pressure = agent.pressure + (agent.fractureSignal ? 0.16 : 0);
          return sum + pressure * Math.exp(-(dx * dx + dy * dy) / sigma2);
        }, 0);

        if (intensity < 0.06) continue;

        const normalized = Math.min(1, intensity);
        const fill = fieldColor(normalized);
        const alpha = Math.min(0.42, 0.08 + normalized * 0.24);
        this.field.beginFill(fill, alpha);
        this.field.drawRect(
          x - cellSize / 2 + gap,
          y - cellSize / 2 + gap,
          cellSize - gap * 2,
          cellSize - gap * 2
        );
        this.field.endFill();
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
