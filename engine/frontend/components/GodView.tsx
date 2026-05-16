"use client";

import { useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from "react";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { PersonaPreview } from "@/components/PersonaPreview";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import { ScenarioSummary } from "@/components/ScenarioSummary";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { CenterMapShell } from "@/components/center-map/CenterMapShell";
import { ChatPanel } from "@/components/ChatPanel";
import { SwarmV2Workspace, type SwarmV2Telemetry } from "@/components/swarm-v2/SwarmV2Workspace";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import type { SessionSummary } from "@/lib/api";
import {
  SimulationInspectorPanel,
  type SelectedBand,
  type SelectedZone,
} from "@/components/SimulationInspectorPanel";
import type { TimelineMarker } from "@/components/TimelineBookmarks";
import {
  createWorld,
  getLocalRuntimeStatus,
  getReviewSummary,
  getWorld,
  installRuntimeDataPack,
  listSnapshotTimes,
  pinRuntimeDataPack,
  getSnapshotAtT,
  sampleCellsForVisualization,
  syncDataPacks,
  testRuntimeLlmConfig,
  updateRuntimeLlmConfig,
  updateWorldRuntimeConfig,
  type CreateWorldResult,
  type CellSnapshot,
  type CollectiveDynamicsListItem,
  type CollectiveDynamicsSummary,
  type GodModePayload,
  type LocalRuntimeStatus,
  type ReviewSummaryResponse,
  type RuntimeLlmTestResponse,
  type IntraTSceneEvent,
  type IntraTSceneMetrics,
  type RuntimeTiming,
  type SocialActionRecord,
  type SwarmV2RunResponse,
  verifyRuntimeDataPack,
} from "@/lib/api";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";
import { socialFieldActionLabel, socialFieldToneFromRecord, socialFieldToneLabel } from "@/lib/socialFieldActions";
import { useSimulation } from "@/hooks/useSimulation";

const PROMPT_PLACEHOLDER =
  "예: 향후 5년간 금리 인상과 주거 보조금이 동시에 시행되면, 시장·가계·정책 주체들이 어떤 장기 신념 변화를 보일까?";
const IMPORTANT_LLM_TASKS = [
  "thought",
  "worldview",
  "action",
  "policy",
  "dialogue",
  "group_deliberation",
  "review_summary",
  "review_diff",
  "agent_interview",
  "agent_interview_diff",
] as const;

const LLM_RUNTIME_PROFILE_PRESETS: Record<string, { cycleBudget: string; agentSample: string; dialoguePairs: string; deliberationGroups: string }> = {
  "rules-first": {
    cycleBudget: "96",
    agentSample: "96",
    dialoguePairs: "64",
    deliberationGroups: "12",
  },
  balanced: {
    cycleBudget: "160",
    agentSample: "256",
    dialoguePairs: "64",
    deliberationGroups: "12",
  },
  "llm-first": {
    cycleBudget: "1200",
    agentSample: "2048",
    dialoguePairs: "320",
    deliberationGroups: "40",
  },
};

const CYCLE_BUDGET_OPTIONS = ["96", "160", "320", "640", "1200", "2048"];
const AGENT_SAMPLE_OPTIONS = ["64", "96", "256", "512", "1024", "2048", "4096"];
const DIALOGUE_PAIR_OPTIONS = ["16", "32", "64", "128", "320"];
const DELIBERATION_GROUP_OPTIONS = ["4", "8", "12", "24", "40", "64"];
const TASK_BUDGET_OPTIONS = ["1", "2", "4", "8", "16", "32", "64", "128", "256", "512", "1024"];
const TASK_PRIORITY_OPTIONS = ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"];
const SWARM_AGENT_OPTIONS = ["512", "1000", "2000", "5000"];
const SWARM_MESO_OPTIONS = ["8", "16", "24", "40", "64"];

type SimulationMode = "precision" | "swarm";
type SwarmLlmMode = "packet" | "agent" | "full-agent";
type SetupRuntimeTab = "swarm-v2" | "legacy";

const LLM_PROVIDER_PRESETS = [
  {
    id: "openai",
    label: "OpenAI",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    models: ["gpt-5-nano", "gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
  },
  {
    id: "ollama",
    label: "Ollama Local",
    provider: "ollama",
    baseUrl: "http://127.0.0.1:11434",
    models: ["llama3.1", "qwen2.5", "deepseek-r1:8b"],
  },
  {
    id: "compatible",
    label: "OpenAI-Compatible",
    provider: "openai-compatible",
    baseUrl: "http://127.0.0.1:8000/v1",
    models: ["custom-model", "local-compatible-model"],
  },
] as const;

type LlmProviderPreset = (typeof LLM_PROVIDER_PRESETS)[number];

export default function GodView({
  locale = "ko",
  initialWorldId = null,
  initialT = null,
  sessions = [],
  initialInjectPreset = null,
  onOpenWorkbenchView,
  onWorldSelected,
  onConsumeInitialInjectPreset,
  runtimeStatusExternal,
  runtimeErrorExternal,
  onRefreshRuntimeExternal,
  onDockPayloadChange,
}: {
  locale?: UiLocale;
  initialWorldId?: string | null;
  initialT?: number | null;
  sessions?: SessionSummary[];
  initialInjectPreset?: ReviewSummaryResponse["inject_presets"][number] | null;
  onOpenWorkbenchView?: (view: WorkbenchView) => void;
  onWorldSelected?: (worldId: string) => void;
  onConsumeInitialInjectPreset?: () => void;
  runtimeStatusExternal?: LocalRuntimeStatus | null;
  runtimeErrorExternal?: string | null;
  onRefreshRuntimeExternal?: () => Promise<void> | void;
  onDockPayloadChange?: (payload: {
    timeControlContent?: ReactNode;
    controlsContent: ReactNode;
    runtimeContent: ReactNode;
    llmCallsContent?: ReactNode;
    insightContent?: ReactNode;
    chatContent?: ReactNode;
    thoughtCells: CellSnapshot[];
    actionRecords?: SocialActionRecord[];
    runtimeTiming?: RuntimeTiming | null;
    currentT: number;
    collectiveSummary: CollectiveDynamicsSummary | null;
    collectiveSignal: string;
    connectionState: {
      key: string;
      label: string;
      tone: "green" | "amber" | "red";
      detail: string;
    };
  } | null) => void;
}) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const [stage, setStage] = useState<"setup" | "run" | "review">("setup");
  const [setupRuntimeTab, setSetupRuntimeTab] = useState<SetupRuntimeTab>("swarm-v2");
  const [simulationMode, setSimulationMode] = useState<SimulationMode>("swarm");
  const [swarmAgentCount, setSwarmAgentCount] = useState("2000");
  const [swarmMesoGroups, setSwarmMesoGroups] = useState("40");
  const [swarmLlmMode, setSwarmLlmMode] = useState<SwarmLlmMode>("agent");
  const [genesisPrompt, setGenesisPrompt] = useState("");
  const [lastGenesis, setLastGenesis] = useState<CreateWorldResult | null>(null);
  const [swarmV2Result, setSwarmV2Result] = useState<SwarmV2RunResponse | null>(null);
  const [swarmV2Telemetry, setSwarmV2Telemetry] = useState<SwarmV2Telemetry | null>(null);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [availableT, setAvailableT] = useState<number[]>([]);
  const [currentT, setCurrentT] = useState(0);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotCells, setSnapshotCells] = useState<CellSnapshot[]>([]);
  const [snapshotSceneEvents, setSnapshotSceneEvents] = useState<IntraTSceneEvent[]>([]);
  const [snapshotSceneMetrics, setSnapshotSceneMetrics] = useState<IntraTSceneMetrics | null>(null);
  const [sceneReplayPaused, setSceneReplayPaused] = useState(false);
  const [sceneReplayIndex, setSceneReplayIndex] = useState(0);
  const [sceneReplaySpeed, setSceneReplaySpeed] = useState(1);
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
  const [godModeEnabled, setGodModeEnabled] = useState(true);
  const [godRoleMode, setGodRoleMode] = useState<"auto" | "manual">("auto");
  const [customTMax, setCustomTMax] = useState("160");
  const [customInitialCells, setCustomInitialCells] = useState("240");
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
  const [streamDensity, setStreamDensity] = useState("1.8");
  const [streamDelayMs, setStreamDelayMs] = useState("2");
  const [streamEpisodeMinDurationMs, setStreamEpisodeMinDurationMs] = useState("1200");
  const [streamMinRounds, setStreamMinRounds] = useState("24");
  const [streamMaxRounds, setStreamMaxRounds] = useState("48");
  const [streamMaxActiveAgents, setStreamMaxActiveAgents] = useState("900");
  const [streamInitialAgentRatio, setStreamInitialAgentRatio] = useState("0.22");
  const [streamGrowthRate, setStreamGrowthRate] = useState("1.55");
  const [streamMaxNeighbors, setStreamMaxNeighbors] = useState("12");
  const [savedGodConfigKey, setSavedGodConfigKey] = useState<string | null>(null);
  const [savedGodConfig, setSavedGodConfig] = useState<GodModePayload | null>(null);
  const [godConfigStatus, setGodConfigStatus] = useState<string | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<CellSnapshot | null>(null);
  const [selectedZone, setSelectedZone] = useState<SelectedZone | null>(null);
  const [selectedBand, setSelectedBand] = useState<SelectedBand | null>(null);
  const [collectiveSummary, setCollectiveSummary] = useState<CollectiveDynamicsSummary | null>(null);
  const [collectiveSignal, setCollectiveSignal] = useState("stable");
  const [bookmarks, setBookmarks] = useState<TimelineMarker[]>([]);
  const [eventMarkers, setEventMarkers] = useState<TimelineMarker[]>([]);
  const [layoutMode, setLayoutMode] = useState<"balanced" | "focus" | "wide-left">("balanced");
  const [autoFitLayout, setAutoFitLayout] = useState(true);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummaryResponse | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewRevisionKey, setReviewRevisionKey] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<LocalRuntimeStatus | null>(null);
  const [runtimeLoading, setRuntimeLoading] = useState(false);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [selectedPackId, setSelectedPackId] = useState("nemotron-kr-core");
  const [installSourcePath, setInstallSourcePath] = useState("");
  const [pinVersion, setPinVersion] = useState("2026.05");
  const [packActionStatus, setPackActionStatus] = useState<string | null>(null);
  const [reviewInjectPreset, setReviewInjectPreset] = useState<{
    label: string;
    t: number;
    eventType: string;
    payload: Record<string, unknown>;
  } | null>(null);
  const [llmEnabled, setLlmEnabled] = useState(false);
  const [llmProviderPreset, setLlmProviderPreset] = useState("openai");
  const [llmProvider, setLlmProvider] = useState("openai");
  const [llmModelPreset, setLlmModelPreset] = useState("gpt-4.1-mini");
  const [llmModel, setLlmModel] = useState("gpt-4.1-mini");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmTemperature, setLlmTemperature] = useState("0.2");
  const [llmTimeout, setLlmTimeout] = useState("20");
  const [llmRuntimeProfile, setLlmRuntimeProfile] = useState("balanced");
  const [llmStrictMode, setLlmStrictMode] = useState("adaptive");
  const [llmCycleBudget, setLlmCycleBudget] = useState("160");
  const [llmAgentSampleSize, setLlmAgentSampleSize] = useState("256");
  const [llmDialoguePairs, setLlmDialoguePairs] = useState("64");
  const [llmDeliberationGroups, setLlmDeliberationGroups] = useState("12");
  const [taskBudgetDraft, setTaskBudgetDraft] = useState<Record<string, string>>({});
  const [taskPriorityDraft, setTaskPriorityDraft] = useState<Record<string, string>>({});
  const [llmConfigStatus, setLlmConfigStatus] = useState<string | null>(null);
  const [llmTestResult, setLlmTestResult] = useState<RuntimeLlmTestResponse | null>(null);
  const [llmTestedConfigKey, setLlmTestedConfigKey] = useState<string | null>(null);
  const usesExternalRuntime = runtimeStatusExternal !== undefined;
  const hydratedInitialWorldKeyRef = useRef<string | null>(null);
  const lastSwarmV2RuntimeRefreshRef = useRef(0);

  const godConfigKey = useMemo(
    () =>
      JSON.stringify({
        enabled: godModeEnabled,
        roleMode: godRoleMode,
        tMax: customTMax,
        initialCells: customInitialCells,
        roles: customRoles,
        country: customCountry,
        nutrient: customNutrient,
        tUnit: customTUnit,
        zoneCount,
        zoneLayout,
        zoneSpacing,
        zoneInfluenceStep,
        zoneFrictionStep,
        zMode,
        zWeight,
        zScale,
        streamDensity,
        streamDelayMs,
        streamEpisodeMinDurationMs,
        streamMinRounds,
        streamMaxRounds,
        streamMaxActiveAgents,
        streamInitialAgentRatio,
        streamGrowthRate,
        streamMaxNeighbors,
        simulationMode,
        swarmAgentCount,
        swarmMesoGroups,
        swarmLlmMode,
      }),
    [
      customCountry,
      customInitialCells,
      customNutrient,
      customRoles,
      customTMax,
      customTUnit,
      godModeEnabled,
      godRoleMode,
      simulationMode,
      streamDelayMs,
      streamDensity,
      streamEpisodeMinDurationMs,
      streamGrowthRate,
      streamInitialAgentRatio,
      streamMaxActiveAgents,
      streamMaxNeighbors,
      streamMaxRounds,
      streamMinRounds,
      swarmAgentCount,
      swarmLlmMode,
      swarmMesoGroups,
      zMode,
      zScale,
      zWeight,
      zoneCount,
      zoneFrictionStep,
      zoneInfluenceStep,
      zoneLayout,
      zoneSpacing,
    ]
  );

  const godConfigDirty = savedGodConfigKey !== godConfigKey;

  const buildGodConfigPayload = useCallback((): GodModePayload => {
    const swarmEnabled = simulationMode === "swarm";
    return {
      enabled: true,
      auto_roles_from_personas: godRoleMode === "auto",
      overrides: {
        t_max: parsePositiveNumber(customTMax),
        initial_cell_count: parsePositiveInt(swarmEnabled ? swarmAgentCount : customInitialCells),
        role_catalog: godRoleMode === "manual" ? splitRoles(customRoles) : undefined,
        simulation_mode: simulationMode,
        t_step_unit: parseAutoText(customTUnit),
        nutrient_per_step: parsePositiveNumber(customNutrient),
        persona_country: parseAutoText(customCountry),
      },
      engine_params: {
        simulation_mode: simulationMode,
        swarm_llm_mode: swarmLlmMode,
        swarm_tier_model: {
          micro: { rule_based: true, visual_agents: parsePositiveInt(swarmAgentCount) },
          meso: { group_count: parsePositiveInt(swarmMesoGroups), llm_mode: swarmLlmMode },
          macro: { fields: ["pressure", "shock", "drift"] },
        },
        zone_count: parsePositiveInt(swarmEnabled ? swarmMesoGroups : zoneCount),
        zone_layout: parseAutoText(swarmEnabled ? "swarm" : zoneLayout),
        zone_spacing: parsePositiveNumber(swarmEnabled ? "1.25" : zoneSpacing),
        zone_influence_step: parseNumber(zoneInfluenceStep),
        zone_friction_step: parseNumber(zoneFrictionStep),
        z_mode: parseAutoText(zMode),
        z_weight: parseNumber(zWeight),
        z_scale: parsePositiveNumber(zScale),
        social_stream_density: parsePositiveNumber(streamDensity),
        scene_stream_delay_ms: parsePositiveNumber(streamDelayMs),
        stream_episode_min_duration_ms: parsePositiveNumber(streamEpisodeMinDurationMs),
        min_interactions_per_step: parsePositiveInt(streamMinRounds),
        max_interactions_per_step: parsePositiveInt(streamMaxRounds),
        swarm_stream_rounds: parsePositiveInt(streamMaxRounds),
        swarm_events_per_round: parsePositiveInt(streamMaxNeighbors),
        swarm_max_session_events: parsePositiveInt(streamMaxRounds) && parsePositiveInt(streamMaxNeighbors)
          ? Number(parsePositiveInt(streamMaxRounds)) * Number(parsePositiveInt(streamMaxNeighbors))
          : undefined,
        stream_topic_expansion: true,
        stream_max_active_agents: parsePositiveInt(streamMaxActiveAgents),
        stream_initial_agent_ratio: parsePositiveNumber(streamInitialAgentRatio),
        stream_growth_rate: parsePositiveNumber(streamGrowthRate),
        internal_max_neighbors: parsePositiveInt(streamMaxNeighbors),
        stream_llm_agent_feel: true,
        llm_agent_sample_size: parsePositiveInt(swarmAgentCount) ?? parsePositiveInt(customInitialCells),
      },
    };
  }, [
    customCountry,
    customInitialCells,
    customNutrient,
    customRoles,
    customTMax,
    customTUnit,
    godRoleMode,
    simulationMode,
    streamDelayMs,
    streamDensity,
    streamEpisodeMinDurationMs,
    streamGrowthRate,
    streamInitialAgentRatio,
    streamMaxActiveAgents,
    streamMaxNeighbors,
    streamMaxRounds,
    streamMinRounds,
    swarmAgentCount,
    swarmLlmMode,
    swarmMesoGroups,
    zMode,
    zScale,
    zWeight,
    zoneCount,
    zoneFrictionStep,
    zoneInfluenceStep,
    zoneLayout,
    zoneSpacing,
  ]);

  const saveGodConfig = useCallback(() => {
    setSavedGodConfig(buildGodConfigPayload());
    setSavedGodConfigKey(godConfigKey);
    setGodConfigStatus(isKo ? "생성 제어 설정 저장됨 · 다음 월드 생성에 적용됩니다" : "Genesis controls saved · applied to the next world creation");
  }, [buildGodConfigPayload, godConfigKey, isKo]);

  const bumpChartRefresh = useCallback(() => {
    setChartRefreshKey((k) => k + 1);
  }, []);

  const applySimulationMode = useCallback((mode: SimulationMode) => {
    setSimulationMode(mode);
    if (mode === "swarm") {
      setGodModeEnabled(true);
      setCustomInitialCells((value) => (Number.parseInt(value, 10) >= 512 ? value : "1000"));
      setCustomTMax((value) => (Number.parseInt(value, 10) >= 80 ? value : "120"));
      setZoneLayout("swarm");
      setZoneCount((value) => (Number.parseInt(value, 10) >= 8 ? value : "24"));
      setZoneSpacing("1.25");
      setZMode("policy");
      setZWeight("0.05");
      setZScale("8.0");
      setStreamDensity("2.2");
      setStreamDelayMs("0");
      setStreamEpisodeMinDurationMs("0");
      setStreamMinRounds("28");
      setStreamMaxRounds("56");
      setStreamMaxActiveAgents("900");
      setStreamInitialAgentRatio("0.18");
      setStreamGrowthRate("1.7");
      setStreamMaxNeighbors("16");
      setLlmRuntimeProfile("balanced");
      setLlmCycleBudget("160");
      setLlmAgentSampleSize("256");
      setLlmDialoguePairs("32");
      setLlmDeliberationGroups("24");
    } else {
      setZoneLayout((value) => (value === "swarm" ? "grid" : value));
    }
  }, []);

  const {
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
  } = useSimulation();

  const applyRuntimePayload = useCallback(
    (payload: LocalRuntimeStatus) => {
      setRuntimeStatus(payload);
      setLlmEnabled(Boolean(payload.llm?.enabled));
      setLlmProvider(String(payload.llm?.provider || "openai"));
      setLlmModel(String(payload.llm?.model || "gpt-4.1-mini"));
      setLlmBaseUrl(String(payload.llm?.base_url || ""));
      const matchedPreset =
        LLM_PROVIDER_PRESETS.find((item) => item.provider === String(payload.llm?.provider || "openai")) ?? null;
      const matchedPresetModels: string[] = matchedPreset ? [...matchedPreset.models] : [];
      setLlmProviderPreset(matchedPreset?.id ?? "custom");
      setLlmModelPreset(
        matchedPresetModels.includes(String(payload.llm?.model || "gpt-4.1-mini"))
          ? String(payload.llm?.model || "gpt-4.1-mini")
          : "custom"
      );
      setLlmRuntimeProfile(String(payload.llm?.runtime_profile || "balanced"));
      setLlmStrictMode(String(payload.llm?.strict_mode || payload.llm_runtime?.strict_mode || "adaptive"));
      setLlmCycleBudget(String(payload.llm_runtime?.cycle_prompt_budget || 160));
      setLlmAgentSampleSize(String(payload.llm_runtime?.agent_sample_size || 256));
      setLlmDialoguePairs(String(payload.llm_runtime?.dialogue_max_pairs || 64));
      setLlmDeliberationGroups(String(payload.llm_runtime?.group_deliberation_max_groups || 12));
      setTaskBudgetDraft(
        Object.fromEntries(
          Object.entries(payload.llm_runtime?.task_budgets ?? {}).map(([key, value]) => [key, String(value)])
        )
      );
      setTaskPriorityDraft(
        Object.fromEntries(
          Object.entries(payload.llm_runtime?.task_priorities ?? {}).map(([key, value]) => [key, String(value)])
        )
      );
      if (!selectedPackId && payload.packs[0]?.pack_id) {
        setSelectedPackId(payload.packs[0].pack_id);
      }
    },
    [selectedPackId]
  );

  const reloadRuntimeStatus = useCallback(async () => {
    const payload = await getLocalRuntimeStatus();
    applyRuntimePayload(payload);
    setRuntimeError(null);
    await onRefreshRuntimeExternal?.();
    return payload;
  }, [applyRuntimePayload, onRefreshRuntimeExternal]);

  useEffect(() => {
    if (stage !== "run" || setupRuntimeTab !== "swarm-v2") return;
    if (!swarmV2Telemetry?.running && swarmV2Telemetry?.status !== "complete") return;
    const now = Date.now();
    const shouldRefresh =
      swarmV2Telemetry.status === "complete" ||
      now - lastSwarmV2RuntimeRefreshRef.current > 1500;
    if (!shouldRefresh) return;
    lastSwarmV2RuntimeRefreshRef.current = now;
    void reloadRuntimeStatus().catch(() => undefined);
  }, [
    reloadRuntimeStatus,
    setupRuntimeTab,
    stage,
    swarmV2Telemetry?.eventCount,
    swarmV2Telemetry?.running,
    swarmV2Telemetry?.status,
  ]);

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
  const selectedPack = useMemo(
    () => runtimeStatus?.packs.find((pack) => pack.pack_id === selectedPackId) ?? runtimeStatus?.packs[0] ?? null,
    [runtimeStatus, selectedPackId]
  );
  const llmRuntime = runtimeStatus?.llm_runtime ?? null;
  const currentLlmConfigKey = useMemo(
    () =>
      JSON.stringify({
        enabled: llmEnabled,
        provider: llmProvider,
        model: llmModel,
        baseUrl: llmBaseUrl.trim(),
        apiKeySet: Boolean(llmApiKey.trim()),
        runtimeProfile: llmRuntimeProfile,
        strictMode: llmStrictMode,
        cycle: llmCycleBudget,
        sample: llmAgentSampleSize,
        dialogue: llmDialoguePairs,
        deliberation: llmDeliberationGroups,
        budgets: taskBudgetDraft,
        priorities: taskPriorityDraft,
      }),
    [
      llmAgentSampleSize,
      llmApiKey,
      llmBaseUrl,
      llmCycleBudget,
      llmDeliberationGroups,
      llmDialoguePairs,
      llmEnabled,
      llmModel,
      llmProvider,
      llmRuntimeProfile,
      llmStrictMode,
      taskBudgetDraft,
      taskPriorityDraft,
    ]
  );
  const llmConnectionState = useMemo(() => {
    if (!llmTestResult || llmTestedConfigKey !== currentLlmConfigKey) {
      return {
        key: "disconnect",
        label: isKo ? "disconnect" : "disconnect",
        tone: "red" as const,
        detail: isKo ? "연결 테스트 전" : "not tested yet",
      };
    }
    if (llmTestResult.ok) {
      return {
        key: "ready",
        label: "ready",
        tone: "green" as const,
        detail: isKo ? "연결 테스트 통과" : "connection test passed",
      };
    }
    return {
      key: "issue",
      label: isKo ? "issue" : "issue",
      tone: "amber" as const,
      detail: llmTestResult.fallback_reason || (isKo ? "연결 이상" : "connection issue"),
    };
  }, [currentLlmConfigKey, isKo, llmTestResult, llmTestedConfigKey]);
  const llmTaskRows = useMemo(
    () =>
      IMPORTANT_LLM_TASKS.map((task) => ({
        task,
        budget: taskBudgetDraft[task] ?? String(llmRuntime?.task_budgets?.[task] ?? ""),
        priority: taskPriorityDraft[task] ?? String(llmRuntime?.task_priorities?.[task] ?? ""),
        totals: llmRuntime?.task_totals?.[task],
      })),
    [llmRuntime, taskBudgetDraft, taskPriorityDraft]
  );
  const activeProviderPreset = useMemo(
    () => (LLM_PROVIDER_PRESETS.find((item) => item.provider === llmProvider) as LlmProviderPreset | undefined) ?? null,
    [llmProvider]
  );
  const availableModelPresets = useMemo(
    () => (activeProviderPreset?.models ? [...activeProviderPreset.models] : []),
    [activeProviderPreset]
  );

  useEffect(() => {
    if (!autoFitLayout) return;
    const applyAutoFit = () => {
      const width = window.innerWidth;
      if (width >= 1720) setLayoutMode("wide-left");
      else if (width >= 1380) setLayoutMode("balanced");
      else setLayoutMode("focus");
    };
    applyAutoFit();
    window.addEventListener("resize", applyAutoFit);
    return () => window.removeEventListener("resize", applyAutoFit);
  }, [autoFitLayout]);

  useEffect(() => {
    if (llmProviderPreset === "custom") return;
    const preset = LLM_PROVIDER_PRESETS.find((item) => item.id === llmProviderPreset);
    if (!preset) return;
    setLlmProvider(preset.provider);
    if (!llmBaseUrl.trim() || llmBaseUrl === activeProviderPreset?.baseUrl) {
      setLlmBaseUrl(preset.baseUrl);
    }
    const presetModels: string[] = [...preset.models];
    if (!presetModels.includes(llmModel)) {
      setLlmModel(presetModels[0] ?? llmModel);
      setLlmModelPreset(presetModels[0] ?? "custom");
    }
  }, [activeProviderPreset?.baseUrl, llmBaseUrl, llmModel, llmProviderPreset]);

  useEffect(() => {
    if (llmModelPreset === "custom") return;
    setLlmModel(llmModelPreset);
  }, [llmModelPreset]);

  useEffect(() => {
    if (!usesExternalRuntime) return;
    if (runtimeStatusExternal) {
      applyRuntimePayload(runtimeStatusExternal);
    } else {
      setRuntimeStatus(null);
    }
    setRuntimeError(runtimeErrorExternal ?? null);
  }, [applyRuntimePayload, runtimeErrorExternal, runtimeStatusExternal, usesExternalRuntime]);

  useEffect(() => {
    if (usesExternalRuntime) return;
    let cancelled = false;
    const refreshRuntime = async (firstLoad: boolean) => {
      if (firstLoad) {
        setRuntimeLoading(true);
        setRuntimeError(null);
      }
      try {
        const payload = await getLocalRuntimeStatus();
        if (cancelled) return;
        applyRuntimePayload(payload);
      } catch (reason) {
        if (!cancelled) {
          setRuntimeError(reason instanceof Error ? reason.message : "runtime status error");
        }
      } finally {
        if (!cancelled && firstLoad) setRuntimeLoading(false);
      }
    };
    refreshRuntime(true);
    const timer = window.setInterval(() => {
      refreshRuntime(false);
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [applyRuntimePayload, usesExternalRuntime]);

  const currentReviewRevisionKey = useMemo(() => {
    if (!worldId || availableT.length === 0) return null;
    return `${worldId}:${availableT[availableT.length - 1] ?? 0}`;
  }, [availableT, worldId]);

  useEffect(() => {
    if (!worldId || availableT.length === 0) {
      setReviewSummary(null);
      setReviewRevisionKey(null);
      setReviewLoading(false);
      setReviewError(null);
      return;
    }
    if (reviewRevisionKey === currentReviewRevisionKey && reviewSummary) {
      return;
    }
    let cancelled = false;
    setReviewLoading(true);
    setReviewError(null);
    getReviewSummary(worldId)
      .then((payload) => {
        if (!cancelled) {
          setReviewSummary(payload);
          setReviewRevisionKey(currentReviewRevisionKey);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setReviewSummary(null);
          setReviewRevisionKey(null);
          setReviewError(reason instanceof Error ? reason.message : "review summary error");
        }
      })
      .finally(() => {
        if (!cancelled) {
          setReviewLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [availableT.length, currentReviewRevisionKey, reviewRevisionKey, reviewSummary, worldId]);

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
      const swarmEnabled = simulationMode === "swarm";
      const currentGodConfig = buildGodConfigPayload();
      const godMode: GodModePayload | null = godModeEnabled || swarmEnabled ? (savedGodConfig && !godConfigDirty ? savedGodConfig : currentGodConfig) : null;
      const out = await createWorld({
        prompt,
        session_id: activeSessionId,
        god_mode: godMode,
      });
      if (godMode) {
        setSavedGodConfig(godMode);
        setSavedGodConfigKey(godConfigKey);
        setGodConfigStatus(
          godConfigDirty || !savedGodConfig
            ? isKo
              ? "현재 God mode 값을 자동 저장하고 월드를 생성했습니다"
              : "Auto-saved current God mode values and created the world"
            : isKo
              ? "이 설정으로 월드를 생성했습니다"
              : "World created with these saved controls"
        );
      }
      setLastGenesis(out);
      setWorldId(out.world_id);
      onWorldSelected?.(out.world_id);
      setActiveSessionId(out.session_id);
      setAvailableT([]);
      setCurrentT(0);
      setVisibleCells([]);
      setSnapshotCells([]);
      setVisualStats(null);
      setCollectiveSummary(null);
      setCollectiveSignal("stable");
      setReviewSummary(null);
      setReviewRevisionKey(null);
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
    buildGodConfigPayload,
    bumpChartRefresh,
    disconnectWebSocket,
    genesisPrompt,
    godConfigDirty,
    godConfigKey,
    godModeEnabled,
    isKo,
    onWorldSelected,
    savedGodConfig,
    simulationMode,
  ]);

  const refreshSnapshots = useCallback(
    async (wid: string, options?: { preferLatest?: boolean }) => {
      const list = await listSnapshotTimes(wid);
      setAvailableT(list.available_t);
      const last = list.available_t[list.available_t.length - 1] ?? 0;
      setCurrentT((previousT) => {
        if (options?.preferLatest) return last;
        if (list.available_t.length === 0) return 0;
        if (list.available_t.includes(previousT)) return previousT;
        return list.available_t.reduce((best, value) =>
          Math.abs(value - previousT) < Math.abs(best - previousT) ? value : best
        );
      });
      bumpChartRefresh();
    },
    [bumpChartRefresh]
  );

  const handleRunStream = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      const shouldApplyGodRuntime = godModeEnabled || simulationMode === "swarm";
      if (shouldApplyGodRuntime) {
        const runtimeConfig = savedGodConfig && !godConfigDirty ? savedGodConfig : buildGodConfigPayload();
        if (!savedGodConfig || godConfigDirty) {
          setSavedGodConfig(runtimeConfig);
          setSavedGodConfigKey(godConfigKey);
        }
        await updateWorldRuntimeConfig(worldId, {
          engine_params: runtimeConfig.engine_params,
          role_catalog: runtimeConfig.overrides?.role_catalog,
          initial_cell_count:
            parsePositiveInt(simulationMode === "swarm" ? swarmAgentCount : customInitialCells) ??
            runtimeConfig.overrides?.initial_cell_count,
        });
        setGodConfigStatus(
          !savedGodConfig || godConfigDirty
            ? isKo
              ? "현재 God mode 값을 자동 저장하고 현재 월드 런타임에 적용했습니다"
              : "Auto-saved current God mode values and applied them to this world runtime"
            : isKo
              ? "저장된 stream 설정을 현재 월드 런타임에 적용했습니다"
              : "Saved stream controls applied to this world runtime"
        );
      }
      await runWithWebSocketStream(worldId);
      await refreshSnapshots(worldId, { preferLatest: true });
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [buildGodConfigPayload, customInitialCells, godConfigDirty, godConfigKey, godModeEnabled, isKo, refreshSnapshots, runWithWebSocketStream, savedGodConfig, simulationMode, swarmAgentCount, worldId]);

  const handleRunSync = useCallback(async () => {
    if (!worldId) return;
    setActionError(null);
    try {
      await runSync(worldId);
      await refreshSnapshots(worldId, { preferLatest: true });
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [refreshSnapshots, runSync, worldId]);

  const handleStopStream = useCallback(async () => {
    await stopStream(worldId);
    if (worldId) {
      await refreshSnapshots(worldId, { preferLatest: true });
    }
  }, [refreshSnapshots, stopStream, worldId]);

  const handleInjected = useCallback(async () => {
    if (!worldId) return;
    await refreshSnapshots(worldId, { preferLatest: true });
  }, [refreshSnapshots, worldId]);

  useEffect(() => {
    if (!isRunning || !worldId) return;
    const liveTargetT = liveT;
    if (liveTargetT == null) return;
    const nextT = Math.max(0, Math.round(liveTargetT));
    setAvailableT((prev) => (prev.includes(nextT) ? prev : [...prev, nextT].sort((a, b) => a - b)));
    setCurrentT(nextT);
  }, [isRunning, liveT, worldId]);

  useEffect(() => {
    if (!worldId || availableT.length === 0) {
      if (availableT.length === 0 && worldId) {
        setVisibleCells([]);
        setSnapshotCells([]);
        setSnapshotSceneEvents([]);
        setSnapshotSceneMetrics(null);
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
          snap.cells,
          simulationMode === "swarm" ? 20000 : undefined
        );
        setSnapshotCells(snap.cells);
        setSnapshotSceneEvents(snap.scene_events ?? []);
        setSnapshotSceneMetrics(snap.scene_metrics ?? null);
        setSceneReplayIndex((snap.scene_events ?? []).length ? 1 : 0);
        setSceneReplayPaused(true);
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
  }, [availableKey, currentT, simulationMode, worldId]);

  const shouldUseLiveObserver =
    Boolean(isRunning) &&
    liveObserver != null &&
    (liveObserver?.cells?.length ?? 0) > 0;
  const shouldUseLiveSceneStream =
    Boolean(isRunning) &&
    liveSceneStream.events.length > 0;
  const observedT = shouldUseLiveSceneStream
    ? Number(liveSceneStream.observedT ?? liveSceneStream.latestEvent?.scene_t ?? liveSceneStream.currentT ?? currentT)
    : currentT;

  const renderedSnapshotCells = shouldUseLiveObserver ? liveObserver?.cells ?? [] : snapshotCells;
  const renderedVisibleCells = shouldUseLiveObserver ? liveObserver?.cells ?? [] : visibleCells;
  const renderedSceneEvents = shouldUseLiveSceneStream
    ? liveSceneStream.events
    : snapshotSceneEvents.slice(0, Math.max(0, Math.min(snapshotSceneEvents.length, sceneReplayIndex)));
  const renderedSceneMetrics = shouldUseLiveSceneStream ? liveSceneStream.metrics : snapshotSceneMetrics;

  useEffect(() => {
    if (shouldUseLiveSceneStream || sceneReplayPaused || snapshotSceneEvents.length === 0) return;
    if (sceneReplayIndex >= snapshotSceneEvents.length) return;
    const delay = Math.max(120, 520 / Math.max(0.5, sceneReplaySpeed));
    const timer = window.setTimeout(() => {
      setSceneReplayIndex((value) => Math.min(snapshotSceneEvents.length, value + 1));
    }, delay);
    return () => window.clearTimeout(timer);
  }, [sceneReplayIndex, sceneReplayPaused, sceneReplaySpeed, shouldUseLiveSceneStream, snapshotSceneEvents.length]);
  const renderedVisualStats = shouldUseLiveObserver
    ? {
        totalCells: liveObserver?.totalCells ?? renderedVisibleCells.length,
        sampled: Boolean(liveObserver?.sampled),
      }
    : visualStats;

  const renderedCollectiveSummary = useMemo(() => {
    if (shouldUseLiveObserver && liveObserver?.groupSummary) {
      return liveObserver.groupSummary;
    }
    const derived = buildCollectiveSummaryFromCells(renderedSnapshotCells);
    return derived ?? collectiveSummary;
  }, [collectiveSummary, liveObserver, renderedSnapshotCells, shouldUseLiveObserver]);

  const renderedCollectiveSignal = useMemo(() => {
    if (shouldUseLiveObserver && liveObserver?.groupSummary) {
      return inferCollectiveSignal(liveObserver.groupSummary);
    }
    if (renderedSnapshotCells.length) {
      return inferCollectiveSignalFromCells(renderedSnapshotCells);
    }
    return collectiveSignal;
  }, [collectiveSignal, liveObserver, renderedSnapshotCells, shouldUseLiveObserver]);

  useEffect(() => {
    if (!selectedAgent) return;
    const refreshed = renderedSnapshotCells.find((cell) => cell.cell_id === selectedAgent.cell_id);
    if (
        refreshed &&
        (
          refreshed.t !== selectedAgent.t ||
          refreshed.action_state?.last_thought_t !== selectedAgent.action_state?.last_thought_t ||
          refreshed.action_state?.last_thought_summary !== selectedAgent.action_state?.last_thought_summary ||
          refreshed.action_state?.role_group_cohesion !== selectedAgent.action_state?.role_group_cohesion ||
          refreshed.action_state?.zone_group_tension !== selectedAgent.action_state?.zone_group_tension ||
          refreshed.action_state?.collective_pressure !== selectedAgent.action_state?.collective_pressure
      )
    ) {
      setSelectedAgent(refreshed);
    }
  }, [renderedSnapshotCells, selectedAgent]);

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

  const reviewMarkers = useMemo(
    () =>
      (reviewSummary?.timeline_annotations ?? []).map((item, index) => ({
        key: `review-${index}-${item.t}`,
        t: item.t,
        label: item.label,
        kind: "annotation" as const,
        severity: item.severity,
        reason: item.reason,
      })),
    [reviewSummary]
  );

  const handleSaveLlmConfig = useCallback(async () => {
    setLlmConfigStatus(isKo ? "LLM 런타임 설정 저장 중…" : "saving llm runtime config…");
    try {
      await updateRuntimeLlmConfig({
        enabled: llmEnabled,
        provider: llmProvider,
        model: llmModel,
        base_url: llmBaseUrl,
        api_key: llmApiKey,
        temperature: Number(llmTemperature) || 0.2,
        timeout_s: Number(llmTimeout) || 20,
        runtime_profile: llmRuntimeProfile,
        strict_mode: llmStrictMode,
        cycle_prompt_budget: Number(llmCycleBudget) || 160,
        agent_sample_size: Number(llmAgentSampleSize) || 256,
        dialogue_max_pairs: Number(llmDialoguePairs) || 64,
        group_deliberation_max_groups: Number(llmDeliberationGroups) || 12,
        task_budgets: Object.fromEntries(Object.entries(taskBudgetDraft).map(([key, value]) => [key, Number(value) || 1])),
        task_priorities: Object.fromEntries(Object.entries(taskPriorityDraft).map(([key, value]) => [key, Number(value) || 0])),
        ui_language: locale,
      });
      setLlmTestResult(null);
      setLlmTestedConfigKey(null);
      await reloadRuntimeStatus();
      setLlmConfigStatus(isKo ? "LLM 런타임 저장 완료" : "llm runtime saved");
    } catch (reason) {
      setLlmConfigStatus(reason instanceof Error ? reason.message : isKo ? "LLM 설정 저장 실패" : "llm config save failed");
    }
  }, [
    isKo,
    llmAgentSampleSize,
    llmApiKey,
    llmBaseUrl,
    llmCycleBudget,
    llmDeliberationGroups,
    llmDialoguePairs,
    llmEnabled,
    llmModel,
    llmProvider,
    llmRuntimeProfile,
    llmStrictMode,
    llmTemperature,
    llmTimeout,
    locale,
    reloadRuntimeStatus,
    taskBudgetDraft,
    taskPriorityDraft,
  ]);

  const handleTestLlmConnection = useCallback(async () => {
    setLlmConfigStatus(isKo ? "LLM 연결 테스트 중…" : "testing llm connection…");
    try {
      const result = await testRuntimeLlmConfig();
      setLlmTestResult(result);
      setLlmTestedConfigKey(currentLlmConfigKey);
      await reloadRuntimeStatus();
      setLlmConfigStatus(
        result.ok
          ? isKo
            ? "LLM 테스트 완료"
            : "llm test completed"
          : `${isKo ? "LLM 테스트 실패" : "llm test failed"}: ${result.fallback_reason}`
      );
    } catch (reason) {
      setLlmConfigStatus(reason instanceof Error ? reason.message : isKo ? "LLM 테스트 실패" : "llm test failed");
    }
  }, [currentLlmConfigKey, isKo, reloadRuntimeStatus]);

  const controlsDockContent = useMemo(
    () => (
      <div className="space-y-3">
        <GodModePrepPanel
          locale={locale}
          enabled={godModeEnabled}
          onEnabledChange={setGodModeEnabled}
          godRoleMode={godRoleMode}
          onGodRoleModeChange={setGodRoleMode}
          customTMax={customTMax}
          onCustomTMaxChange={setCustomTMax}
          customInitialCells={customInitialCells}
          onCustomInitialCellsChange={setCustomInitialCells}
          customRoles={customRoles}
          onCustomRolesChange={setCustomRoles}
          customCountry={customCountry}
          onCustomCountryChange={setCustomCountry}
          customNutrient={customNutrient}
          onCustomNutrientChange={setCustomNutrient}
          customTUnit={customTUnit}
          onCustomTUnitChange={setCustomTUnit}
          zoneCount={zoneCount}
          onZoneCountChange={setZoneCount}
          zoneLayout={zoneLayout}
          onZoneLayoutChange={setZoneLayout}
          zoneSpacing={zoneSpacing}
          onZoneSpacingChange={setZoneSpacing}
          zoneInfluenceStep={zoneInfluenceStep}
          onZoneInfluenceStepChange={setZoneInfluenceStep}
          zoneFrictionStep={zoneFrictionStep}
          onZoneFrictionStepChange={setZoneFrictionStep}
          zMode={zMode}
          onZModeChange={setZMode}
          zWeight={zWeight}
          onZWeightChange={setZWeight}
          zScale={zScale}
          onZScaleChange={setZScale}
          streamDensity={streamDensity}
          onStreamDensityChange={setStreamDensity}
          streamDelayMs={streamDelayMs}
          onStreamDelayMsChange={setStreamDelayMs}
          streamEpisodeMinDurationMs={streamEpisodeMinDurationMs}
          onStreamEpisodeMinDurationMsChange={setStreamEpisodeMinDurationMs}
          streamMinRounds={streamMinRounds}
          onStreamMinRoundsChange={setStreamMinRounds}
          streamMaxRounds={streamMaxRounds}
          onStreamMaxRoundsChange={setStreamMaxRounds}
          streamMaxActiveAgents={streamMaxActiveAgents}
          onStreamMaxActiveAgentsChange={setStreamMaxActiveAgents}
          streamInitialAgentRatio={streamInitialAgentRatio}
          onStreamInitialAgentRatioChange={setStreamInitialAgentRatio}
          streamGrowthRate={streamGrowthRate}
          onStreamGrowthRateChange={setStreamGrowthRate}
          streamMaxNeighbors={streamMaxNeighbors}
          onStreamMaxNeighborsChange={setStreamMaxNeighbors}
          dirty={godConfigDirty}
          status={godConfigStatus}
          onSave={saveGodConfig}
        />
        <DataPackPrepPanel
          locale={locale}
          runtimeLoading={runtimeLoading}
          runtimeError={runtimeError}
          runtimeStatus={runtimeStatus}
          selectedPackId={selectedPack?.pack_id ?? ""}
          selectedPack={selectedPack}
          onSelectedPackIdChange={setSelectedPackId}
          installSourcePath={installSourcePath}
          onInstallSourcePathChange={setInstallSourcePath}
          pinVersion={pinVersion}
          onPinVersionChange={setPinVersion}
          packActionStatus={packActionStatus}
          onSync={async () => {
            setPackActionStatus("syncing manifest…");
            try {
              await syncDataPacks();
              await reloadRuntimeStatus();
              setPackActionStatus("manifest synced");
            } catch (reason) {
              setPackActionStatus(reason instanceof Error ? reason.message : "sync failed");
            }
          }}
          onVerify={async () => {
            if (!selectedPack) return;
            setPackActionStatus("verifying pack…");
            try {
              await verifyRuntimeDataPack(selectedPack.pack_id);
              await reloadRuntimeStatus();
              setPackActionStatus("verification complete");
            } catch (reason) {
              setPackActionStatus(reason instanceof Error ? reason.message : "verify failed");
            }
          }}
          onPin={async () => {
            if (!selectedPack || !pinVersion.trim()) return;
            setPackActionStatus("pinning pack…");
            try {
              await pinRuntimeDataPack(selectedPack.pack_id, pinVersion.trim());
              await reloadRuntimeStatus();
              setPackActionStatus("pin updated");
            } catch (reason) {
              setPackActionStatus(reason instanceof Error ? reason.message : "pin failed");
            }
          }}
          onInstall={async () => {
            if (!selectedPack || !installSourcePath.trim()) return;
            setPackActionStatus("installing pack…");
            try {
              await installRuntimeDataPack({
                pack_id: selectedPack.pack_id,
                source_path: installSourcePath.trim(),
                version: pinVersion.trim() || selectedPack.version,
                dataset_id: selectedPack.dataset_id,
                source_url: selectedPack.source_url,
              });
              await reloadRuntimeStatus();
              setPackActionStatus("install complete");
            } catch (reason) {
              setPackActionStatus(reason instanceof Error ? reason.message : "install failed");
            }
          }}
        />
        <RunPanel
          locale={locale}
          worldId={worldId}
          isRunning={isRunning}
          liveT={liveT}
          observedT={observedT}
          liveCellCount={liveCellCount}
          streamStatus={streamStatus}
          onRunStream={handleRunStream}
          onRunSync={handleRunSync}
          onStopStream={handleStopStream}
          compact
        />
        <IntraTScenePanel
          locale={locale}
          sceneStream={liveSceneStream}
          chapterT={currentT}
          snapshotEvents={snapshotSceneEvents}
          snapshotMetrics={snapshotSceneMetrics}
          renderedMetrics={renderedSceneMetrics}
          isRunning={isRunning}
          replayIndex={sceneReplayIndex}
          replayPaused={sceneReplayPaused}
          replaySpeed={sceneReplaySpeed}
          onReplayIndexChange={setSceneReplayIndex}
          onReplayPausedChange={setSceneReplayPaused}
          onReplaySpeedChange={setSceneReplaySpeed}
          selectedAgentId={selectedAgent?.cell_id ?? null}
          selectedGroupId={selectedZone?.zoneId ?? selectedAgent?.role_key ?? null}
        />
        <InjectPanel
          locale={locale}
          worldId={worldId}
          suggestedT={currentT}
          simRunning={isRunning}
          preset={reviewInjectPreset}
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
        <ScenarioTimeline
          locale={locale}
          worldId={worldId}
          refreshKey={chartRefreshKey}
          annotations={reviewSummary?.timeline_annotations ?? []}
          compact
          emergentCurve={
            ((reviewSummary?.emergent_dynamics?.worldview_curve as
              | Array<Record<string, unknown>>
              | undefined) ?? []
            ).map((item) => ({
              t: Number(item.t ?? 0),
              avg_z: Number(item.avg_z ?? 0),
              cell_count: Number(item.cell_count ?? 0),
            }))
          }
          onJumpToT={setCurrentT}
        />
        <ScenarioSummary worldId={worldId} refreshKey={chartRefreshKey} />
      </div>
    ),
    [
      chartRefreshKey,
      customCountry,
      customInitialCells,
      customNutrient,
      customRoles,
      customTMax,
      customTUnit,
      currentT,
      godModeEnabled,
      godRoleMode,
      handleInjected,
      handleRunStream,
      handleRunSync,
      installSourcePath,
      isKo,
      isRunning,
      liveCellCount,
      liveSceneStream,
      liveT,
      locale,
      packActionStatus,
      pinVersion,
      reloadRuntimeStatus,
      reviewInjectPreset,
      reviewSummary,
      runtimeError,
      runtimeLoading,
      runtimeStatus,
      selectedPack,
      streamDelayMs,
      streamDensity,
      streamEpisodeMinDurationMs,
      streamGrowthRate,
      streamInitialAgentRatio,
      streamMaxActiveAgents,
      streamMaxNeighbors,
      streamMaxRounds,
      streamMinRounds,
      worldId,
      zMode,
      zScale,
      godConfigDirty,
      godConfigStatus,
      saveGodConfig,
      zWeight,
      zoneCount,
      zoneFrictionStep,
      zoneInfluenceStep,
      zoneLayout,
      zoneSpacing,
    ]
  );

  const runtimeDockContent = useMemo(
    () => (
      <div className="space-y-3">
        <div className="grid gap-3">
          <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs font-semibold text-slate-700">
            <input type="checkbox" checked={llmEnabled} onChange={(event) => setLlmEnabled(event.target.checked)} />
            {isKo ? "실시간 LLM cognition 사용" : "enable live LLM cognition"}
          </label>
          <div className="grid grid-cols-2 gap-2">
            <ConnectionMetric
              label={isKo ? "현재 프로바이더" : "current provider"}
              value={runtimeStatus?.llm?.provider ?? "stub"}
              tone={llmConnectionState.tone}
              detail={runtimeStatus?.llm?.model ?? "stub"}
            />
            <ConnectionMetric
              label={isKo ? "연결 상태" : "connection"}
              value={llmConnectionState.label}
              tone={llmConnectionState.tone}
              detail={llmConnectionState.detail}
            />
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "연결 프리셋" : "connection preset"}
            <select className="app-input" value={llmProviderPreset} onChange={(event) => setLlmProviderPreset(event.target.value)}>
              {LLM_PROVIDER_PRESETS.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
              <option value="custom">{isKo ? "직접 입력" : "Custom"}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "프로바이더" : "provider"}
            <select
              className="app-input"
              value={llmProvider}
              onChange={(event) => {
                setLlmProviderPreset("custom");
                setLlmProvider(event.target.value);
              }}
            >
              <option value="openai">OpenAI</option>
              <option value="openai-compatible">OpenAI-compatible</option>
              <option value="ollama">Ollama</option>
              <option value="stub">Stub</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "추천 모델" : "model preset"}
            <select className="app-input" value={llmModelPreset} onChange={(event) => setLlmModelPreset(event.target.value)}>
              {availableModelPresets.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
              <option value="custom">{isKo ? "직접 입력" : "Custom"}</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "직접 모델 입력" : "custom model"}
            <input
              className="app-input"
              value={llmModel}
              onChange={(event) => {
                setLlmModelPreset("custom");
                setLlmModel(event.target.value);
              }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "직접 URL 입력" : "custom base url"}
            <input
              className="app-input"
              value={llmBaseUrl}
              onChange={(event) => {
                setLlmProviderPreset("custom");
                setLlmBaseUrl(event.target.value);
              }}
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "API 키" : "api key"}
            <input type="password" className="app-input" value={llmApiKey} onChange={(event) => setLlmApiKey(event.target.value)} />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "런타임 프로필" : "runtime profile"}
            <select
              className="app-input"
              value={llmRuntimeProfile}
              onChange={(event) => {
                const nextProfile = event.target.value;
                setLlmRuntimeProfile(nextProfile);
                const preset = LLM_RUNTIME_PROFILE_PRESETS[nextProfile];
                if (preset) {
                  setLlmCycleBudget(preset.cycleBudget);
                  setLlmAgentSampleSize(preset.agentSample);
                  setLlmDialoguePairs(preset.dialoguePairs);
                  setLlmDeliberationGroups(preset.deliberationGroups);
                }
              }}
            >
              <option value="rules-first">Rules-first</option>
              <option value="balanced">Balanced</option>
              <option value="llm-first">LLM-first</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "엄격 모드" : "strict mode"}
            <select className="app-input" value={llmStrictMode} onChange={(event) => setLlmStrictMode(event.target.value)}>
              <option value="adaptive">Adaptive</option>
              <option value="llm-preferred">LLM-preferred</option>
              <option value="fail-hard">Fail-hard</option>
            </select>
          </label>
        </div>
        <details className="group rounded-2xl border border-slate-200 bg-slate-50" open={false}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{isKo ? "태스크 예산" : "Task Budgets"}</p>
              <p className="mt-1 text-xs text-slate-500">
                {isKo ? "필요할 때만 펼쳐서 pressure를 조절합니다." : "Expand only when you need to tune task pressure."}
              </p>
            </div>
            <span className="text-xs font-medium text-slate-500 group-open:hidden">{isKo ? "접힘" : "Collapsed"}</span>
            <span className="hidden text-xs font-medium text-slate-500 group-open:inline">{isKo ? "열림" : "Open"}</span>
          </summary>
          <div className="grid gap-2 border-t border-slate-200 p-3">
            {llmTaskRows.map((row) => (
              <details key={row.task} className="rounded-2xl border border-slate-200 bg-white px-3 py-3" open={false}>
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-700">{row.task}</p>
                  <span className="text-[11px] text-slate-500">
                    live {row.totals?.prompt_count_sent ?? 0}/{row.totals?.prompt_count_in ?? 0}
                  </span>
                </summary>
                <div className="mt-3 grid gap-2 grid-cols-2">
                  <label className="flex flex-col gap-1 text-[11px] text-slate-500">
                    {isKo ? "예산" : "budget"}
                    <select className="app-input" value={row.budget} onChange={(event) => setTaskBudgetDraft((current) => ({ ...current, [row.task]: event.target.value }))}>
                      {TASK_BUDGET_OPTIONS.map((item) => (
                        <option key={`${row.task}-budget-${item}`} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-[11px] text-slate-500">
                    {isKo ? "우선순위" : "priority"}
                    <select className="app-input" value={row.priority} onChange={(event) => setTaskPriorityDraft((current) => ({ ...current, [row.task]: event.target.value }))}>
                      {TASK_PRIORITY_OPTIONS.map((item) => (
                        <option key={`${row.task}-priority-${item}`} value={item}>
                          {item}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              </details>
            ))}
          </div>
        </details>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="app-button app-button--ghost" onClick={() => void handleSaveLlmConfig()}>
            {isKo ? "LLM 설정 저장" : "Save LLM Config"}
          </button>
          <button type="button" className="app-button app-button--ghost" onClick={() => void handleTestLlmConnection()}>
            {isKo ? "연결 테스트" : "Test Connection"}
          </button>
        </div>
        {llmConfigStatus ? <p className="text-xs text-slate-500">{llmConfigStatus}</p> : null}
        {llmTestResult ? (
          <div className="session-thread-card">
            <div className="session-thread-card__header">
              <p className="session-thread-card__title">{isKo ? "LLM 테스트 결과" : "LLM Test Result"}</p>
              <span className="session-thread-card__meta">
                {llmTestResult.provider} · {llmTestResult.model}
              </span>
            </div>
            <p className="session-thread-card__prompt">{llmTestResult.preview}</p>
            <p className="text-xs text-slate-500">
              mode={llmTestResult.mode} · {isKo ? "폴백" : "fallback"}={String(llmTestResult.used_fallback)}
              {llmTestResult.fallback_reason ? ` · ${llmTestResult.fallback_reason}` : ""}
            </p>
          </div>
        ) : null}
        {reviewError ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-3 text-xs text-rose-700">
            <p className="font-semibold">{isKo ? "리뷰 실행 오류" : "Review Runtime Error"}</p>
            <p className="mt-1">{reviewError}</p>
          </div>
        ) : null}
      </div>
    ),
    [
      addBookmark,
      availableModelPresets,
      availableT.length,
      bookmarks,
      currentT,
      currentLlmConfigKey,
      handleSaveLlmConfig,
      handleTestLlmConnection,
      isKo,
      llmAgentSampleSize,
      llmApiKey,
      llmBaseUrl,
      llmConfigStatus,
      llmConnectionState.detail,
      llmConnectionState.label,
      llmConnectionState.tone,
      llmCycleBudget,
      llmDeliberationGroups,
      llmDialoguePairs,
      llmEnabled,
      llmModel,
      llmModelPreset,
      llmProvider,
      llmProviderPreset,
      llmRuntimeProfile,
      llmStrictMode,
      llmTaskRows,
      locale,
      reviewError,
      reviewMarkers,
      runtimeStatus?.llm?.model,
      runtimeStatus?.llm?.provider,
      sliderDisabled,
      taskBudgetDraft,
      taskPriorityDraft,
      timelineMarkers,
      tSliderMax,
      tSliderMin,
      llmTestResult,
    ]
  );

  const timeDockContent = useMemo(
    () => (
      <CompactTimeControl
        locale={locale}
        t={currentT}
        liveObservedT={isRunning ? observedT : null}
        tMin={tSliderMin}
        tMax={tSliderMax}
        frameCount={availableT.length}
        disabled={sliderDisabled || isRunning}
        isRunning={isRunning}
        markers={[...timelineMarkers, ...reviewMarkers]}
        bookmarks={bookmarks}
        onJump={setCurrentT}
        onAddBookmark={addBookmark}
        onRemoveBookmark={removeBookmark}
        compact
      />
    ),
    [
      addBookmark,
      availableT.length,
      bookmarks,
      currentT,
      isRunning,
      locale,
      observedT,
      reviewMarkers,
      sliderDisabled,
      timelineMarkers,
      tSliderMax,
      tSliderMin,
    ]
  );

  const insightDockContent = useMemo(
    () => (
      <SimulationInspectorPanel
        locale={locale}
        selectedAgent={selectedAgent}
        selectedZone={selectedZone}
        selectedBand={selectedBand}
        worldSummary={{
          worldId,
          currentT,
          visibleCount: renderedVisibleCells.length,
          totalCount: renderedVisualStats?.totalCells ?? renderedVisibleCells.length,
          sampled: renderedVisualStats?.sampled ?? false,
          collectiveSummary: renderedCollectiveSummary,
          collectiveSignal: renderedCollectiveSignal,
        }}
        agentRoster={renderedSnapshotCells}
        onSelectAgent={setSelectedAgent}
        onOpenWorldAt={(_, t) => {
          if (typeof t === "number") setCurrentT(t);
        }}
        onClearSelection={clearSelection}
      />
    ),
    [
      clearSelection,
      currentT,
      locale,
      renderedCollectiveSignal,
      renderedCollectiveSummary,
      renderedSnapshotCells,
      renderedVisibleCells.length,
      renderedVisualStats?.sampled,
      renderedVisualStats?.totalCells,
      selectedAgent,
      selectedBand,
      selectedZone,
      worldId,
    ]
  );

  const chatDockContent = useMemo(
    () => (
      <ChatPanel
        locale={locale}
        worldId={worldId}
        currentT={currentT}
        cells={renderedSnapshotCells}
        selectedAgent={selectedAgent}
        selectedZone={selectedZone}
      />
    ),
    [currentT, locale, renderedSnapshotCells, selectedAgent, selectedZone, worldId]
  );

  const swarmV2TimeDockContent = useMemo(
    () => (
      <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-3">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-700">Swarm V2 Session</p>
        <p className="mt-1 text-sm font-semibold text-slate-950">
          {swarmV2Telemetry?.sessionId ? swarmV2Telemetry.sessionId.slice(0, 8) : isKo ? "세션 대기" : "Idle"}
        </p>
        <div className="mt-3 h-2 overflow-hidden rounded-full bg-white">
          <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${swarmV2Telemetry?.activePercent ?? 0}%` }} />
        </div>
        <p className="mt-2 text-xs leading-5 text-slate-600">
          {isKo ? "V2는 t 슬라이더가 아니라 독립 세션 스트림을 기준으로 관찰합니다." : "V2 is observed as independent session streams, not a legacy t slider."}
        </p>
      </div>
    ),
    [isKo, swarmV2Telemetry?.activePercent, swarmV2Telemetry?.sessionId]
  );

  const swarmV2SessionDockContent = useMemo(
    () => (
      <div className="space-y-3">
        <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
                {isKo ? "세션 리드아웃" : "Session Readout"}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-950">
                {swarmV2Telemetry?.status ?? "idle"} · {swarmV2Telemetry?.currentPhase ?? "opening"}
              </p>
            </div>
            <button
              type="button"
              className="app-button app-button--ghost px-3 py-1 text-xs"
              onClick={() => setStage("setup")}
            >
              {isKo ? "준비" : "Setup"}
            </button>
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <MetricChip
              label={isKo ? "보이는 에이전트" : "visible agents"}
              value={`${swarmV2Telemetry?.visibleAgentCount ?? 0}/${swarmV2Telemetry?.totalAgents ?? swarmV2Result?.agent_count ?? 0}`}
            />
            <MetricChip
              label={isKo ? "이벤트" : "events"}
              value={`${swarmV2Telemetry?.eventCount ?? swarmV2Result?.events.length ?? 0}/${swarmV2Telemetry?.expectedEvents ?? swarmV2Result?.events.length ?? 0}`}
            />
            <MetricChip label="agent LLM" value={String(swarmV2Telemetry?.agentChannelCount ?? 0)} />
            <MetricChip label={isKo ? "응답 체인" : "reply chain"} value={String(swarmV2Telemetry?.replyChainCount ?? 0)} />
          </div>
          <div className="mt-3 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
            LLM {String((swarmV2Telemetry?.summary.llm as Record<string, unknown> | undefined)?.mode ?? swarmV2Telemetry?.llmMode ?? "packet")}
            {" · enriched "}
            {String((swarmV2Telemetry?.summary.llm as Record<string, unknown> | undefined)?.enriched_events ?? 0)}
            {" · samples "}
            {swarmV2Telemetry?.llmMode === "full-agent" ? "all" : String(swarmV2Telemetry?.llmSampleSize ?? 0)}
            {" · persisted "}
            {swarmV2Telemetry?.sessionId ? "yes" : "no"}
          </div>
          {swarmV2Telemetry?.thinkingEvent ? (
            <div className="mt-3 rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2 w-2 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex h-2 w-2 rounded-full bg-amber-500" />
                </span>
                <span className="font-semibold">
                  {isKo ? "지금 생각 중" : "Thinking now"}
                </span>
              </div>
              <p className="mt-1 text-amber-800/80">
                {swarmV2Telemetry.thinkingEvent.source_label || swarmV2Telemetry.thinkingEvent.source_id}
                {" → "}
                {swarmV2Telemetry.thinkingEvent.target_label || swarmV2Telemetry.thinkingEvent.target_id}
              </p>
              {swarmV2Telemetry.thinkingEvent.topic ? (
                <p className="mt-1 text-[11px] text-amber-700/75">{swarmV2Telemetry.thinkingEvent.topic}</p>
              ) : null}
            </div>
          ) : null}
          <div className="mt-3 rounded-2xl border border-sky-100 bg-sky-50/70 px-3 py-3 text-xs leading-5 text-slate-600">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-600">
                {isKo ? "Scenario Director" : "Scenario Director"}
              </p>
              <span className="rounded-full bg-white px-2 py-0.5 text-[10px] font-semibold text-sky-700">
                {String(swarmV2Telemetry?.summary.scenario_director_mode ?? "pending")}
              </span>
            </div>
            <p className="mt-2 line-clamp-3 text-slate-700">
              {String(
                swarmV2Telemetry?.summary.scenario_actor_roles
                  ? (swarmV2Telemetry.summary.scenario_actor_roles as unknown[]).join(" · ")
                  : isKo
                    ? "세션 시작 시 원문을 실행용 브리프로 보정합니다."
                    : "The raw scenario is compiled into a runtime brief on session start."
              )}
            </p>
            {swarmV2Telemetry?.summary.scenario_director_fallback_reason ? (
              <p className="mt-1 text-[11px] text-slate-400">
                fallback: {String(swarmV2Telemetry.summary.scenario_director_fallback_reason)}
              </p>
            ) : null}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            {isKo ? "현재 토론" : "Current Debate"}
          </p>
          <p className="mt-1 text-sm font-semibold leading-5 text-slate-900">
            {swarmV2Telemetry?.latestEvent?.topic ?? (isKo ? "아직 형성 전" : "Not formed yet")}
          </p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            {swarmV2Telemetry?.latestEvent?.summary ?? (isKo ? "세션을 시작하면 최근 상호작용이 여기에 고정됩니다." : "Start a session to pin the latest interaction here.")}
          </p>
          {swarmV2Telemetry?.latestEvent ? (
            <p className="mt-2 rounded-xl bg-white px-2 py-2 text-xs leading-5 text-slate-700">
              <span className="font-semibold text-slate-900">
                {swarmV2Telemetry.latestEvent.llm_enriched ? (isKo ? "LLM 생각" : "LLM thought") : (isKo ? "생각" : "Thought")}:{" "}
              </span>
              {swarmEventThought(swarmV2Telemetry.latestEvent)}
            </p>
          ) : null}
        </div>
      </div>
    ),
    [
      isKo,
      swarmV2Result?.agent_count,
      swarmV2Result?.events.length,
      swarmV2Telemetry?.agentChannelCount,
      swarmV2Telemetry?.currentPhase,
      swarmV2Telemetry?.eventCount,
      swarmV2Telemetry?.expectedEvents,
      swarmV2Telemetry?.latestEvent?.summary,
      swarmV2Telemetry?.latestEvent?.topic,
      swarmV2Telemetry?.latestEvent,
      swarmV2Telemetry?.replyChainCount,
      swarmV2Telemetry?.llmMode,
      swarmV2Telemetry?.llmSampleSize,
      swarmV2Telemetry?.sessionId,
      swarmV2Telemetry?.status,
      swarmV2Telemetry?.summary,
      swarmV2Telemetry?.thinkingEvent,
      swarmV2Telemetry?.totalAgents,
      swarmV2Telemetry?.visibleAgentCount,
    ]
  );

  const swarmV2RuntimeDockContent = useMemo(
    () => (
      <div className="space-y-3">
        <div className="grid gap-3">
          <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs font-semibold text-slate-700">
            <input type="checkbox" checked={llmEnabled} onChange={(event) => setLlmEnabled(event.target.checked)} />
            {isKo ? "V2 LLM 채널 사용" : "enable V2 LLM channels"}
          </label>
          <div className="grid grid-cols-2 gap-2">
            <ConnectionMetric
              label={isKo ? "API 연결" : "api connection"}
              value={runtimeStatus?.llm?.provider ?? "stub"}
              tone={llmConnectionState.tone}
              detail={runtimeStatus?.llm?.model ?? "stub"}
            />
            <ConnectionMetric
              label={isKo ? "V2 모드" : "v2 mode"}
              value={swarmV2Telemetry?.llmMode ?? "packet"}
              tone={llmConnectionState.tone}
              detail={
                swarmV2Telemetry?.llmMode === "full-agent"
                  ? `${swarmV2Telemetry?.llmParallelism ?? 1} parallel`
                  : `${swarmV2Telemetry?.llmSampleSize ?? 12} samples`
              }
            />
          </div>
        </div>
        <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            {isKo ? "API 설정" : "API Settings"}
          </p>
          <div className="grid gap-2 md:grid-cols-2">
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              {isKo ? "연결 프리셋" : "connection preset"}
              <select className="app-input" value={llmProviderPreset} onChange={(event) => setLlmProviderPreset(event.target.value)}>
                {LLM_PROVIDER_PRESETS.map((item) => (
                  <option key={`v2-${item.id}`} value={item.id}>
                    {item.label}
                  </option>
                ))}
                <option value="custom">{isKo ? "직접 입력" : "Custom"}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              {isKo ? "프로바이더" : "provider"}
              <select
                className="app-input"
                value={llmProvider}
                onChange={(event) => {
                  setLlmProviderPreset("custom");
                  setLlmProvider(event.target.value);
                }}
              >
                <option value="openai">OpenAI</option>
                <option value="openai-compatible">OpenAI-compatible</option>
                <option value="ollama">Ollama</option>
                <option value="stub">Stub</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              {isKo ? "추천 모델" : "model preset"}
              <select className="app-input" value={llmModelPreset} onChange={(event) => setLlmModelPreset(event.target.value)}>
                {availableModelPresets.map((item) => (
                  <option key={`v2-model-${item}`} value={item}>
                    {item}
                  </option>
                ))}
                <option value="custom">{isKo ? "직접 입력" : "Custom"}</option>
              </select>
            </label>
            <label className="flex flex-col gap-1 text-xs text-slate-500">
              {isKo ? "모델" : "model"}
              <input
                className="app-input"
                value={llmModel}
                onChange={(event) => {
                  setLlmModelPreset("custom");
                  setLlmModel(event.target.value);
                }}
              />
            </label>
          </div>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "Base URL" : "base url"}
            <input
              className="app-input"
              value={llmBaseUrl}
              onChange={(event) => {
                setLlmProviderPreset("custom");
                setLlmBaseUrl(event.target.value);
              }}
              placeholder="https://api.openai.com/v1"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs text-slate-500">
            {isKo ? "API 키" : "api key"}
            <input type="password" className="app-input" value={llmApiKey} onChange={(event) => setLlmApiKey(event.target.value)} />
          </label>
        </div>
        <div className="flex flex-wrap gap-2">
          <button type="button" className="app-button app-button--ghost" onClick={() => void handleSaveLlmConfig()}>
            {isKo ? "API 설정 저장" : "Save API Config"}
          </button>
          <button type="button" className="app-button app-button--ghost" onClick={() => void handleTestLlmConnection()}>
            {isKo ? "연결 테스트" : "Test Connection"}
          </button>
        </div>
        {llmConfigStatus ? <p className="text-xs text-slate-500">{llmConfigStatus}</p> : null}
        {llmTestResult ? (
          <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
            <p className="text-xs font-semibold text-slate-900">
              {llmTestResult.ok ? (isKo ? "연결됨" : "connected") : (isKo ? "연결 확인 필요" : "needs check")}
            </p>
            <p className="mt-1 text-[11px] leading-5 text-slate-500">
              {llmTestResult.provider} · {llmTestResult.model}
              {llmTestResult.fallback_reason ? ` · ${llmTestResult.fallback_reason}` : ""}
            </p>
          </div>
        ) : null}
        <details className="group rounded-2xl border border-slate-200 bg-slate-50" open={false}>
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                {isKo ? "호출 내역 / 예산" : "Call History / Budgets"}
              </p>
              <p className="mt-1 text-xs text-slate-500">
                {isKo ? "V2에서 쓰는 전역 LLM 호출 상태입니다." : "Global LLM call state used by V2."}
              </p>
            </div>
            <span className="text-xs font-medium text-slate-500 group-open:hidden">{isKo ? "접힘" : "Collapsed"}</span>
            <span className="hidden text-xs font-medium text-slate-500 group-open:inline">{isKo ? "열림" : "Open"}</span>
          </summary>
          <div className="grid gap-2 border-t border-slate-200 p-3">
            {llmTaskRows.map((row) => (
              <div key={`v2-${row.task}`} className="rounded-2xl border border-slate-200 bg-white px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-700">{row.task}</p>
                  <span className="text-[11px] text-slate-500">
                    live {row.totals?.prompt_count_sent ?? 0}/{row.totals?.prompt_count_in ?? 0}
                  </span>
                </div>
                {row.totals?.fallback_calls ? (
                  <p className="mt-1 text-[11px] text-amber-700">
                    fallback {row.totals.fallback_calls}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </details>
      </div>
    ),
    [
      handleSaveLlmConfig,
      handleTestLlmConnection,
      isKo,
      availableModelPresets,
      llmApiKey,
      llmBaseUrl,
      llmConfigStatus,
      llmConnectionState.tone,
      llmEnabled,
      llmModel,
      llmModelPreset,
      llmProvider,
      llmProviderPreset,
      llmTaskRows,
      llmTestResult,
      runtimeStatus?.llm?.model,
      runtimeStatus?.llm?.provider,
      swarmV2Telemetry?.llmMode,
      swarmV2Telemetry?.llmParallelism,
      swarmV2Telemetry?.llmSampleSize,
    ]
  );

  const swarmV2LlmCallsDockContent = useMemo(
    () => (
      <div className="rounded-2xl border border-slate-900 bg-slate-950 px-3 py-3 font-mono text-[11px] leading-5 text-slate-200 shadow-inner">
        <div className="mb-2 flex items-center justify-between gap-2 border-b border-slate-800 pb-2">
          <span className="font-semibold text-emerald-300">
            {isKo ? "V2 LLM 호출 로그" : "V2 LLM call log"}
          </span>
          <span className="text-slate-500">
            {swarmV2Telemetry?.llmMode ?? "packet"} · x{swarmV2Telemetry?.llmParallelism ?? 1}
          </span>
        </div>
        <div className="max-h-[360px] space-y-1 overflow-y-auto pr-1">
          {swarmV2Telemetry?.llmLogs?.length ? swarmV2Telemetry.llmLogs.map((log, index) => {
            const time = new Date(log.loggedAt).toLocaleTimeString(isKo ? "ko-KR" : "en-US", {
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            });
            const tone = log.status === "completed"
              ? "text-emerald-300"
              : log.status === "fallback"
                ? "text-amber-300"
                : "text-sky-300";
            return (
              <div key={`${log.status}-${log.event_id ?? log.event_ids?.join("-") ?? index}-${index}`} className="whitespace-pre-wrap break-words">
                <span className="text-slate-500">[{time}] </span>
                <span className={tone}>{log.status}</span>
                <span className="text-slate-400"> {log.task}</span>
                {log.batch_size ? <span className="text-slate-500"> batch={log.batch_size}/p{log.parallelism ?? 1}</span> : null}
                {log.event_id ? <span className="text-slate-500"> event={log.event_id}</span> : null}
                {log.source_label ? <span className="text-slate-300"> {log.source_label} → {log.target_label}</span> : null}
                {log.topic ? <span className="text-slate-500"> · {log.topic}</span> : null}
                {log.elapsed_ms ? <span className="text-slate-500"> · {Math.round(log.elapsed_ms)}ms</span> : null}
                {log.fallback_reason ? <span className="text-amber-300"> · {log.fallback_reason}</span> : null}
              </div>
            );
          }) : (
            <p className="text-slate-500">
              {isKo ? "V2 full-agent/agent 실행을 시작하면 호출 로그가 터미널처럼 쌓입니다." : "Start a V2 full-agent/agent run to stream terminal-like call logs."}
            </p>
          )}
        </div>
      </div>
    ),
    [isKo, swarmV2Telemetry?.llmLogs, swarmV2Telemetry?.llmMode, swarmV2Telemetry?.llmParallelism]
  );

  const swarmV2InsightDockContent = useMemo(
    () => (
      <div className="space-y-3">
        <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
            {isKo ? "최근 V2 상호작용" : "Recent V2 Interactions"}
          </p>
          <div className="mt-2 max-h-[420px] space-y-2 overflow-y-auto pr-1">
            {swarmV2Telemetry?.recentEvents.length ? swarmV2Telemetry.recentEvents.map((event) => (
              <div key={`dock-${event.event_id}`} className="rounded-2xl bg-slate-50 px-3 py-2">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-semibold text-slate-500">#{event.event_index}</span>
                  <span className="text-[11px] font-semibold text-sky-700">
                    {event.llm_mode ?? "packet"}{event.llm_action ? ` · ${event.llm_action}` : ""}
                    {event.llm_influenced_by_event_id ? " · influenced" : ""}
                  </span>
                </div>
                <p className="mt-1 text-[11px] leading-4 text-slate-500">{event.topic}</p>
                <p className="mt-1 text-[11px] font-semibold text-slate-600">
                  {event.source_label ?? event.source_id} → {event.target_label ?? event.target_id}
                </p>
                <p className="mt-1 rounded-xl bg-white px-2 py-1 text-xs leading-5 text-slate-700">
                  <span className="font-semibold text-slate-900">
                    {event.llm_enriched ? (isKo ? "LLM 생각" : "LLM thought") : (isKo ? "생각" : "Thought")}:{" "}
                  </span>
                  {swarmEventThought(event)}
                </p>
                <p className="mt-1 text-xs leading-5 text-slate-700">
                  <span className="font-semibold text-slate-900">{isKo ? "발화" : "Speech"}: </span>
                  {event.agent_speech || event.llm_content || event.summary}
                </p>
                {typeof event.llm_action_effect === "number" ? (
                  <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-sky-700">
                    action effect {event.llm_action_effect.toFixed(3)}
                  </p>
                ) : null}
                {typeof event.decision_relation_delta === "number" || typeof event.decision_pressure_delta === "number" ? (
                  <p className="mt-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                    relation {formatSignedDelta(event.decision_relation_delta)} · pressure {formatSignedDelta(event.decision_pressure_delta)}
                  </p>
                ) : null}
                {event.memory_write || event.next_intent ? (
                  <p className="mt-1 rounded-xl bg-white px-2 py-1 text-[11px] leading-4 text-slate-500">
                    {event.memory_write ? `${isKo ? "기억" : "Memory"}: ${event.memory_write}` : ""}
                    {event.memory_write && event.next_intent ? " · " : ""}
                    {event.next_intent ? `${isKo ? "다음 의도" : "Next"}: ${event.next_intent}` : ""}
                  </p>
                ) : null}
                {event.llm_reasoning ? (
                  <p className="mt-1 rounded-xl bg-white px-2 py-1 text-[11px] leading-4 text-slate-500">
                    {event.llm_reasoning}
                  </p>
                ) : null}
              </div>
            )) : (
              <p className="rounded-2xl bg-slate-50 px-3 py-4 text-xs leading-5 text-slate-500">
                {isKo ? "V2 세션을 시작하면 이벤트가 여기에 쌓입니다." : "Start a V2 session to stream events here."}
              </p>
            )}
          </div>
        </div>
      </div>
    ),
    [isKo, swarmV2Telemetry?.recentEvents]
  );

  useEffect(() => {
    const useSwarmV2Dock = stage === "run" && setupRuntimeTab === "swarm-v2";
    onDockPayloadChange?.({
      timeControlContent: useSwarmV2Dock ? swarmV2TimeDockContent : timeDockContent,
      controlsContent: useSwarmV2Dock ? swarmV2SessionDockContent : controlsDockContent,
      runtimeContent: useSwarmV2Dock ? swarmV2RuntimeDockContent : runtimeDockContent,
      llmCallsContent: useSwarmV2Dock ? swarmV2LlmCallsDockContent : undefined,
      insightContent: useSwarmV2Dock ? swarmV2InsightDockContent : insightDockContent,
      chatContent: chatDockContent,
      thoughtCells: renderedSnapshotCells,
      actionRecords: liveSceneStream.recentActions,
      runtimeTiming: liveSceneStream.runtimeTiming,
      currentT: observedT,
      collectiveSummary: renderedCollectiveSummary,
      collectiveSignal: renderedCollectiveSignal,
      connectionState: llmConnectionState,
    });
  }, [chatDockContent, controlsDockContent, currentT, insightDockContent, liveSceneStream.recentActions, liveSceneStream.runtimeTiming, llmConnectionState, observedT, onDockPayloadChange, renderedCollectiveSignal, renderedCollectiveSummary, renderedSnapshotCells, runtimeDockContent, setupRuntimeTab, stage, swarmV2InsightDockContent, swarmV2LlmCallsDockContent, swarmV2RuntimeDockContent, swarmV2SessionDockContent, swarmV2TimeDockContent, timeDockContent]);


  useEffect(() => {
    if (!initialInjectPreset) return;
    setReviewInjectPreset({
      label: String(initialInjectPreset.label ?? (isKo ? "리뷰 프리셋" : "Review preset")),
      t: Number(initialInjectPreset.t ?? 0),
      eventType: String(initialInjectPreset.event_type ?? "policy_shift"),
      payload: (initialInjectPreset.payload ?? {}) as Record<string, unknown>,
    });
    if (typeof initialInjectPreset.t === "number") {
      setCurrentT(Number(initialInjectPreset.t));
      setStage("run");
    }
    onConsumeInitialInjectPreset?.();
  }, [initialInjectPreset, isKo, onConsumeInitialInjectPreset]);

  useEffect(() => {
    if (!initialWorldId) return;
    const hydrateKey = `${initialWorldId}:${typeof initialT === "number" ? initialT : "first"}`;
    if (hydratedInitialWorldKeyRef.current === hydrateKey) return;
    let cancelled = false;
    setActionError(null);
    Promise.all([getWorld(initialWorldId), listSnapshotTimes(initialWorldId)])
      .then(([meta, snapshots]) => {
        if (cancelled) return;
        hydratedInitialWorldKeyRef.current = hydrateKey;
        setWorldId(meta.world_id);
        onWorldSelected?.(meta.world_id);
        setCollectiveSummary(normalizeCollectiveSummary(meta.group_state));
        setCollectiveSignal(inferCollectiveSignalFromGroupState(meta.group_state));
        setGenesisPrompt(meta.genesis_prompt ?? "");
        setAvailableT(snapshots.available_t);
        const hydratedReviewRevisionKey =
          snapshots.available_t.length > 0
            ? `${meta.world_id}:${snapshots.available_t[snapshots.available_t.length - 1] ?? 0}`
            : null;
        setReviewSummary(meta.cached_review_summary ?? null);
        setReviewRevisionKey(meta.cached_review_summary ? hydratedReviewRevisionKey : null);
        setReviewError(null);
        const firstT = snapshots.available_t[0] ?? 0;
        if (typeof initialT === "number" && snapshots.available_t.length > 0) {
          const nearest = snapshots.available_t.reduce((best, value) =>
            Math.abs(value - initialT) < Math.abs(best - initialT) ? value : best
          );
          setCurrentT(nearest);
        } else {
          setCurrentT(firstT);
        }
        setStage("run");
      })
      .catch((e) => {
        if (!cancelled) setActionError((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [initialT, initialWorldId, onWorldSelected]);

  return (
    <div className="godview-staged">
      <AppPanel
        title={strings.simulationWorkspace}
        subtitle={
          swarmV2Result
            ? `Swarm V2 · ${swarmV2Result.agent_count.toLocaleString()} agents · ${swarmV2Result.events.length.toLocaleString()} events`
            :
          stage === "run" && worldId
            ? `${worldId} · ${isKo ? "장면" : "scene"} t=${observedT.toFixed(2)} · ${renderedVisibleCells.length.toLocaleString()} agents`
            : isKo
              ? "설정 · 실행 · 리뷰를 한 흐름으로 엽니다"
              : "Open setup, run, and review in one flow"
        }
        bodyClassName="flex flex-wrap items-center justify-between gap-3"
      >
        <div className="flex flex-wrap items-center gap-3">
          <div className="godview-stage-switch">
            <button
              type="button"
              className={`godview-stage-switch__button ${stage === "setup" ? "is-active" : ""}`}
              onClick={() => setStage("setup")}
            >
              01 {strings.setup}
            </button>
            <button
              type="button"
              className={`godview-stage-switch__button ${stage === "run" ? "is-active" : ""}`}
              onClick={() => setStage("run")}
              disabled={setupRuntimeTab === "legacy" && !worldId}
            >
              02 {strings.run}
            </button>
            <button
              type="button"
              className={`godview-stage-switch__button ${stage === "review" ? "is-active" : ""}`}
              onClick={() => setStage("review")}
              disabled={!worldId}
            >
              03 {isKo ? "리뷰" : "Review"}
            </button>
          </div>
          {stage === "run" ? (
            <div className="unified-dashboard__mode-toggle" aria-label="simulation mode">
              <button
                type="button"
                className={setupRuntimeTab === "swarm-v2" ? "is-active" : ""}
                onClick={() => {
                  setSetupRuntimeTab("swarm-v2");
                  setSimulationMode("swarm");
                }}
              >
                Swarm V2
              </button>
              <button
                type="button"
                className={setupRuntimeTab === "legacy" ? "is-active" : ""}
                onClick={() => {
                  setSetupRuntimeTab("legacy");
                  applySimulationMode("precision");
                }}
              >
                Legacy Precision
              </button>
            </div>
          ) : null}
          {stage === "run" ? (
            <div className="unified-dashboard__status-strip">
              {setupRuntimeTab === "swarm-v2" ? (
                <>
                  <span>Swarm V2</span>
                  <span>{swarmV2Result ? `${swarmV2Result.events.length.toLocaleString()} events` : isKo ? "세션 대기" : "session idle"}</span>
                  <span>{swarmV2Result ? `${swarmV2Result.agent_count.toLocaleString()} agents` : isKo ? "새 런타임" : "new runtime"}</span>
                </>
              ) : (
                <>
                  <span>{renderedCollectiveSignal}</span>
                  <span>{isKo ? "압력" : "pressure"} {Math.round((renderedCollectiveSummary?.role?.avg_fracture_risk ?? 0) * 100)}</span>
                  {renderedVisualStats?.sampled ? (
                    <span className="is-warn">
                      {isKo ? "샘플링" : "sampled"} {renderedVisibleCells.length.toLocaleString()} / {renderedVisualStats.totalCells.toLocaleString()}
                    </span>
                  ) : null}
                </>
              )}
            </div>
          ) : null}
        </div>
        <div className="hidden" />
      </AppPanel>

      {stage === "setup" && (
        <div className="godview-setup">
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
            <div className="flex flex-wrap gap-2 rounded-[24px] border border-slate-200 bg-white p-2">
              <button
                type="button"
                className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                  setupRuntimeTab === "swarm-v2" ? "bg-sky-600 text-white shadow" : "text-slate-600 hover:bg-slate-50"
                }`}
                onClick={() => setSetupRuntimeTab("swarm-v2")}
              >
                Swarm V2
              </button>
              <button
                type="button"
                className={`rounded-2xl px-4 py-2 text-sm font-semibold transition ${
                  setupRuntimeTab === "legacy" ? "bg-slate-900 text-white shadow" : "text-slate-600 hover:bg-slate-50"
                }`}
                onClick={() => setSetupRuntimeTab("legacy")}
              >
                Legacy Precision
              </button>
            </div>

            {setupRuntimeTab === "swarm-v2" ? (
            <div>
              <SwarmV2Workspace
                variant="setup"
                prompt={genesisPrompt || PROMPT_PLACEHOLDER}
                scenarioPrompt={genesisPrompt}
                onScenarioPromptChange={setGenesisPrompt}
                locale={locale}
                onOpenRun={() => {
                  setSetupRuntimeTab("swarm-v2");
                  setSimulationMode("swarm");
                  setStage("run");
                }}
                onTelemetryChange={setSwarmV2Telemetry}
                onResult={(result) => {
                  setSwarmV2Result(result);
                  setSimulationMode("swarm");
                }}
              />
            </div>
            ) : (
            <>
            <div className="grid gap-4 xl:grid-cols-2">
            <AppPanel
              title={isKo ? "Legacy Precision 생성" : "Legacy Precision Genesis"}
              subtitle={isKo ? "기존 엔진은 보조/비교용으로 남겨둡니다" : "The legacy engine remains only as a secondary comparison path"}
              bodyClassName="space-y-4"
            >
              <label className="flex flex-col gap-2">
                <span className="text-xs font-medium uppercase tracking-[0.14em] text-slate-500">
                  {isKo ? "시나리오 프롬프트" : "Scenario prompt"}
                </span>
                <textarea
                  value={genesisPrompt}
                  onChange={(e) => setGenesisPrompt(e.target.value)}
                  placeholder={PROMPT_PLACEHOLDER}
                  rows={8}
                  className="app-textarea"
                />
              </label>
              <div className="grid gap-3 rounded-[22px] border border-slate-200 bg-white/80 p-3 md:grid-cols-2">
                <button
                  type="button"
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    simulationMode === "precision"
                      ? "border-slate-900 bg-slate-900 text-white shadow-lg"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300"
                  }`}
                  onClick={() => applySimulationMode("precision")}
                >
                  <span className="block text-xs font-semibold uppercase tracking-[0.18em] opacity-70">Precision Mode</span>
                  <span className="mt-1 block text-sm font-semibold">
                    {isKo ? "고해상도 개인/집단 분석" : "High-resolution individual and group analysis"}
                  </span>
                </button>
                <button
                  type="button"
                  className={`rounded-2xl border px-4 py-3 text-left transition ${
                    simulationMode === "swarm"
                      ? "border-sky-500 bg-sky-50 text-sky-950 shadow-lg"
                      : "border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-300"
                  }`}
                  onClick={() => applySimulationMode("swarm")}
                >
                  <span className="block text-xs font-semibold uppercase tracking-[0.18em] opacity-70">Swarm Mode</span>
                  <span className="mt-1 block text-sm font-semibold">
                    {isKo ? "MiroFish식 대량 에이전트 스트림" : "MiroFish-style mass-agent stream"}
                  </span>
                </button>
              </div>
              {simulationMode === "swarm" ? (
                <div className="grid gap-3 rounded-[22px] border border-sky-200 bg-sky-50/80 p-4 md:grid-cols-3">
                  <label className="flex flex-col gap-1 text-xs text-sky-800">
                    {isKo ? "Swarm agents" : "Swarm agents"}
                    <select value={swarmAgentCount} onChange={(e) => setSwarmAgentCount(e.target.value)} className="app-input">
                      {SWARM_AGENT_OPTIONS.map((value) => (
                        <option key={value} value={value}>{Number(value).toLocaleString()}</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-sky-800">
                    {isKo ? "Meso groups" : "Meso groups"}
                    <select value={swarmMesoGroups} onChange={(e) => setSwarmMesoGroups(e.target.value)} className="app-input">
                      {SWARM_MESO_OPTIONS.map((value) => (
                        <option key={value} value={value}>{value}</option>
                      ))}
                    </select>
                  </label>
                  <label className="flex flex-col gap-1 text-xs text-sky-800">
                    {isKo ? "LLM 모드" : "LLM mode"}
                    <select value={swarmLlmMode} onChange={(e) => setSwarmLlmMode(e.target.value as SwarmLlmMode)} className="app-input">
                      <option value="packet">{isKo ? "Packet: group/state 단위" : "Packet: group/state"}</option>
                      <option value="agent">{isKo ? "1:1 Agent: 개별 호출" : "1:1 Agent calls"}</option>
                      <option value="full-agent">{isKo ? "Full Agent: 모든 이벤트 LLM" : "Full Agent: every event"}</option>
                    </select>
                  </label>
                  <p className="md:col-span-3 rounded-2xl bg-white/75 px-3 py-2 text-[11px] leading-5 text-sky-900">
                    {isKo
                      ? "기본 실행은 clean-room MiroFish식 Swarm 런타임을 탑니다. 한 번의 stream session에서 다수 에이전트 관계 이벤트가 쏟아지고, session 완료 후 다음 t로 커밋됩니다."
                      : "Default execution uses the clean-room MiroFish-style Swarm runtime: one stream session emits many agent relationship events, then commits the next t."}
                  </p>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={handleCreateWorld} className="app-button app-button--primary">
                  {isKo ? "Legacy 월드 생성" : "Create legacy world"}
                </button>
                {worldId && (
                  <button type="button" onClick={() => setStage("run")} className="app-button app-button--secondary">
                    {isKo ? "실행 단계 열기" : "Open Run Stage"}
                  </button>
                )}
              </div>
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

            </div>

            <PersonaPreview worldId={worldId} refreshKey={personaRefreshKey} />

          <div className="grid gap-4 xl:grid-cols-2">
            <AppPanel
              title={isKo ? "설정 체크리스트" : "Setup Checklist"}
              subtitle={isKo ? "짧게 확인하고 바로 실행으로 넘어갑니다" : "Quick checks before moving into run"}
              bodyClassName="grid gap-2 md:grid-cols-2"
            >
              <SetupItem index="01" title={isKo ? "시나리오 프롬프트" : "Scenario Prompt"} body={isKo ? "장기 정책/시장/사회 시나리오를 먼저 정의합니다." : "Define the long-run policy, market, and social scenario first."} />
              <SetupItem index="02" title={isKo ? "페르소나와 데이터 팩" : "Persona & Data Packs"} body={isKo ? "우측 실행 메뉴에서 persona pack 준비 상태를 확인합니다." : "Check persona pack readiness from the right run menu."} />
              <SetupItem index="03" title={isKo ? "생성 제어" : "Genesis Controls"} body={isKo ? "우측 실행 메뉴의 God mode에서 zone/z/role seed를 미세 조정합니다." : "Fine-tune zone, z, and role seeds from God mode in the right run menu."} />
              <SetupItem index="04" title={isKo ? "실행 단계 진입" : "Enter Run Stage"} body={isKo ? "world가 생성되면 Run 단계에서 실행·주입·탐색을 시작합니다." : "Once the world is created, start execution, injection, and exploration in Run."} />
            </AppPanel>

            {lastGenesis ? (
              <GenesisMeta locale={locale} lastGenesis={lastGenesis} />
            ) : (
              <AppPanel
                title={isKo ? "다음 단계" : "Next Stage"}
                subtitle={isKo ? "실행과 리뷰가 같은 흐름 안에 있습니다" : "Run and review now stay in the same flow"}
                bodyClassName="grid gap-2 md:grid-cols-3"
              >
                <MetricChip label={isKo ? "02 실행" : "02 Run"} value={isKo ? "제어 · 필드 · 시간축" : "Controls · Field · Timeline"} />
                <MetricChip label={isKo ? "03 리뷰" : "03 Review"} value={isKo ? "요약 · 원인 · 프리셋" : "Summary · Causality · Presets"} />
                <MetricChip label={isKo ? "데이터 관리" : "Data Mgmt"} value={isKo ? "데이터팩 · 월드 · 세션" : "Packs · Worlds · Sessions"} />
              </AppPanel>
            )}
          </div>
            </>
            )}
        </div>
      </div>
      )}
      {stage === "review" && (
        <div className="grid min-h-0 gap-4 overflow-y-auto pr-1">
          {reviewSummary ? (
            <AppPanel
              title={isKo ? "리뷰" : "Review"}
              subtitle={reviewLoading ? (isKo ? "분석 요약 새로고침 중…" : "Refreshing analyst summary…") : reviewSummary.headline}
              bodyClassName="space-y-4"
              action={
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => setStage("run")}
                >
                  {isKo ? "실행으로 돌아가기" : "Back to Run"}
                </button>
              }
            >
              <p className="text-sm leading-6 text-slate-700">{reviewSummary.summary}</p>
              <div className="grid gap-3 xl:grid-cols-2">
                {reviewSummary.causal_analysis.map((item, index) => (
                  <div key={`${index}-${item}`} className="session-thread-card">
                    <p className="session-thread-card__prompt">{item}</p>
                  </div>
                ))}
              </div>
              {Array.isArray(reviewSummary.inject_presets) && reviewSummary.inject_presets.length ? (
                <div className="grid gap-2">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                    {isKo ? "리뷰 기반 정책 프리셋" : "Review-driven Policy Presets"}
                  </p>
                  {reviewSummary.inject_presets.map((item, index) => (
                    <div
                      key={`${index}-${String(item.label ?? "preset")}`}
                      className="session-thread-card"
                    >
                      <div className="session-thread-card__header">
                        <p className="session-thread-card__title">{String(item.label ?? "Policy preset")}</p>
                        <span className="session-thread-card__meta">
                          t={Number(item.t ?? currentT).toFixed(0)}
                        </span>
                      </div>
                      <p className="session-thread-card__prompt">{String(item.description ?? "")}</p>
                      <div className="session-thread-card__actions">
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() => {
                            setReviewInjectPreset({
                              label: String(item.label ?? "Policy preset"),
                              t: Number(item.t ?? currentT),
                              eventType: String(item.event_type ?? "policy_shift"),
                              payload: (item.payload as Record<string, unknown>) ?? {},
                            });
                            setCurrentT(Number(item.t ?? currentT));
                            setStage("run");
                          }}
                        >
                          {isKo ? "주입 패널로 사용" : "Use in Injection Panel"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
            </AppPanel>
          ) : (
            <AppPanel
              title={isKo ? "리뷰" : "Review"}
              subtitle={isKo ? "리뷰를 준비 중입니다" : "Review is preparing"}
              bodyClassName="space-y-3"
            >
              <p className="text-sm leading-6 text-slate-600">
                {reviewError
                  ? reviewError
                  : isKo
                    ? "월드를 실행하면 여기서 LLM 기반 리뷰를 바로 확인할 수 있습니다."
                    : "Run the world to unlock the LLM-backed review here."}
              </p>
            </AppPanel>
          )}
        </div>
      )}
      {stage === "run" && (
        setupRuntimeTab === "swarm-v2" ? (
        <div className="grid min-h-0 gap-4 overflow-y-auto pr-1">
          <div className="rounded-[28px] border border-sky-200 bg-sky-50/70 px-4 py-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-sky-700">
              {isKo ? "Swarm V2 실행면" : "Swarm V2 Runtime Surface"}
            </p>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              {isKo
                ? "이 탭은 레거시 t-step 엔진과 분리된 새 세션 스트림입니다. 한 번의 세션이 끝나면 그 결과가 하나의 t 챕터 후보가 됩니다."
                : "This tab is the new session-stream runtime, separated from the legacy t-step engine. One completed session becomes one candidate t chapter."}
            </p>
          </div>
          <SwarmV2Workspace
            variant="run"
            prompt={genesisPrompt || PROMPT_PLACEHOLDER}
            scenarioPrompt={genesisPrompt}
            onScenarioPromptChange={setGenesisPrompt}
            locale={locale}
            onTelemetryChange={setSwarmV2Telemetry}
            onResult={(result) => {
              setSwarmV2Result(result);
              setSimulationMode("swarm");
            }}
          />
        </div>
        ) : (
        <div className="unified-dashboard">
          <main className="unified-dashboard__center">
            <div className="unified-dashboard__center-header">
              <div>
                <p className="unified-dashboard__section-label">{isKo ? "Center Visualization" : "Center Visualization"}</p>
                <h3>{isKo ? "실시간 소셜 필드" : "Live Social Field"}</h3>
                <p className="mt-1 text-xs text-slate-500">
                  {isKo
                    ? "현재 t 내부에서 발생하는 에이전트 접촉, 압력, 구역 흐름을 관찰합니다."
                    : "Observe intra-t agent contact, pressure, and zone flow."}
                </p>
              </div>
              <div className="unified-dashboard__status-strip">
                <span>{simulationMode}</span>
                <span>{renderedCollectiveSignal}</span>
                <span>{isKo ? "압력" : "pressure"} {Math.round((renderedCollectiveSummary?.role?.avg_fracture_risk ?? 0) * 100)}</span>
                {renderedVisualStats?.sampled ? (
                  <span className="is-warn">
                    {isKo ? "샘플링" : "sampled"} {renderedVisibleCells.length.toLocaleString()} / {renderedVisualStats.totalCells.toLocaleString()}
                  </span>
                ) : null}
              </div>
            </div>
            {err ? (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {err}
              </div>
            ) : null}
            <CenterMapShell
              mode={simulationMode}
              cells={renderedVisibleCells}
              totalCells={renderedVisualStats?.totalCells ?? renderedVisibleCells.length}
              sampled={renderedVisualStats?.sampled ?? false}
              currentT={observedT}
              annotations={reviewSummary?.timeline_annotations ?? []}
              groundingItems={flattenReviewGrounding(reviewSummary?.grounding ?? {})}
              collectiveSummary={renderedCollectiveSummary}
              reviewSummary={reviewSummary}
              sceneEvents={renderedSceneEvents}
              locale={locale}
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
              onClearSelection={clearSelection}
              onJumpToT={setCurrentT}
            />
          </main>

        </div>
        )
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

function parseAutoText(value: string): string | undefined {
  const text = String(value || "").trim();
  if (!text || text.toLowerCase() === "auto") return undefined;
  return text;
}

function splitRoles(value: string): string[] | undefined {
  const roles = value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  return roles.length ? roles : undefined;
}

function CompactTimeControl({
  locale,
  t,
  liveObservedT = null,
  tMin,
  tMax,
  frameCount,
  disabled,
  isRunning = false,
  markers,
  bookmarks,
  onJump,
  onAddBookmark,
  onRemoveBookmark,
  compact = false,
}: {
  locale: UiLocale;
  t: number;
  liveObservedT?: number | null;
  tMin: number;
  tMax: number;
  frameCount: number;
  disabled: boolean;
  isRunning?: boolean;
  markers: TimelineMarker[];
  bookmarks: TimelineMarker[];
  onJump: (t: number) => void;
  onAddBookmark: () => void;
  onRemoveBookmark: (key: string) => void;
  compact?: boolean;
}) {
  const isKo = locale === "ko";
  const span = Math.max(1, tMax - tMin);
  const safeMax = Math.max(tMin + 1, tMax);
  return (
    <div className={`rounded-[22px] border border-slate-200 bg-white shadow-sm ${compact ? "px-3 py-2" : "px-4 py-3"}`}>
      <div className={`${compact ? "mb-1.5" : "mb-2"} flex items-center justify-between gap-3`}>
        <div>
          <p className={`${compact ? "text-xs" : "text-sm"} font-semibold text-slate-900`}>
            {isKo ? "t 챕터 선택" : "t chapter"}{" "}
            <span className="font-mono">
              {t.toFixed(0)} / {frameCount}{isKo ? "개 스냅샷" : " snapshots"}
            </span>
          </p>
          <p className="mt-0.5 text-[11px] leading-4 text-slate-500">
            {isRunning
              ? isKo
                ? `실행 중에는 stream 관찰 우선 · 현재 내부시점 ${Number(liveObservedT ?? t).toFixed(2)}`
                : `Locked while streaming · observed intra-t ${Number(liveObservedT ?? t).toFixed(2)}`
              : isKo
                ? "완료된 t 챕터 스냅샷을 선택합니다. 내부 stream 재생은 아래 패널에서 조절합니다."
                : "Select completed t snapshots. Control intra-t stream replay below."}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button type="button" className="app-button app-button--ghost !px-3 !py-2 text-xs" onClick={onAddBookmark} disabled={disabled}>
            {isKo ? "북마크" : "Bookmark"}
          </button>
          <details className="relative">
            <summary className="flex h-9 w-9 cursor-pointer list-none items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-xs font-semibold text-slate-700">
              ▾
            </summary>
            <div className="absolute right-0 z-30 mt-2 w-64 rounded-2xl border border-slate-200 bg-white p-3 shadow-xl">
              <p className="mb-2 text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                {isKo ? "북마크" : "Bookmarks"}
              </p>
              {bookmarks.length ? (
                <div className="max-h-52 space-y-2 overflow-y-auto pr-1">
                  {bookmarks.map((bookmark) => (
                    <div key={bookmark.key} className="flex items-center justify-between gap-2 rounded-xl border border-slate-100 bg-slate-50 px-2 py-2">
                      <button type="button" className="min-w-0 truncate text-left text-xs font-semibold text-slate-700" onClick={() => onJump(bookmark.t)}>
                        {bookmark.label}
                      </button>
                      <button
                        type="button"
                        className="rounded-full px-2 text-sm text-slate-400 hover:bg-white hover:text-rose-600"
                        onClick={() => onRemoveBookmark(bookmark.key)}
                        aria-label={`Remove ${bookmark.label}`}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-500">{isKo ? "저장된 북마크가 없습니다." : "No bookmarks yet."}</p>
              )}
            </div>
          </details>
        </div>
      </div>
      <TimeSlider
        t={t}
        tMin={tMin}
        tMax={safeMax}
        step={1}
        onChange={onJump}
        disabled={disabled}
        label={isKo ? "t 챕터" : "t chapter"}
      />
      <div className="relative mt-2 h-4 rounded-full bg-slate-100">
        {markers.map((marker) => (
          <button
            key={marker.key}
            type="button"
            className={`absolute top-1 h-2 w-2 -translate-x-1/2 rounded-full ${
              marker.kind === "inject"
                ? "bg-amber-500"
                : marker.kind === "annotation"
                  ? "bg-sky-500"
                  : marker.kind === "bookmark"
                    ? "bg-slate-900"
                    : "bg-slate-400"
            }`}
            style={{ left: `${((marker.t - tMin) / span) * 100}%` }}
            onClick={() => onJump(marker.t)}
            title={`${marker.label} · t=${marker.t}${marker.reason ? ` · ${marker.reason}` : ""}`}
          />
        ))}
      </div>
    </div>
  );
}

function GodModePrepPanel({
  locale,
  enabled,
  onEnabledChange,
  godRoleMode,
  onGodRoleModeChange,
  customTMax,
  onCustomTMaxChange,
  customInitialCells,
  onCustomInitialCellsChange,
  customRoles,
  onCustomRolesChange,
  customCountry,
  onCustomCountryChange,
  customNutrient,
  onCustomNutrientChange,
  customTUnit,
  onCustomTUnitChange,
  zoneCount,
  onZoneCountChange,
  zoneLayout,
  onZoneLayoutChange,
  zoneSpacing,
  onZoneSpacingChange,
  zoneInfluenceStep,
  onZoneInfluenceStepChange,
  zoneFrictionStep,
  onZoneFrictionStepChange,
  zMode,
  onZModeChange,
  zWeight,
  onZWeightChange,
  zScale,
  onZScaleChange,
  streamDensity,
  onStreamDensityChange,
  streamDelayMs,
  onStreamDelayMsChange,
  streamEpisodeMinDurationMs,
  onStreamEpisodeMinDurationMsChange,
  streamMinRounds,
  onStreamMinRoundsChange,
  streamMaxRounds,
  onStreamMaxRoundsChange,
  streamMaxActiveAgents,
  onStreamMaxActiveAgentsChange,
  streamInitialAgentRatio,
  onStreamInitialAgentRatioChange,
  streamGrowthRate,
  onStreamGrowthRateChange,
  streamMaxNeighbors,
  onStreamMaxNeighborsChange,
  dirty,
  status,
  onSave,
}: {
  locale: UiLocale;
  enabled: boolean;
  onEnabledChange: (value: boolean) => void;
  godRoleMode: "auto" | "manual";
  onGodRoleModeChange: (value: "auto" | "manual") => void;
  customTMax: string;
  onCustomTMaxChange: (value: string) => void;
  customInitialCells: string;
  onCustomInitialCellsChange: (value: string) => void;
  customRoles: string;
  onCustomRolesChange: (value: string) => void;
  customCountry: string;
  onCustomCountryChange: (value: string) => void;
  customNutrient: string;
  onCustomNutrientChange: (value: string) => void;
  customTUnit: string;
  onCustomTUnitChange: (value: string) => void;
  zoneCount: string;
  onZoneCountChange: (value: string) => void;
  zoneLayout: string;
  onZoneLayoutChange: (value: string) => void;
  zoneSpacing: string;
  onZoneSpacingChange: (value: string) => void;
  zoneInfluenceStep: string;
  onZoneInfluenceStepChange: (value: string) => void;
  zoneFrictionStep: string;
  onZoneFrictionStepChange: (value: string) => void;
  zMode: string;
  onZModeChange: (value: string) => void;
  zWeight: string;
  onZWeightChange: (value: string) => void;
  zScale: string;
  onZScaleChange: (value: string) => void;
  streamDensity: string;
  onStreamDensityChange: (value: string) => void;
  streamDelayMs: string;
  onStreamDelayMsChange: (value: string) => void;
  streamEpisodeMinDurationMs: string;
  onStreamEpisodeMinDurationMsChange: (value: string) => void;
  streamMinRounds: string;
  onStreamMinRoundsChange: (value: string) => void;
  streamMaxRounds: string;
  onStreamMaxRoundsChange: (value: string) => void;
  streamMaxActiveAgents: string;
  onStreamMaxActiveAgentsChange: (value: string) => void;
  streamInitialAgentRatio: string;
  onStreamInitialAgentRatioChange: (value: string) => void;
  streamGrowthRate: string;
  onStreamGrowthRateChange: (value: string) => void;
  streamMaxNeighbors: string;
  onStreamMaxNeighborsChange: (value: string) => void;
  dirty: boolean;
  status: string | null;
  onSave: () => void;
}) {
  const isKo = locale === "ko";
  return (
    <details className="rounded-[22px] border border-slate-200 bg-white shadow-sm" open={enabled}>
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{isKo ? "God mode 생성 제어" : "God mode genesis controls"}</p>
          <p className="mt-1 text-xs text-slate-500">
            {enabled ? (isKo ? "월드 생성 seed를 직접 조정합니다." : "Manual world-seed overrides are active.") : (isKo ? "필요할 때만 열어 seed를 조정합니다." : "Open only when you need seed overrides.")}
          </p>
        </div>
        <label className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700" onClick={(event) => event.stopPropagation()}>
          <input type="checkbox" checked={enabled} onChange={(event) => onEnabledChange(event.target.checked)} />
          {enabled ? (isKo ? "켜짐" : "on") : (isKo ? "꺼짐" : "off")}
        </label>
      </summary>
      <div className="grid gap-3 border-t border-slate-200 p-3">
        <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-slate-800">
                {dirty ? (isKo ? "저장되지 않은 변경 있음" : "Unsaved changes") : isKo ? "설정 저장됨" : "Settings saved"}
              </p>
              <p className="mt-1 text-[11px] leading-5 text-slate-500">
                {status ??
                  (isKo
                    ? "값을 조정한 뒤 저장 버튼을 누르면 다음 월드 생성에 적용됩니다."
                    : "Adjust values, then save to apply them to the next world creation.")}
              </p>
            </div>
            <button type="button" className={`app-button ${dirty ? "app-button--primary" : "app-button--ghost"}`} onClick={onSave}>
              {isKo ? "설정 저장" : "Save"}
            </button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <MiniField label="t_max" value={customTMax} onChange={onCustomTMaxChange} placeholder="auto" />
          <MiniField label={isKo ? "에이전트" : "agents"} value={customInitialCells} onChange={onCustomInitialCellsChange} placeholder="auto" />
          <MiniField label={isKo ? "국가" : "country"} value={customCountry} onChange={onCustomCountryChange} placeholder="auto" />
          <MiniField label={isKo ? "자원/step" : "nutrient/step"} value={customNutrient} onChange={onCustomNutrientChange} placeholder="auto" />
          <label className="flex flex-col gap-1 text-[11px] text-slate-500">
            {isKo ? "시간 단위" : "time unit"}
            <select value={customTUnit} onChange={(event) => onCustomTUnitChange(event.target.value)} className="app-input">
              <option value="auto">{isKo ? "자동" : "auto"}</option>
              <option value="hour">hour</option>
              <option value="day">day</option>
              <option value="month">month</option>
              <option value="year">year</option>
              <option value="decade_scale">decade_scale</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-[11px] text-slate-500">
            {isKo ? "역할 방식" : "role mode"}
            <select value={godRoleMode} onChange={(event) => onGodRoleModeChange(event.target.value as "auto" | "manual")} className="app-input">
              <option value="auto">{isKo ? "자동" : "auto"}</option>
              <option value="manual">{isKo ? "수동" : "manual"}</option>
            </select>
          </label>
        </div>
        {godRoleMode === "manual" ? <MiniField label={isKo ? "역할 목록" : "roles"} value={customRoles} onChange={onCustomRolesChange} placeholder="auto" /> : null}
        <div className="grid grid-cols-2 gap-2">
          <MiniField label={isKo ? "구역 수" : "zones"} value={zoneCount} onChange={onZoneCountChange} placeholder="auto" />
          <label className="flex flex-col gap-1 text-[11px] text-slate-500">
            {isKo ? "구역 레이아웃" : "zone layout"}
            <select value={zoneLayout} onChange={(event) => onZoneLayoutChange(event.target.value)} className="app-input">
              <option value="auto">{isKo ? "자동" : "auto"}</option>
              <option value="grid">grid</option>
              <option value="bands">bands</option>
              <option value="ring">ring</option>
            </select>
          </label>
          <MiniField label={isKo ? "구역 간격" : "spacing"} value={zoneSpacing} onChange={onZoneSpacingChange} placeholder="auto" />
          <MiniField label={isKo ? "영향 단계" : "influence"} value={zoneInfluenceStep} onChange={onZoneInfluenceStepChange} placeholder="auto" />
          <MiniField label={isKo ? "마찰 단계" : "friction"} value={zoneFrictionStep} onChange={onZoneFrictionStepChange} placeholder="auto" />
          <label className="flex flex-col gap-1 text-[11px] text-slate-500">
            {isKo ? "z 모드" : "z mode"}
            <select value={zMode} onChange={(event) => onZModeChange(event.target.value)} className="app-input">
              <option value="auto">{isKo ? "자동" : "auto"}</option>
              <option value="hybrid">hybrid</option>
              <option value="wealth">wealth</option>
              <option value="influence">influence</option>
              <option value="policy">policy</option>
              <option value="memory">memory</option>
              <option value="flat">flat</option>
            </select>
          </label>
          <MiniField label={isKo ? "z 가중치" : "z weight"} value={zWeight} onChange={onZWeightChange} placeholder="auto" />
          <MiniField label={isKo ? "z 스케일" : "z scale"} value={zScale} onChange={onZScaleChange} placeholder="auto" />
        </div>
        <div className="rounded-2xl border border-sky-100 bg-sky-50/70 px-3 py-3">
          <div className="mb-2 flex items-start justify-between gap-3">
            <div>
              <p className="text-xs font-semibold text-slate-900">{isKo ? "Stream 확장 / 페이싱" : "Stream expansion / pacing"}</p>
              <p className="mt-1 text-[11px] leading-5 text-slate-600">
                {isKo
                  ? "한 t 안에서 주제 주변으로 참여자가 점점 모이고, stream 장면을 충분히 보여준 뒤 다음 t로 넘어가게 합니다."
                  : "Grow the cast around one topic inside t, then pace scene playback before advancing to the next t."}
              </p>
            </div>
            <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold text-sky-700">
              {isKo ? "자동 확장" : "auto grow"}
            </span>
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MiniField label={isKo ? "장면 간격 ms" : "scene delay ms"} value={streamDelayMs} onChange={onStreamDelayMsChange} placeholder="24" />
            <MiniField label={isKo ? "t당 최소 재생 ms" : "min session ms"} value={streamEpisodeMinDurationMs} onChange={onStreamEpisodeMinDurationMsChange} placeholder="4500" />
            <MiniField label={isKo ? "stream 밀도" : "stream density"} value={streamDensity} onChange={onStreamDensityChange} placeholder="1.45" />
            <MiniField label={isKo ? "최소 라운드" : "min rounds"} value={streamMinRounds} onChange={onStreamMinRoundsChange} placeholder="16" />
            <MiniField label={isKo ? "최대 라운드" : "max rounds"} value={streamMaxRounds} onChange={onStreamMaxRoundsChange} placeholder="28" />
            <MiniField label={isKo ? "최대 참여자" : "max active agents"} value={streamMaxActiveAgents} onChange={onStreamMaxActiveAgentsChange} placeholder="320" />
            <MiniField label={isKo ? "이웃 fanout" : "neighbor fanout"} value={streamMaxNeighbors} onChange={onStreamMaxNeighborsChange} placeholder="10" />
            <MiniField label={isKo ? "초기 참여율" : "initial ratio"} value={streamInitialAgentRatio} onChange={onStreamInitialAgentRatioChange} placeholder="0.35" />
            <MiniField label={isKo ? "확장 속도" : "growth rate"} value={streamGrowthRate} onChange={onStreamGrowthRateChange} placeholder="1.35" />
          </div>
        </div>
      </div>
    </details>
  );
}

function DataPackPrepPanel({
  locale,
  runtimeLoading,
  runtimeError,
  runtimeStatus,
  selectedPackId,
  selectedPack,
  onSelectedPackIdChange,
  installSourcePath,
  onInstallSourcePathChange,
  pinVersion,
  onPinVersionChange,
  packActionStatus,
  onSync,
  onVerify,
  onPin,
  onInstall,
}: {
  locale: UiLocale;
  runtimeLoading: boolean;
  runtimeError: string | null;
  runtimeStatus: LocalRuntimeStatus | null;
  selectedPackId: string;
  selectedPack: LocalRuntimeStatus["packs"][number] | null;
  onSelectedPackIdChange: (value: string) => void;
  installSourcePath: string;
  onInstallSourcePathChange: (value: string) => void;
  pinVersion: string;
  onPinVersionChange: (value: string) => void;
  packActionStatus: string | null;
  onSync: () => Promise<void>;
  onVerify: () => Promise<void>;
  onPin: () => Promise<void>;
  onInstall: () => Promise<void>;
}) {
  const isKo = locale === "ko";
  const ready = String((selectedPack?.verification as Record<string, unknown> | undefined)?.ready_for_genesis ?? "unknown");
  const schema = String((selectedPack?.verification as Record<string, unknown> | undefined)?.schema_health ?? "unknown");
  return (
    <details className="rounded-[22px] border border-slate-200 bg-white shadow-sm">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-slate-900">{isKo ? "데이터팩 준비" : "Data pack prep"}</p>
          <p className="mt-1 truncate text-xs text-slate-500">
            {selectedPack ? `${selectedPack.pack_id} · ${selectedPack.country} · ${selectedPack.version}` : runtimeLoading ? (isKo ? "불러오는 중…" : "loading…") : "no pack"}
          </p>
        </div>
        <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${ready === "true" ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
          ready {ready}
        </span>
      </summary>
      <div className="grid gap-3 border-t border-slate-200 p-3">
        {runtimeError ? <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{runtimeError}</p> : null}
        {runtimeStatus ? (
          <select className="app-input" value={selectedPackId} onChange={(event) => onSelectedPackIdChange(event.target.value)}>
            {runtimeStatus.packs.map((pack) => (
              <option key={pack.pack_id} value={pack.pack_id}>
                {pack.pack_id} · {pack.country} · {pack.version}
              </option>
            ))}
          </select>
        ) : null}
        <div className="grid grid-cols-2 gap-2">
          <MetricChip label="schema" value={schema} />
          <MetricChip label={isKo ? "설치" : "installed"} value={selectedPack?.installed ? (isKo ? "예" : "yes") : (isKo ? "아니오" : "no")} />
        </div>
        <MiniField label={isKo ? "설치 소스 경로" : "install source path"} value={installSourcePath} onChange={onInstallSourcePathChange} placeholder="/absolute/path/to/personas.jsonl" />
        <MiniField label={isKo ? "고정 버전" : "pin version"} value={pinVersion} onChange={onPinVersionChange} />
        <div className="flex flex-wrap gap-2">
          <button type="button" className="app-button app-button--ghost" onClick={() => void onSync()}>{isKo ? "동기화" : "Sync"}</button>
          <button type="button" className="app-button app-button--ghost" onClick={() => void onVerify()} disabled={!selectedPack}>{isKo ? "검증" : "Verify"}</button>
          <button type="button" className="app-button app-button--ghost" onClick={() => void onPin()} disabled={!selectedPack || !pinVersion.trim()}>{isKo ? "고정" : "Pin"}</button>
          <button type="button" className="app-button app-button--ghost" onClick={() => void onInstall()} disabled={!selectedPack || !installSourcePath.trim()}>{isKo ? "설치" : "Install"}</button>
        </div>
        {packActionStatus ? <p className="text-xs text-slate-500">{packActionStatus}</p> : null}
      </div>
    </details>
  );
}

function MiniField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-500">
      {label}
      <input className="app-input" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} />
    </label>
  );
}

function RunPanel({
  locale = "ko",
  worldId,
  isRunning,
  liveT,
  observedT = null,
  liveCellCount,
  streamStatus,
  onRunStream,
  onRunSync,
  onStopStream,
  compact = false,
}: {
  locale?: UiLocale;
  worldId: string | null;
  isRunning: boolean;
  liveT: number | null;
  observedT?: number | null;
  liveCellCount: number | null;
  streamStatus?: {
    phase: string;
    progress: number;
    t: number | null;
    tMax: number | null;
    lastHeartbeatAt: number | null;
    message: string;
  };
  onRunStream: () => Promise<void>;
  onRunSync: () => Promise<void>;
  onStopStream: () => Promise<void>;
  compact?: boolean;
}) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const progress = Math.max(0, Math.min(1, Number(streamStatus?.progress ?? 0)));
  const heartbeatAge =
    streamStatus?.lastHeartbeatAt && isRunning
      ? Math.max(0, Math.round((Date.now() - streamStatus.lastHeartbeatAt) / 1000))
      : null;
  return (
    <AppPanel
      title={isKo ? "실행" : "Execution"}
      subtitle={
        compact
          ? isKo
            ? "실행과 상태를 한 패널에서 빠르게 제어합니다"
            : "Quick execution and state control in one panel"
          : isKo
            ? "이 머신에서 로컬로 실행"
            : "Run locally on this machine"
      }
      bodyClassName="space-y-3"
    >
      <div className="grid gap-2">
        <button
          type="button"
          disabled={!worldId || isRunning}
          onClick={() => void onRunStream()}
          className="app-button app-button--success"
        >
          {strings.runWithStream}
        </button>
        <button
          type="button"
          disabled={!worldId || isRunning}
          onClick={() => void onRunSync()}
          className="app-button app-button--secondary"
        >
          {strings.runSync}
        </button>
        <button
          type="button"
          disabled={!worldId || !isRunning}
          onClick={() => void onStopStream()}
          className="app-button app-button--ghost"
        >
          {isKo ? "스트림 중지" : "Stop Stream"}
        </button>
      </div>
      <div className="rounded-2xl bg-slate-50 px-3 py-3 text-sm text-slate-600">
        {isRunning ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
              <span>
                {isKo ? "stream 실행 중" : "stream active"}
                {liveT != null ? ` · t 챕터 ${liveT.toFixed(0)}` : ""}
                {observedT != null ? ` · 내부 ${observedT.toFixed(2)}` : ""}
                {streamStatus?.tMax != null ? ` / ${streamStatus.tMax.toFixed(0)}` : ""}
                {liveCellCount != null ? ` · ${liveCellCount} cells` : ""}
              </span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-slate-200">
              <div
                className="h-full rounded-full bg-emerald-500 transition-all duration-300"
                style={{ width: `${Math.round(progress * 100)}%` }}
              />
            </div>
            <div className="flex items-center justify-between text-xs text-slate-500">
              <span>{Math.round(progress * 100)}%</span>
              <span>
                {heartbeatAge != null
                  ? isKo
                    ? `heartbeat ${heartbeatAge}s 전`
                    : `heartbeat ${heartbeatAge}s ago`
                  : streamStatus?.phase ?? "starting"}
              </span>
            </div>
            {streamStatus?.message ? (
              <p className="rounded-xl bg-white px-2 py-1 text-[11px] text-slate-500">
                {streamStatus.message}
              </p>
            ) : null}
          </div>
        ) : (
          strings.runtimeReadyLocal
        )}
      </div>
    </AppPanel>
  );
}

function IntraTScenePanel({
  locale = "ko",
  sceneStream,
  chapterT,
  snapshotEvents,
  snapshotMetrics,
  renderedMetrics,
  isRunning,
  replayIndex,
  replayPaused,
  replaySpeed,
  onReplayIndexChange,
  onReplayPausedChange,
  onReplaySpeedChange,
  selectedAgentId = null,
  selectedGroupId = null,
}: {
  locale?: UiLocale;
  sceneStream: {
    currentT: number | null;
    observedT?: number | null;
    activePhase?: string | null;
    events: IntraTSceneEvent[];
    latestEvent: IntraTSceneEvent | null;
  };
  chapterT: number;
  snapshotEvents: IntraTSceneEvent[];
  snapshotMetrics: IntraTSceneMetrics | null;
  renderedMetrics: IntraTSceneMetrics | null;
  isRunning: boolean;
  replayIndex: number;
  replayPaused: boolean;
  replaySpeed: number;
  onReplayIndexChange: (value: number) => void;
  onReplayPausedChange: (value: boolean) => void;
  onReplaySpeedChange: (value: number) => void;
  selectedAgentId?: string | null;
  selectedGroupId?: string | null;
}) {
  const isKo = locale === "ko";
  const sourceEvents = isRunning ? sceneStream.events : snapshotEvents.slice(0, replayIndex);
  const focusedEvents = filterSceneEvents(sourceEvents, selectedAgentId, selectedGroupId);
  const events = focusedEvents.slice(-8).reverse();
  const latest = isRunning ? sceneStream.latestEvent : sourceEvents[sourceEvents.length - 1] ?? null;
  const observedT = Number(sceneStream.observedT ?? latest?.scene_t ?? sceneStream.currentT ?? 0);
  const chapter = Number(sceneStream.currentT ?? chapterT ?? latest?.t ?? 0);
  const streamRound = Number(latest?.stream_round_index ?? latest?.session_index ?? 0);
  const streamRoundCount = Number(latest?.stream_round_count ?? latest?.session_count ?? 0);
  const eventCursor = isRunning ? sourceEvents.length : Math.max(0, Math.min(snapshotEvents.length, replayIndex));
  const activeEvent = isRunning ? latest : snapshotEvents[Math.max(0, eventCursor - 1)] ?? latest;
  const metrics = renderedMetrics ?? snapshotMetrics;
  const progress =
    streamRound && streamRoundCount
      ? Math.max(0, Math.min(1, streamRound / Math.max(1, streamRoundCount)))
      : latest?.scene_index && latest?.scene_count
        ? Math.max(0, Math.min(1, Number(latest.scene_index) / Math.max(1, Number(latest.scene_count))))
      : snapshotEvents.length
        ? Math.max(0, Math.min(1, replayIndex / snapshotEvents.length))
        : 0;
  return (
    <AppPanel
      title={isKo ? "Stream 재생 콘솔" : "Stream Playback Console"}
      subtitle={
        isKo
          ? "t 챕터 안에서 흐르는 에이전트 협의/압력/관계 이벤트를 재생합니다"
          : "Play the consultation, pressure, and relationship events inside the selected t chapter"
      }
      bodyClassName="space-y-3"
    >
      <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
        <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-start">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {isKo ? "현재 t 챕터" : "current t chapter"}
            </p>
            <p className="mt-1 text-sm font-semibold text-slate-900">
              t {chapter.toFixed(0)}
              <span className="ml-2 text-xs font-normal text-slate-500">
                {isKo ? `내부 관찰시점 ${observedT.toFixed(2)}` : `intra-t ${observedT.toFixed(2)}`}
              </span>
            </p>
            <p className="mt-1 text-xs leading-5 text-slate-500">
              {isKo
                ? "t는 책 한 권이고, 아래 round/event가 그 안에서 재생되는 장면입니다."
                : "t is the chapter; round/event is the scene stream inside it."}
            </p>
          </div>
          <div className="rounded-2xl border border-slate-100 bg-slate-50 px-3 py-2 text-right">
            <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {isKo ? "stream round" : "stream round"}
            </p>
            <p className="mt-1 font-mono text-sm font-semibold text-slate-900">
              {streamRound || "-"} / {streamRoundCount || "-"}
            </p>
            <p className={isRunning ? "mt-1 text-xs text-emerald-600" : "mt-1 text-xs text-slate-400"}>
              {isRunning ? (isKo ? "라이브 재생" : "live") : replayPaused ? (isKo ? "일시정지" : "paused") : (isKo ? "리플레이" : "replay")}
            </p>
          </div>
        </div>
        <div className="mt-3 space-y-1.5">
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>{isKo ? "round 진행" : "round progress"}</span>
            <span>{Math.round(progress * 100)}%</span>
          </div>
          <div className="h-2 overflow-hidden rounded-full bg-slate-100">
            <div className="h-full rounded-full bg-sky-500 transition-all duration-300" style={{ width: `${Math.round(progress * 100)}%` }} />
          </div>
          <div className="flex items-center justify-between text-[11px] text-slate-500">
            <span>{isKo ? "event 커서" : "event cursor"}</span>
            <span>{eventCursor}/{isRunning ? sourceEvents.length : snapshotEvents.length}</span>
          </div>
        </div>
        {activeEvent?.summary ? (
          <p className="mt-3 rounded-2xl bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            {activeEvent.summary}
          </p>
        ) : null}
      </div>
      {!isRunning && snapshotEvents.length ? (
        <div className="grid gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3">
          <input
            type="range"
            min={0}
            max={snapshotEvents.length}
            value={Math.max(0, Math.min(snapshotEvents.length, replayIndex))}
            onChange={(event) => onReplayIndexChange(Number(event.target.value))}
            className="w-full accent-sky-500"
            aria-label={isKo ? "장면 스크러버" : "Scene scrubber"}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-xs text-slate-500">
              {isKo ? "stream event 재생" : "stream event replay"} · {eventCursor}/{snapshotEvents.length}
            </span>
            <div className="flex items-center gap-1">
            <button
              type="button"
              className="app-button app-button--ghost px-2 py-1 text-xs"
              onClick={() => {
                onReplayPausedChange(true);
                onReplayIndexChange(0);
              }}
            >
              ⏮
            </button>
            <button
              type="button"
              className="app-button app-button--ghost px-2 py-1 text-xs"
              onClick={() => {
                onReplayPausedChange(true);
                onReplayIndexChange(Math.max(0, replayIndex - 1));
              }}
            >
              ←
            </button>
            <button type="button" className="app-button app-button--ghost px-2 py-1 text-xs" onClick={() => onReplayPausedChange(!replayPaused)}>
              {replayPaused ? (isKo ? "재생" : "Play") : isKo ? "정지" : "Pause"}
            </button>
            <button
              type="button"
              className="app-button app-button--ghost px-2 py-1 text-xs"
              onClick={() => {
                onReplayPausedChange(true);
                onReplayIndexChange(Math.min(snapshotEvents.length, replayIndex + 1));
              }}
            >
              →
            </button>
            <button type="button" className="app-button app-button--ghost px-2 py-1 text-xs" onClick={() => {
              onReplayIndexChange(snapshotEvents.length);
              onReplayPausedChange(true);
            }}>
              ⏭
            </button>
            <button
              type="button"
              className="app-button app-button--ghost px-2 py-1 text-xs"
              onClick={() => onReplaySpeedChange(replaySpeed >= 2 ? 0.5 : replaySpeed + 0.5)}
            >
              {replaySpeed.toFixed(1)}x
            </button>
            </div>
          </div>
        </div>
      ) : null}
      {metrics ? (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <MetricPill label={isKo ? "협의" : "Talks"} value={String(metrics.scenes_per_t ?? sourceEvents.length)} />
          <MetricPill label={isKo ? "참여율" : "Participation"} value={`${Math.round(Number(metrics.agent_participation_rate ?? 0) * 100)}%`} />
          <MetricPill label={isKo ? "연속성" : "Continuity"} value={`${Math.round(Number(metrics.narrative_continuity_score ?? 0) * 100)}%`} />
          <MetricPill label={isKo ? "구체성" : "Specificity"} value={`${Math.round(Number(metrics.narrative_specificity_score ?? 0) * 100)}%`} />
          <MetricPill label={isKo ? "시나리오" : "Scenario"} value={`${Math.round(Number(metrics.scenario_link_rate ?? 0) * 100)}%`} />
          <MetricPill label={isKo ? "품질" : "Quality"} value={sceneQualityLabel(metrics.scene_quality_grade, isKo)} />
        </div>
      ) : null}
      {metrics?.quality_warnings?.length ? (
        <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
          <span className="font-semibold">{isKo ? "협의 품질 경고" : "Consultation quality warnings"}</span>
          <span className="ml-1">
            {metrics.quality_warnings.map((item) => sceneWarningLabel(item, isKo)).join(" · ")}
          </span>
        </div>
      ) : null}
      {events.length ? (
        <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
          {events.map((event) => (
            <div key={`${event.scene_id}-${event.scene_index}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                <span>{sceneToneLabel(event.interaction_type, event.action_record, isKo)}</span>
                <span>
                  {event.action_record ? `${socialFieldActionLabel(event.action_record, isKo ? "ko" : "en")} · ` : ""}
                  {isKo ? "스트림" : "stream"} {event.stream_round_index ?? event.session_index ?? "-"} / {event.stream_round_count ?? event.session_count ?? "-"}
                </span>
              </div>
              <p className="mt-1 text-sm leading-5 text-slate-700">{event.summary || (isKo ? "협의 이벤트 없음" : "No consultation event")}</p>
              {event.action_record?.agent_name || event.action_record?.target_label ? (
                <p className="mt-1 text-[11px] leading-4 text-slate-500">
                  {isKo ? "행동 원장" : "Action log"}: {event.action_record?.agent_name ?? "field"}
                  {event.action_record?.target_label ? ` → ${event.action_record.target_label}` : ""}
                  {event.action_record?.field_axis ? ` · ${event.action_record.field_axis}` : ""}
                </p>
              ) : null}
              {event.action_record?.interpretation ? (
                <p className="mt-1 text-[11px] leading-4 text-slate-500">
                  {event.action_record.interpretation}
                </p>
              ) : null}
              {event.narrative_reason ? (
                <p className="mt-1 text-xs leading-5 text-slate-500">{event.narrative_reason}</p>
              ) : null}
              {event.scenario_relevance ? (
                <p className="mt-1 rounded-xl bg-white px-2 py-1 text-[11px] leading-4 text-slate-500">
                  {isKo ? "시나리오" : "Scenario"}: {event.scenario_relevance}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      ) : (
        <p className="rounded-2xl bg-slate-50 px-3 py-3 text-sm leading-6 text-slate-500">
          {isKo
            ? "실행을 시작하면 한 t 내부의 협의, 긴장, 압력 변화가 빠른 이벤트로 표시됩니다."
            : "Run the simulation to see fast consultation, tension, and pressure events inside each t."}
        </p>
      )}
    </AppPanel>
  );
}

function MetricPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.12em] text-slate-400">{label}</p>
      <p className="mt-1 font-semibold text-slate-800">{value}</p>
    </div>
  );
}

function filterSceneEvents(events: IntraTSceneEvent[], selectedAgentId?: string | null, selectedGroupId?: string | null) {
  if (!selectedAgentId && !selectedGroupId) return events;
  return events.filter((event) => {
    const agentMatch =
      selectedAgentId &&
      (event.source_id === selectedAgentId || (event.target_ids ?? []).includes(selectedAgentId));
    const groupMatch = selectedGroupId && (event.group_ids ?? []).includes(selectedGroupId);
    return agentMatch || groupMatch;
  });
}

function sceneToneLabel(type: IntraTSceneEvent["interaction_type"], record: SocialActionRecord | null | undefined, isKo: boolean): string {
  return socialFieldToneLabel(socialFieldToneFromRecord(record, type), isKo ? "ko" : "en");
}

function sceneQualityLabel(value: unknown, isKo: boolean): string {
  const raw = String(value || "unknown");
  if (!isKo) return raw;
  if (raw === "strong") return "강함";
  if (raw === "usable") return "사용 가능";
  if (raw === "thin") return "얇음";
  if (raw === "weak") return "약함";
  return "미확인";
}

function sceneWarningLabel(value: string, isKo: boolean): string {
  if (!isKo) return value.replaceAll("_", " ");
  const labels: Record<string, string> = {
    too_few_scenes: "장면 수 부족",
    low_agent_participation: "참여율 낮음",
    weak_relationship_stream: "관계 흐름 약함",
    generic_scene_text: "장면 문장 추상적",
    weak_scenario_link: "시나리오 연결 약함",
  };
  return labels[value] ?? value;
}

function GenesisMeta({ locale = "ko", lastGenesis }: { locale?: UiLocale; lastGenesis: CreateWorldResult }) {
  const isKo = locale === "ko";
  return (
    <AppPanel
      title={isKo ? "월드 제안" : "World Proposal"}
      subtitle={isKo ? "초기 시뮬레이션 파라미터와 persona-aware genesis" : "Initial simulation parameters and persona-aware genesis"}
      bodyClassName="grid gap-3"
    >
      <MetricChip label="t_max" value={String(lastGenesis.t_max)} />
      <MetricChip label={isKo ? "초기 에이전트" : "Initial agents"} value={String(lastGenesis.initial_cell_count)} />
      <MetricChip label={isKo ? "스텝 의미" : "Step meaning"} value={`${lastGenesis.t_step_semantic} (${lastGenesis.t_step_unit})`} />
      <MetricChip label={isKo ? "자원" : "Nutrient"} value={String(lastGenesis.nutrient_per_step)} />
      <MetricChip label={isKo ? "역할" : "Roles"} value={lastGenesis.role_catalog.join(", ")} />
      {lastGenesis.persona_distribution_summary ? (
        <MetricChip
          label={isKo ? "페르소나 시드" : "Persona seed"}
          value={`${Number(lastGenesis.persona_distribution_summary.persona_count ?? 0)} ${isKo ? "페르소나" : "personas"}`}
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

function ConnectionMetric({
  label,
  value,
  tone,
  detail,
}: {
  label: string;
  value: string;
  tone: "green" | "amber" | "red";
  detail: string;
}) {
  const dotClass =
    tone === "green"
      ? "bg-emerald-500"
      : tone === "amber"
        ? "bg-amber-500"
        : "bg-rose-500";
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <div className="mt-1 flex items-center gap-2">
        <span className={`inline-block h-2.5 w-2.5 rounded-full ${dotClass}`} />
        <p className="text-sm font-semibold text-slate-900">{value}</p>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">{detail}</p>
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

function normalizeCollectiveSummary(groupState: unknown): CollectiveDynamicsSummary | null {
  const summary = (groupState as { summary?: CollectiveDynamicsSummary } | null | undefined)?.summary;
  if (!summary || typeof summary !== "object") return null;
  return summary;
}

function inferCollectiveSignalFromGroupState(groupState: unknown): string {
  const signal = (groupState as { collective_signal?: string } | null | undefined)?.collective_signal;
  return typeof signal === "string" && signal ? signal : "stable";
}

function inferCollectiveSignal(summary: CollectiveDynamicsSummary | null | undefined): string {
  if (!summary) return "stable";
  const roleFracture = Number(summary.role?.avg_fracture_risk ?? 0);
  const zoneFracture = Number(summary.zone?.avg_fracture_risk ?? 0);
  const roleDrift = Number(summary.role?.avg_drift_velocity ?? 0);
  const zoneDrift = Number(summary.zone?.avg_drift_velocity ?? 0);
  if (roleFracture >= 0.72 || zoneFracture >= 0.72) return "fracturing";
  if (roleDrift >= 0.42 || zoneDrift >= 0.42) return "realigning";
  return "stable";
}

function formatSignedDelta(value: number | undefined) {
  if (typeof value !== "number") return "0.000";
  return `${value >= 0 ? "+" : ""}${value.toFixed(3)}`;
}

function swarmEventThought(event: SwarmV2RunResponse["events"][number] | undefined): string {
  if (!event) return "";
  const decision = event.agent_decision ?? {};
  const thought = decision.thought ?? event.agent_thought ?? event.llm_reasoning ?? event.summary;
  return String(thought ?? "");
}

function inferCollectiveSignalFromCells(cells: CellSnapshot[]): string {
  const first = cells.find((cell) => String(cell.action_state?.collective_signal ?? "").trim());
  return String(first?.action_state?.collective_signal ?? "stable");
}

function buildCollectiveSummaryFromCells(cells: CellSnapshot[]): CollectiveDynamicsSummary | null {
  if (!cells.length) return null;
  const roleMap = new Map<string, CollectiveDynamicsListItem>();
  const zoneMap = new Map<string, CollectiveDynamicsListItem>();

  for (const cell of cells) {
    const actionState = cell.action_state ?? {};
    const roleId = String(actionState.role_group_id ?? cell.role_key ?? "agent");
    if (!roleMap.has(roleId)) {
      roleMap.set(roleId, {
        group_id: roleId,
        group_label: String(actionState.role_group_label ?? cell.role_label ?? roleId),
        fracture_risk: Number(actionState.role_group_fracture_risk ?? 0),
        tension: Number(actionState.role_group_tension ?? 0),
        drift_velocity: Number(actionState.role_group_drift_velocity ?? 0),
        cohesion: Number(actionState.role_group_cohesion ?? 0),
      });
    }
    const zoneId = String(actionState.zone_group_id ?? cell.zone_id ?? "zone");
    if (!zoneMap.has(zoneId)) {
      zoneMap.set(zoneId, {
        group_id: zoneId,
        group_label: String(actionState.zone_group_label ?? cell.zone_label ?? zoneId),
        fracture_risk: Number(actionState.zone_group_fracture_risk ?? 0),
        tension: Number(actionState.zone_group_tension ?? 0),
        drift_velocity: Number(actionState.zone_group_drift_velocity ?? 0),
        cohesion: Number(actionState.zone_group_cohesion ?? 0),
      });
    }
  }

  const summarizeAxis = (items: CollectiveDynamicsListItem[]) => {
    const count = items.length;
    const avg = (key: keyof CollectiveDynamicsListItem) =>
      count ? items.reduce((sum, item) => sum + Number(item[key] ?? 0), 0) / count : 0;
    return {
      count,
      avg_cohesion: avg("cohesion"),
      avg_tension: avg("tension"),
      avg_fracture_risk: avg("fracture_risk"),
      avg_drift_velocity: avg("drift_velocity"),
      top_fracturing: [...items]
        .sort((left, right) => Number(right.fracture_risk ?? 0) - Number(left.fracture_risk ?? 0))
        .slice(0, 4),
      top_drifting: [...items]
        .sort((left, right) => Number(right.drift_velocity ?? 0) - Number(left.drift_velocity ?? 0))
        .slice(0, 4),
    };
  };

  return {
    role: summarizeAxis(Array.from(roleMap.values())),
    zone: summarizeAxis(Array.from(zoneMap.values())),
  };
}

function flattenReviewGrounding(
  grounding: ReviewSummaryResponse["grounding"] | undefined
) {
  return Object.values(grounding ?? {}).flat();
}
