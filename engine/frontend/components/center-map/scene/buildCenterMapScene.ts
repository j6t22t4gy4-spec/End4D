"use client";

import { emotionToColorAndScale, type CellSnapshot } from "@/lib/api";
import {
  CENTER_MAP_SCENE_HEIGHT,
  CENTER_MAP_SCENE_PADDING,
  CENTER_MAP_SCENE_WIDTH,
  type CenterMapScene,
} from "@/components/center-map/scene/sceneTypes";

type BuildCenterMapSceneArgs = {
  cells: CellSnapshot[];
  selectedAgentId?: string | null;
};

export function buildCenterMapScene({
  cells,
  selectedAgentId = null,
}: BuildCenterMapSceneArgs): CenterMapScene {
  if (!cells.length) {
    return {
      width: CENTER_MAP_SCENE_WIDTH,
      height: CENTER_MAP_SCENE_HEIGHT,
      agents: [],
      zones: [],
    };
  }

  const xs = cells.map((cell) => cell.x);
  const ys = cells.map((cell) => cell.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const innerWidth = CENTER_MAP_SCENE_WIDTH - CENTER_MAP_SCENE_PADDING * 2;
  const innerHeight = CENTER_MAP_SCENE_HEIGHT - CENTER_MAP_SCENE_PADDING * 2;

  const projectX = (x: number) =>
    CENTER_MAP_SCENE_PADDING + ((x - minX) / spanX) * innerWidth;
  const projectY = (y: number) =>
    CENTER_MAP_SCENE_PADDING + (1 - (y - minY) / spanY) * innerHeight;

  const zoneAcc = new Map<
    string,
    {
      id: string;
      centerX: number;
      centerY: number;
      x0: number;
      x1: number;
      y0: number;
      y1: number;
      avgPressure: number;
      avgDrift: number;
      count: number;
      fractureSignals: number;
    }
  >();

  const agents = cells.map((cell) => {
    const px = projectX(cell.x);
    const py = projectY(cell.y);
    const zoneId = String(cell.zone_id ?? "zone-0");
    const zone = zoneAcc.get(zoneId) ?? {
      id: zoneId,
      centerX: px,
      centerY: py,
      x0: px,
      x1: px,
      y0: py,
      y1: py,
      avgPressure: 0,
      avgDrift: 0,
      count: 0,
      fractureSignals: 0,
    };
    zone.centerX += px;
    zone.centerY += py;
    zone.x0 = Math.min(zone.x0, px);
    zone.x1 = Math.max(zone.x1, px);
    zone.y0 = Math.min(zone.y0, py);
    zone.y1 = Math.max(zone.y1, py);
    zone.avgPressure += Number(cell.action_state?.collective_pressure ?? 0);
    zone.avgDrift += Number(cell.action_state?.zone_group_drift_velocity ?? 0);
    zone.fractureSignals += Number(Boolean(cell.action_state?.fracture_signal_received));
    zone.count += 1;
    zoneAcc.set(zoneId, zone);

    const { rgb, scale } = emotionToColorAndScale(cell.emotion_vec);
    return {
      id: cell.cell_id,
      x: px,
      y: py,
      radius: 3 + scale * 5 + Number(cell.action_state?.observer_score ?? 0) * 1.8,
      color: rgbToHex(rgb),
      pressure: Math.max(
        0,
        Math.min(1, Number(cell.action_state?.collective_pressure ?? 0))
      ),
      observerScore: Math.max(
        0,
        Math.min(1, Number(cell.action_state?.observer_score ?? 0))
      ),
      selected: cell.cell_id === selectedAgentId,
      fractureSignal: Boolean(cell.action_state?.fracture_signal_received),
    };
  });

  return {
    width: CENTER_MAP_SCENE_WIDTH,
    height: CENTER_MAP_SCENE_HEIGHT,
    agents,
    zones: Array.from(zoneAcc.values()).map((zone) => ({
      id: zone.id,
      centerX: zone.centerX / zone.count,
      centerY: zone.centerY / zone.count,
      width: Math.max(78, zone.x1 - zone.x0 + 34),
      height: Math.max(56, zone.y1 - zone.y0 + 28),
      avgPressure: zone.avgPressure / zone.count,
      avgDrift: zone.avgDrift / zone.count,
      count: zone.count,
      fractureSignals: zone.fractureSignals,
    })),
  };
}

function rgbToHex(rgb: [number, number, number]) {
  return ((rgb[0] ?? 0) << 16) | ((rgb[1] ?? 0) << 8) | (rgb[2] ?? 0);
}
