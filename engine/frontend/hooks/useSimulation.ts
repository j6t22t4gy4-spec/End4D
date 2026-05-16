"use client";

/**
 * 시뮬 실행 + WebSocket 스트림 (Phase 5.2)
 * WS 연결 후 stream=true run → step/done 메시지
 */
import { type Dispatch, type MutableRefObject, type SetStateAction, useCallback, useRef, useState } from "react";
import {
  type CellSnapshot,
  type CollectiveDynamicsSummary,
  type IntraTSceneEvent,
  type IntraTSceneMetrics,
  type RuntimeTiming,
  type SocialActionRecord,
  getWorldWebSocketUrl,
  runSimulation,
  stopSimulation,
} from "@/lib/api";

export type StreamMessage =
  | {
      type: "started";
      t?: number;
      t_max?: number;
      progress?: number;
      cell_count?: number;
      heartbeat_at?: number;
      message?: string;
      engine_revision?: string;
      recent_actions?: SocialActionRecord[];
    }
  | {
      type: "step";
      t: number;
      t_max?: number;
      progress?: number;
      cell_count: number;
      observer_cells?: CellSnapshot[];
      observer_total_cells?: number;
      observer_sampled?: boolean;
      group_state_summary?: CollectiveDynamicsSummary;
      scene_events?: IntraTSceneEvent[];
      scene_metrics?: IntraTSceneMetrics;
      runtime_timing?: RuntimeTiming;
      recent_actions?: SocialActionRecord[];
      heartbeat_at?: number;
      engine_revision?: string;
    }
  | {
      type: "scene";
      t: number;
      t_max?: number;
      progress?: number;
      scene_event: IntraTSceneEvent;
      action_event?: SocialActionRecord;
      recent_actions?: SocialActionRecord[];
      scene_index?: number;
      scene_count?: number;
      observer_cells?: CellSnapshot[];
      observer_total_cells?: number;
      observer_sampled?: boolean;
      heartbeat_at?: number;
      engine_revision?: string;
    }
  | {
      type: "heartbeat";
      t?: number;
      t_max?: number;
      progress?: number;
      cell_count?: number;
      runtime_timing?: RuntimeTiming;
      heartbeat_at?: number;
      engine_revision?: string;
    }
  | { type: "done"; t?: number; t_max?: number; progress?: number; heartbeat_at?: number }
  | { type: "error"; message?: string }
  | { type: "pong" };

export type LiveObserverState = {
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  t: number;
  groupSummary?: CollectiveDynamicsSummary | null;
} | null;

export type LiveSceneStreamState = {
  currentT: number | null;
  observedT: number | null;
  activePhase: string | null;
  events: IntraTSceneEvent[];
  latestEvent: IntraTSceneEvent | null;
  metrics: IntraTSceneMetrics | null;
  runtimeTiming: RuntimeTiming | null;
  recentActions: SocialActionRecord[];
};

export type StreamStatus = {
  phase: "idle" | "connecting" | "started" | "running" | "reconnecting" | "stalled" | "completed" | "stopping" | "stopped" | "error";
  progress: number;
  t: number | null;
  tMax: number | null;
  lastHeartbeatAt: number | null;
  message: string;
};

export function useSimulation() {
  const wsRef = useRef<WebSocket | null>(null);
  const expectedCloseRef = useRef(false);
  const pingTimerRef = useRef<number | null>(null);
  const heartbeatWatchRef = useRef<number | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const [liveT, setLiveT] = useState<number | null>(null);
  const [liveCellCount, setLiveCellCount] = useState<number | null>(null);
  const [liveObserver, setLiveObserver] = useState<LiveObserverState>(null);
  const [liveSceneStream, setLiveSceneStream] = useState<LiveSceneStreamState>({
    currentT: null,
    observedT: null,
    activePhase: null,
    events: [],
    latestEvent: null,
    metrics: null,
    runtimeTiming: null,
    recentActions: [],
  });
  const [isRunning, setIsRunning] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>({
    phase: "idle",
    progress: 0,
    t: null,
    tMax: null,
    lastHeartbeatAt: null,
    message: "",
  });

  const disconnectWebSocket = useCallback(() => {
    clearRuntimeTimers(pingTimerRef, heartbeatWatchRef, reconnectTimerRef);
    if (wsRef.current) {
      expectedCloseRef.current = true;
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  const stopStream = useCallback(
    async (worldId?: string | null) => {
      setStreamStatus((prev) => ({
        ...prev,
        phase: "stopping",
        message: "stopping stream",
        lastHeartbeatAt: Date.now(),
      }));
      if (worldId) {
        try {
          await stopSimulation(worldId);
        } catch {
          /* Closing the client stream is still useful even if the stop request fails. */
        }
      }
      disconnectWebSocket();
      setIsRunning(false);
      setStreamStatus((prev) => ({
        ...prev,
        phase: "stopped",
        message: "stopped",
        lastHeartbeatAt: Date.now(),
      }));
    },
    [disconnectWebSocket]
  );

  /**
   * WebSocket 연결 → POST run(stream) → done/error 까지 대기
   */
  const runWithWebSocketStream = useCallback(
    (worldId: string): Promise<void> => {
      disconnectWebSocket();
      setStreamError(null);
      setLiveT(null);
      setLiveCellCount(null);
      setLiveObserver(null);
      setLiveSceneStream({ currentT: null, observedT: null, activePhase: null, events: [], latestEvent: null, metrics: null, runtimeTiming: null, recentActions: [] });
      setIsRunning(true);
      setStreamStatus({
        phase: "connecting",
        progress: 0,
        t: null,
        tMax: null,
        lastHeartbeatAt: null,
        message: "connecting",
      });

      return new Promise((resolve, reject) => {
        const url = getWorldWebSocketUrl(worldId);
        let settled = false;
        let runTriggered = false;
        let streamActive = true;
        let reconnectAttempts = 0;
        const maxReconnectAttempts = 3;

        const settleResolve = () => {
          if (settled) return;
          settled = true;
          resolve();
        };
        const settleReject = (error: Error) => {
          if (settled) return;
          settled = true;
          reject(error);
        };
        const connect = (mode: "initial" | "reconnect") => {
          clearRuntimeTimers(pingTimerRef, heartbeatWatchRef, reconnectTimerRef);
          const ws = new WebSocket(url);
          wsRef.current = ws;
          expectedCloseRef.current = false;
          setStreamStatus((prev) => ({
            ...prev,
            phase: mode === "reconnect" ? "reconnecting" : prev.phase,
            message: mode === "reconnect" ? "reconnecting" : prev.message,
          }));

          ws.onmessage = (ev) => handleStreamMessage(ev.data);

          ws.onerror = () => {
            if (!settled && isRecoverableStreamStatus() && reconnectAttempts < maxReconnectAttempts) {
              scheduleReconnect("socket error");
              return;
            }
            const message = mode === "reconnect" ? "WebSocket 재연결 실패" : "WebSocket 연결 실패";
            setStreamError(message);
            setStreamStatus((prev) => ({ ...prev, phase: "error", message }));
            expectedCloseRef.current = true;
            disconnectWebSocket();
            setIsRunning(false);
            settleReject(new Error(message));
          };

          ws.onclose = () => {
            if (expectedCloseRef.current || settled) return;
            clearRuntimeTimers(pingTimerRef, heartbeatWatchRef, reconnectTimerRef);
            if (isRecoverableStreamStatus() && reconnectAttempts < maxReconnectAttempts) {
              scheduleReconnect("socket closed");
              return;
            }
            setIsRunning(false);
            const message = "WebSocket 연결이 끊겼습니다. 최신 상태를 다시 조회해 주세요.";
            setStreamError(message);
            setStreamStatus((prev) => ({ ...prev, phase: "error", message }));
            settleReject(new Error(message));
          };

          ws.onopen = () => {
            startRuntimeTimers(ws, setStreamStatus, pingTimerRef, heartbeatWatchRef);
            if (mode === "reconnect") {
              setStreamStatus((prev) => ({
                ...prev,
                phase: "running",
                lastHeartbeatAt: Date.now(),
                message: "reconnected",
              }));
              return;
            }
            if (runTriggered) return;
            runTriggered = true;
            runSimulation(worldId, { stream: true })
              .then(() => {
                /* 백그라운드 실행 시작; 완료는 WS done */
              })
              .catch((e: Error) => {
                setIsRunning(false);
                setStreamError(e.message);
                setStreamStatus((prev) => ({ ...prev, phase: "error", message: e.message }));
                expectedCloseRef.current = true;
                disconnectWebSocket();
                settleReject(e);
              });
          };
        };

        const isRecoverableStreamStatus = () => {
          return streamActive;
        };

        const scheduleReconnect = (reason: string) => {
          reconnectAttempts += 1;
          clearRuntimeTimers(pingTimerRef, heartbeatWatchRef, reconnectTimerRef);
          expectedCloseRef.current = true;
          if (wsRef.current) {
            wsRef.current.close();
            wsRef.current = null;
          }
          const delayMs = 700 + reconnectAttempts * 650;
          setStreamStatus((prev) => ({
            ...prev,
            phase: "reconnecting",
            message: `stream reconnecting (${reason}, ${reconnectAttempts}/${maxReconnectAttempts})`,
          }));
          reconnectTimerRef.current = window.setTimeout(() => connect("reconnect"), delayMs);
        };

        const handleStreamMessage = (data: string) => {
          try {
            const msg = JSON.parse(data) as StreamMessage;
            if (msg.type === "started") {
              setLiveSceneStream({
                currentT: null,
                observedT: null,
                activePhase: null,
                events: [],
                latestEvent: null,
                metrics: null,
                runtimeTiming: null,
                recentActions: msg.recent_actions ?? [],
              });
              setLiveCellCount(msg.cell_count ?? null);
              setStreamStatus({
                phase: "started",
                progress: clampProgress(msg.progress),
                t: typeof msg.t === "number" ? msg.t : null,
                tMax: typeof msg.t_max === "number" ? msg.t_max : null,
                lastHeartbeatAt: Date.now(),
                message: msg.engine_revision ? `${msg.message ?? "started"} · ${msg.engine_revision}` : msg.message ?? "started",
              });
            } else if (msg.type === "step") {
              setLiveT(msg.t);
              setLiveCellCount(msg.cell_count);
              const heartbeatAt = toMillis(msg.heartbeat_at) ?? Date.now();
              setStreamStatus({
                phase: "running",
                progress: clampProgress(msg.progress),
                t: msg.t,
                tMax: typeof msg.t_max === "number" ? msg.t_max : null,
                lastHeartbeatAt: heartbeatAt,
                message: "step",
              });
              setLiveObserver({
                cells: msg.observer_cells ?? [],
                totalCells: msg.observer_total_cells ?? msg.cell_count,
                sampled: Boolean(msg.observer_sampled),
                t: msg.t,
                groupSummary: msg.group_state_summary ?? null,
              });
              if (msg.scene_events?.length) {
                setLiveSceneStream((prev) => {
                  const sameT = prev.currentT != null && Math.round(prev.currentT) === Math.round(msg.t);
                  const hasLiveBeats = sameT && prev.events.some((event) => event.live_computed);
                  if (hasLiveBeats) {
                    return {
                      ...prev,
                      metrics: msg.scene_metrics ?? prev.metrics,
                      runtimeTiming: msg.runtime_timing ?? prev.runtimeTiming,
                      recentActions: msg.recent_actions ?? prev.recentActions,
                    };
                  }
                  return {
                    currentT: msg.t,
                    observedT: msg.scene_events?.[msg.scene_events.length - 1]?.scene_t ?? msg.t,
                    activePhase: msg.scene_events?.[msg.scene_events.length - 1]?.stream_phase ?? "step_snapshot",
                    events: msg.scene_events ?? [],
                    latestEvent: msg.scene_events?.[msg.scene_events.length - 1] ?? null,
                    metrics: msg.scene_metrics ?? null,
                    runtimeTiming: msg.runtime_timing ?? null,
                    recentActions: msg.recent_actions ?? prev.recentActions,
                  };
                });
              } else if (msg.recent_actions?.length) {
                setLiveSceneStream((prev) => ({
                  ...prev,
                  runtimeTiming: msg.runtime_timing ?? prev.runtimeTiming,
                  recentActions: msg.recent_actions ?? prev.recentActions,
                }));
              } else if (msg.runtime_timing) {
                setLiveSceneStream((prev) => ({ ...prev, runtimeTiming: msg.runtime_timing ?? prev.runtimeTiming }));
              }
            } else if (msg.type === "scene") {
              const heartbeatAt = toMillis(msg.heartbeat_at) ?? Date.now();
              const observedT = Number(msg.scene_event?.scene_t ?? msg.t);
              if (msg.observer_cells?.length) {
                setLiveObserver((prev) => ({
                  cells: mergeLiveCells(prev?.cells ?? [], msg.observer_cells ?? []),
                  totalCells: msg.observer_total_cells ?? prev?.totalCells ?? msg.observer_cells?.length ?? 0,
                  sampled: Boolean(msg.observer_sampled ?? prev?.sampled),
                  t: observedT,
                  groupSummary: prev?.groupSummary ?? null,
                }));
                setLiveCellCount(msg.observer_total_cells ?? msg.observer_cells.length);
              }
              setStreamStatus((prev) => ({
                phase: "running",
                progress: clampProgress(msg.progress ?? prev.progress),
                t: typeof msg.t === "number" ? msg.t : prev.t,
                tMax: typeof msg.t_max === "number" ? msg.t_max : prev.tMax,
                lastHeartbeatAt: heartbeatAt,
                message: `t chapter ${Math.round(Number(msg.t ?? 0))} · stream round ${msg.scene_event.stream_round_index ?? msg.scene_event.session_index ?? "?"}/${msg.scene_event.stream_round_count ?? msg.scene_event.session_count ?? "?"} · ${msg.scene_event.stream_phase ?? "scene"}`,
              }));
              setLiveSceneStream((prev) => {
                const resetForNewT = prev.currentT == null || Math.round(prev.currentT) !== Math.round(msg.t);
                const nextEvents = resetForNewT ? [msg.scene_event] : [...prev.events, msg.scene_event].slice(-180);
                const recentActions = msg.recent_actions?.length
                  ? msg.recent_actions
                  : msg.action_event
                    ? [...prev.recentActions, msg.action_event].slice(-50)
                    : prev.recentActions;
                return {
                  currentT: msg.t,
                  observedT,
                  activePhase: msg.scene_event.stream_phase ?? "scene",
                  events: nextEvents,
                  latestEvent: msg.scene_event,
                  metrics: prev.metrics,
                  runtimeTiming: prev.runtimeTiming,
                  recentActions,
                };
              });
            } else if (msg.type === "heartbeat") {
              const heartbeatAt = toMillis(msg.heartbeat_at) ?? Date.now();
              if (typeof msg.t === "number") setLiveT(msg.t);
              if (typeof msg.cell_count === "number") setLiveCellCount(msg.cell_count);
              setStreamStatus((prev) => ({
                phase: "running",
                progress: clampProgress(msg.progress ?? prev.progress),
                t: typeof msg.t === "number" ? msg.t : prev.t,
                tMax: typeof msg.t_max === "number" ? msg.t_max : prev.tMax,
                lastHeartbeatAt: heartbeatAt,
                message: "heartbeat",
              }));
              if (msg.runtime_timing) {
                setLiveSceneStream((prev) => ({ ...prev, runtimeTiming: msg.runtime_timing ?? prev.runtimeTiming }));
              }
            } else if (msg.type === "done") {
              streamActive = false;
              setIsRunning(false);
              setStreamStatus((prev) => ({
                phase: "completed",
                progress: clampProgress(msg.progress ?? 1),
                t: typeof msg.t === "number" ? msg.t : prev.t,
                tMax: typeof msg.t_max === "number" ? msg.t_max : prev.tMax,
                lastHeartbeatAt: toMillis(msg.heartbeat_at) ?? Date.now(),
                message: "completed",
              }));
              expectedCloseRef.current = true;
              disconnectWebSocket();
              settleResolve();
            } else if (msg.type === "error") {
              streamActive = false;
              setIsRunning(false);
              const err = msg.message ?? "Stream error";
              setStreamError(err);
              setStreamStatus((prev) => ({ ...prev, phase: "error", message: err }));
              expectedCloseRef.current = true;
              disconnectWebSocket();
              settleReject(new Error(err));
            } else if (msg.type === "pong") {
              setStreamStatus((prev) => ({
                ...prev,
                lastHeartbeatAt: Date.now(),
                message: prev.phase === "stalled" ? "heartbeat recovered" : prev.message,
                phase: prev.phase === "stalled" ? "running" : prev.phase,
              }));
            }
          } catch {
            /* ignore non-JSON */
          }
        };
        connect("initial");
      });
    },
    [disconnectWebSocket]
  );

  /** 동기 실행 (WS 없음, 스냅샷만 갱신용) */
  const runSync = useCallback(async (worldId: string) => {
    setStreamError(null);
    setIsRunning(true);
    setLiveT(null);
    setLiveCellCount(null);
    setLiveObserver(null);
    setLiveSceneStream({ currentT: null, observedT: null, activePhase: null, events: [], latestEvent: null, metrics: null, runtimeTiming: null, recentActions: [] });
    setStreamStatus({
      phase: "started",
      progress: 0,
      t: null,
      tMax: null,
      lastHeartbeatAt: Date.now(),
      message: "sync running",
    });
    try {
      await runSimulation(worldId, { stream: false });
      setStreamStatus((prev) => ({
        ...prev,
        phase: "completed",
        progress: 1,
        lastHeartbeatAt: Date.now(),
        message: "completed",
      }));
    } finally {
      setIsRunning(false);
    }
  }, []);

  return {
    liveT,
    liveCellCount,
    liveObserver,
    liveSceneStream,
    isRunning,
    streamError,
    streamStatus,
    runWithWebSocketStream,
    runSync,
    stopStream,
    disconnectWebSocket,
  };
}

function clearRuntimeTimers(
  pingTimerRef: MutableRefObject<number | null>,
  heartbeatWatchRef: MutableRefObject<number | null>,
  reconnectTimerRef: MutableRefObject<number | null>
) {
  if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
  if (heartbeatWatchRef.current) window.clearInterval(heartbeatWatchRef.current);
  if (reconnectTimerRef.current) window.clearTimeout(reconnectTimerRef.current);
  pingTimerRef.current = null;
  heartbeatWatchRef.current = null;
  reconnectTimerRef.current = null;
}

function startRuntimeTimers(
  ws: WebSocket,
  setStreamStatus: Dispatch<SetStateAction<StreamStatus>>,
  pingTimerRef: MutableRefObject<number | null>,
  heartbeatWatchRef: MutableRefObject<number | null>
) {
  if (pingTimerRef.current) window.clearInterval(pingTimerRef.current);
  if (heartbeatWatchRef.current) window.clearInterval(heartbeatWatchRef.current);
  const sendPing = () => {
    if (ws.readyState === WebSocket.OPEN) {
      ws.send("ping");
    }
  };
  sendPing();
  // Keep the socket active and make silent stalls visible before the browser
  // decides to close the connection.
  pingTimerRef.current = window.setInterval(sendPing, 10_000);
  heartbeatWatchRef.current = window.setInterval(() => {
    setStreamStatus((prev) => {
      if (!prev.lastHeartbeatAt || !["started", "running", "reconnecting"].includes(prev.phase)) return prev;
      const ageMs = Date.now() - prev.lastHeartbeatAt;
      if (ageMs < 30_000) return prev;
      return {
        ...prev,
        phase: "stalled",
        message: `heartbeat stale ${Math.round(ageMs / 1000)}s`,
      };
    });
  }, 5_000);
}

function clampProgress(value: unknown): number {
  const num = typeof value === "number" ? value : 0;
  return Math.max(0, Math.min(1, Number.isFinite(num) ? num : 0));
}

function mergeLiveCells(previous: CellSnapshot[], incoming: CellSnapshot[]): CellSnapshot[] {
  if (!previous.length) return incoming;
  const rows = new Map<string, CellSnapshot>();
  for (const cell of previous) rows.set(cell.cell_id, cell);
  for (const cell of incoming) rows.set(cell.cell_id, cell);
  return Array.from(rows.values()).slice(-96);
}

function toMillis(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value > 10_000_000_000 ? value : value * 1000;
}
