"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import SimulationMap2D from "@/components/SimulationMap2D";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { PersonaPreview } from "@/components/PersonaPreview";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import { ScenarioSummary } from "@/components/ScenarioSummary";
import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  createWorld,
  getWorld,
  listSnapshotTimes,
  getSnapshotAtT,
  sampleCellsForVisualization,
  type CreateWorldResult,
  type CellSnapshot,
  type GodModePayload,
} from "@/lib/api";
import { useSimulation } from "@/hooks/useSimulation";

const PROMPT_PLACEHOLDER =
  "예: 향후 5년간 금리 인상과 주거 보조금이 동시에 시행되면, 시장·가계·정책 주체들이 어떤 장기 신념 변화를 보일까?";

export default function GodView({
  initialWorldId = null,
}: {
  initialWorldId?: string | null;
}) {
  const [genesisPrompt, setGenesisPrompt] = useState("");
  const [lastGenesis, setLastGenesis] = useState<CreateWorldResult | null>(null);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [availableT, setAvailableT] = useState<number[]>([]);
  const [currentT, setCurrentT] = useState(0);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [visibleCells, setVisibleCells] = useState<CellSnapshot[]>([]);
  const [visualStats, setVisualStats] = useState<{
    totalCells: number;
    sampled: boolean;
  } | null>(null);
  const [createError, setCreateError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [chartRefreshKey, setChartRefreshKey] = useState(0);
  const [personaRefreshKey, setPersonaRefreshKey] = useState(0);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [godModeEnabled, setGodModeEnabled] = useState(false);
  const [autoRolesFromPersonas, setAutoRolesFromPersonas] = useState(true);
  const [customTMax, setCustomTMax] = useState("160");
  const [customInitialCells, setCustomInitialCells] = useState("16");
  const [customRoles, setCustomRoles] = useState("시민, 규제자, 시장참여자, 기업, 관측자");
  const [customCountry, setCustomCountry] = useState("KR");
  const [customNutrient, setCustomNutrient] = useState("1.0");
  const [customTUnit, setCustomTUnit] = useState("day");
  const [zoneCount, setZoneCount] = useState("4");
  const [zoneLayout, setZoneLayout] = useState("grid");
  const [zoneSpacing, setZoneSpacing] = useState("2.0");
  const [zoneInfluenceStep, setZoneInfluenceStep] = useState("0.08");
  const [zoneFrictionStep, setZoneFrictionStep] = useState("0.10");

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
      const godMode: GodModePayload | null = godModeEnabled
        ? {
            enabled: true,
            auto_roles_from_personas: autoRolesFromPersonas,
            overrides: {
              t_max: parsePositiveNumber(customTMax),
              initial_cell_count: parsePositiveInt(customInitialCells),
              role_catalog: splitRoles(customRoles),
              t_step_unit: customTUnit.trim() || undefined,
              nutrient_per_step: parsePositiveNumber(customNutrient),
              persona_country: customCountry.trim() || undefined,
            },
            engine_params: {
              zone_count: parsePositiveInt(zoneCount),
              zone_layout: zoneLayout,
              zone_spacing: parsePositiveNumber(zoneSpacing),
              zone_influence_step: parseNumber(zoneInfluenceStep),
              zone_friction_step: parseNumber(zoneFrictionStep),
            },
          }
        : null;
      const out = await createWorld({
        prompt,
        session_id: activeSessionId,
        god_mode: godMode,
      });
      setLastGenesis(out);
      setWorldId(out.world_id);
      setActiveSessionId(out.session_id);
      setAvailableT([]);
      setCurrentT(0);
      setVisibleCells([]);
      setVisualStats(null);
      setPersonaRefreshKey((k) => k + 1);
      bumpChartRefresh();
    } catch (e) {
      setCreateError((e as Error).message);
    }
  }, [
    activeSessionId,
    autoRolesFromPersonas,
    bumpChartRefresh,
    customCountry,
    customInitialCells,
    customNutrient,
    customRoles,
    customTMax,
    customTUnit,
    disconnectWebSocket,
    genesisPrompt,
    godModeEnabled,
    zoneCount,
    zoneFrictionStep,
    zoneInfluenceStep,
    zoneLayout,
    zoneSpacing,
  ]);

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
        setVisibleCells([]);
        setVisualStats(null);
      }
      return;
    }

    let cancelled = false;
    setSnapshotLoading(true);
    getSnapshotAtT(worldId, currentT)
      .then((snap) => {
        if (cancelled) return;
        const { cells, totalCells, sampled } = sampleCellsForVisualization(
          snap.cells
        );
        setVisibleCells(cells);
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

  useEffect(() => {
    if (!initialWorldId) return;
    let cancelled = false;
    setActionError(null);
    Promise.all([getWorld(initialWorldId), listSnapshotTimes(initialWorldId)])
      .then(([meta, snapshots]) => {
        if (cancelled) return;
        setWorldId(meta.world_id);
        setGenesisPrompt(meta.genesis_prompt ?? "");
        setAvailableT(snapshots.available_t);
        const lastT = snapshots.available_t[snapshots.available_t.length - 1] ?? 0;
        setCurrentT(lastT);
      })
      .catch((e) => {
        if (!cancelled) setActionError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [initialWorldId]);

  return (
    <div className="grid h-full min-h-0 gap-4 xl:grid-cols-[300px_minmax(0,1fr)]">
      <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
        <AppPanel
          title="Scenario Genesis"
          subtitle="Prompt-driven world creation"
          bodyClassName="space-y-4"
          action={
            <label className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
              <input
                type="checkbox"
                checked={godModeEnabled}
                onChange={(e) => setGodModeEnabled(e.target.checked)}
              />
              God Mode
            </label>
          }
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
          {godModeEnabled && (
            <div className="grid gap-3 rounded-[22px] border border-slate-200 bg-slate-50/90 p-4">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  t_max
                  <input value={customTMax} onChange={(e) => setCustomTMax(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  initial cells
                  <input value={customInitialCells} onChange={(e) => setCustomInitialCells(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500 md:col-span-2">
                  roles (comma separated)
                  <input value={customRoles} onChange={(e) => setCustomRoles(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  persona country
                  <input value={customCountry} onChange={(e) => setCustomCountry(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  nutrient / step
                  <input value={customNutrient} onChange={(e) => setCustomNutrient(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  time unit
                  <select value={customTUnit} onChange={(e) => setCustomTUnit(e.target.value)} className="app-input">
                    <option value="hour">hour</option>
                    <option value="day">day</option>
                    <option value="month">month</option>
                    <option value="year">year</option>
                    <option value="decade_scale">decade_scale</option>
                  </select>
                </label>
                <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={autoRolesFromPersonas}
                    onChange={(e) => setAutoRolesFromPersonas(e.target.checked)}
                  />
                  persona roles auto-merge
                </label>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  zone count
                  <input value={zoneCount} onChange={(e) => setZoneCount(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  zone layout
                  <select value={zoneLayout} onChange={(e) => setZoneLayout(e.target.value)} className="app-input">
                    <option value="grid">grid</option>
                    <option value="bands">bands</option>
                    <option value="ring">ring</option>
                  </select>
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  zone spacing
                  <input value={zoneSpacing} onChange={(e) => setZoneSpacing(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  influence step
                  <input value={zoneInfluenceStep} onChange={(e) => setZoneInfluenceStep(e.target.value)} className="app-input" />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  friction step
                  <input value={zoneFrictionStep} onChange={(e) => setZoneFrictionStep(e.target.value)} className="app-input" />
                </label>
              </div>
            </div>
          )}
          {worldId && (
            <div className="grid gap-2">
              <p className="rounded-2xl bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-500">
                world_id: {worldId}
              </p>
              <p className="rounded-2xl bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-500">
                session_id: {activeSessionId ?? "pending"}
              </p>
            </div>
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
                sampled {visibleCells.length.toLocaleString()} / {visualStats.totalCells.toLocaleString()}
              </span>
            ) : undefined
          }
        >
          {err && (
            <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
              {err}
            </div>
          )}

          <div className="grid min-h-0 gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
            <div className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm">
              <SimulationMap2D
                cells={visibleCells}
                totalCells={visualStats?.totalCells ?? visibleCells.length}
                sampled={visualStats?.sampled ?? false}
              />
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

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_420px]">
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

    </div>
  );
}

function parsePositiveInt(value: string): number | undefined {
  const parsed = parseInt(value, 10);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function parsePositiveNumber(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > 0 ? parsed : undefined;
}

function parseNumber(value: string): number | undefined {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function splitRoles(value: string): string[] | undefined {
  const roles = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return roles.length ? roles : undefined;
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
