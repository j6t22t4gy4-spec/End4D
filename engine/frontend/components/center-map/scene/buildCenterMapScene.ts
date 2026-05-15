"use client";

import { emotionToColorAndScale, type CellSnapshot, type IntraTSceneEvent } from "@/lib/api";
import {
  CENTER_MAP_SCENE_HEIGHT,
  CENTER_MAP_SCENE_PADDING,
  CENTER_MAP_SCENE_WIDTH,
  type CenterMapScene,
} from "@/components/center-map/scene/sceneTypes";

type BuildCenterMapSceneArgs = {
  cells: CellSnapshot[];
  selectedAgentId?: string | null;
  sceneEvents?: IntraTSceneEvent[];
};

export function buildCenterMapScene({
  cells,
  selectedAgentId = null,
  sceneEvents = [],
}: BuildCenterMapSceneArgs): CenterMapScene {
  if (!cells.length) {
    return {
      width: CENTER_MAP_SCENE_WIDTH,
      height: CENTER_MAP_SCENE_HEIGHT,
      agents: [],
      zones: [],
      interactions: [],
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

  const projected = new Map<string, { x: number; y: number }>();
  const agents = cells.map((cell) => {
    const px = projectX(cell.x);
    const py = projectY(cell.y);
    projected.set(cell.cell_id, { x: px, y: py });
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
      heat: Math.max(
        0,
        Math.min(
          1,
          Number(cell.action_state?.local_density ?? 0) * 0.34 +
            Number(cell.action_state?.scene_participation_count ?? 0) * 0.16 +
            Number(cell.action_state?.observer_score ?? 0) * 0.22 +
            Number(cell.action_state?.last_spatial_shift ?? 0) * 0.02
        )
      ),
      observerScore: Math.max(
        0,
        Math.min(1, Number(cell.action_state?.observer_score ?? 0))
      ),
      selected: cell.cell_id === selectedAgentId,
      fractureSignal: Boolean(cell.action_state?.fracture_signal_received),
    };
  });

  const cellInteractions = cells.flatMap((cell) => {
    const source = projected.get(cell.cell_id);
    if (!source) return [];
    return (cell.interaction_events ?? []).flatMap((event, eventIndex) => {
      const targetIds = Array.isArray(event.target_ids) ? event.target_ids : [];
      const eventType = normalizeInteractionType(event.type);
      const quality = Math.max(0.15, Math.min(1, Number(event.quality ?? 0.5)));
      const eventT = Number(event.t ?? cell.t);
      const age = Math.max(0, Math.min(1, Math.abs(Number(cell.t ?? 0) - eventT)));
      return targetIds.flatMap((targetId, targetIndex) => {
        const target = projected.get(String(targetId));
        if (!target) return [];
        return [
          {
            id: `${cell.cell_id}-${String(targetId)}-${eventIndex}-${targetIndex}`,
            sourceId: cell.cell_id,
            targetId: String(targetId),
            x0: source.x,
            y0: source.y,
            x1: target.x,
            y1: target.y,
            type: eventType,
            intensity: quality,
            age,
          },
        ];
      });
    });
  });
  const sceneInteractions = sceneEvents.flatMap((event, eventIndex) => {
    const sourceId = String(event.source_id ?? "");
    const source = projected.get(sourceId);
    if (!source) return [];
    const targetIds = Array.isArray(event.target_ids) ? event.target_ids : [];
    const eventType = normalizeInteractionType(event.interaction_type);
    const pressureDelta = Number(event.pressure_delta ?? 0);
    const relationshipDelta = Number(event.relationship_delta ?? 0);
    const hasNarrative = Boolean(event.narrative_reason || event.scenario_relevance);
    const isLatestScene =
      Number(event.scene_index ?? eventIndex + 1) >= Math.max(1, Number(event.scene_count ?? sceneEvents.length) - 2);
    const intensity = Math.max(
      0.25,
      Math.min(
        1,
        Math.abs(pressureDelta) * 4.6
          + Math.abs(relationshipDelta) * 3.4
          + (eventType === "hostile" ? 0.28 : eventType === "negative" ? 0.18 : eventType === "positive" ? 0.12 : 0.04)
          + (hasNarrative ? 0.16 : 0)
          + 0.28
      )
    );
    return targetIds.flatMap((targetId, targetIndex) => {
      const target = projected.get(String(targetId));
      if (!target) return [];
      return [
        {
          id: `scene-${String(event.scene_id ?? eventIndex)}-${String(targetId)}-${targetIndex}`,
          sourceId,
          targetId: String(targetId),
          x0: source.x,
          y0: source.y,
          x1: target.x,
          y1: target.y,
          type: eventType,
          intensity,
          age: Math.max(0, 1 - Number(event.scene_index ?? 1) / Math.max(1, Number(event.scene_count ?? 1))),
          fresh:
            isLatestScene ||
            Boolean((event.visual_hint as Record<string, unknown> | undefined)?.pulse) ||
            Boolean((event as Record<string, unknown>).live_computed),
          sceneId: String(event.scene_id ?? ""),
          pressureDelta,
          salience: intensity,
        },
      ];
    });
  });
  const interactions = [...sceneInteractions, ...cellInteractions].slice(0, 128);

  return {
    width: CENTER_MAP_SCENE_WIDTH,
    height: CENTER_MAP_SCENE_HEIGHT,
    agents,
    zones: Array.from(zoneAcc.values()).map((zone) => ({
      id: zone.id,
      centerX: zone.centerX / zone.count,
      centerY: zone.centerY / zone.count,
      x0: Math.max(CENTER_MAP_SCENE_PADDING - 8, zone.x0 - 20),
      x1: Math.min(CENTER_MAP_SCENE_WIDTH - CENTER_MAP_SCENE_PADDING + 8, zone.x1 + 20),
      y0: Math.max(CENTER_MAP_SCENE_PADDING - 8, zone.y0 - 18),
      y1: Math.min(CENTER_MAP_SCENE_HEIGHT - CENTER_MAP_SCENE_PADDING + 8, zone.y1 + 18),
      width: Math.max(78, zone.x1 - zone.x0 + 34),
      height: Math.max(56, zone.y1 - zone.y0 + 28),
      avgPressure: zone.avgPressure / zone.count,
      avgDrift: zone.avgDrift / zone.count,
      count: zone.count,
      fractureSignals: zone.fractureSignals,
    })),
    interactions,
  };
}

function rgbToHex(rgb: [number, number, number]) {
  return ((rgb[0] ?? 0) << 16) | ((rgb[1] ?? 0) << 8) | (rgb[2] ?? 0);
}

function normalizeInteractionType(value: unknown): "positive" | "negative" | "hostile" | "dialogue" {
  const raw = String(value ?? "dialogue");
  if (raw === "positive" || raw === "negative" || raw === "hostile" || raw === "dialogue") return raw;
  if (raw === "alignment") return "positive";
  if (raw === "conflict") return "hostile";
  return "dialogue";
}
