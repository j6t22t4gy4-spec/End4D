"use client";

/**
 * 시뮬 실행 + WebSocket 스트림 (Phase 5.2)
 * WS 연결 후 stream=true run → step/done 메시지
 */
import { useCallback, useRef, useState } from "react";
import {
  type CellSnapshot,
  getWorldWebSocketUrl,
  runSimulation,
} from "@/lib/api";

export type StreamMessage =
  | {
      type: "step";
      t: number;
      cell_count: number;
      observer_cells?: CellSnapshot[];
      observer_total_cells?: number;
      observer_sampled?: boolean;
    }
  | { type: "done" }
  | { type: "error"; message?: string }
  | { type: "pong" };

export type LiveObserverState = {
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  t: number;
} | null;

export function useSimulation() {
  const wsRef = useRef<WebSocket | null>(null);
  const [liveT, setLiveT] = useState<number | null>(null);
  const [liveCellCount, setLiveCellCount] = useState<number | null>(null);
  const [liveObserver, setLiveObserver] = useState<LiveObserverState>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [streamError, setStreamError] = useState<string | null>(null);

  const disconnectWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

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
      setIsRunning(true);

      return new Promise((resolve, reject) => {
        const url = getWorldWebSocketUrl(worldId);
        const ws = new WebSocket(url);
        wsRef.current = ws;

        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data) as StreamMessage;
            if (msg.type === "step") {
              setLiveT(msg.t);
              setLiveCellCount(msg.cell_count);
              setLiveObserver({
                cells: msg.observer_cells ?? [],
                totalCells: msg.observer_total_cells ?? msg.cell_count,
                sampled: Boolean(msg.observer_sampled),
                t: msg.t,
              });
            } else if (msg.type === "done") {
              setIsRunning(false);
              disconnectWebSocket();
              resolve();
            } else if (msg.type === "error") {
              setIsRunning(false);
              const err = msg.message ?? "Stream error";
              setStreamError(err);
              disconnectWebSocket();
              reject(new Error(err));
            }
          } catch {
            /* ignore non-JSON */
          }
        };

        ws.onerror = () => {
          setIsRunning(false);
          setStreamError("WebSocket 연결 실패");
          disconnectWebSocket();
          reject(new Error("WebSocket error"));
        };

        ws.onopen = () => {
          runSimulation(worldId, { stream: true })
            .then(() => {
              /* 백그라운드 실행 시작; 완료는 WS done */
            })
            .catch((e: Error) => {
              setIsRunning(false);
              setStreamError(e.message);
              disconnectWebSocket();
              reject(e);
            });
        };
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
    try {
      await runSimulation(worldId, { stream: false });
    } finally {
      setIsRunning(false);
    }
  }, []);

  return {
    liveT,
    liveCellCount,
    liveObserver,
    isRunning,
    streamError,
    runWithWebSocketStream,
    runSync,
    disconnectWebSocket,
  };
}
