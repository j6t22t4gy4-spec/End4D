"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { R3fErrorBoundary } from "@/components/R3fErrorBoundary";
import Scene3DCanvas from "@/components/Scene3D/Scene3DCanvas";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { PersonaPreview } from "@/components/PersonaPreview";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import { ScenarioSummary } from "@/components/ScenarioSummary";
import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  createWorld,
  listSnapshotTimes,
  getSnapshotAtT,
  cellsToInstanceBuffers,
  getMaxVisualCellsLimit,
  type CreateWorldResult,
} from "@/lib/api";
import { useSimulation } from "@/hooks/useSimulation";

const PROMPT_PLACEHOLDER =
  "예: 향후 5년간 금리 인상과 주거 보조금이 동시에 시행되면, 시장·가계·정책 주체들이 어떤 장기 신념 변화를 보일까?";

export default function GodView() {
  const [genesisPrompt, setGenesisPrompt] = useState("");
  const [lastGenesis, setLastGenesis] = useState<CreateWorldResult | null>(null);
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
  const [mount3d, setMount3d] = useState(false);
  const [chartRefreshKey, setChartRefreshKey] = useState(0);
  const [personaRefreshKey, setPersonaRefreshKey] = useState(0);

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
  const err = createError || actionError || streamError;

  const handleCreateWorld = useCallback(async () => {
    setCreateError(null);
    setActionError(null);
    const prompt = genesisPrompt.trim();
    if (!prompt) {
      setCreateError("질의(프롬프트)를 입력해 주세요.");
      return;
    }
    try {
      disconnectWebSocket();
      const out = await createWorld({ prompt });
      setLastGenesis(out);
      setWorldId(out.world_id);
      setAvailableT([]);
      setCurrentT(0);
      setCellCount(0);
      setPositions(new Float32Array(0));
      setColors(new Float32Array(0));
      setScales(new Float32Array(0));
      setVisualStats(null);
      setPersonaRefreshKey((k) => k + 1);
      bumpChartRefresh();
    } catch (e) {
      setCreateError((e as Error).message);
    }
  }, [bumpChartRefresh, disconnectWebSocket, genesisPrompt]);

  const refreshSnapshots = useCallback(
    async (wid: string) => {
      const list = await listSnapshotTimes(wid);
      setAvailableT(list.available_t);
      const last = list.available_t[list.available_t.length - 1] ?? 0;
      setCurrentT(last);
      bumpChartRefresh();
    },
    [bumpChartRefresh]
  );

  const handleRunStream = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      await runWithWebSocketStream(worldId);
      await refreshSnapshots(worldId);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [refreshSnapshots, runWithWebSocketStream, worldId]);

  const handleRunSync = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      await runSync(worldId);
      await refreshSnapshots(worldId);
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [refreshSnapshots, runSync, worldId]);

  const handleInjected = useCallback(async () => {
    if (!worldId) return;
    await refreshSnapshots(worldId);
  }, [refreshSnapshots, worldId]);

  useEffect(() => {
    if (!worldId || availableT.length === 0) {
      if (availableT.length === 0 && worldId) {
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
        const {
          positions: p,
          colors: c,
          scales: sc,
          count,
          totalCells,
          sampled,
        } = cellsToInstanceBuffers(snap.cells);
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
  }, [availableKey, currentT, worldId]);

  const sliderDisabled = availableT.length === 0 || snapshotLoading;

  return (
    <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[320px_minmax(0,1fr)_340px]">
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
        <AppPanel
          title="Scenario Genesis"
          subtitle="Prompt-driven world creation"
          bodyClassName="space-y-4"
        >
          <label className="flex flex-col gap-2">
            <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
              Scenario prompt
            </span>
            <textarea
              value={genesisPrompt}
              onChange={(e) => setGenesisPrompt(e.target.value)}
              placeholder={PROMPT_PLACEHOLDER}
              rows={8}
              className="app-textarea"
            />
          </label>
          <div className="flex flex-wrap gap-2">
            <button type="button" onClick={handleCreateWorld} className="app-button app-button--primary">
              Create world
            </button>
            {worldId && (
              <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-medium text-slate-600">
                Active world loaded
              </span>
            )}
          </div>
          {worldId && (
            <p className="rounded-2xl bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-500">
              world_id: {worldId}
            </p>
          )}
        </AppPanel>

        <PersonaPreview worldId={worldId} refreshKey={personaRefreshKey} />
        <InjectPanel
          worldId={worldId}
          suggestedT={currentT}
          simRunning={isRunning}
          onInjected={handleInjected}
        />
      </div>

      <div className="grid min-h-0 gap-4 xl:grid-rows-[minmax(0,1fr)_auto]">
        <AppPanel
          title="Simulation View"
          subtitle="Belief dynamics and agent field"
          className="min-h-0"
          bodyClassName="flex h-full min-h-0 flex-col gap-4"
          action={
            visualStats?.sampled ? (
              <span className="rounded-full bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
                sampled {cellCount.toLocaleString()} / {visualStats.totalCells.toLocaleString()}
              </span>
            ) : undefined
          }
        >
          {err && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {err}
            </div>
          )}

          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
            <div className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm">
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
                  className="flex h-[min(62vh,540px)] items-center justify-center rounded-[24px] border border-dashed border-slate-300 bg-slate-50 text-sm text-slate-500"
                  data-testid="scene-placeholder"
                >
                  3D scene loading…
                </div>
              )}
            </div>

            <div className="grid gap-3 content-start">
              <RunPanel
                worldId={worldId}
                isRunning={isRunning}
                liveT={liveT}
                liveCellCount={liveCellCount}
                onRunStream={handleRunStream}
                onRunSync={handleRunSync}
              />
              <ScenarioSummary worldId={worldId} refreshKey={chartRefreshKey} />
              {lastGenesis && (
                <GenesisMeta lastGenesis={lastGenesis} />
              )}
            </div>
          </div>
        </AppPanel>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_380px]">
          <AppPanel
            title="Time Navigation"
            subtitle="Browse saved snapshots"
            bodyClassName="space-y-3"
          >
            <TimeSlider
              t={currentT}
              tMin={tSliderMin}
              tMax={tSliderMax}
              step={1}
              onChange={setCurrentT}
              disabled={sliderDisabled}
            />
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>
                {snapshotLoading
                  ? "스냅샷 로딩 중"
                  : availableT.length === 0 && worldId && !isRunning
                    ? "시뮬을 실행하면 스냅샷을 탐색할 수 있습니다."
                    : "저장된 t 시점을 탐색합니다."}
              </span>
              <span>{availableT.length} frames</span>
            </div>
          </AppPanel>

          <ScenarioTimeline worldId={worldId} refreshKey={chartRefreshKey} />
        </div>
      </div>

      <div className="hidden min-h-0 xl:flex xl:flex-col xl:gap-4 xl:overflow-y-auto xl:pr-1">
        <AppPanel
          title="Operator Notes"
          subtitle="Design separated from engine and data workflows"
          bodyClassName="space-y-3 text-sm leading-6 text-slate-600"
        >
          <p>
            툴바, 런처, 패널 시스템은 워크벤치 셸 컴포넌트로 분리되어 있습니다.
          </p>
          <p>
            엔진 로직은 그대로 `GodView`, 시뮬 훅, API 계층에서 계속 개발할 수 있게 유지합니다.
          </p>
        </AppPanel>

        <AppPanel
          title="Current Session"
          subtitle="Workspace health"
          bodyClassName="grid gap-3"
        >
          <MetricChip label="Cells in view" value={cellCount.toLocaleString()} />
          <MetricChip label="Snapshots" value={String(availableT.length)} />
          <MetricChip
            label="Simulation state"
            value={isRunning ? "Running" : worldId ? "Ready" : "Idle"}
          />
        </AppPanel>
      </div>
    </div>
  );
}

function RunPanel({
  worldId,
  isRunning,
  liveT,
  liveCellCount,
  onRunStream,
  onRunSync,
}: {
  worldId: string | null;
  isRunning: boolean;
  liveT: number | null;
  liveCellCount: number | null;
  onRunStream: () => Promise<void>;
  onRunSync: () => Promise<void>;
}) {
  return (
    <AppPanel
      title="Execution"
      subtitle="Run locally on this machine"
      bodyClassName="space-y-3"
    >
      <div className="grid gap-2">
        <button
          type="button"
          disabled={!worldId || isRunning}
          onClick={() => void onRunStream()}
          className="app-button app-button--success"
        >
          Run with stream
        </button>
        <button
          type="button"
          disabled={!worldId || isRunning}
          onClick={() => void onRunSync()}
          className="app-button app-button--secondary"
        >
          Run sync
        </button>
      </div>
      <div className="rounded-2xl bg-slate-50 px-3 py-3 text-sm text-slate-600">
        {isRunning ? (
          <>
            실행 중
            {liveT != null ? ` · t ${liveT.toFixed(1)}` : ""}
            {liveCellCount != null ? ` · ${liveCellCount} cells` : ""}
          </>
        ) : (
          "로컬 런타임이 준비되면 이 머신에서 바로 계산합니다."
        )}
      </div>
    </AppPanel>
  );
}

function GenesisMeta({ lastGenesis }: { lastGenesis: CreateWorldResult }) {
  return (
    <AppPanel
      title="World Proposal"
      subtitle="Initial simulation parameters"
      bodyClassName="grid gap-3"
    >
      <MetricChip label="t_max" value={String(lastGenesis.t_max)} />
      <MetricChip
        label="Initial agents"
        value={String(lastGenesis.initial_cell_count)}
      />
      <MetricChip
        label="Step meaning"
        value={`${lastGenesis.t_step_semantic} (${lastGenesis.t_step_unit})`}
      />
      <MetricChip
        label="Nutrient"
        value={String(lastGenesis.nutrient_per_step)}
      />
      <MetricChip
        label="Roles"
        value={lastGenesis.role_catalog.join(", ")}
      />
      <p className="rounded-2xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
        {lastGenesis.rationale}
      </p>
    </AppPanel>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}
