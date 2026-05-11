"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import SimulationMap2D from "@/components/SimulationMap2D";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { PersonaPreview } from "@/components/PersonaPreview";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import { ScenarioSummary } from "@/components/ScenarioSummary";
import { AppPanel } from "@/components/app-shell/AppPanel";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import {
  SimulationInspectorPanel,
  type SelectedBand,
  type SelectedZone,
} from "@/components/SimulationInspectorPanel";
import {
  TimelineBookmarks,
  type TimelineMarker,
} from "@/components/TimelineBookmarks";
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
  onOpenWorkbenchView,
}: {
  initialWorldId?: string | null;
  onOpenWorkbenchView?: (view: WorkbenchView) => void;
}) {
  const [stage, setStage] = useState<"setup" | "run">("setup");
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
  const [zMode, setZMode] = useState("hybrid");
  const [zWeight, setZWeight] = useState("0.08");
  const [zScale, setZScale] = useState("12.0");
  const [selectedAgent, setSelectedAgent] = useState<CellSnapshot | null>(null);
  const [selectedZone, setSelectedZone] = useState<SelectedZone | null>(null);
  const [selectedBand, setSelectedBand] = useState<SelectedBand | null>(null);
  const [bookmarks, setBookmarks] = useState<TimelineMarker[]>([]);
  const [eventMarkers, setEventMarkers] = useState<TimelineMarker[]>([]);
  const [layoutMode, setLayoutMode] = useState<"balanced" | "focus" | "wide-left">("balanced");

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
              z_mode: zMode,
              z_weight: parseNumber(zWeight),
              z_scale: parsePositiveNumber(zScale),
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
      setSelectedAgent(null);
      setSelectedZone(null);
      setSelectedBand(null);
      setBookmarks([]);
      setEventMarkers([]);
      setPersonaRefreshKey((k) => k + 1);
      setStage("run");
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
    zMode,
    zScale,
    zWeight,
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
  const timelineMarkers = useMemo(() => {
    const frameMarkers = availableT.slice(-12).map((value) => ({
      key: `frame-${value}`,
      t: value,
      label: `Saved frame ${value}`,
      kind: "frame" as const,
    }));
    const dedup = new Map<string, TimelineMarker>();
    [...frameMarkers, ...eventMarkers, ...bookmarks].forEach((marker) => {
      dedup.set(marker.key, marker);
    });
    return Array.from(dedup.values()).sort((a, b) => a.t - b.t);
  }, [availableT, bookmarks, eventMarkers]);

  const clearSelection = useCallback(() => {
    setSelectedAgent(null);
    setSelectedZone(null);
    setSelectedBand(null);
  }, []);

  const addBookmark = useCallback(() => {
    const key = `bookmark-${currentT}`;
    setBookmarks((prev) => {
      if (prev.some((item) => item.key === key)) return prev;
      return [
        ...prev,
        {
          key,
          t: currentT,
          label: `Bookmark t=${currentT}`,
          kind: "bookmark" as const,
        },
      ].sort((a, b) => a.t - b.t);
    });
  }, [currentT]);

  const removeBookmark = useCallback((key: string) => {
    setBookmarks((prev) => prev.filter((item) => item.key !== key));
  }, []);

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
        setStage("run");
      })
      .catch((e) => {
        if (!cancelled) setActionError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [initialWorldId]);

  return (
    <div className="godview-staged">
      <AppPanel
        title="Simulation Workspace"
        subtitle="Two-step setup and execution flow"
        bodyClassName="flex flex-wrap items-center justify-between gap-3"
      >
        <div className="godview-stage-switch">
          <button
            type="button"
            className={`godview-stage-switch__button ${stage === "setup" ? "is-active" : ""}`}
            onClick={() => setStage("setup")}
          >
            01 Setup
          </button>
          <button
            type="button"
            className={`godview-stage-switch__button ${stage === "run" ? "is-active" : ""}`}
            onClick={() => setStage("run")}
            disabled={!worldId}
          >
            02 Run
          </button>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenWorkbenchView?.("data-packs")}
          >
            Open Data Packs
          </button>
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenWorkbenchView?.("review-lab")}
          >
            Open Review Lab
          </button>
        </div>
      </AppPanel>

      {stage === "setup" ? (
        <div className="godview-setup">
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
            <AppPanel
              title="Scenario Genesis"
              subtitle="Prompt, persona packs, and world seed configuration"
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
                  <button type="button" onClick={() => setStage("run")} className="app-button app-button--secondary">
                    Open Run Stage
                  </button>
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
                  <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white/80 p-3 md:grid-cols-3">
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      z mode
                      <select value={zMode} onChange={(e) => setZMode(e.target.value)} className="app-input">
                        <option value="hybrid">hybrid</option>
                        <option value="wealth">wealth</option>
                        <option value="influence">influence</option>
                        <option value="policy">policy</option>
                        <option value="memory">memory</option>
                        <option value="flat">flat</option>
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      z weight
                      <input value={zWeight} onChange={(e) => setZWeight(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      z scale
                      <input value={zScale} onChange={(e) => setZScale(e.target.value)} className="app-input" />
                    </label>
                    <p className="md:col-span-3 rounded-2xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
                      `z` is treated as social elevation, not mesh height. Use `weight` to control how much elevation affects interaction distance, and `scale` to control field amplitude.
                    </p>
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
          </div>

          <div className="grid min-h-0 gap-4">
            <AppPanel
              title="Setup Checklist"
              subtitle="Prepare the world before entering live simulation"
              bodyClassName="grid gap-3 md:grid-cols-2"
            >
              <SetupItem index="01" title="Scenario Prompt" body="장기 정책/시장/사회 시나리오를 먼저 정의합니다." />
              <SetupItem index="02" title="Persona & Data Packs" body="국가별 persona pack과 source attribution을 확인합니다." />
              <SetupItem index="03" title="Genesis Controls" body="필요하면 God Mode에서 zone/z/role seed를 미세 조정합니다." />
              <SetupItem index="04" title="Enter Run Stage" body="world가 생성되면 Run 단계에서 실행·주입·탐색을 시작합니다." />
            </AppPanel>

            {lastGenesis ? (
              <GenesisMeta lastGenesis={lastGenesis} />
            ) : (
              <AppPanel
                title="Next Stage"
                subtitle="What unlocks after world creation"
                bodyClassName="space-y-3"
              >
                <p className="text-sm leading-7 text-slate-600">
                  world를 만든 뒤에는 실행 패널, 시뮬레이션 맵, 선택 상세 패널, 시간축 북마크,
                  정책 주입 패널이 모두 `Run` 단계에서 열립니다. 지금은 설정에 집중하고,
                  실행 중 분석은 다음 단계에서 분리해서 보게 됩니다.
                </p>
                <div className="grid gap-2 md:grid-cols-2">
                  <MetricChip label="Run stage" value="Execution + Map + Timeline" />
                  <MetricChip label="Review stage" value="Future LLM analysis workspace" />
                </div>
              </AppPanel>
            )}
          </div>
        </div>
      ) : (
        <div
          className={`godview-layout ${
            layoutMode === "focus"
              ? "godview-layout--focus"
              : layoutMode === "wide-left"
                ? "godview-layout--wide-left"
                : "godview-layout--balanced"
          }`}
        >
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
            <AppPanel
              title="Run Controls"
              subtitle="Execution, injections, and time navigation"
              bodyClassName="flex flex-wrap gap-2"
              action={
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => setStage("setup")}
                >
                  Back to Setup
                </button>
              }
            >
              <button
                type="button"
                className={`app-button ${layoutMode === "balanced" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => setLayoutMode("balanced")}
              >
                Balanced
              </button>
              <button
                type="button"
                className={`app-button ${layoutMode === "focus" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => setLayoutMode("focus")}
              >
                Focus Viz
              </button>
              <button
                type="button"
                className={`app-button ${layoutMode === "wide-left" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => setLayoutMode("wide-left")}
              >
                Wide Controls
              </button>
            </AppPanel>

            <RunPanel
              worldId={worldId}
              isRunning={isRunning}
              liveT={liveT}
              liveCellCount={liveCellCount}
              onRunStream={handleRunStream}
              onRunSync={handleRunSync}
            />

            <InjectPanel
              worldId={worldId}
              suggestedT={currentT}
              simRunning={isRunning}
              onInjected={async ({ t, eventType }) => {
                setEventMarkers((prev) => [
                  ...prev,
                  {
                    key: `inject-${t}-${eventType}-${prev.length}`,
                    t,
                    label: `${eventType} @ t=${t}`,
                    kind: "inject" as const,
                  },
                ]);
                await handleInjected();
              }}
            />

            <ScenarioSummary worldId={worldId} refreshKey={chartRefreshKey} />
          </div>

          <div className="grid min-h-0 gap-4 xl:grid-rows-[minmax(0,1fr)_auto]">
            <AppPanel
              title="Simulation View"
              subtitle="Belief dynamics, selection, and map-driven inspection"
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

              <div className="godview-main">
                <div className="rounded-3xl border border-slate-200 bg-white p-3 shadow-sm min-h-0">
                  <SimulationMap2D
                    cells={visibleCells}
                    totalCells={visualStats?.totalCells ?? visibleCells.length}
                    sampled={visualStats?.sampled ?? false}
                    selectedAgentId={selectedAgent?.cell_id ?? null}
                    selectedZoneId={selectedZone?.zoneId ?? null}
                    selectedBandKey={selectedBand?.key ?? null}
                    onSelectAgent={(cell) => {
                      setSelectedAgent(cell);
                      setSelectedZone(null);
                    }}
                    onSelectZone={(zone) => {
                      setSelectedZone(zone);
                      setSelectedAgent(null);
                    }}
                    onSelectBand={(band) => {
                      setSelectedBand(band);
                    }}
                  />
                </div>

                <div className="grid gap-3 content-start">
                  {lastGenesis ? <GenesisMeta lastGenesis={lastGenesis} /> : null}
                </div>

                <SimulationInspectorPanel
                  selectedAgent={selectedAgent}
                  selectedZone={selectedZone}
                  selectedBand={selectedBand}
                  worldSummary={{
                    worldId,
                    currentT,
                    visibleCount: visibleCells.length,
                    totalCount: visualStats?.totalCells ?? visibleCells.length,
                    sampled: visualStats?.sampled ?? false,
                  }}
                  onClearSelection={clearSelection}
                />
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
                <TimelineBookmarks
                  t={currentT}
                  tMin={tSliderMin}
                  tMax={Math.max(tSliderMin + 1, tSliderMax)}
                  markers={timelineMarkers}
                  bookmarks={bookmarks}
                  onJump={setCurrentT}
                  onAddBookmark={addBookmark}
                  onRemoveBookmark={removeBookmark}
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
      )}
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
            실행 중 · stream active
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
      subtitle="Initial simulation parameters and persona-aware genesis"
      bodyClassName="grid gap-3"
    >
      <MetricChip label="t_max" value={String(lastGenesis.t_max)} />
      <MetricChip label="Initial agents" value={String(lastGenesis.initial_cell_count)} />
      <MetricChip label="Step meaning" value={`${lastGenesis.t_step_semantic} (${lastGenesis.t_step_unit})`} />
      <MetricChip label="Nutrient" value={String(lastGenesis.nutrient_per_step)} />
      <MetricChip label="Roles" value={lastGenesis.role_catalog.join(", ")} />
      {lastGenesis.persona_distribution_summary ? (
        <MetricChip
          label="Persona seed"
          value={`${Number(lastGenesis.persona_distribution_summary.persona_count ?? 0)} personas`}
        />
      ) : null}
      <p className="rounded-2xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-600">
        {lastGenesis.rationale}
      </p>
    </AppPanel>
  );
}

function MetricChip({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className="mt-1 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function SetupItem({
  index,
  title,
  body,
}: {
  index: string;
  title: string;
  body: string;
}) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{index}</p>
      <p className="mt-2 text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-600">{body}</p>
    </div>
  );
}
