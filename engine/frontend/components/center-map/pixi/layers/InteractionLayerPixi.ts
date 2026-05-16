"use client";

import { Container, Graphics } from "pixi.js";
import type { CenterMapSceneInteraction } from "@/components/center-map/scene/sceneTypes";

export class InteractionLayerPixi {
  readonly container = new Container();
  private interactions: CenterMapSceneInteraction[] = [];

  updateInteractions(interactions: CenterMapSceneInteraction[]) {
    this.interactions = interactions
      .slice()
      .sort(
        (a, b) =>
          Number(b.swarmSession) - Number(a.swarmSession) ||
          Number(b.fresh) - Number(a.fresh) ||
          Number(b.sessionIndex ?? 0) - Number(a.sessionIndex ?? 0) ||
          b.intensity - a.intensity
      )
      .slice(0, interactions.some((item) => item.swarmSession) ? 900 : 420);
  }

  animate(renderTime: number) {
    this.container.removeChildren().forEach((child) => child.destroy());
    if (!this.interactions.length) return;

    const flow = (renderTime * 0.0018) % 1;
    const swarmBatch = new Graphics();
    let hasSwarmBatch = false;
    for (const interaction of this.interactions) {
      const isSwarm = Boolean(interaction.swarmSession);
      const g = isSwarm ? swarmBatch : new Graphics();
      const color = interaction.color ?? colorForType(interaction.type);
      const style = isSwarm ? swarmStyleForType(interaction.type) : styleForType(interaction.type);
      const sessionCount = Math.max(1, Number(interaction.sessionCount ?? 1));
      const sessionIndex = Math.max(1, Number(interaction.sessionIndex ?? 1));
      const sessionProgress = Math.max(0, Math.min(1, sessionIndex / sessionCount));
      const pulse = interaction.fresh
        ? 0.5 + 0.5 * Math.sin(renderTime * style.pulseSpeed + interaction.intensity * 4.2)
        : 0;
      const alpha = Math.max(
        interaction.fresh ? 0.13 : 0.026,
        Math.min(
          style.maxAlpha,
          style.baseAlpha +
            interaction.intensity * style.alphaGain -
            interaction.age * 0.16 +
            pulse * style.pulseAlpha
        )
      );
      const width = style.baseWidth + interaction.intensity * style.widthGain + pulse * style.pulseWidth;
      const midX = (interaction.x0 + interaction.x1) / 2;
      const midY = (interaction.y0 + interaction.y1) / 2;
      const dx = interaction.x1 - interaction.x0;
      const dy = interaction.y1 - interaction.y0;
      const len = Math.max(1, Math.hypot(dx, dy));
      const bend =
        style.bend +
        Math.sin(sessionIndex * 1.73 + interaction.intensity * 5.1) * 6 +
        Math.min(18, len * 0.035);
      const cx = midX + (-dy / len) * bend;
      const cy = midY + (dx / len) * bend;
      const t = (flow + sessionProgress * 0.64 + interaction.intensity * 0.31) % 1;
      if (isSwarm) hasSwarmBatch = true;

      if (interaction.fresh) {
        g.lineStyle(width + 1 + pulse * 0.7, color, alpha * 0.06);
        g.moveTo(interaction.x0, interaction.y0);
        g.quadraticCurveTo(cx, cy, interaction.x1, interaction.y1);
      }
      g.lineStyle(width, color, alpha);
      drawStreamCurve(g, interaction.x0, interaction.y0, cx, cy, interaction.x1, interaction.y1);
      drawFlowParticles(g, {
        x0: interaction.x0,
        y0: interaction.y0,
        cx,
        cy,
        x1: interaction.x1,
        y1: interaction.y1,
        color,
        alpha,
        style,
        t,
        intensity: interaction.intensity,
        fresh: Boolean(interaction.fresh),
        pulse,
        swarm: isSwarm,
      });
      if (interaction.fresh) {
        g.lineStyle(0);
        const head = pointOnQuadratic(interaction.x0, interaction.y0, cx, cy, interaction.x1, interaction.y1, t);
        g.beginFill(color, alpha * style.haloAlpha * 0.45);
        g.drawCircle(head.x, head.y, style.haloRadius + pulse * style.haloPulse + interaction.intensity * 2.2);
        g.endFill();
        g.lineStyle(0.55, color, alpha * 0.22);
        g.drawCircle(interaction.x0, interaction.y0, 2.2 + pulse * 0.45);
        g.drawCircle(interaction.x1, interaction.y1, 2.5 + pulse * 0.55);
      }
      g.beginFill(color, alpha * 0.24);
      g.drawCircle(interaction.x1, interaction.y1, 0.72 + interaction.intensity * 0.34);
      g.endFill();
      if (!isSwarm) this.container.addChild(g);
    }
    if (hasSwarmBatch) this.container.addChild(swarmBatch);
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
      baseAlpha: 0.24,
      alphaGain: 0.3,
      maxAlpha: 0.62,
      pulseAlpha: 0.16,
      baseWidth: 0.42,
      widthGain: 0.48,
      pulseWidth: 0.16,
      pulseSpeed: 0.01,
      bend: 16,
      dotRadius: 1.2,
      haloAlpha: 0.16,
      haloRadius: 5,
      haloPulse: 5,
    };
  }
  if (type === "negative") {
    return {
      baseAlpha: 0.18,
      alphaGain: 0.22,
      maxAlpha: 0.46,
      pulseAlpha: 0.1,
      baseWidth: 0.36,
      widthGain: 0.42,
      pulseWidth: 0.12,
      pulseSpeed: 0.007,
      bend: 10,
      dotRadius: 1.1,
      haloAlpha: 0.12,
      haloRadius: 4.8,
      haloPulse: 4.5,
    };
  }
  if (type === "positive") {
    return {
      baseAlpha: 0.16,
      alphaGain: 0.2,
      maxAlpha: 0.42,
      pulseAlpha: 0.09,
      baseWidth: 0.34,
      widthGain: 0.38,
      pulseWidth: 0.1,
      pulseSpeed: 0.0055,
      bend: -9,
      dotRadius: 1.1,
      haloAlpha: 0.13,
      haloRadius: 5.2,
      haloPulse: 4.5,
    };
  }
  return {
    baseAlpha: 0.08,
    alphaGain: 0.13,
    maxAlpha: 0.28,
    pulseAlpha: 0.05,
    baseWidth: 0.28,
    widthGain: 0.32,
    pulseWidth: 0.1,
    pulseSpeed: 0.004,
    bend: 5,
    dotRadius: 0.95,
    haloAlpha: 0.07,
    haloRadius: 3.8,
    haloPulse: 3.4,
  };
}

function swarmStyleForType(type: CenterMapSceneInteraction["type"]) {
  const base = styleForType(type);
  return {
    ...base,
    baseAlpha: base.baseAlpha * 0.72,
    alphaGain: base.alphaGain * 0.78,
    maxAlpha: Math.min(base.maxAlpha, 0.36),
    pulseAlpha: base.pulseAlpha * 0.72,
    baseWidth: Math.max(0.18, base.baseWidth * 0.7),
    widthGain: base.widthGain * 0.62,
    pulseWidth: base.pulseWidth * 0.55,
    bend: base.bend * 0.72,
    dotRadius: Math.max(0.7, base.dotRadius * 0.72),
    haloAlpha: base.haloAlpha * 0.7,
    haloRadius: base.haloRadius * 0.74,
    haloPulse: base.haloPulse * 0.65,
  };
}

function drawStreamCurve(g: Graphics, x0: number, y0: number, cx: number, cy: number, x1: number, y1: number) {
  drawQuadraticSegment(g, x0, y0, cx, cy, x1, y1, 0.04, 0.96);
}

function drawQuadraticSegment(
  g: Graphics,
  x0: number,
  y0: number,
  cx: number,
  cy: number,
  x1: number,
  y1: number,
  start: number,
  end: number
) {
  const steps = 8;
  for (let idx = 0; idx <= steps; idx += 1) {
    const t = start + ((end - start) * idx) / steps;
    const x = quadraticAt(x0, cx, x1, t);
    const y = quadraticAt(y0, cy, y1, t);
    if (idx === 0) {
      g.moveTo(x, y);
    } else {
      g.lineTo(x, y);
    }
  }
}

function quadraticAt(a: number, b: number, c: number, t: number) {
  const inv = 1 - t;
  return inv * inv * a + 2 * inv * t * b + t * t * c;
}

function pointOnQuadratic(x0: number, y0: number, cx: number, cy: number, x1: number, y1: number, t: number) {
  return {
    x: quadraticAt(x0, cx, x1, t),
    y: quadraticAt(y0, cy, y1, t),
  };
}

function drawFlowParticles(
  g: Graphics,
  args: {
    x0: number;
    y0: number;
    cx: number;
    cy: number;
    x1: number;
    y1: number;
    color: number;
    alpha: number;
    style: ReturnType<typeof styleForType>;
    t: number;
    intensity: number;
    fresh: boolean;
    pulse: number;
    swarm?: boolean;
  }
) {
  const count = args.swarm ? (args.fresh ? 3 : 1) : args.fresh ? 4 : 2;
  for (let idx = 0; idx < count; idx += 1) {
    const localT = (args.t + idx * (args.swarm ? 0.13 : 0.085)) % 1;
    const point = pointOnQuadratic(args.x0, args.y0, args.cx, args.cy, args.x1, args.y1, localT);
    const fade = 1 - idx / Math.max(1, count);
    const radius = args.style.dotRadius + args.intensity * 0.44 + (args.fresh ? args.pulse * 0.18 : 0);
    g.beginFill(args.color, args.alpha * ((args.swarm ? 0.48 : 0.66) * fade + 0.08));
    g.drawCircle(point.x, point.y, radius * (0.75 + fade * 0.45));
    g.endFill();
  }
}
