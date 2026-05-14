"use client";

import { useState, useEffect, useCallback, useMemo, useRef, type ReactNode } from "react";
import { TimeSlider } from "@/components/TimeSlider/TimeSlider";
import { InjectPanel } from "@/components/InjectPanel/InjectPanel";
import { PersonaPreview } from "@/components/PersonaPreview";
import { ScenarioTimeline } from "@/components/ScenarioTimeline/ScenarioTimeline";
import { ScenarioSummary } from "@/components/ScenarioSummary";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { CenterMapShell } from "@/components/center-map/CenterMapShell";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import type { SessionSummary } from "@/lib/api";
import {
  AgentDirectoryPanel,
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
  diffRuntimeDataPack,
  getLocalRuntimeStatus,
  getReviewSummary,
  getWorld,
  installRuntimeDataPack,
  listSnapshotTimes,
  pinRuntimeDataPack,
  rollbackRuntimeDataPack,
  getSnapshotAtT,
  sampleCellsForVisualization,
  syncDataPacks,
  testRuntimeLlmConfig,
  updateRuntimeLlmConfig,
  type CreateWorldResult,
  type CellSnapshot,
  type CollectiveDynamicsListItem,
  type CollectiveDynamicsSummary,
  type DataPackDiffResponse,
  type GodModePayload,
  type LocalRuntimeStatus,
  type ReviewSummaryResponse,
  type RuntimeLlmTestResponse,
  type IntraTSceneEvent,
  type IntraTSceneMetrics,
  verifyRuntimeDataPack,
} from "@/lib/api";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";
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
type SwarmLlmMode = "packet" | "agent";

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
    controlsContent: ReactNode;
    runtimeContent: ReactNode;
    thoughtCells: CellSnapshot[];
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
  const [simulationMode, setSimulationMode] = useState<SimulationMode>("precision");
  const [swarmAgentCount, setSwarmAgentCount] = useState("1000");
  const [swarmMesoGroups, setSwarmMesoGroups] = useState("24");
  const [swarmLlmMode, setSwarmLlmMode] = useState<SwarmLlmMode>("packet");
  const [genesisPrompt, setGenesisPrompt] = useState("");
  const [lastGenesis, setLastGenesis] = useState<CreateWorldResult | null>(null);
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
  const [godModeEnabled, setGodModeEnabled] = useState(false);
  const [godRoleMode, setGodRoleMode] = useState<"auto" | "manual">("auto");
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
  const [selectedHistoryIndex, setSelectedHistoryIndex] = useState<number | null>(null);
  const [packDiffPreview, setPackDiffPreview] = useState<DataPackDiffResponse | null>(null);
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
  const selectedHistoryEntry = useMemo(() => {
    if (!selectedPack || selectedHistoryIndex == null || !Array.isArray(selectedPack.history)) return null;
    return (selectedPack.history[selectedHistoryIndex] as Record<string, unknown> | undefined) ?? null;
  }, [selectedHistoryIndex, selectedPack]);
  const verificationHistory = useMemo(
    () =>
      Array.isArray(selectedPack?.history)
        ? selectedPack.history.filter((item) => {
            const action = String((item as Record<string, unknown>).action ?? "");
            return action === "verify" || action === "validate";
          })
        : [],
    [selectedPack]
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

  useEffect(() => {
    setSelectedHistoryIndex(null);
    setPackDiffPreview(null);
  }, [selectedPackId]);

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
      const godMode: GodModePayload | null = godModeEnabled || swarmEnabled
        ? {
            enabled: true,
            auto_roles_from_personas: godRoleMode === "auto",
            overrides: {
              t_max: parsePositiveNumber(customTMax),
              initial_cell_count: parsePositiveInt(swarmEnabled ? swarmAgentCount : customInitialCells),
              role_catalog: godRoleMode === "manual" ? splitRoles(customRoles) : undefined,
              simulation_mode: simulationMode,
              t_step_unit: customTUnit.trim() || undefined,
              nutrient_per_step: parsePositiveNumber(customNutrient),
              persona_country: customCountry.trim() || undefined,
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
              zone_layout: swarmEnabled ? "swarm" : zoneLayout,
              zone_spacing: parsePositiveNumber(swarmEnabled ? "1.25" : zoneSpacing),
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
    bumpChartRefresh,
    customCountry,
    customInitialCells,
    customNutrient,
    customRoles,
    customTMax,
    customTUnit,
    disconnectWebSocket,
    godRoleMode,
    genesisPrompt,
    godModeEnabled,
    simulationMode,
    swarmAgentCount,
    swarmLlmMode,
    swarmMesoGroups,
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
      await runWithWebSocketStream(worldId);
      await refreshSnapshots(worldId, { preferLatest: true });
    } catch (e) {
      setActionError((e as Error).message);
    }
  }, [refreshSnapshots, runWithWebSocketStream, worldId]);

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

  const handleInjected = useCallback(async () => {
    if (!worldId) return;
    await refreshSnapshots(worldId, { preferLatest: true });
  }, [refreshSnapshots, worldId]);

  useEffect(() => {
    if (!isRunning || !worldId || liveT == null) return;
    const nextT = Math.max(0, Math.round(liveT));
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
        setSceneReplayIndex(Math.min(1, (snap.scene_events ?? []).length));
        setSceneReplayPaused(false);
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
    Math.round(Number(liveObserver?.t ?? -1)) === Math.round(currentT) &&
    (liveObserver?.cells?.length ?? 0) > 0;

  const renderedSnapshotCells = shouldUseLiveObserver ? liveObserver?.cells ?? [] : snapshotCells;
  const renderedVisibleCells = shouldUseLiveObserver ? liveObserver?.cells ?? [] : visibleCells;
  const renderedSceneEvents = shouldUseLiveObserver
    ? liveSceneStream.events
    : snapshotSceneEvents.slice(0, Math.max(0, Math.min(snapshotSceneEvents.length, sceneReplayIndex)));
  const renderedSceneMetrics = shouldUseLiveObserver ? liveSceneStream.metrics : snapshotSceneMetrics;

  useEffect(() => {
    if (shouldUseLiveObserver || sceneReplayPaused || snapshotSceneEvents.length === 0) return;
    if (sceneReplayIndex >= snapshotSceneEvents.length) return;
    const delay = Math.max(120, 520 / Math.max(0.5, sceneReplaySpeed));
    const timer = window.setTimeout(() => {
      setSceneReplayIndex((value) => Math.min(snapshotSceneEvents.length, value + 1));
    }, delay);
    return () => window.clearTimeout(timer);
  }, [sceneReplayIndex, sceneReplayPaused, sceneReplaySpeed, shouldUseLiveObserver, snapshotSceneEvents.length]);
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
        <RunPanel
          locale={locale}
          worldId={worldId}
          isRunning={isRunning}
          liveT={liveT}
          liveCellCount={liveCellCount}
          streamStatus={streamStatus}
          onRunStream={handleRunStream}
          onRunSync={handleRunSync}
          compact
        />
        <IntraTScenePanel
          locale={locale}
          sceneStream={liveSceneStream}
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
        <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4 shadow-sm">
          <div className="mb-3 flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-slate-900">{isKo ? "t 시점 변경" : "Time Step Control"}</p>
              <p className="mt-1 text-xs text-slate-500">
                {isKo ? "현재 관측 중인 시점을 즉시 옮깁니다." : "Move the currently observed simulation time instantly."}
              </p>
            </div>
            <span className="text-xs text-slate-500">
              {availableT.length} {isKo ? "프레임" : "frames"}
            </span>
          </div>
          <div className="space-y-3">
            <TimeSlider t={currentT} tMin={tSliderMin} tMax={tSliderMax} step={1} onChange={setCurrentT} disabled={sliderDisabled} />
            <TimelineBookmarks
              t={currentT}
              tMin={tSliderMin}
              tMax={Math.max(tSliderMin + 1, tSliderMax)}
              markers={[...timelineMarkers, ...reviewMarkers]}
              bookmarks={bookmarks}
              onJump={setCurrentT}
              onAddBookmark={addBookmark}
              onRemoveBookmark={removeBookmark}
            />
          </div>
        </div>
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
      addBookmark,
      availableT.length,
      bookmarks,
      chartRefreshKey,
      currentT,
      handleInjected,
      handleRunStream,
      handleRunSync,
      isKo,
      isRunning,
      liveCellCount,
      liveSceneStream,
      liveT,
      locale,
      reviewInjectPreset,
      reviewSummary,
      reviewMarkers,
      sliderDisabled,
      timelineMarkers,
      tSliderMax,
      tSliderMin,
      worldId,
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
      availableModelPresets,
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
      runtimeStatus?.llm?.model,
      runtimeStatus?.llm?.provider,
      taskBudgetDraft,
      taskPriorityDraft,
      llmTestResult,
    ]
  );

  useEffect(() => {
    onDockPayloadChange?.({
      controlsContent: controlsDockContent,
      runtimeContent: runtimeDockContent,
      thoughtCells: renderedSnapshotCells,
      currentT,
      collectiveSummary: renderedCollectiveSummary,
      collectiveSignal: renderedCollectiveSignal,
      connectionState: llmConnectionState,
    });
  }, [controlsDockContent, currentT, llmConnectionState, onDockPayloadChange, renderedCollectiveSignal, renderedCollectiveSummary, renderedSnapshotCells, runtimeDockContent]);


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
          stage === "run" && worldId
            ? `${worldId} · t=${currentT.toFixed(1)} · ${renderedVisibleCells.length.toLocaleString()} agents`
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
              disabled={!worldId}
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
                className={simulationMode === "precision" ? "is-active" : ""}
                onClick={() => applySimulationMode("precision")}
              >
                Precision
              </button>
              <button
                type="button"
                className={simulationMode === "swarm" ? "is-active" : ""}
                onClick={() => applySimulationMode("swarm")}
              >
                Swarm
              </button>
            </div>
          ) : null}
          {stage === "run" ? (
            <div className="unified-dashboard__status-strip">
              <span>{renderedCollectiveSignal}</span>
              <span>{isKo ? "압력" : "pressure"} {Math.round((renderedCollectiveSummary?.role?.avg_fracture_risk ?? 0) * 100)}</span>
              {renderedVisualStats?.sampled ? (
                <span className="is-warn">
                  {isKo ? "샘플링" : "sampled"} {renderedVisibleCells.length.toLocaleString()} / {renderedVisualStats.totalCells.toLocaleString()}
                </span>
              ) : null}
            </div>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenWorkbenchView?.("data-packs")}
          >
            {strings.openDataPacks}
          </button>
        </div>
      </AppPanel>

      {stage === "setup" && (
        <div className="godview-setup">
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
            <div className="grid gap-4 xl:grid-cols-2">
            <AppPanel
              title={isKo ? "시나리오 생성" : "Scenario Genesis"}
              subtitle={isKo ? "프롬프트, 페르소나 팩, 월드 시드 구성을 먼저 정합니다" : "Prompt, persona packs, and world seed configuration"}
              bodyClassName="space-y-4"
              action={
                <label className="flex items-center gap-2 rounded-full bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700">
                  <input
                    type="checkbox"
                    checked={godModeEnabled}
                    onChange={(e) => setGodModeEnabled(e.target.checked)}
                  />
                  {isKo ? "갓 모드" : "God Mode"}
                </label>
              }
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
                    {isKo ? "대량 에이전트 + Meso packet LLM" : "Mass agents + meso packet LLM"}
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
                    </select>
                  </label>
                  <p className="md:col-span-3 rounded-2xl bg-white/75 px-3 py-2 text-[11px] leading-5 text-sky-900">
                    {isKo
                      ? "MVP에서는 Micro agent는 rule 기반으로 빠르게 움직이고, Meso group packet 설정을 engine params에 보존합니다. Packet/1:1 실제 호출 전략은 다음 단계에서 이 설정을 소비하도록 확장합니다."
                      : "In this MVP, micro agents move through rules while meso group packet settings are persisted in engine params. The next step wires Packet/1:1 settings into the live LLM scheduler."}
                  </p>
                </div>
              ) : null}
              <div className="flex flex-wrap gap-2">
                <button type="button" onClick={handleCreateWorld} className="app-button app-button--primary">
                  {isKo ? "월드 생성" : "Create world"}
                </button>
                {worldId && (
                  <button type="button" onClick={() => setStage("run")} className="app-button app-button--secondary">
                    {isKo ? "실행 단계 열기" : "Open Run Stage"}
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
                      {isKo ? "초기 에이전트 수" : "initial cells"}
                      <input value={customInitialCells} onChange={(e) => setCustomInitialCells(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500 md:col-span-2">
                      {isKo ? "역할 선택 방식" : "role selection mode"}
                      <select
                        value={godRoleMode}
                        onChange={(e) => setGodRoleMode(e.target.value as "auto" | "manual")}
                        className="app-input"
                      >
                        <option value="auto">{isKo ? "자동 (페르소나 기반)" : "Auto (from personas)"}</option>
                        <option value="manual">{isKo ? "수동 입력" : "Manual"}</option>
                      </select>
                    </label>
                    {godRoleMode === "manual" ? (
                      <label className="flex flex-col gap-1 text-xs text-slate-500 md:col-span-2">
                        {isKo ? "역할 목록 (쉼표 구분)" : "roles (comma separated)"}
                        <input value={customRoles} onChange={(e) => setCustomRoles(e.target.value)} className="app-input" />
                      </label>
                    ) : null}
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "페르소나 국가" : "persona country"}
                      <input value={customCountry} onChange={(e) => setCustomCountry(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "단계당 자원" : "nutrient / step"}
                      <input value={customNutrient} onChange={(e) => setCustomNutrient(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "시간 단위" : "time unit"}
                      <select value={customTUnit} onChange={(e) => setCustomTUnit(e.target.value)} className="app-input">
                        <option value="hour">hour</option>
                        <option value="day">day</option>
                        <option value="month">month</option>
                        <option value="year">year</option>
                        <option value="decade_scale">decade_scale</option>
                      </select>
                    </label>
                    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                      {godRoleMode === "auto"
                        ? isKo
                          ? "페르소나 분포를 기준으로 역할 목록을 자동 구성합니다."
                          : "Role catalog is derived automatically from persona distribution."
                        : isKo
                          ? "수동 입력한 역할 목록을 그대로 사용합니다."
                          : "The manual role catalog is used as entered."}
                    </div>
                  </div>
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "구역 수" : "zone count"}
                      <input value={zoneCount} onChange={(e) => setZoneCount(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "구역 레이아웃" : "zone layout"}
                      <select value={zoneLayout} onChange={(e) => setZoneLayout(e.target.value)} className="app-input">
                        <option value="grid">grid</option>
                        <option value="bands">bands</option>
                        <option value="ring">ring</option>
                      </select>
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "구역 간격" : "zone spacing"}
                      <input value={zoneSpacing} onChange={(e) => setZoneSpacing(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "영향력 단계치" : "influence step"}
                      <input value={zoneInfluenceStep} onChange={(e) => setZoneInfluenceStep(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "마찰 단계치" : "friction step"}
                      <input value={zoneFrictionStep} onChange={(e) => setZoneFrictionStep(e.target.value)} className="app-input" />
                    </label>
                  </div>
                  <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white/80 p-3 md:grid-cols-3">
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "z 모드" : "z mode"}
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
                      {isKo ? "z 가중치" : "z weight"}
                      <input value={zWeight} onChange={(e) => setZWeight(e.target.value)} className="app-input" />
                    </label>
                    <label className="flex flex-col gap-1 text-xs text-slate-500">
                      {isKo ? "z 스케일" : "z scale"}
                      <input value={zScale} onChange={(e) => setZScale(e.target.value)} className="app-input" />
                    </label>
                    <p className="md:col-span-3 rounded-2xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
                      {isKo
                        ? "`z`는 메시 높이가 아니라 사회적 고도로 취급됩니다. `weight`는 상호작용 거리에서 고도가 얼마나 반영되는지, `scale`은 필드 진폭을 얼마나 크게 둘지 조절합니다."
                        : "`z` is treated as social elevation, not mesh height. Use `weight` to control how much elevation affects interaction distance, and `scale` to control field amplitude."}
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

            <AppPanel
              title={isKo ? "데이터 팩 라이프사이클" : "Data Pack Lifecycle"}
              subtitle={isKo ? "장기 시뮬레이션 전에 페르소나 팩 상태를 준비합니다" : "Prepare persona packs before long-run simulation"}
              bodyClassName="space-y-3"
            >
              {runtimeLoading ? <p className="text-sm text-slate-500">{isKo ? "런타임 상태 불러오는 중…" : "Runtime status loading…"}</p> : null}
              {runtimeError ? (
                <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                  runtime/data-pack 상태를 읽지 못했습니다: {runtimeError}
                </p>
              ) : null}
              {runtimeStatus ? (
                <>
                  <div className="grid gap-2 md:grid-cols-[220px_minmax(0,1fr)]">
                    <select
                      className="app-input"
                      value={selectedPack?.pack_id ?? ""}
                      onChange={(event) => setSelectedPackId(event.target.value)}
                    >
                      {runtimeStatus.packs.map((pack) => (
                        <option key={pack.pack_id} value={pack.pack_id}>
                          {pack.pack_id} · {pack.country} · {pack.version}
                        </option>
                      ))}
                    </select>
                    <div className="grid gap-2 md:grid-cols-3">
                      <MetricChip label={isKo ? "설치됨" : "installed"} value={selectedPack?.installed ? (isKo ? "예" : "yes") : isKo ? "아니오" : "no"} />
                      <MetricChip
                        label={isKo ? "고정 버전" : "pinned"}
                        value={selectedPack?.pinned ? String(selectedPack?.pinned_version || (isKo ? "예" : "yes")) : isKo ? "아니오" : "no"}
                      />
                      <MetricChip
                        label={isKo ? "생성 준비" : "genesis ready"}
                        value={String((selectedPack?.verification as Record<string, unknown> | undefined)?.ready_for_genesis ?? "unknown")}
                      />
                    </div>
                  </div>
                  {selectedPack ? (
                    <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white/80 p-3">
                      <p className="text-sm leading-6 text-slate-600">
                        {selectedPack.dataset_id || selectedPack.description}
                      </p>
                      <div className="grid gap-2 md:grid-cols-2">
                        <MetricChip
                          label="schema"
                          value={String((selectedPack.verification as Record<string, unknown> | undefined)?.schema_health ?? "unknown")}
                        />
                        <MetricChip
                          label="country consistency"
                          value={String((selectedPack.verification as Record<string, unknown> | undefined)?.country_consistency ?? "n/a")}
                        />
                      </div>
                      <div className="grid gap-3 md:grid-cols-2">
                        <label className="flex flex-col gap-1 text-xs text-slate-500">
                          {isKo ? "설치 소스 경로" : "install source path"}
                          <input
                            value={installSourcePath}
                            onChange={(event) => setInstallSourcePath(event.target.value)}
                            className="app-input"
                            placeholder="/absolute/path/to/personas.jsonl"
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-xs text-slate-500">
                          {isKo ? "고정할 버전" : "pin version"}
                          <input
                            value={pinVersion}
                            onChange={(event) => setPinVersion(event.target.value)}
                            className="app-input"
                            placeholder="2026.05"
                          />
                        </label>
                      </div>
                      <div className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={async () => {
                            setPackActionStatus("syncing manifest…");
                            try {
                              await syncDataPacks();
                              await reloadRuntimeStatus();
                              setPackActionStatus("manifest synced");
                            } catch (reason) {
                              setPackActionStatus(reason instanceof Error ? reason.message : "sync failed");
                            }
                          }}
                        >
                          {isKo ? "매니페스트 동기화" : "Sync Manifest"}
                        </button>
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={async () => {
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
                        >
                          {isKo ? "검증" : "Verify"}
                        </button>
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={async () => {
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
                        >
                          {isKo ? "버전 고정" : "Pin Version"}
                        </button>
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={async () => {
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
                        >
                          {isKo ? "설치 / 새로고침" : "Install / Refresh"}
                        </button>
                      </div>
                      {Array.isArray(selectedPack.history) && selectedPack.history.length ? (
                        <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {isKo ? "라이프사이클 이력" : "Lifecycle History"}
                          </p>
                          {selectedPack.history
                            .slice()
                            .reverse()
                            .slice(0, 6)
                            .map((item, index) => {
                              const historyIndex = selectedPack.history
                                ? selectedPack.history.length - 1 - index
                                : index;
                              return (
                                <div key={`${historyIndex}-${String(item.at ?? "at")}`} className="session-thread-card">
                                  <div className="session-thread-card__header">
                                    <p className="session-thread-card__title">{String(item.action ?? "event")}</p>
                                    <span className="session-thread-card__meta">{String(item.at ?? "")}</span>
                                  </div>
                                  <p className="session-thread-card__prompt">
                                    {String((item.detail as Record<string, unknown> | undefined)?.version ?? (item.detail as Record<string, unknown> | undefined)?.restored_version ?? "")}
                                  </p>
                                  <div className="session-thread-card__actions">
                                    <button
                                      type="button"
                                      className="app-button app-button--ghost"
                                      onClick={async () => {
                                        if (!selectedPack) return;
                                        setPackActionStatus("loading diff preview…");
                                        setSelectedHistoryIndex(historyIndex);
                                        try {
                                          const preview = await diffRuntimeDataPack(selectedPack.pack_id, historyIndex);
                                          setPackDiffPreview(preview);
                                          setPackActionStatus("diff preview ready");
                                        } catch (reason) {
                                          setPackActionStatus(
                                            reason instanceof Error ? reason.message : "diff preview failed"
                                          );
                                        }
                                      }}
                                    >
                                      {isKo ? "미리보기" : "Preview"}
                                    </button>
                                    <button
                                      type="button"
                                      className="app-button app-button--ghost"
                                      onClick={async () => {
                                        if (!selectedPack) return;
                                        setPackActionStatus("rolling back pack…");
                                        try {
                                          await rollbackRuntimeDataPack(selectedPack.pack_id, historyIndex);
                                          await reloadRuntimeStatus();
                                          setPackActionStatus("rollback complete");
                                        } catch (reason) {
                                          setPackActionStatus(
                                            reason instanceof Error ? reason.message : "rollback failed"
                                          );
                                        }
                                      }}
                                    >
                                      {isKo ? "롤백" : "Rollback"}
                                    </button>
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      ) : null}
                      {selectedHistoryEntry ? (
                        <div className="grid gap-2 rounded-2xl border border-sky-200 bg-sky-50/80 p-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-sky-700">
                            {isKo ? "버전 차이 미리보기" : "Version Diff Preview"}
                          </p>
                          <p className="text-sm text-slate-600">
                            {isKo ? "선택한 이력 항목" : "selected history entry"}: {String(selectedHistoryEntry.action ?? "event")} · {String(selectedHistoryEntry.at ?? "")}
                          </p>
                          {packDiffPreview?.changes.length ? (
                            <div className="grid gap-2">
                              {packDiffPreview.changes.map((item) => (
                                <div key={String(item.field ?? "field")} className="session-thread-card">
                                  <div className="session-thread-card__header">
                                    <p className="session-thread-card__title">{String(item.field ?? "field")}</p>
                                  </div>
                                  <p className="session-thread-card__prompt">
                                    current: {String(item.current ?? "n/a")} {"->"} rollback: {String(item.rollback ?? "n/a")}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p className="text-xs text-slate-500">{isKo ? "현재 상태와 달라지는 주요 필드가 없습니다." : "No major fields change from the current state."}</p>
                          )}
                          {packDiffPreview?.verification_changes.length ? (
                            <div className="grid gap-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                                {isKo ? "검증 차이" : "Verification Delta"}
                              </p>
                              {packDiffPreview.verification_changes.map((item) => (
                                <div key={`verify-${String(item.field ?? "field")}`} className="session-thread-card">
                                  <div className="session-thread-card__header">
                                    <p className="session-thread-card__title">{String(item.field ?? "field")}</p>
                                  </div>
                                  <p className="session-thread-card__prompt">
                                    current: {String(item.current ?? "n/a")} {"->"} rollback: {String(item.rollback ?? "n/a")}
                                  </p>
                                </div>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                      {verificationHistory.length ? (
                        <div className="grid gap-2 rounded-2xl border border-slate-200 bg-white/80 p-3">
                          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                            {isKo ? "검증 타임라인" : "Verification Timeline"}
                          </p>
                          {verificationHistory.slice().reverse().slice(0, 4).map((item, index) => (
                            <div key={`${index}-${String((item as Record<string, unknown>).at ?? "")}`} className="session-thread-card">
                              <div className="session-thread-card__header">
                                <p className="session-thread-card__title">{String((item as Record<string, unknown>).action ?? "verify")}</p>
                                <span className="session-thread-card__meta">{String((item as Record<string, unknown>).at ?? "")}</span>
                              </div>
                              <p className="session-thread-card__prompt">
                                schema {String(((item as Record<string, unknown>).detail as Record<string, unknown> | undefined)?.schema_health ?? "n/a")} · ready {String(((item as Record<string, unknown>).detail as Record<string, unknown> | undefined)?.ready_for_genesis ?? "n/a")}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                      {packActionStatus ? <p className="text-xs text-slate-500">{packActionStatus}</p> : null}
                    </div>
                  ) : null}
                </>
              ) : null}
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
              <SetupItem index="02" title={isKo ? "페르소나와 데이터 팩" : "Persona & Data Packs"} body={isKo ? "국가별 persona pack과 source attribution을 확인합니다." : "Check country packs and source attribution before genesis."} />
              <SetupItem index="03" title={isKo ? "생성 제어" : "Genesis Controls"} body={isKo ? "필요하면 God Mode에서 zone/z/role seed를 미세 조정합니다." : "Use God Mode to fine-tune zone, z, and role seeds when needed."} />
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
        <div className="unified-dashboard">
          <main className="unified-dashboard__center">
            <div className="unified-dashboard__center-header">
              <div>
                <p className="unified-dashboard__section-label">{isKo ? "Center Visualization" : "Center Visualization"}</p>
                <h3>{isKo ? "실시간 소셜 필드" : "Live Social Field"}</h3>
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
              currentT={currentT}
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

          <aside className="unified-dashboard__right">
            <div className="unified-dashboard__section-label">{isKo ? "Live Insights" : "Live Insights"}</div>
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
            {reviewSummary ? (
              <AppPanel
                title={isKo ? "리뷰 스냅샷" : "Review Snapshot"}
                subtitle={reviewLoading ? (isKo ? "분석 요약 새로고침 중…" : "Refreshing analyst summary…") : reviewSummary.headline}
                bodyClassName="space-y-3"
              >
              <p className="text-sm leading-6 text-slate-700">{reviewSummary.summary}</p>
              {reviewSummary.causal_analysis.slice(0, 2).map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="session-thread-card__prompt">{item}</p>
                </div>
              ))}
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
                          }}
                        >
                          {isKo ? "주입 패널로 사용" : "Use in Injection Panel"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              ) : null}
              <button
                type="button"
                className="app-button app-button--ghost"
                onClick={() => setStage("review")}
              >
                {isKo ? "리뷰 단계 열기" : "Open Review Stage"}
              </button>
              </AppPanel>
            ) : null}
          </aside>

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
  locale = "ko",
  worldId,
  isRunning,
  liveT,
  liveCellCount,
  streamStatus,
  onRunStream,
  onRunSync,
  compact = false,
}: {
  locale?: UiLocale;
  worldId: string | null;
  isRunning: boolean;
  liveT: number | null;
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
      </div>
      <div className="rounded-2xl bg-slate-50 px-3 py-3 text-sm text-slate-600">
        {isRunning ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent" />
              <span>
                {isKo ? "실행 중 · stream active" : "Running · stream active"}
                {liveT != null ? ` · t ${liveT.toFixed(1)}` : ""}
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
  sceneStream: { currentT: number | null; events: IntraTSceneEvent[]; latestEvent: IntraTSceneEvent | null };
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
  const metrics = renderedMetrics ?? snapshotMetrics;
  const progress =
    latest?.scene_index && latest?.scene_count
      ? Math.max(0, Math.min(1, Number(latest.scene_index) / Math.max(1, Number(latest.scene_count))))
      : snapshotEvents.length
        ? Math.max(0, Math.min(1, replayIndex / snapshotEvents.length))
        : 0;
  return (
    <AppPanel
      title={isKo ? "t 내부 장면 스트림" : "Intra-T Scene Stream"}
      subtitle={
        isKo
          ? "선택한 t는 그대로 유지하고, 그 안의 상호작용을 장면처럼 재생합니다"
          : "Keep discrete t selection while replaying its internal interaction beats"
      }
      bodyClassName="space-y-3"
    >
      <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
        <div className="flex items-center justify-between gap-3 text-xs text-slate-500">
          <span>
            {sceneStream.currentT != null ? `t ${sceneStream.currentT.toFixed(0)}` : isKo ? "대기 중" : "idle"}
            {latest?.scene_index && latest?.scene_count ? ` · scene ${latest.scene_index}/${latest.scene_count}` : ""}
          </span>
          <span className={isRunning ? "text-emerald-600" : "text-slate-400"}>
            {isRunning ? (isKo ? "재생 중" : "playing") : isKo ? "정지" : "paused"}
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-sky-500 transition-all duration-300" style={{ width: `${Math.round(progress * 100)}%` }} />
        </div>
      </div>
      {!isRunning && snapshotEvents.length ? (
        <div className="grid grid-cols-[1fr_auto] items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-3">
          <input
            type="range"
            min={0}
            max={snapshotEvents.length}
            value={Math.max(0, Math.min(snapshotEvents.length, replayIndex))}
            onChange={(event) => onReplayIndexChange(Number(event.target.value))}
            className="w-full accent-sky-500"
            aria-label={isKo ? "장면 스크러버" : "Scene scrubber"}
          />
          <div className="flex items-center gap-1">
            <button type="button" className="app-button app-button--ghost px-2 py-1 text-xs" onClick={() => onReplayPausedChange(!replayPaused)}>
              {replayPaused ? (isKo ? "재생" : "Play") : isKo ? "정지" : "Pause"}
            </button>
            <button type="button" className="app-button app-button--ghost px-2 py-1 text-xs" onClick={() => {
              onReplayIndexChange(0);
              onReplayPausedChange(false);
            }}>
              {isKo ? "다시" : "Replay"}
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
      ) : null}
      {metrics ? (
        <div className="grid grid-cols-3 gap-2 text-xs">
          <MetricPill label={isKo ? "장면" : "Scenes"} value={String(metrics.scenes_per_t ?? sourceEvents.length)} />
          <MetricPill label={isKo ? "참여율" : "Participation"} value={`${Math.round(Number(metrics.agent_participation_rate ?? 0) * 100)}%`} />
          <MetricPill label={isKo ? "연속성" : "Continuity"} value={`${Math.round(Number(metrics.narrative_continuity_score ?? 0) * 100)}%`} />
        </div>
      ) : null}
      {events.length ? (
        <div className="max-h-56 space-y-2 overflow-y-auto pr-1">
          {events.map((event) => (
            <div key={`${event.scene_id}-${event.scene_index}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-2">
              <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-[0.14em] text-slate-400">
                <span>{sceneToneLabel(event.interaction_type, isKo)}</span>
                <span>{event.scene_index ?? "-"} / {event.scene_count ?? "-"}</span>
              </div>
              <p className="mt-1 text-sm leading-5 text-slate-700">{event.summary || (isKo ? "장면 요약 없음" : "No scene summary")}</p>
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
            ? "실행을 시작하면 한 t 내부의 협의, 긴장, 압력 변화가 장면 단위로 표시됩니다."
            : "Run the simulation to see conversations, tension, and pressure shifts inside each t."}
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

function sceneToneLabel(type: IntraTSceneEvent["interaction_type"], isKo: boolean): string {
  if (type === "positive") return isKo ? "협력" : "positive";
  if (type === "negative") return isKo ? "갈등" : "negative";
  if (type === "hostile") return isKo ? "적대" : "hostile";
  if (type === "dialogue") return isKo ? "대화" : "dialogue";
  return isKo ? "압력" : "pressure";
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
