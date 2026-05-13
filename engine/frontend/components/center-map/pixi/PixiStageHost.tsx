"use client";

import { useEffect, useMemo, useRef } from "react";
import { Application } from "pixi.js";

import {
  PixiSceneController,
  type PixiCameraState,
} from "@/components/center-map/pixi/PixiSceneController";
import type { TimelineAnnotation } from "@/lib/api";
import type {
  CenterMapScene,
  PointerField,
} from "@/components/center-map/scene/sceneTypes";

type PixiStageHostProps = {
  scene: CenterMapScene;
  annotations: TimelineAnnotation[];
  currentT: number;
  renderTime: number;
  transitionPhase: number;
  pointerField: PointerField;
  layerVisibility?: PixiLayerVisibility | undefined;
  onInteractionApiReady?: ((api: PixiInteractionApi | null) => void) | undefined;
  onCameraStateChange?: ((camera: PixiCameraState) => void) | undefined;
};

export type PixiLayerVisibility = {
  zones: boolean;
  agents: boolean;
  clusters: boolean;
  pressure: boolean;
  shocks: boolean;
};

export type PixiInteractionApi = {
  hitTestAtScreen: (x: number, y: number) => string | null;
  hitTestAtNormalized: (x: number, y: number) => string | null;
  setHoveredAgent: (agentId: string | null) => void;
  panByScreen: (dx: number, dy: number) => void;
  zoomAtScreen: (factor: number, x: number, y: number) => void;
  zoomAtNormalized: (factor: number, x: number, y: number) => void;
  resetCamera: () => void;
};

export function PixiStageHost({
  scene,
  annotations,
  currentT,
  renderTime,
  transitionPhase,
  pointerField,
  layerVisibility,
  onInteractionApiReady,
  onCameraStateChange,
}: PixiStageHostProps) {
  const hostRef = useRef<HTMLDivElement | null>(null);
  const appRef = useRef<Application | null>(null);
  const controllerRef = useRef<PixiSceneController | null>(null);
  const stableScene = useMemo(() => scene, [scene]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;

    let disposed = false;
    let resizeObserver: ResizeObserver | null = null;

    const boot = async () => {
      const app = new Application();
      await app.init({
        backgroundAlpha: 0,
        antialias: true,
        autoDensity: true,
        resolution: window.devicePixelRatio || 1,
      });
      if (disposed) {
        app.destroy(true, { children: true });
        return;
      }

      app.canvas.classList.add("simulation-map__pixi-canvas");
      host.appendChild(app.canvas);

      const controller = new PixiSceneController(app, onCameraStateChange);
      appRef.current = app;
      controllerRef.current = controller;

      controller.updateScene(stableScene);
      controller.updateShocks(annotations, currentT);
      controller.setPointerField(pointerField);
      controller.setTransitionPhase(transitionPhase);
      if (layerVisibility) controller.setLayerVisibility(layerVisibility);
      onInteractionApiReady?.({
        hitTestAtScreen: (x, y) => controller.hitTestScreen(x, y),
        hitTestAtNormalized: (x, y) =>
          controller.hitTestScreen(host.clientWidth * x, host.clientHeight * y),
        setHoveredAgent: (agentId) => controller.setHoveredAgent(agentId),
        panByScreen: (dx, dy) => controller.panByScreen(dx, dy),
        zoomAtScreen: (factor, x, y) => controller.zoomAtScreen(factor, x, y),
        zoomAtNormalized: (factor, x, y) =>
          controller.zoomAtScreen(
            factor,
            host.clientWidth * x,
            host.clientHeight * y
          ),
        resetCamera: () => controller.resetCamera(),
      });

      resizeObserver = new ResizeObserver((entries) => {
        const entry = entries[0];
        if (!entry) return;
        const { width, height } = entry.contentRect;
        void app.renderer.resize(width, height);
        controller.resize(width, height);
      });
      resizeObserver.observe(host);

      const rect = host.getBoundingClientRect();
      if (rect.width > 0 && rect.height > 0) {
        void app.renderer.resize(rect.width, rect.height);
        controller.resize(rect.width, rect.height);
      }

      app.ticker.add(() => {
        controller.render(renderTimeRef.current);
      });
    };

    void boot();

    return () => {
      disposed = true;
      onInteractionApiReady?.(null);
      resizeObserver?.disconnect();
      controllerRef.current?.destroy();
      controllerRef.current = null;
      if (appRef.current) {
        appRef.current.destroy(true, { children: true });
        appRef.current = null;
      }
      if (host.firstChild) host.textContent = "";
    };
  }, []);

  const renderTimeRef = useRef(renderTime);
  useEffect(() => {
    renderTimeRef.current = renderTime;
  }, [renderTime]);

  useEffect(() => {
    controllerRef.current?.updateScene(stableScene);
  }, [stableScene]);

  useEffect(() => {
    controllerRef.current?.updateShocks(annotations, currentT);
  }, [annotations, currentT, stableScene]);

  useEffect(() => {
    controllerRef.current?.setPointerField(pointerField);
  }, [pointerField]);

  useEffect(() => {
    controllerRef.current?.setTransitionPhase(transitionPhase);
  }, [transitionPhase]);

  useEffect(() => {
    if (!layerVisibility) return;
    controllerRef.current?.setLayerVisibility(layerVisibility);
  }, [layerVisibility]);

  return <div ref={hostRef} className="simulation-map__pixi-stage" aria-hidden="true" />;
}
