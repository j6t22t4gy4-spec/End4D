"use client";

export const CENTER_MAP_SCENE_WIDTH = 960;
export const CENTER_MAP_SCENE_HEIGHT = 640;
export const CENTER_MAP_SCENE_PADDING = 56;

export type PointerField = {
  x: number;
  y: number;
  active: boolean;
};

export type CenterMapSceneAgent = {
  id: string;
  x: number;
  y: number;
  radius: number;
  color: number;
  pressure: number;
  observerScore: number;
  selected: boolean;
  fractureSignal: boolean;
};

export type CenterMapSceneZone = {
  id: string;
  centerX: number;
  centerY: number;
  x0: number;
  x1: number;
  y0: number;
  y1: number;
  width: number;
  height: number;
  avgPressure: number;
  avgDrift: number;
  count: number;
  fractureSignals: number;
};

export type CenterMapScene = {
  width: number;
  height: number;
  agents: CenterMapSceneAgent[];
  zones: CenterMapSceneZone[];
};
