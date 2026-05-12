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
  type DataPackDiffResponse,
  type GodModePayload,
  type LocalRuntimeStatus,
  type ReviewSummaryResponse,
  type RuntimeLlmTestResponse,
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

const LLM_PROVIDER_PRESETS = [
  {
    id: "openai",
    label: "OpenAI",
    provider: "openai",
    baseUrl: "https://api.openai.com/v1",
    models: ["gpt-4.1-mini", "gpt-4.1", "gpt-4o-mini"],
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
  initialInjectPreset = null,
  onOpenWorkbenchView,
  onWorldSelected,
  onConsumeInitialInjectPreset,
  runtimeStatusExternal,
  runtimeErrorExternal,
  onRefreshRuntimeExternal,
}: {
  locale?: UiLocale;
  initialWorldId?: string | null;
  initialT?: number | null;
  initialInjectPreset?: ReviewSummaryResponse["inject_presets"][number] | null;
  onOpenWorkbenchView?: (view: WorkbenchView) => void;
  onWorldSelected?: (worldId: string) => void;
  onConsumeInitialInjectPreset?: () => void;
  runtimeStatusExternal?: LocalRuntimeStatus | null;
  runtimeErrorExternal?: string | null;
  onRefreshRuntimeExternal?: () => Promise<void> | void;
}) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const [stage, setStage] = useState<"setup" | "run">("setup");
  const [genesisPrompt, setGenesisPrompt] = useState("");
  const [lastGenesis, setLastGenesis] = useState<CreateWorldResult | null>(null);
  const [worldId, setWorldId] = useState<string | null>(null);
  const [availableT, setAvailableT] = useState<number[]>([]);
  const [currentT, setCurrentT] = useState(0);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotCells, setSnapshotCells] = useState<CellSnapshot[]>([]);
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
  const [autoFitLayout, setAutoFitLayout] = useState(true);
  const [reviewSummary, setReviewSummary] = useState<ReviewSummaryResponse | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
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
  const usesExternalRuntime = runtimeStatusExternal !== undefined;

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
  const llmHealth = llmRuntime?.health ?? null;
  const liveBenchmarkReadiness = useMemo(() => {
    const provider = runtimeStatus?.llm?.provider ?? "stub";
    const model = runtimeStatus?.llm?.model ?? "stub";
    const hasKey = Boolean(runtimeStatus?.llm?.has_api_key);
    const enabled = Boolean(runtimeStatus?.llm?.enabled);
    const baseUrl = String(runtimeStatus?.llm?.base_url || "");
    const isLocalOllama = provider === "ollama";
    const ready = enabled && provider !== "stub" && (isLocalOllama || hasKey) && Boolean(baseUrl);
    const reasons: string[] = [];
    if (!enabled) reasons.push(isKo ? "LLM 런타임이 비활성화됨" : "LLM runtime disabled");
    if (provider === "stub") reasons.push(isKo ? "provider가 stub 상태" : "provider is still stub");
    if (!baseUrl) reasons.push(isKo ? "base URL이 비어 있음" : "base URL is missing");
    if (!isLocalOllama && !hasKey) reasons.push(isKo ? "API 키가 없음" : "API key missing");
    return {
      ready,
      provider,
      model,
      reasons,
      command: `engine/backend/.venv/bin/python engine/backend/scripts/benchmark_simulation.py --cells 1000 --steps 4 --repeat 1 --llm-mode runtime-config --llm-profiles balanced llm-first --llm-strict-mode llm-preferred --include-review-payload --include-review-suite --json`,
    };
  }, [isKo, runtimeStatus]);
  const recentFallbackRuns = useMemo(
    () => (llmRuntime?.recent_runs ?? []).filter((item) => item.used_fallback).slice(0, 5),
    [llmRuntime]
  );
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
  }, [applyRuntimePayload, personaRefreshKey, usesExternalRuntime]);

  useEffect(() => {
    setSelectedHistoryIndex(null);
    setPackDiffPreview(null);
  }, [selectedPackId]);

  useEffect(() => {
    if (!worldId || availableT.length === 0) {
      setReviewSummary(null);
      setReviewLoading(false);
      setReviewError(null);
      return;
    }
    let cancelled = false;
    setReviewLoading(true);
    setReviewError(null);
    getReviewSummary(worldId)
      .then((payload) => {
        if (!cancelled) {
          setReviewSummary(payload);
        }
      })
      .catch((reason) => {
        if (!cancelled) {
          setReviewSummary(null);
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
  }, [availableKey, chartRefreshKey, worldId]);

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
      onWorldSelected?.(out.world_id);
      setActiveSessionId(out.session_id);
      setAvailableT([]);
      setCurrentT(0);
      setVisibleCells([]);
      setSnapshotCells([]);
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
    if (!worldId || availableT.length === 0) {
      if (availableT.length === 0 && worldId) {
      setVisibleCells([]);
      setSnapshotCells([]);
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
        setSnapshotCells(snap.cells);
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
    let cancelled = false;
    setActionError(null);
    Promise.all([getWorld(initialWorldId), listSnapshotTimes(initialWorldId)])
      .then(([meta, snapshots]) => {
        if (cancelled) return;
        setWorldId(meta.world_id);
        onWorldSelected?.(meta.world_id);
        setGenesisPrompt(meta.genesis_prompt ?? "");
        setAvailableT(snapshots.available_t);
        const lastT = snapshots.available_t[snapshots.available_t.length - 1] ?? 0;
        if (typeof initialT === "number" && snapshots.available_t.length > 0) {
          const nearest = snapshots.available_t.reduce((best, value) =>
            Math.abs(value - initialT) < Math.abs(best - initialT) ? value : best
          );
          setCurrentT(nearest);
        } else {
          setCurrentT(lastT);
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
        subtitle={strings.twoStepFlow}
        bodyClassName="flex flex-wrap items-center justify-between gap-3"
      >
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
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenWorkbenchView?.("data-packs")}
          >
            {strings.openDataPacks}
          </button>
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenWorkbenchView?.("review-lab")}
          >
            {strings.openReviewLab}
          </button>
        </div>
      </AppPanel>

      {stage === "setup" ? (
        <div className="godview-setup">
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto pr-1">
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
                      {isKo ? "역할 목록 (쉼표 구분)" : "roles (comma separated)"}
                      <input value={customRoles} onChange={(e) => setCustomRoles(e.target.value)} className="app-input" />
                    </label>
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
                    <label className="flex items-center gap-2 rounded-2xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
                      <input
                        type="checkbox"
                        checked={autoRolesFromPersonas}
                        onChange={(e) => setAutoRolesFromPersonas(e.target.checked)}
                      />
                      {isKo ? "페르소나 역할 자동 병합" : "persona roles auto-merge"}
                    </label>
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

            <PersonaPreview worldId={worldId} refreshKey={personaRefreshKey} />

            <AppPanel
              title={isKo ? "LLM 런타임 연결" : "LLM Runtime Connection"}
              subtitle={
                isKo
                  ? "실제 프로바이더를 연결해서 에이전트가 실시간 LLM 호출로 생각하고 행동하게 합니다"
                  : "Connect a real provider so agents think, decide, and act through live LLM calls"
              }
              bodyClassName="space-y-3"
            >
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex items-center gap-2 text-xs text-slate-600">
                  <input
                    type="checkbox"
                    checked={llmEnabled}
                    onChange={(event) => setLlmEnabled(event.target.checked)}
                  />
                  {isKo ? "실시간 LLM cognition 사용" : "enable live LLM cognition"}
                </label>
                <div className="grid gap-2 md:grid-cols-2">
                  <MetricChip label={isKo ? "현재 프로바이더" : "current provider"} value={runtimeStatus?.llm?.provider ?? "stub"} />
                  <MetricChip
                    label={isKo ? "API 키" : "api key"}
                    value={runtimeStatus?.llm?.has_api_key ? (isKo ? "설정됨" : "configured") : isKo ? "없음" : "missing"}
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "연결 프리셋" : "connection preset"}
                  <select
                    className="app-input"
                    value={llmProviderPreset}
                    onChange={(event) => setLlmProviderPreset(event.target.value)}
                  >
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
                  <select
                    className="app-input"
                    value={llmModelPreset}
                    onChange={(event) => setLlmModelPreset(event.target.value)}
                  >
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
                    placeholder={isKo ? "예: gpt-4.1-mini / llama3.1 / custom-model" : "e.g. gpt-4.1-mini / llama3.1 / custom-model"}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "추천 URL" : "url preset"}
                  <select
                    className="app-input"
                    value={llmProviderPreset === "custom" ? "custom" : llmBaseUrl || activeProviderPreset?.baseUrl || ""}
                    onChange={(event) => {
                      const next = event.target.value;
                      if (next === "custom") return;
                      setLlmBaseUrl(next);
                    }}
                  >
                    {LLM_PROVIDER_PRESETS.map((item) => (
                      <option key={`${item.id}-url`} value={item.baseUrl}>
                        {item.label} · {item.baseUrl}
                      </option>
                    ))}
                    <option value="custom">{isKo ? "직접 입력" : "Custom"}</option>
                  </select>
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
                    placeholder={isKo ? "https://api.openai.com/v1 또는 http://127.0.0.1:11434" : "https://api.openai.com/v1 or http://127.0.0.1:11434"}
                  />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "API 키" : "api key"}
                  <input
                    type="password"
                    className="app-input"
                    value={llmApiKey}
                    onChange={(event) => setLlmApiKey(event.target.value)}
                    placeholder={isKo ? "sk-... 또는 로컬 토큰" : "sk-... or local token"}
                  />
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
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "온도" : "temperature"}
                  <input className="app-input" value={llmTemperature} onChange={(event) => setLlmTemperature(event.target.value)} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "타임아웃(초)" : "timeout (s)"}
                  <input className="app-input" value={llmTimeout} onChange={(event) => setLlmTimeout(event.target.value)} />
                </label>
              </div>
              <div className="grid gap-3 md:grid-cols-4">
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "사이클 프롬프트 예산" : "cycle prompt budget"}
                  <input className="app-input" value={llmCycleBudget} onChange={(event) => setLlmCycleBudget(event.target.value)} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "에이전트 샘플 수" : "agent sample size"}
                  <input className="app-input" value={llmAgentSampleSize} onChange={(event) => setLlmAgentSampleSize(event.target.value)} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "대화 최대 페어" : "dialogue max pairs"}
                  <input className="app-input" value={llmDialoguePairs} onChange={(event) => setLlmDialoguePairs(event.target.value)} />
                </label>
                <label className="flex flex-col gap-1 text-xs text-slate-500">
                  {isKo ? "협의 그룹 수" : "deliberation groups"}
                  <input className="app-input" value={llmDeliberationGroups} onChange={(event) => setLlmDeliberationGroups(event.target.value)} />
                </label>
              </div>
              <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">{isKo ? "태스크 예산" : "Task Budgets"}</p>
                  <span className="text-xs text-slate-500">
                    {isKo ? "Mirofish처럼 thought/action/dialogue 비중을 높게 유지합니다" : "Mirofish-like mode: keep thought/action/dialogue high"}
                  </span>
                </div>
                <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                  {llmTaskRows.map((row) => (
                    <div key={row.task} className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-700">{row.task}</p>
                        <span className="text-[11px] text-slate-500">
                          live {row.totals?.prompt_count_sent ?? 0}/{row.totals?.prompt_count_in ?? 0}
                        </span>
                      </div>
                      <div className="mt-2 grid gap-2 grid-cols-2">
                        <label className="flex flex-col gap-1 text-[11px] text-slate-500">
                          {isKo ? "예산" : "budget"}
                          <input
                            className="app-input"
                            value={row.budget}
                            onChange={(event) =>
                              setTaskBudgetDraft((current) => ({ ...current, [row.task]: event.target.value }))
                            }
                          />
                        </label>
                        <label className="flex flex-col gap-1 text-[11px] text-slate-500">
                          {isKo ? "우선순위" : "priority"}
                          <input
                            className="app-input"
                            value={row.priority}
                            onChange={(event) =>
                              setTaskPriorityDraft((current) => ({ ...current, [row.task]: event.target.value }))
                            }
                          />
                        </label>
                      </div>
                      <p className="mt-2 text-[11px] text-slate-500">
                        {isKo ? "폴백" : "fallback"} {row.totals?.fallback_calls ?? 0} · {isKo ? "태스크 예산 초과" : "skipped task"} {row.totals?.prompt_count_skipped_by_task_budget ?? 0}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={async () => {
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
                        task_budgets: Object.fromEntries(
                          Object.entries(taskBudgetDraft).map(([key, value]) => [key, Number(value) || 1])
                        ),
                        task_priorities: Object.fromEntries(
                          Object.entries(taskPriorityDraft).map(([key, value]) => [key, Number(value) || 0])
                        ),
                      });
                      await reloadRuntimeStatus();
                      setLlmConfigStatus(isKo ? "LLM 런타임 저장 완료" : "llm runtime saved");
                    } catch (reason) {
                      setLlmConfigStatus(reason instanceof Error ? reason.message : isKo ? "LLM 설정 저장 실패" : "llm config save failed");
                    }
                  }}
                >
                  {isKo ? "LLM 설정 저장" : "Save LLM Config"}
                </button>
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={async () => {
                    setLlmConfigStatus(isKo ? "LLM 연결 테스트 중…" : "testing llm connection…");
                    try {
                      const result = await testRuntimeLlmConfig();
                      setLlmTestResult(result);
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
                  }}
                >
                  {isKo ? "연결 테스트" : "Test Connection"}
                </button>
              </div>
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
              <div className={`rounded-2xl border px-3 py-3 text-xs ${liveBenchmarkReadiness.ready ? "border-emerald-200 bg-emerald-50 text-emerald-800" : "border-amber-200 bg-amber-50 text-amber-800"}`}>
                <div className="flex items-center justify-between gap-3">
                  <p className="font-semibold">{isKo ? "Live Baseline 준비도" : "Live Baseline Readiness"}</p>
                  <span className="rounded-full border border-current/20 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.12em]">
                    {liveBenchmarkReadiness.ready ? (isKo ? "준비됨" : "ready") : (isKo ? "미준비" : "not ready")}
                  </span>
                </div>
                <p className="mt-2">
                  {isKo
                    ? `현재 설정: ${liveBenchmarkReadiness.provider} · ${liveBenchmarkReadiness.model}`
                    : `Current config: ${liveBenchmarkReadiness.provider} · ${liveBenchmarkReadiness.model}`}
                </p>
                {liveBenchmarkReadiness.reasons.length ? (
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {liveBenchmarkReadiness.reasons.map((item, index) => (
                      <li key={`${index}-${item}`}>{item}</li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-2">
                    {isKo
                      ? "이제 실제 provider 기준 short baseline을 바로 수집할 수 있습니다."
                      : "You can now run the short live-provider baseline directly."}
                  </p>
                )}
                <div className="mt-3 rounded-2xl border border-current/10 bg-white/70 px-3 py-2 font-mono text-[11px] break-all">
                  {liveBenchmarkReadiness.command}
                </div>
              </div>
              {llmTestResult && !llmTestResult.ok ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-800">
                  <p className="font-semibold">{isKo ? "연결 진단" : "Connection Diagnosis"}</p>
                  <p className="mt-1">{llmTestResult.diagnosis}</p>
                  <p className="mt-1">
                    {llmTestResult.fallback_reason || (isKo ? "프로바이더 응답이 유효하지 않습니다." : "The provider response is invalid.")}
                  </p>
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {!llmApiKey && llmProvider !== "ollama" ? (
                      <li>{isKo ? "선택한 프로바이더에 API 키가 없습니다." : "The selected provider is missing an API key."}</li>
                    ) : null}
                    {llmProvider === "ollama" && !llmBaseUrl ? (
                      <li>{isKo ? "Ollama base URL을 입력하세요. 예: http://127.0.0.1:11434" : "Provide an Ollama base URL, for example http://127.0.0.1:11434"}</li>
                    ) : null}
                    {llmTestResult.suggestions.map((item, index) => (
                      <li key={`${index}-${item}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              <p className="text-xs text-slate-500">
                {isKo
                  ? "`LLM-first`를 선택하면 Thought, Worldview, Action, Policy, Dialogue, Group Deliberation의 샘플링과 예산이 더 공격적으로 올라가서 규칙보다 실제 provider 호출이 주가 되도록 맞춥니다."
                  : "`LLM-first` raises sampling and budgets for Thought, Worldview, Action, Policy, Dialogue, and Group Deliberation so live provider calls dominate over rule-based execution."}
              </p>
              {llmHealth ? (
                <div className="grid gap-2 md:grid-cols-4">
                  <MetricChip label={isKo ? "상태" : "health"} value={llmHealth.status} />
                  <MetricChip label={isKo ? "최근 호출" : "recent calls"} value={String(llmHealth.recent_call_count)} />
                  <MetricChip label={isKo ? "실시간 비율" : "live rate"} value={`${Math.round((llmHealth.live_call_rate ?? 0) * 100)}%`} />
                  <MetricChip label={isKo ? "폴백 비율" : "fallback rate"} value={`${Math.round((llmHealth.recent_fallback_rate ?? 0) * 100)}%`} />
                  <MetricChip label={isKo ? "주요 실패" : "dominant failure"} value={llmHealth.dominant_failure_reason || (isKo ? "없음" : "none")} />
                </div>
              ) : null}
              {runtimeStatus?.llm_runtime?.recommended_actions?.length ? (
                <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700">
                  <p className="font-semibold">{isKo ? "권장 조치" : "Recommended Actions"}</p>
                  <ul className="mt-2 list-disc space-y-1 pl-4">
                    {runtimeStatus.llm_runtime.recommended_actions.map((item, index) => (
                      <li key={`${index}-${item}`}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {recentFallbackRuns.length ? (
                <div className="grid gap-2 rounded-2xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">{isKo ? "폴백 압력" : "Fallback Pressure"}</p>
                  {recentFallbackRuns.map((run, index) => (
                    <div key={`${run.task}-${index}`} className="session-thread-card">
                      <div className="session-thread-card__header">
                        <p className="session-thread-card__title">{run.task}</p>
                        <span className="session-thread-card__meta">
                          {run.prompt_count_sent}/{run.prompt_count_in} · p{run.task_priority}
                        </span>
                      </div>
                      <p className="session-thread-card__prompt">{run.fallback_reason || (isKo ? "폴백" : "fallback")}</p>
                    </div>
                  ))}
                </div>
              ) : null}
              {reviewError ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-3 text-xs text-rose-700">
                  <p className="font-semibold">{isKo ? "리뷰 실행 오류" : "Review Runtime Error"}</p>
                  <p className="mt-1">{reviewError}</p>
                  <p className="mt-1">
                    {isKo
                      ? "연결 테스트보다 review 프롬프트가 훨씬 크기 때문에 timeout이 더 쉽게 발생할 수 있습니다."
                      : "Review prompts are much heavier than the connection test, so timeouts can appear there first."}
                  </p>
                </div>
              ) : null}
              {llmConfigStatus ? <p className="text-xs text-slate-500">{llmConfigStatus}</p> : null}
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

          <div className="grid min-h-0 gap-4">
            <AppPanel
              title={isKo ? "설정 체크리스트" : "Setup Checklist"}
              subtitle={isKo ? "실시간 시뮬레이션에 들어가기 전에 월드를 준비합니다" : "Prepare the world before entering live simulation"}
              bodyClassName="grid gap-3 md:grid-cols-2"
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
                subtitle={isKo ? "월드를 만든 뒤 열리는 기능" : "What unlocks after world creation"}
                bodyClassName="space-y-3"
              >
                <p className="text-sm leading-7 text-slate-600">
                  {isKo
                    ? "world를 만든 뒤에는 실행 패널, 시뮬레이션 맵, 선택 상세 패널, 시간축 북마크, 정책 주입 패널이 모두 `Run` 단계에서 열립니다. 지금은 설정에 집중하고, 실행 중 분석은 다음 단계에서 분리해서 보게 됩니다."
                    : "After world creation, execution controls, the simulation map, the selection inspector, timeline bookmarks, and policy injection all open in Run. Stay focused on setup first, then move into live analysis."}
                </p>
                <div className="grid gap-2 md:grid-cols-2">
                  <MetricChip label={isKo ? "실행 단계" : "Run stage"} value={isKo ? "실행 + 맵 + 타임라인" : "Execution + Map + Timeline"} />
                  <MetricChip label={isKo ? "리뷰 단계" : "Review stage"} value={isKo ? "향후 LLM 분석 워크스페이스" : "Future LLM analysis workspace"} />
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
              title={isKo ? "실행 제어" : "Run Controls"}
              subtitle={isKo ? "실행, 주입, 시간 탐색" : "Execution, injections, and time navigation"}
              bodyClassName="flex flex-wrap gap-2"
              action={
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => setStage("setup")}
                >
                  {strings.backToSetup}
                </button>
              }
            >
              <button
                type="button"
                className={`app-button ${autoFitLayout ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => setAutoFitLayout(true)}
              >
                {strings.autoFit}
              </button>
              <button
                type="button"
                className={`app-button ${!autoFitLayout && layoutMode === "balanced" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => {
                  setAutoFitLayout(false);
                  setLayoutMode("balanced");
                }}
              >
                {strings.balanced}
              </button>
              <button
                type="button"
                className={`app-button ${!autoFitLayout && layoutMode === "focus" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => {
                  setAutoFitLayout(false);
                  setLayoutMode("focus");
                }}
              >
                {strings.focusViz}
              </button>
              <button
                type="button"
                className={`app-button ${!autoFitLayout && layoutMode === "wide-left" ? "app-button--primary" : "app-button--secondary"}`}
                onClick={() => {
                  setAutoFitLayout(false);
                  setLayoutMode("wide-left");
                }}
              >
                {strings.wideControls}
              </button>
              <span className="rounded-full bg-slate-100 px-3 py-2 text-xs text-slate-600">
                {autoFitLayout ? (isKo ? "자동 맞춤 활성" : "Auto-fit enabled") : isKo ? "수동 레이아웃" : "Manual layout"}
              </span>
            </AppPanel>

            <RunPanel
              locale={locale}
              worldId={worldId}
              isRunning={isRunning}
              liveT={liveT}
              liveCellCount={liveCellCount}
              onRunStream={handleRunStream}
              onRunSync={handleRunSync}
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

            <ScenarioSummary worldId={worldId} refreshKey={chartRefreshKey} />
          </div>

          <div className="grid min-h-0 gap-4 xl:grid-rows-[minmax(0,1fr)_minmax(320px,0.48fr)]">
            <AppPanel
              title={isKo ? "시뮬레이션 뷰" : "Simulation View"}
              subtitle={isKo ? "신념 동학, 선택 상태, 맵 기반 검사" : "Belief dynamics, selection, and map-driven inspection"}
              className="min-h-0"
              bodyClassName="flex h-full min-h-0 flex-col gap-4"
              action={
                visualStats?.sampled ? (
                  <span className="rounded-full bg-amber-50 px-3 py-2 text-xs font-medium text-amber-700">
                    {isKo ? "샘플링" : "sampled"} {visibleCells.length.toLocaleString()} / {visualStats.totalCells.toLocaleString()}
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
                  {lastGenesis ? <GenesisMeta locale={locale} lastGenesis={lastGenesis} /> : null}
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
                        onClick={() => onOpenWorkbenchView?.("review-lab")}
                      >
                        {isKo ? "전체 리뷰 열기" : "Open Full Review"}
                      </button>
                    </AppPanel>
                  ) : null}
                </div>

                <SimulationInspectorPanel
                  locale={locale}
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
                  agentRoster={snapshotCells}
                  onSelectAgent={setSelectedAgent}
                  onOpenWorldAt={(_, t) => {
                    if (typeof t === "number") setCurrentT(t);
                  }}
                  onClearSelection={clearSelection}
                />
              </div>
            </AppPanel>

            <div className="grid min-h-0 gap-4 xl:grid-cols-[minmax(300px,0.42fr)_minmax(0,1fr)]">
              <AppPanel
                title={isKo ? "시간 탐색" : "Time Navigation"}
                subtitle={isKo ? "저장된 스냅샷 탐색" : "Browse saved snapshots"}
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
                  markers={[...timelineMarkers, ...reviewMarkers]}
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
                  <span>{availableT.length} {isKo ? "프레임" : "frames"}</span>
                </div>
              </AppPanel>

              <div className="grid min-h-0 gap-3">
                <ScenarioTimeline
                  locale={locale}
                  worldId={worldId}
                  refreshKey={chartRefreshKey}
                  annotations={reviewSummary?.timeline_annotations ?? []}
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
                <AppPanel
                  title={isKo ? "분석 그래프" : "Analysis Graph"}
                  subtitle={isKo ? "장기 추세를 읽기 위한 확장 차트 레인" : "A larger chart lane for long-run trend reading"}
                  bodyClassName="space-y-2"
                >
                  <p className="text-sm leading-6 text-slate-600">
                    시간축 그래프를 별도 영역으로 분리해서, 실행 뷰와 시계열 분석을 동시에 보더라도
                    흐름이 덜 답답하게 유지되도록 했습니다. annotation을 클릭하면 해당 시점으로 바로
                    이동합니다.
                  </p>
                  <div className="grid gap-2 md:grid-cols-3">
                    <MetricChip label={isKo ? "프레임 수" : "Frames"} value={String(availableT.length)} />
                    <MetricChip
                      label={isKo ? "어노테이션 수" : "Annotations"}
                      value={String(reviewSummary?.timeline_annotations.length ?? 0)}
                    />
                    <MetricChip label={isKo ? "현재 t" : "Current t"} value={String(currentT)} />
                  </div>
                </AppPanel>
              </div>
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
  locale = "ko",
  worldId,
  isRunning,
  liveT,
  liveCellCount,
  onRunStream,
  onRunSync,
}: {
  locale?: UiLocale;
  worldId: string | null;
  isRunning: boolean;
  liveT: number | null;
  liveCellCount: number | null;
  onRunStream: () => Promise<void>;
  onRunSync: () => Promise<void>;
}) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  return (
    <AppPanel
      title={isKo ? "실행" : "Execution"}
      subtitle={isKo ? "이 머신에서 로컬로 실행" : "Run locally on this machine"}
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
          <>
            {isKo ? "실행 중 · stream active" : "Running · stream active"}
            {liveT != null ? ` · t ${liveT.toFixed(1)}` : ""}
            {liveCellCount != null ? ` · ${liveCellCount} cells` : ""}
          </>
        ) : (
          strings.runtimeReadyLocal
        )}
      </div>
    </AppPanel>
  );
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
