"use client";

import { Application, Container, Graphics } from "pixi.js";

import { AgentLayerPixi } from "@/components/center-map/pixi/layers/AgentLayerPixi";
import { ClusterLayerPixi } from "@/components/center-map/pixi/layers/ClusterLayerPixi";
import { PressureLayerPixi } from "@/components/center-map/pixi/layers/PressureLayerPixi";
import { ShockLayerPixi } from "@/components/center-map/pixi/layers/ShockLayerPixi";
import type { TimelineAnnotation } from "@/lib/api";
import type {
  CenterMapScene,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

export class PixiSceneController {
  private readonly root = new Container();
  private readonly fieldLayer = new Container();
  private readonly transitionOverlay = new Graphics();
  private readonly clusterLayer = new ClusterLayerPixi();
  private readonly pressureLayer = new PressureLayerPixi();
  private readonly shockLayer = new ShockLayerPixi();
  private readonly agentLayer = new AgentLayerPixi();

  private sceneAgents: CenterMapScene["agents"] = [];

  private pointerField: PointerField = { x: 0.5, y: 0.5, active: false };
  private transitionPhase = 0;
  private sceneWidth = 960;
  private sceneHeight = 640;

  constructor(private readonly app: Application) {
    this.root.addChild(this.fieldLayer);
    this.root.addChild(this.clusterLayer.container);
    this.root.addChild(this.pressureLayer.container);
    this.root.addChild(this.shockLayer.container);
    this.root.addChild(this.agentLayer.container);
    this.root.addChild(this.transitionOverlay);
    this.app.stage.addChild(this.root);
  }

  updateScene(scene: CenterMapScene) {
    this.sceneWidth = scene.width;
    this.sceneHeight = scene.height;
    this.sceneAgents = scene.agents;
    this.clusterLayer.updateZones(scene.zones);
    this.pressureLayer.updateAgents(scene.agents);
    this.agentLayer.updateAgents(scene.agents);
  }

  updateShocks(annotations: TimelineAnnotation[], currentT: number) {
    this.shockLayer.updateAnnotations(annotations, currentT, this.sceneAgents);
  }

  resize(width: number, height: number) {
    if (width <= 0 || height <= 0) return;
    this.root.scale.set(width / this.sceneWidth, height / this.sceneHeight);
    this.transitionOverlay.clear();
    this.transitionOverlay.beginFill(0xffffff, 0);
    this.transitionOverlay.drawRoundedRect(56, 56, this.sceneWidth - 112, this.sceneHeight - 112, 28);
    this.transitionOverlay.endFill();
  }

  setPointerField(pointerField: PointerField) {
    this.pointerField = pointerField;
  }

  setTransitionPhase(transitionPhase: number) {
    this.transitionPhase = transitionPhase;
  }

  setHoveredAgent(agentId: string | null) {
    this.agentLayer.setHoveredAgent(agentId);
  }

  hitTest(x: number, y: number) {
    return this.agentLayer.hitTest(x, y);
  }

  render(renderTime: number) {
    this.drawField(renderTime);
    this.clusterLayer.animate(renderTime, this.pointerField);
    this.pressureLayer.animate(renderTime, this.pointerField);
    this.shockLayer.animate(renderTime);
    this.agentLayer.animate(renderTime, this.pointerField);
    this.transitionOverlay.alpha = this.transitionPhase * 0.24;
  }

  destroy() {
    this.clusterLayer.destroy();
    this.pressureLayer.destroy();
    this.shockLayer.destroy();
    this.agentLayer.destroy();
    this.root.destroy({ children: true });
  }

  private drawField(renderTime: number) {
    this.fieldLayer.removeChildren().forEach((child) => child.destroy());

    const pointerX = 56 + this.pointerField.x * (this.sceneWidth - 112);
    const pointerY = 56 + this.pointerField.y * (this.sceneHeight - 112);

    for (let i = 0; i < 3; i += 1) {
      const ellipse = new Graphics();
      const driftX = Math.sin(renderTime * (0.22 + i * 0.07) + i) * (28 + i * 10);
      const driftY = Math.cos(renderTime * (0.18 + i * 0.05) + i * 1.3) * (22 + i * 8);
      const baseX = this.sceneWidth * (0.22 + i * 0.26);
      const baseY = this.sceneHeight * (0.28 + (i % 2) * 0.24);
      const color = i === 0 ? 0x38bdf8 : i === 1 ? 0x6366f1 : 0xfb7185;
      ellipse.beginFill(color, 0.06 + i * 0.01);
      ellipse.drawEllipse(baseX + driftX, baseY + driftY, 120 + i * 26, 82 + i * 20);
      ellipse.endFill();
      this.fieldLayer.addChild(ellipse);
    }

    const pointerAura = new Graphics();
    pointerAura.beginFill(0x7dd3fc, this.pointerField.active ? 0.08 : 0.04);
    pointerAura.drawEllipse(
      pointerX,
      pointerY,
      90 + Math.sin(renderTime * 1.4) * 8,
      64 + Math.cos(renderTime * 1.2) * 6
    );
    pointerAura.endFill();
    this.fieldLayer.addChild(pointerAura);
  }
}
