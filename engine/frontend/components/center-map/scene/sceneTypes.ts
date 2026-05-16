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
  heat: number;
  observerScore: number;
  selected: boolean;
  sessionActive: boolean;
  sessionRole: "source" | "target" | "ambient";
  sessionIntensity: number;
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

export type CenterMapSceneInteraction = {
  id: string;
  sourceId: string;
  targetId: string;
  x0: number;
  y0: number;
  x1: number;
  y1: number;
  type: "positive" | "negative" | "hostile" | "dialogue";
  actionType?: string;
  actionLabel?: string;
  fieldAxis?: string;
  color?: number;
  intensity: number;
  age: number;
  fresh?: boolean;
  sceneId?: string;
  streamSessionId?: string;
  sessionIndex?: number;
  sessionCount?: number;
  sessionEventIndex?: number;
  pressureDelta?: number;
  salience?: number;
  swarmSession?: boolean;
  llmAgentChannel?: string;
};

export type CenterMapSceneSession = {
  id: string;
  index: number;
  count: number;
  eventCount: number;
  activeAgentIds: string[];
  sourceIds: string[];
  targetIds: string[];
  latestSummary: string;
  activePhase: string;
  dominantTone: "positive" | "negative" | "hostile" | "dialogue";
  intensity: number;
};

export type CenterMapScene = {
  width: number;
  height: number;
  agents: CenterMapSceneAgent[];
  zones: CenterMapSceneZone[];
  interactions: CenterMapSceneInteraction[];
  activeSession: CenterMapSceneSession | null;
};
