"use client";

import { Application, Container, Graphics } from "pixi.js";

import { AgentLayerPixi } from "@/components/center-map/pixi/layers/AgentLayerPixi";
import { ClusterLayerPixi } from "@/components/center-map/pixi/layers/ClusterLayerPixi";
import { PressureLayerPixi } from "@/components/center-map/pixi/layers/PressureLayerPixi";
import { InteractionLayerPixi } from "@/components/center-map/pixi/layers/InteractionLayerPixi";
import { ShockLayerPixi } from "@/components/center-map/pixi/layers/ShockLayerPixi";
import { ZoneRegionLayerPixi } from "@/components/center-map/pixi/layers/ZoneRegionLayerPixi";
import type { TimelineAnnotation } from "@/lib/api";
import type {
  CenterMapScene,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";
import type { PixiLayerVisibility } from "@/components/center-map/pixi/PixiStageHost";

export type PixiCameraState = {
  offsetX: number;
  offsetY: number;
  scaleX: number;
  scaleY: number;
  zoom: number;
};

export class PixiSceneController {
  private readonly root = new Container();
  private readonly fieldLayer = new Container();
  private readonly shockFlashOverlay = new Graphics();
  private readonly transitionOverlay = new Graphics();
  private readonly zoneRegionLayer = new ZoneRegionLayerPixi();
  private readonly clusterLayer = new ClusterLayerPixi();
  private readonly pressureLayer = new PressureLayerPixi();
  private readonly interactionLayer = new InteractionLayerPixi();
  private readonly shockLayer = new ShockLayerPixi();
  private readonly agentLayer = new AgentLayerPixi();

  private sceneAgents: CenterMapScene["agents"] = [];

  private pointerField: PointerField = { x: 0.5, y: 0.5, active: false };
  private transitionPhase = 0;
  private sceneWidth = 960;
  private sceneHeight = 640;
  private viewportWidth = 960;
  private viewportHeight = 640;
  private zoom = 1;
  private offsetX = 0;
  private offsetY = 0;

  constructor(
    private readonly app: Application,
    private readonly onCameraStateChange?: (camera: PixiCameraState) => void
  ) {
    this.root.addChild(this.fieldLayer);
    this.root.addChild(this.zoneRegionLayer.container);
    this.root.addChild(this.clusterLayer.container);
    this.root.addChild(this.pressureLayer.container);
    this.root.addChild(this.interactionLayer.container);
    this.root.addChild(this.shockLayer.container);
    this.root.addChild(this.shockFlashOverlay);
    this.root.addChild(this.agentLayer.container);
    this.root.addChild(this.transitionOverlay);
    this.app.stage.addChild(this.root);
  }

  updateScene(scene: CenterMapScene) {
    this.sceneWidth = scene.width;
    this.sceneHeight = scene.height;
    this.sceneAgents = scene.agents;
    this.zoneRegionLayer.updateZones(scene.zones);
    this.clusterLayer.updateZones(scene.zones);
    this.pressureLayer.updateAgents(scene.agents);
    this.interactionLayer.updateInteractions(scene.interactions);
    this.pressureLayer.updateInteractions(scene.interactions, performance.now());
    this.agentLayer.updateAgents(scene.agents);
  }

  updateShocks(annotations: TimelineAnnotation[], currentT: number) {
    this.shockLayer.updateAnnotations(annotations, currentT, this.sceneAgents);
  }

  resize(width: number, height: number) {
    if (width <= 0 || height <= 0) return;
    const centerWorldX = this.screenToWorldX(this.viewportWidth / 2);
    const centerWorldY = this.screenToWorldY(this.viewportHeight / 2);
    this.viewportWidth = width;
    this.viewportHeight = height;
    const scale = this.viewportScale();
    this.offsetX = width / 2 - centerWorldX * scale;
    this.offsetY = height / 2 - centerWorldY * scale;
    this.applyViewportTransform();
    this.shockFlashOverlay.clear();
    this.shockFlashOverlay.beginFill(0xf8fafc, 0);
    this.shockFlashOverlay.drawRoundedRect(56, 56, this.sceneWidth - 112, this.sceneHeight - 112, 28);
    this.shockFlashOverlay.endFill();
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

  setLayerVisibility(layers: PixiLayerVisibility) {
    this.zoneRegionLayer.container.visible = layers.zones;
    this.agentLayer.container.visible = layers.agents;
    this.clusterLayer.container.visible = layers.clusters;
    this.pressureLayer.container.visible = layers.pressure;
    this.interactionLayer.container.visible = layers.agents;
    this.shockLayer.container.visible = layers.shocks;
    this.shockFlashOverlay.visible = layers.shocks;
  }

  setHoveredAgent(agentId: string | null) {
    this.agentLayer.setHoveredAgent(agentId);
  }

  hitTest(x: number, y: number) {
    return this.agentLayer.hitTest(x, y);
  }

  hitTestScreen(screenX: number, screenY: number) {
    return this.agentLayer.hitTest(
      this.screenToWorldX(screenX),
      this.screenToWorldY(screenY)
    );
  }

  panByScreen(dx: number, dy: number) {
    this.offsetX += dx;
    this.offsetY += dy;
    this.applyViewportTransform();
  }

  zoomAtScreen(factor: number, screenX: number, screenY: number) {
    const worldX = this.screenToWorldX(screenX);
    const worldY = this.screenToWorldY(screenY);
    this.zoom = Math.max(0.75, Math.min(3.2, this.zoom * factor));
    const scale = this.viewportScale();
    this.offsetX = screenX - worldX * scale;
    this.offsetY = screenY - worldY * scale;
    this.applyViewportTransform();
  }

  resetCamera() {
    this.zoom = 1;
    const scale = this.viewportScale();
    this.offsetX = (this.viewportWidth - this.sceneWidth * scale) / 2;
    this.offsetY = (this.viewportHeight - this.sceneHeight * scale) / 2;
    this.applyViewportTransform();
  }

  getCameraState(): PixiCameraState {
    return {
      offsetX: this.offsetX,
      offsetY: this.offsetY,
      scaleX: this.viewportScale(),
      scaleY: this.viewportScale(),
      zoom: this.zoom,
    };
  }

  render(renderTime: number) {
    this.drawField(renderTime);
    this.clusterLayer.animate(renderTime, this.pointerField);
    this.pressureLayer.animate(renderTime, this.pointerField);
    this.interactionLayer.animate(renderTime);
    this.shockLayer.animate(renderTime);
    this.shockFlashOverlay.alpha = 0.03 + Math.min(0.16, this.shockLayer.getFlashLevel(renderTime));
    this.agentLayer.animate(renderTime, this.pointerField, this.transitionPhase);
    this.transitionOverlay.alpha = this.transitionPhase * 0.24;
  }

  destroy() {
    this.zoneRegionLayer.destroy();
    this.clusterLayer.destroy();
    this.pressureLayer.destroy();
    this.interactionLayer.destroy();
    this.shockLayer.destroy();
    this.agentLayer.destroy();
    this.root.destroy({ children: true });
  }

  private applyViewportTransform() {
    this.root.position.set(this.offsetX, this.offsetY);
    const scale = this.viewportScale();
    this.root.scale.set(scale, scale);
    this.onCameraStateChange?.(this.getCameraState());
  }

  private viewportScale() {
    return Math.min(
      this.viewportWidth / this.sceneWidth,
      this.viewportHeight / this.sceneHeight
    ) * this.zoom;
  }

  private screenToWorldX(screenX: number) {
    return (screenX - this.offsetX) / this.viewportScale();
  }

  private screenToWorldY(screenY: number) {
    return (screenY - this.offsetY) / this.viewportScale();
  }

  private drawField(renderTime: number) {
    this.fieldLayer.removeChildren().forEach((child) => child.destroy());

    void renderTime;

    const grid = new Graphics();
    grid.lineStyle(1, 0x94a3b8, 0.08);
    for (let x = 56; x <= this.sceneWidth - 56; x += 72) {
      grid.moveTo(x, 56);
      grid.lineTo(x, this.sceneHeight - 56);
    }
    for (let y = 56; y <= this.sceneHeight - 56; y += 72) {
      grid.moveTo(56, y);
      grid.lineTo(this.sceneWidth - 56, y);
    }
    this.fieldLayer.addChild(grid);

    const pointerX = 56 + this.pointerField.x * (this.sceneWidth - 112);
    const pointerY = 56 + this.pointerField.y * (this.sceneHeight - 112);
    const crosshair = new Graphics();
    crosshair.lineStyle(1, 0x0ea5e9, this.pointerField.active ? 0.16 : 0.06);
    crosshair.moveTo(pointerX - 18, pointerY);
    crosshair.lineTo(pointerX + 18, pointerY);
    crosshair.moveTo(pointerX, pointerY - 18);
    crosshair.lineTo(pointerX, pointerY + 18);
    this.fieldLayer.addChild(crosshair);
  }
}
