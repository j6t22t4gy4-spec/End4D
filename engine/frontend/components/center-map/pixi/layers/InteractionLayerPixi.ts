"use client";

import { Container, Graphics } from "pixi.js";
import type { CenterMapSceneInteraction } from "@/components/center-map/scene/sceneTypes";

export class InteractionLayerPixi {
  readonly container = new Container();
  private interactions: CenterMapSceneInteraction[] = [];

  updateInteractions(interactions: CenterMapSceneInteraction[]) {
    this.interactions = interactions
      .slice()
      .sort((a, b) => Number(b.fresh) - Number(a.fresh) || b.intensity - a.intensity)
      .slice(0, 96);
  }

  animate(renderTime: number) {
    this.container.removeChildren().forEach((child) => child.destroy());
    if (!this.interactions.length) return;

    const flow = (renderTime * 0.0024) % 1;
    for (const interaction of this.interactions) {
      const g = new Graphics();
      const color = colorForType(interaction.type);
      const style = styleForType(interaction.type);
      const pulse = interaction.fresh ? 0.5 + 0.5 * Math.sin(renderTime * style.pulseSpeed + interaction.intensity * 4.2) : 0;
      const alpha = Math.max(
        interaction.fresh ? 0.08 : 0.025,
        Math.min(
          style.maxAlpha,
          style.baseAlpha + interaction.intensity * style.alphaGain - interaction.age * 0.16 + pulse * style.pulseAlpha
        )
      );
      const width = style.baseWidth + interaction.intensity * style.widthGain + pulse * style.pulseWidth;
      const midX = (interaction.x0 + interaction.x1) / 2;
      const midY = (interaction.y0 + interaction.y1) / 2;
      const dx = interaction.x1 - interaction.x0;
      const dy = interaction.y1 - interaction.y0;
      const len = Math.max(1, Math.hypot(dx, dy));
      const bend = style.bend;
      const cx = midX + (-dy / len) * bend;
      const cy = midY + (dx / len) * bend;
      const t = (flow + interaction.intensity * 0.37 + interaction.age * 0.23) % 1;
      const qx = quadraticAt(interaction.x0, cx, interaction.x1, t);
      const qy = quadraticAt(interaction.y0, cy, interaction.y1, t);

      if (interaction.fresh) {
        g.lineStyle(width + 2.2 + pulse * 2.8, color, alpha * 0.1);
        g.moveTo(interaction.x0, interaction.y0);
        g.quadraticCurveTo(cx, cy, interaction.x1, interaction.y1);
      }
      g.lineStyle(width, color, alpha);
      g.moveTo(interaction.x0, interaction.y0);
      g.quadraticCurveTo(cx, cy, interaction.x1, interaction.y1);
      if (interaction.type === "hostile" && interaction.fresh) {
        drawSpark(g, qx, qy, color, alpha, pulse);
      }
      g.beginFill(color, alpha * 0.64);
      g.drawCircle(qx, qy, style.dotRadius + interaction.intensity * 0.85 + pulse * 0.5);
      g.endFill();
      if (interaction.fresh) {
        g.lineStyle(0);
        g.beginFill(color, alpha * style.haloAlpha);
        g.drawCircle(qx, qy, style.haloRadius + pulse * style.haloPulse + interaction.intensity * 5);
        g.endFill();
        g.lineStyle(0.75, color, alpha * 0.38);
        g.drawCircle(interaction.x0, interaction.y0, 3.8 + pulse * 1.4);
        g.drawCircle(interaction.x1, interaction.y1, 4.6 + pulse * 1.8);
      }
      g.beginFill(color, alpha * 0.28);
      g.drawCircle(interaction.x1, interaction.y1, 0.9 + interaction.intensity * 0.65);
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

function styleForType(type: CenterMapSceneInteraction["type"]) {
  if (type === "hostile") {
    return {
      baseAlpha: 0.2,
      alphaGain: 0.32,
      maxAlpha: 0.74,
      pulseAlpha: 0.2,
      baseWidth: 0.48,
      widthGain: 0.9,
      pulseWidth: 0.34,
      pulseSpeed: 0.012,
      bend: 14,
      dotRadius: 1.35,
      haloAlpha: 0.2,
      haloRadius: 7,
      haloPulse: 9,
    };
  }
  if (type === "negative") {
    return {
      baseAlpha: 0.16,
      alphaGain: 0.25,
      maxAlpha: 0.58,
      pulseAlpha: 0.14,
      baseWidth: 0.44,
      widthGain: 0.74,
      pulseWidth: 0.28,
      pulseSpeed: 0.008,
      bend: 9,
      dotRadius: 1.25,
      haloAlpha: 0.15,
      haloRadius: 6,
      haloPulse: 7,
    };
  }
  if (type === "positive") {
    return {
      baseAlpha: 0.14,
      alphaGain: 0.22,
      maxAlpha: 0.54,
      pulseAlpha: 0.12,
      baseWidth: 0.42,
      widthGain: 0.66,
      pulseWidth: 0.24,
      pulseSpeed: 0.006,
      bend: -8,
      dotRadius: 1.35,
      haloAlpha: 0.18,
      haloRadius: 8,
      haloPulse: 8,
    };
  }
  return {
    baseAlpha: 0.06,
    alphaGain: 0.16,
    maxAlpha: 0.34,
    pulseAlpha: 0.08,
    baseWidth: 0.36,
    widthGain: 0.52,
    pulseWidth: 0.16,
    pulseSpeed: 0.005,
    bend: 5,
    dotRadius: 1.05,
    haloAlpha: 0.1,
    haloRadius: 5,
    haloPulse: 5,
  };
}

function drawSpark(g: Graphics, x: number, y: number, color: number, alpha: number, pulse: number) {
  const size = 5 + pulse * 5;
  g.lineStyle(0.9, color, alpha * 0.56);
  g.moveTo(x - size, y);
  g.lineTo(x + size, y);
  g.moveTo(x, y - size);
  g.lineTo(x, y + size);
}

function quadraticAt(a: number, b: number, c: number, t: number) {
  const inv = 1 - t;
  return inv * inv * a + 2 * inv * t * b + t * t * c;
}
