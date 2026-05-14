"use client";

import { Container, Graphics } from "pixi.js";
import type { CenterMapSceneInteraction } from "@/components/center-map/scene/sceneTypes";

export class InteractionLayerPixi {
  readonly container = new Container();
  private interactions: CenterMapSceneInteraction[] = [];

  updateInteractions(interactions: CenterMapSceneInteraction[]) {
    this.interactions = interactions.slice(0, 128);
  }

  animate(renderTime: number) {
    this.container.removeChildren().forEach((child) => child.destroy());
    if (!this.interactions.length) return;

    const flow = (renderTime * 0.0018) % 1;
    for (const interaction of this.interactions) {
      const g = new Graphics();
      const color = colorForType(interaction.type);
      const pulse = interaction.fresh ? 0.5 + 0.5 * Math.sin(renderTime * 0.006 + interaction.intensity * 4.2) : 0;
      const alpha = Math.max(0.06, Math.min(0.62, 0.14 + interaction.intensity * 0.24 - interaction.age * 0.18 + pulse * 0.14));
      const width = 0.5 + interaction.intensity * 0.9 + pulse * 0.35;
      const midX = (interaction.x0 + interaction.x1) / 2;
      const midY = (interaction.y0 + interaction.y1) / 2;
      const dx = interaction.x1 - interaction.x0;
      const dy = interaction.y1 - interaction.y0;
      const len = Math.max(1, Math.hypot(dx, dy));
      const bend = interaction.type === "hostile" ? 12 : interaction.type === "negative" ? 8 : interaction.type === "positive" ? -7 : 5;
      const cx = midX + (-dy / len) * bend;
      const cy = midY + (dx / len) * bend;
      const t = (flow + interaction.intensity * 0.37 + interaction.age * 0.23) % 1;
      const qx = quadraticAt(interaction.x0, cx, interaction.x1, t);
      const qy = quadraticAt(interaction.y0, cy, interaction.y1, t);

      g.lineStyle(width, color, alpha);
      g.moveTo(interaction.x0, interaction.y0);
      g.quadraticCurveTo(cx, cy, interaction.x1, interaction.y1);
      g.beginFill(color, alpha * 0.72);
      g.drawCircle(qx, qy, 1.4 + interaction.intensity * 1.15);
      g.endFill();
      if (interaction.fresh) {
        g.lineStyle(0);
        g.beginFill(color, alpha * 0.14);
        g.drawCircle(qx, qy, 5 + pulse * 7 + interaction.intensity * 4);
        g.endFill();
      }
      g.beginFill(color, alpha * 0.36);
      g.drawCircle(interaction.x1, interaction.y1, 1.1 + interaction.intensity * 0.9);
      g.endFill();
      this.container.addChild(g);
    }
  }

  destroy() {
    this.container.destroy({ children: true });
  }
}

function colorForType(type: CenterMapSceneInteraction["type"]) {
  if (type === "positive") return 0x16a34a;
  if (type === "negative") return 0xf59e0b;
  if (type === "hostile") return 0xdc2626;
  return 0x64748b;
}

function quadraticAt(a: number, b: number, c: number, t: number) {
  const inv = 1 - t;
  return inv * inv * a + 2 * inv * t * b + t * t * c;
}
