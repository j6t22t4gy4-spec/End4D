"use client";

import { emotionToColorAndScale, type CellSnapshot, type IntraTSceneEvent } from "@/lib/api";
import {
  CENTER_MAP_SCENE_HEIGHT,
  CENTER_MAP_SCENE_PADDING,
  CENTER_MAP_SCENE_WIDTH,
  type CenterMapScene,
  type CenterMapSceneSession,
} from "@/components/center-map/scene/sceneTypes";
import {
  socialFieldActionLabel,
  socialFieldColorFromRecord,
  socialFieldToneFromRecord,
  type SocialFieldTone,
} from "@/lib/socialFieldActions";

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
      activeSession: null,
    };
  }

  const activeSession = buildActiveSession(sceneEvents);
  const activeAgentRoles = new Map<string, "source" | "target">();
  for (const id of activeSession?.sourceIds ?? []) activeAgentRoles.set(id, "source");
  for (const id of activeSession?.targetIds ?? []) {
    if (!activeAgentRoles.has(id)) activeAgentRoles.set(id, "target");
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
      sessionActive: activeAgentRoles.has(cell.cell_id),
      sessionRole: (activeAgentRoles.get(cell.cell_id) ?? "ambient") as "source" | "target" | "ambient",
      sessionIntensity: activeAgentRoles.has(cell.cell_id) ? activeSession?.intensity ?? 0.7 : 0,
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
            color: socialFieldColorFromRecord(null, event.type),
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
    const eventType = socialFieldToneFromRecord(event.action_record, event.interaction_type);
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
    const sessionIndex = Number(event.stream_round_index ?? event.session_index ?? event.beat_index ?? event.scene_index ?? eventIndex + 1);
    const sessionCount = Number(event.stream_round_count ?? event.session_count ?? event.beat_count ?? event.scene_count ?? sceneEvents.length);
    const visualKind = String((event.visual_hint as Record<string, unknown> | undefined)?.kind ?? "");
    const swarmSession =
      visualKind.includes("miro_swarm") ||
      String(event.t_composition_role ?? "").includes("mirofish_cleanroom") ||
      String(event.stream_phase ?? "").includes("miro_swarm");
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
          actionType: event.action_record?.action_type,
          actionLabel: socialFieldActionLabel(event.action_record, "ko"),
          fieldAxis: event.action_record?.field_axis,
          color: socialFieldColorFromRecord(event.action_record, event.interaction_type),
          intensity,
          age: Math.max(0, 1 - Number(event.scene_index ?? 1) / Math.max(1, Number(event.scene_count ?? 1))),
          fresh:
            isLatestScene ||
            String(event.stream_session_id ?? "") === String(activeSession?.id ?? "") ||
            Boolean((event.visual_hint as Record<string, unknown> | undefined)?.pulse) ||
            Boolean((event as Record<string, unknown>).live_computed),
          sceneId: String(event.scene_id ?? ""),
          streamSessionId: String(event.stream_session_id ?? ""),
          sessionIndex,
          sessionCount,
          sessionEventIndex: Number(event.session_event_index ?? targetIndex + 1),
          pressureDelta,
          salience: intensity,
          swarmSession,
          llmAgentChannel: event.llm_agent_channel,
        },
      ];
    });
  });
  const hasSwarmSession = sceneInteractions.some((interaction) => interaction.swarmSession);
  const interactions = [...sceneInteractions, ...cellInteractions].slice(0, hasSwarmSession ? 900 : 240);

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
    activeSession,
  };
}

function buildActiveSession(sceneEvents: IntraTSceneEvent[]): CenterMapSceneSession | null {
  if (!sceneEvents.length) return null;
  const latest = sceneEvents[sceneEvents.length - 1];
  const sessionId = eventStreamId(latest);
  const sessionEvents = sceneEvents.filter((event) => {
    const id = eventStreamId(event);
    return id === sessionId;
  });
  const latestRound = Number(latest.stream_round_index ?? latest.session_index ?? latest.beat_index ?? latest.scene_index ?? 1);
  const activeRoundEvents = sessionEvents.filter((event) => {
    const round = Number(event.stream_round_index ?? event.session_index ?? event.beat_index ?? event.scene_index ?? 1);
    return Math.abs(round - latestRound) <= 1;
  });
  const focusEvents = activeRoundEvents.length ? activeRoundEvents : sessionEvents.slice(-12);
  const sourceIds = uniqueStrings(focusEvents.map((event) => String(event.source_id ?? "")).filter(Boolean));
  const targetIds = uniqueStrings(focusEvents.flatMap((event) => event.target_ids ?? []).map(String).filter(Boolean));
  const tones = focusEvents.map((event) => socialFieldToneFromRecord(event.action_record, event.interaction_type));
  const dominantTone = dominantSessionTone(tones);
  const intensity = Math.max(
    0.28,
    Math.min(
      1,
      focusEvents.reduce((sum, event) => {
        const pressure = Math.abs(Number(event.pressure_delta ?? 0)) * 3.4;
        const relation = Math.abs(Number(event.relationship_delta ?? 0)) * 2.4;
        const hostile = socialFieldToneFromRecord(event.action_record, event.interaction_type) === "hostile" ? 0.22 : 0;
        return sum + pressure + relation + hostile + 0.18;
      }, 0) / Math.max(1, focusEvents.length)
    )
  );
  return {
    id: sessionId,
    index: latestRound,
    count: Number(latest.stream_round_count ?? latest.session_count ?? latest.beat_count ?? latest.scene_count ?? 1),
    eventCount: sessionEvents.length,
    activeAgentIds: uniqueStrings([...sourceIds, ...targetIds]),
    sourceIds,
    targetIds,
    latestSummary: String(latest.summary ?? ""),
    activePhase: String(latest.stream_phase ?? "session"),
    dominantTone,
    intensity,
  };
}

function eventStreamId(event: IntraTSceneEvent) {
  return String(
    event.stream_episode_id ??
      event.stream_session_id ??
      `stream-${event.t ?? 0}-${event.stream_round_index ?? event.session_index ?? event.beat_index ?? event.scene_index ?? ""}`
  );
}

function uniqueStrings(values: string[]) {
  return Array.from(new Set(values.filter(Boolean)));
}

function dominantSessionTone(tones: SocialFieldTone[]): SocialFieldTone {
  if (tones.includes("hostile")) return "hostile";
  if (tones.includes("negative")) return "negative";
  if (tones.includes("positive")) return "positive";
  return "dialogue";
}

function rgbToHex(rgb: [number, number, number]) {
  return ((rgb[0] ?? 0) << 16) | ((rgb[1] ?? 0) << 8) | (rgb[2] ?? 0);
}

function normalizeInteractionType(value: unknown): SocialFieldTone {
  const raw = String(value ?? "dialogue");
  if (raw === "positive" || raw === "negative" || raw === "hostile" || raw === "dialogue") return raw;
  if (raw === "alignment") return "positive";
  if (raw === "conflict") return "hostile";
  return "dialogue";
}
