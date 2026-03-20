"use client";

/**
 * God View E2E (Phase 5~7)
 * 세계 생성 → 실행 → t 슬라이더 → 주입·타임라인 → 3D
 */
import { useState, useEffect, useCallback, useMemo } from "react";
import { R3fErrorBoundary } from "@/components/R3fErrorBoundary";
import Scene3DCanvas from "@/components/Scene3D/Scene3DCanvas";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import {
  createWorld,
  getApiBase,
  listSnapshotTimes,
  getSnapshotAtT,
  cellsToInstanceBuffers,
  getMaxVisualCellsLimit,
} from "@/lib/api";
import { useSimulation } from "@/hooks/useSimulation";

const DEFAULT_CELLS = 5;
const DEFAULT_T_MAX = 50;

export default function GodView() {
  const [initialCells, setInitialCells] = useState(DEFAULT_CELLS);
  const [tMaxInput, setTMaxInput] = useState(DEFAULT_T_MAX);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [availableT, setAvailableT] = useState<number[]>([]);
  const [currentT, setCurrentT] = useState(0);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [positions, setPositions] = useState<Float32Array>(
    () => new Float32Array(0)
  );
  const [colors, setColors] = useState<Float32Array>(() => new Float32Array(0));
  const [scales, setScales] = useState<Float32Array>(() => new Float32Array(0));
  const [cellCount, setCellCount] = useState(0);
  const [visualStats, setVisualStats] = useState<{
    totalCells: number;
    sampled: boolean;
  } | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  /** 클라이언트 마운트 후에만 Canvas 로드 → 폼·버튼 먼저 페인트 (E2E·SSR 안정) */
  const [mount3d, setMount3d] = useState(false);
  const [chartRefreshKey, setChartRefreshKey] = useState(0);
  useEffect(() => {
    setMount3d(true);
  }, []);

  const bumpChartRefresh = useCallback(() => {
    setChartRefreshKey((k) => k + 1);
  }, []);

  const {
    liveT,
    liveCellCount,
    isRunning,
    streamError,
    runWithWebSocketStream,
    runSync,
    disconnectWebSocket,
  } = useSimulation();

  const tSliderMin = useMemo(
    () => (availableT.length ? Math.min(...availableT) : 0),
    [availableT]
  );
  const tSliderMax = useMemo(
    () => (availableT.length ? Math.max(...availableT) : 0),
    [availableT]
  );

  const availableKey = availableT.join(",");

  const handleCreateWorld = useCallback(async () => {
    setCreateError(null);
    setActionError(null);
    try {
      disconnectWebSocket();
      const { world_id } = await createWorld({
        initial_cell_count: initialCells,
        t_max: tMaxInput,
      });
      setWorldId(world_id);
      setAvailableT([]);
      setCurrentT(0);
      setCellCount(0);
      setPositions(new Float32Array(0));
      setColors(new Float32Array(0));
      setScales(new Float32Array(0));
      setVisualStats(null);
      bumpChartRefresh();
    } catch (e) {
      setCreateError((e as Error).message);
    }
  }, [initialCells, tMaxInput, disconnectWebSocket, bumpChartRefresh]);

  const refreshSnapshots = useCallback(async (wid: string) => {
    const list = await listSnapshotTimes(wid);
    setAvailableT(list.available_t);
    const last = list.available_t[list.available_t.length - 1] ?? 0;
    setCurrentT(last);
    bumpChartRefresh();
  }, [bumpChartRefresh]);

  const handleRunStream = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      await runWithWebSocketStream(worldId);
      await refreshSnapshots(worldId);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [worldId, runWithWebSocketStream, refreshSnapshots]);

  const handleRunSync = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      await runSync(worldId);
      await refreshSnapshots(worldId);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [worldId, runSync, refreshSnapshots]);

  const handleInjected = useCallback(async () => {
    if (!worldId) return;
    await refreshSnapshots(worldId);
  }, [worldId, refreshSnapshots]);

  useEffect(() => {
    if (!worldId || availableT.length === 0) {
      if (availableT.length === 0 && worldId) {
        /* 생성 직후 스냅샷 없음 — 버퍼 비움 */
        setCellCount(0);
        setPositions(new Float32Array(0));
        setColors(new Float32Array(0));
        setScales(new Float32Array(0));
        setVisualStats(null);
      }
      return;
    }

    let cancelled = false;
    setSnapshotLoading(true);
    getSnapshotAtT(worldId, currentT)
      .then((snap) => {
        if (cancelled) return;
        const { positions: p, colors: c, scales: sc, count, totalCells, sampled } =
          cellsToInstanceBuffers(snap.cells);
        setPositions(p);
        setColors(c);
        setScales(sc);
        setCellCount(count);
        setVisualStats({ totalCells, sampled });
      })
      .catch((e) => {
        if (!cancelled) setActionError((e as Error).message);
      })
      .finally(() => {
        if (!cancelled) setSnapshotLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [worldId, currentT, availableKey]);

  const sliderDisabled = availableT.length === 0 || snapshotLoading;
  const err = createError || actionError || streamError;

  return (
    <div className="flex flex-col gap-6 max-w-4xl">
      <p className="text-sm text-slate-400">
        API: <code className="text-cyan-400/90">{getApiBase()}</code> ·{" "}
        <code className="text-slate-500">NEXT_PUBLIC_API_URL</code>
      </p>

      {err && (
        <div
          className="rounded-md border border-red-900/60 bg-red-950/40 px-3 py-2 text-sm text-red-200"
          role="alert"
        >
          {err}
        </div>
      )}

      <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
        <h2 className="text-sm font-medium text-slate-300">1. 세계 생성</h2>
        <div className="flex flex-wrap gap-4 items-end">
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            초기 세포 수
            <input
              type="number"
              min={1}
              max={500}
              value={initialCells}
              onChange={(e) => setInitialCells(Number(e.target.value))}
              className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-white w-24"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-400">
            t_max
            <input
              type="number"
              min={1}
              max={5000}
              value={tMaxInput}
              onChange={(e) => setTMaxInput(Number(e.target.value))}
              className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-white w-24"
            />
          </label>
          <button
            type="button"
            onClick={handleCreateWorld}
            className="rounded-md bg-cyan-700 hover:bg-cyan-600 px-4 py-2 text-sm font-medium"
          >
            세계 생성
          </button>
        </div>
        {worldId && (
          <p className="text-xs text-slate-500 font-mono break-all">
            world_id: {worldId}
          </p>
        )}
      </section>

      <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
        <h2 className="text-sm font-medium text-slate-300">2. 시뮬 실행</h2>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            disabled={!worldId || isRunning}
            onClick={handleRunStream}
            className="rounded-md bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 px-4 py-2 text-sm"
          >
            실행 (WebSocket 스트림)
          </button>
          <button
            type="button"
            disabled={!worldId || isRunning}
            onClick={handleRunSync}
            className="rounded-md bg-slate-600 hover:bg-slate-500 disabled:opacity-40 px-4 py-2 text-sm"
          >
            실행 (동기)
          </button>
        </div>
        {isRunning && (
          <p className="text-sm text-amber-200/90">
            실행 중…
            {liveT != null && (
              <>
                {" "}
                t = {liveT.toFixed(1)}, 세포 수 = {liveCellCount ?? "—"}
              </>
            )}
          </p>
        )}
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-medium text-slate-300">3. 시간 t → 스냅샷</h2>
        <TimeSlider
          t={currentT}
          tMin={tSliderMin}
          tMax={tSliderMax}
          step={1}
          onChange={setCurrentT}
          disabled={sliderDisabled}
        />
        {snapshotLoading && (
          <p className="text-xs text-slate-500">스냅샷 로딩…</p>
        )}
        {availableT.length === 0 && worldId && !isRunning && (
          <p className="text-xs text-slate-500">
            시뮬을 실행하면 슬라이더로 t를 탐색할 수 있습니다.
          </p>
        )}
      </section>

      <InjectPanel
        worldId={worldId}
        suggestedT={currentT}
        simRunning={isRunning}
        onInjected={handleInjected}
      />

      <ScenarioTimeline
        worldId={worldId}
        refreshKey={chartRefreshKey}
      />

      {visualStats?.sampled && (
        <p className="text-xs text-amber-200/80">
          시각화 샘플링: {cellCount.toLocaleString()}개 인스턴스 / 전체{" "}
          {visualStats.totalCells.toLocaleString()} 세포 (
          <code className="text-slate-400">NEXT_PUBLIC_MAX_VISUAL_CELLS</code>)
        </p>
      )}

      {mount3d ? (
        <R3fErrorBoundary>
          <Scene3DCanvas
            count={cellCount}
            positions={positions}
            colors={colors}
            scales={scales}
            maxInstances={getMaxVisualCellsLimit() + 256}
          />
        </R3fErrorBoundary>
      ) : (
        <div
          className="h-[min(70vh,560px)] w-full rounded-lg border border-slate-800 bg-slate-900/40 flex items-center justify-center text-sm text-slate-500"
          data-testid="scene-placeholder"
        >
          3D 씬 준비 중…
        </div>
      )}
    </div>
  );
}
