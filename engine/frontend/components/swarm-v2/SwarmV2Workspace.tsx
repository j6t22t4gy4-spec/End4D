"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import {
  createSwarmV2Session,
  getLocalRuntimeStatus,
  getSwarmV2WebSocketUrl,
  listSwarmV2Sessions,
  replaySwarmV2Session,
  testRuntimeLlmConfig,
  type LocalRuntimeStatus,
  type RuntimeLlmTestResponse,
  type SwarmV2Agent,
  type SwarmV2Event,
  type SwarmV2RunResponse,
  type SwarmV2SavedSession,
  type SwarmV2StreamMessage,
} from "@/lib/api";

type Props = {
  prompt: string;
  locale?: "ko" | "en";
  variant?: "setup" | "run";
  scenarioPrompt?: string;
  onScenarioPromptChange?: (value: string) => void;
  onOpenRun?: () => void;
  onTelemetryChange?: (telemetry: SwarmV2Telemetry) => void;
  onResult?: (result: SwarmV2RunResponse) => void;
};

export type SwarmV2Telemetry = {
  status: StreamStatus;
  sessionId: string | null;
  running: boolean;
  visibleAgentCount: number;
  totalAgents: number;
  eventCount: number;
  expectedEvents: number;
  activePercent: number;
  roundProgress: number;
  rounds: number;
  currentPhase: string;
  latestEvent: SwarmV2Event | null;
  recentEvents: SwarmV2Event[];
  agentChannelCount: number;
  packetChannelCount: number;
  replyChainCount: number;
  llmMode: SwarmV2LlmMode;
  llmSampleSize: number;
  llmParallelism: number;
  llmLogs: SwarmV2LlmLog[];
  runtimeStatus: LocalRuntimeStatus | null;
  llmTestResult: RuntimeLlmTestResponse | null;
  summary: Record<string, unknown>;
  thinkingEvent: ThinkingEvent | null;
};

export type StreamStatus = "idle" | "connecting" | "streaming" | "complete" | "stopped";
type SwarmV2LlmMode = "off" | "packet" | "agent" | "hybrid" | "full-agent";
type SwarmV2LlmLog = Extract<SwarmV2StreamMessage, { type: "llm_log" }> & {
  loggedAt: number;
};
type VisualPulse = {
  id: string;
  event: SwarmV2Event;
  bornAt: number;
  kind: "burst" | "wave" | "branch" | "newcomer";
};
type VisualAgentState = {
  x: number;
  y: number;
  targetX: number;
  targetY: number;
  heat: number;
  lastHitAt: number;
};
type ThinkingEvent = Extract<SwarmV2StreamMessage, { type: "agent_thinking" }> & {
  bornAt: number;
};

const SESSION_PHASES = ["opening", "escalation", "branching", "convergence", "outcome"];
const PHASE_LABEL: Record<string, string> = {
  opening: "개장",
  escalation: "고조",
  branching: "분기",
  convergence: "수렴",
  outcome: "결과",
};

export function SwarmV2Workspace({
  prompt,
  locale = "ko",
  variant = "run",
  scenarioPrompt: controlledScenarioPrompt,
  onScenarioPromptChange,
  onOpenRun,
  onTelemetryChange,
  onResult,
}: Props) {
  const isKo = locale === "ko";
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const replayTimerRef = useRef<number | null>(null);
  const agentsRef = useRef<SwarmV2Agent[]>([]);
  const eventsRef = useRef<SwarmV2Event[]>([]);
  const pulsesRef = useRef<VisualPulse[]>([]);
  const visualAgentStateRef = useRef<Map<string, VisualAgentState>>(new Map());
  const visibleAgentIdsRef = useRef<Set<string>>(new Set());
  const newcomerIdsRef = useRef<Map<string, number>>(new Map());
  const thinkingEventRef = useRef<ThinkingEvent | null>(null);
  const [agents, setAgents] = useState<SwarmV2Agent[]>([]);
  const [events, setEvents] = useState<SwarmV2Event[]>([]);
  const [visibleAgentCount, setVisibleAgentCount] = useState(0);
  const [summary, setSummary] = useState<Record<string, unknown>>({});
  const [draftScenarioPrompt, setDraftScenarioPrompt] = useState(prompt);
  const [runtimeStatus, setRuntimeStatus] = useState<LocalRuntimeStatus | null>(null);
  const [llmTestResult, setLlmTestResult] = useState<RuntimeLlmTestResponse | null>(null);
  const [llmTesting, setLlmTesting] = useState(false);
  const [agentCount, setAgentCount] = useState(1600);
  const [rounds, setRounds] = useState(64);
  const [eventsPerRound, setEventsPerRound] = useState(24);
  const [paceMs, setPaceMs] = useState(0);
  const [llmMode, setLlmMode] = useState<SwarmV2LlmMode>("hybrid");
  const [llmSampleSize, setLlmSampleSize] = useState(96);
  const [llmParallelism, setLlmParallelism] = useState(4);
  const [llmLogs, setLlmLogs] = useState<SwarmV2LlmLog[]>([]);
  const [expectedEvents, setExpectedEvents] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [savedSessions, setSavedSessions] = useState<SwarmV2SavedSession[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [roundProgress, setRoundProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [thinkingEvent, setThinkingEvent] = useState<ThinkingEvent | null>(null);

  const running = status === "connecting" || status === "streaming";
  const activePercent = expectedEvents ? Math.min(100, Math.round((events.length / expectedEvents) * 100)) : 0;
  const recentEvents = useMemo(() => events.slice(-7).reverse(), [events]);
  const agentChannelCount = useMemo(() => events.filter((event) => event.llm_mode === "agent").length, [events]);
  const packetChannelCount = Math.max(0, events.length - agentChannelCount);
  const replyChainCount = useMemo(() => events.filter((event) => event.reply_to_event_id).length, [events]);
  const latestEvent = events[events.length - 1];
  const currentPhase = latestEvent?.phase ?? "opening";
  const scenarioPrompt = controlledScenarioPrompt ?? draftScenarioPrompt;
  const setScenarioPrompt = onScenarioPromptChange ?? setDraftScenarioPrompt;

  useEffect(() => {
    onTelemetryChange?.({
      status,
      sessionId,
      running,
      visibleAgentCount,
      totalAgents: agents.length || agentCount,
      eventCount: events.length,
      expectedEvents,
      activePercent,
      roundProgress,
      rounds,
      currentPhase,
      latestEvent: latestEvent ?? null,
      recentEvents,
      agentChannelCount,
      packetChannelCount,
      replyChainCount,
      llmMode,
      llmSampleSize,
      llmParallelism,
      llmLogs,
      runtimeStatus,
      llmTestResult,
      summary,
      thinkingEvent,
    });
  }, [
    activePercent,
    agentChannelCount,
    agentCount,
    agents.length,
    currentPhase,
    events.length,
    expectedEvents,
    latestEvent,
    llmMode,
    llmParallelism,
    llmLogs,
    llmSampleSize,
    llmTestResult,
    onTelemetryChange,
    packetChannelCount,
    recentEvents,
    replyChainCount,
    roundProgress,
    rounds,
    running,
    runtimeStatus,
    sessionId,
    status,
    summary,
    thinkingEvent,
    visibleAgentCount,
  ]);

  useEffect(() => {
    if (controlledScenarioPrompt == null) {
      setDraftScenarioPrompt((current) => current || prompt);
    }
  }, [controlledScenarioPrompt, prompt]);

  async function refreshRuntimeStatus() {
    try {
      const response = await getLocalRuntimeStatus();
      setRuntimeStatus(response);
    } catch {
      setRuntimeStatus(null);
    }
  }

  function setSessionAgents(nextAgents: SwarmV2Agent[]) {
    agentsRef.current = nextAgents;
    syncVisualAgents(nextAgents, visualAgentStateRef.current);
    setAgents(nextAgents);
  }

  function clearReplayTimer() {
    if (replayTimerRef.current !== null) {
      window.clearInterval(replayTimerRef.current);
      replayTimerRef.current = null;
    }
  }

  function appendPlaybackEvent(event: SwarmV2Event, allAgents = agentsRef.current, totalRounds = rounds) {
    eventsRef.current = [...eventsRef.current, event];
    revealAgentsFromEvent(event, allAgents, visibleAgentIdsRef.current, newcomerIdsRef.current, pulsesRef.current);
    stirVisualAgents(event, allAgents, visualAgentStateRef.current);
    pushVisualPulses(event, pulsesRef.current);
    setVisibleAgentCount(visibleAgentIdsRef.current.size);
    setEvents(eventsRef.current);
    if (event.round && totalRounds) {
      setRoundProgress(Math.min(1, event.round / Math.max(1, totalRounds)));
    }
  }

  async function refreshSavedSessions() {
    try {
      const response = await listSwarmV2Sessions(8);
      setSavedSessions(response.sessions);
    } catch {
      setSavedSessions([]);
    }
  }

  async function run() {
    wsRef.current?.close();
    clearReplayTimer();
    eventsRef.current = [];
    pulsesRef.current = [];
    visibleAgentIdsRef.current = new Set();
    newcomerIdsRef.current = new Map();
    thinkingEventRef.current = null;
    setThinkingEvent(null);
    setEvents([]);
    setSessionAgents([]);
    setVisibleAgentCount(0);
    setSummary({});
    setSessionId(null);
    setExpectedEvents(0);
    setLlmLogs([]);
    setRoundProgress(0);
    setError(null);
    setStatus("connecting");
    try {
      const session = await createSwarmV2Session({
        prompt: scenarioPrompt || prompt,
        agent_count: agentCount,
        rounds,
        events_per_round: eventsPerRound,
        zone_count: 32,
        pace_ms: paceMs,
        llm_mode: llmMode,
        llm_sample_size: llmSampleSize,
        llm_parallelism: llmParallelism,
      });
      setSessionId(session.session_id);
      setSessionAgents(session.agents);
      seedInitialVisibleAgents(session.agents, visibleAgentIdsRef.current, newcomerIdsRef.current);
      setVisibleAgentCount(visibleAgentIdsRef.current.size);
      setExpectedEvents(session.event_count);
      setSummary(session.summary);
      void refreshSavedSessions();

      const ws = new WebSocket(getSwarmV2WebSocketUrl(session.session_id));
      wsRef.current = ws;
      ws.onopen = () => setStatus("streaming");
      ws.onmessage = (message) => {
        const payload = JSON.parse(message.data) as SwarmV2StreamMessage;
        if (payload.type === "session_started") {
          setSessionAgents(payload.agents);
          seedInitialVisibleAgents(payload.agents, visibleAgentIdsRef.current, newcomerIdsRef.current);
          setVisibleAgentCount(visibleAgentIdsRef.current.size);
          setExpectedEvents(payload.event_count);
          setSummary(payload.summary);
          return;
        }
        if (payload.type === "round_started") {
          setRoundProgress(payload.progress);
          return;
        }
        if (payload.type === "agent_thinking") {
          const nextThinking = { ...payload, bornAt: performance.now() };
          thinkingEventRef.current = nextThinking;
          setThinkingEvent(nextThinking);
          return;
        }
        if (payload.type === "llm_log") {
          setLlmLogs((current) => [{ ...payload, loggedAt: Date.now() }, ...current].slice(0, 160));
          return;
        }
        if (payload.type === "event") {
          thinkingEventRef.current = null;
          setThinkingEvent(null);
          appendPlaybackEvent(payload.event);
          return;
        }
        if (payload.type === "session_completed") {
          const completedEvents = eventsRef.current;
          setSessionAgents(payload.agents);
          setSummary(payload.summary);
          setStatus("complete");
          void refreshSavedSessions();
          ws.close();
          onResult?.({
            runtime: session.runtime,
            prompt: session.prompt,
            agent_count: session.agent_count,
            rounds: session.rounds,
            events_per_round: session.events_per_round,
            zone_count: session.zone_count,
            llm_mode: session.llm_mode,
            agents: payload.agents,
            events: completedEvents,
            summary: payload.summary,
          });
        }
      };
      ws.onerror = () => {
        setError(isKo ? "Swarm V2 스트림 연결이 끊겼습니다." : "Swarm V2 stream connection failed.");
        setStatus("stopped");
      };
      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "swarm v2 failed");
      setStatus("stopped");
    }
  }

  function stop() {
    wsRef.current?.close();
    clearReplayTimer();
    wsRef.current = null;
    setStatus(eventsRef.current.length ? "stopped" : "idle");
  }

  async function replay(sessionIdToReplay: string) {
    wsRef.current?.close();
    clearReplayTimer();
    eventsRef.current = [];
    pulsesRef.current = [];
    visibleAgentIdsRef.current = new Set();
    newcomerIdsRef.current = new Map();
    thinkingEventRef.current = null;
    setThinkingEvent(null);
    setStatus("connecting");
    setError(null);
    try {
      const replaySession = await replaySwarmV2Session(sessionIdToReplay);
      setSessionId(replaySession.session_id);
      setScenarioPrompt(replaySession.prompt || scenarioPrompt);
      setSessionAgents(replaySession.agents);
      setAgentCount(replaySession.agent_count);
      setRounds(replaySession.rounds);
      setEventsPerRound(replaySession.events_per_round);
      setPaceMs(replaySession.pace_ms);
      setLlmParallelism(replaySession.llm_parallelism ?? 1);
      if (["off", "packet", "agent", "hybrid", "full-agent"].includes(String(replaySession.llm_mode))) {
        setLlmMode(replaySession.llm_mode as typeof llmMode);
      }
      setSummary({ llm: replaySession.summary.llm });
      setExpectedEvents(replaySession.event_count);
      seedInitialVisibleAgents(replaySession.agents, visibleAgentIdsRef.current, newcomerIdsRef.current);
      setVisibleAgentCount(visibleAgentIdsRef.current.size);
      setRoundProgress(0);
      setLlmLogs([]);
      setEvents([]);
      setStatus("streaming");
      let cursor = 0;
      const intervalMs = Math.max(4, Math.min(80, paceMs || replaySession.pace_ms || 12));
      replayTimerRef.current = window.setInterval(() => {
        const event = replaySession.events[cursor];
        if (!event) {
          clearReplayTimer();
          setSummary(replaySession.summary);
          setRoundProgress(1);
          setStatus("complete");
          onResult?.({
            runtime: replaySession.runtime,
            prompt: replaySession.prompt,
            agent_count: replaySession.agent_count,
            rounds: replaySession.rounds,
            events_per_round: replaySession.events_per_round,
            zone_count: replaySession.zone_count,
            llm_mode: replaySession.llm_mode,
            agents: replaySession.agents,
            events: replaySession.events,
            summary: replaySession.summary,
          });
          return;
        }
        appendPlaybackEvent(event, replaySession.agents, replaySession.rounds);
        cursor += 1;
      }, intervalMs);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "replay failed");
      setStatus("stopped");
    }
  }

  useEffect(() => {
    void refreshSavedSessions();
    void refreshRuntimeStatus();
    return () => {
      clearReplayTimer();
      wsRef.current?.close();
    };
  }, []);

  if (variant === "setup") {
    return (
      <section className="rounded-[32px] border border-sky-200 bg-white p-5 shadow-sm ring-4 ring-sky-50">
        <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-600">Primary Runtime</p>
            <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">
              {isKo ? "Swarm V2 준비" : "Prepare Swarm V2"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-slate-600">
              {isKo
                ? "여기서는 시나리오와 연결 상태만 준비합니다. 실제 agents/streams/LLM mode 실행은 Run 탭의 V2 콘솔에서 조정합니다."
                : "Prepare the scenario and connection here. Tune agents, streams, and LLM mode in the V2 Run console."}
            </p>
            <label className="mt-5 flex flex-col gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
                {isKo ? "시나리오 입력" : "Scenario"}
              </span>
              <textarea
                className="app-textarea min-h-36"
                value={scenarioPrompt}
                onChange={(event) => setScenarioPrompt(event.target.value)}
                placeholder={isKo ? "예: 기본소득이 지역 상권과 노동시장에 미치는 갈등을 시뮬레이션" : "Describe the scenario to simulate"}
              />
            </label>
            <div className="mt-4 flex flex-wrap gap-2">
              <button type="button" className="app-button app-button--primary" onClick={onOpenRun}>
                {isKo ? "Run에서 V2 스트림 열기" : "Open V2 Stream in Run"}
              </button>
              <button type="button" className="app-button app-button--ghost" onClick={refreshSavedSessions}>
                {isKo ? "저장 세션 새로고침" : "Refresh sessions"}
              </button>
            </div>
          </div>
          <aside className="space-y-3">
            <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">LLM Connection</p>
                  <p className="mt-1 font-semibold text-slate-900">
                    {runtimeStatus?.llm.enabled ? "enabled" : "disabled"} · {runtimeStatus?.llm.provider ?? "unknown"} · {runtimeStatus?.llm.model ?? "unknown"}
                  </p>
                </div>
                <button type="button" className="app-button app-button--ghost" onClick={testLlmConnection} disabled={llmTesting}>
                  {llmTesting ? "testing" : "test"}
                </button>
              </div>
              {llmTestResult ? (
                <p className={`mt-2 rounded-xl px-2 py-2 ${llmTestResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                  {llmTestResult.ok ? "connected" : "not connected"} · {llmTestResult.provider} · {llmTestResult.model}
                  {llmTestResult.fallback_reason ? ` · ${llmTestResult.fallback_reason}` : ""}
                </p>
              ) : null}
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {isKo ? "최근 V2 세션" : "Recent V2 Sessions"}
              </p>
              <div className="mt-2 max-h-48 space-y-2 overflow-y-auto pr-1">
                {savedSessions.length ? savedSessions.slice(0, 4).map((item) => (
                  <div key={item.session_id} className="rounded-xl bg-slate-50 px-3 py-2 text-xs text-slate-600">
                    <p className="font-semibold text-slate-900">{item.session_id.slice(0, 8)} · {item.event_count} events</p>
                    <p className="mt-1 truncate">{item.prompt || "Swarm V2 session"}</p>
                  </div>
                )) : (
                  <p className="rounded-xl bg-slate-50 px-3 py-3 text-xs leading-5 text-slate-500">
                    {isKo ? "아직 저장된 세션이 없습니다." : "No saved sessions yet."}
                  </p>
                )}
              </div>
            </div>
          </aside>
        </div>
      </section>
    );
  }

  async function testLlmConnection() {
    setLlmTesting(true);
    setLlmTestResult(null);
    try {
      const result = await testRuntimeLlmConfig();
      setLlmTestResult(result);
      await refreshRuntimeStatus();
    } catch (reason) {
      setLlmTestResult({
        ok: false,
        mode: "error",
        provider: "unknown",
        model: "unknown",
        used_fallback: false,
        fallback_reason: reason instanceof Error ? reason.message : "test failed",
        preview: "",
        diagnosis: "connection test failed",
        suggestions: [],
      });
    } finally {
      setLlmTesting(false);
    }
  }

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    let raf = 0;
    const bounds = agents.length ? boundsFor(agents) : { minX: -1, maxX: 1, minY: -1, maxY: 1 };
    const draw = () => {
      resizeCanvasToDisplaySize(canvas);
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);
      drawBackground(ctx, width, height);
      tickVisualAgents(agents, visualAgentStateRef.current);
      const byId = new Map(agents.map((agent) => [agent.agent_id, agentForDraw(agent, visualAgentStateRef.current)]));
      const visibleAgents = agents
        .filter((agent) => visibleAgentIdsRef.current.has(agent.agent_id))
        .map((agent) => agentForDraw(agent, visualAgentStateRef.current));
      const visibleEvents = eventsRef.current.slice(-420);
      drawTopicBranches(ctx, visibleEvents, byId, bounds, width, height);
      drawThinkingEvent(ctx, thinkingEventRef.current, byId, bounds, width, height);
      drawPulses(ctx, pulsesRef.current, byId, bounds, width, height);
      visibleEvents.forEach((event, index) => {
        const source = byId.get(event.source_id);
        const target = byId.get(event.target_id);
        if (!source || !target) return;
        const age = index / Math.max(1, visibleEvents.length);
        drawEventLine(ctx, source, target, event, bounds, width, height, age);
      });
      visibleAgents
        .slice(0, 3600)
        .forEach((agent) => drawAgent(ctx, agent, bounds, width, height, newcomerIdsRef.current.get(agent.agent_id), visualAgentStateRef.current.get(agent.agent_id)));
      trimVisualPulses(pulsesRef.current);
      trimNewcomers(newcomerIdsRef.current);
      ctx.fillStyle = "#0f172a";
      ctx.font = "600 13px sans-serif";
      const thinkingText = thinkingEventRef.current
        ? ` · thinking: ${thinkingEventRef.current.source_label || thinkingEventRef.current.source_id}`
        : "";
      ctx.fillText(`Swarm V2 session · ${eventsRef.current.length}/${expectedEvents || 0} events${thinkingText}`, 24, 28);
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [agents, expectedEvents]);

  return (
    <section className="overflow-hidden rounded-[32px] border border-sky-200 bg-white shadow-sm ring-4 ring-sky-50">
      <div className="grid min-h-[680px] gap-0 xl:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="border-b border-slate-200 bg-slate-50/80 p-5 xl:border-b-0 xl:border-r">
          <p className="text-[11px] font-semibold uppercase tracking-[0.22em] text-sky-600">Primary Runtime</p>
          <h2 className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-slate-950">Swarm V2</h2>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            {isKo
              ? "한 번의 t를 여러 개의 빠른 상호작용 스트림으로 구성합니다. 기존 precision 경로와 분리된 새 실행면입니다."
              : "One t is composed from many fast interaction streams. This is a new path separated from legacy precision."}
          </p>
          <label className="mt-5 flex flex-col gap-2">
            <span className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
              {isKo ? "시나리오 입력" : "Scenario"}
            </span>
            <textarea
              className="app-textarea min-h-28"
              value={scenarioPrompt}
              onChange={(event) => setScenarioPrompt(event.target.value)}
              placeholder={isKo ? "예: 기본소득이 지역 상권과 노동시장에 미치는 갈등을 시뮬레이션" : "Describe the scenario to simulate"}
            />
          </label>
          <div className="mt-5 grid gap-3">
            <NumberControl label="agents" value={agentCount} min={32} max={10000} setValue={setAgentCount} />
            <NumberControl label="streams" value={rounds} min={4} max={160} setValue={setRounds} />
            <NumberControl label="events / stream" value={eventsPerRound} min={4} max={80} setValue={setEventsPerRound} />
            <NumberControl label={isKo ? "render delay ms" : "render delay ms"} value={paceMs} min={0} max={250} setValue={setPaceMs} />
            <p className="-mt-2 text-[11px] leading-4 text-slate-500">
              {isKo
                ? "0이면 LLM 출력이 도착하는 즉시 다음 이벤트를 표시합니다. 이 값은 LLM timeout이 아니라 화면 재생 간격입니다."
                : "0 emits the next event as soon as the LLM result arrives. This controls display pacing, not LLM timeout."}
            </p>
            <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500">
              LLM mode
              <select className="app-input" value={llmMode} onChange={(event) => setLlmMode(event.target.value as typeof llmMode)}>
                <option value="off">off</option>
                <option value="packet">packet</option>
                <option value="agent">agent</option>
                <option value="hybrid">hybrid</option>
                <option value="full-agent">full-agent · 모든 이벤트 1:1 LLM</option>
              </select>
            </label>
            {llmMode === "full-agent" ? (
              <p className="-mt-2 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-4 text-amber-800">
                {isKo
                  ? "full-agent는 모든 생각/발화를 개별 LLM 호출로 처리합니다. 품질 검증용이며 비용과 실행 시간이 크게 증가합니다."
                  : "full-agent sends every thought/speech through per-agent LLM calls. Use for quality checks; cost and latency increase sharply."}
              </p>
            ) : null}
            {llmMode === "full-agent" ? (
              <div className="rounded-2xl border border-amber-100 bg-white px-3 py-2 text-[11px] leading-4 text-slate-600">
                {isKo
                  ? "LLM samples 제한은 무시됩니다. 생성된 모든 이벤트가 agent LLM 호출을 기다린 뒤 표시됩니다."
                  : "LLM sample limits are ignored. Every generated event waits for an agent LLM decision before display."}
              </div>
            ) : (
              <NumberControl label="LLM samples" value={llmSampleSize} min={1} max={512} setValue={setLlmSampleSize} />
            )}
            {(llmMode === "full-agent" || llmMode === "agent" || llmMode === "hybrid") ? (
              <NumberControl label={isKo ? "LLM 병렬 호출" : "LLM parallel calls"} value={llmParallelism} min={1} max={16} setValue={setLlmParallelism} />
            ) : null}
          </div>
          <div className="mt-5 flex gap-2">
            <button type="button" className="app-button app-button--primary flex-1" onClick={run} disabled={running}>
              {running ? (isKo ? "스트리밍 중" : "Streaming") : isKo ? "세션 시작" : "Start Session"}
            </button>
            {running ? (
              <button type="button" className="app-button app-button--ghost" onClick={stop}>
                {isKo ? "중지" : "Stop"}
              </button>
            ) : null}
          </div>
          <div className="mt-4 rounded-2xl border border-slate-200 bg-white px-3 py-3 text-xs text-slate-600">
            <div className="flex items-center justify-between gap-2">
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">LLM Connection</p>
                <p className="mt-1 font-semibold text-slate-900">
                  {runtimeStatus?.llm.enabled ? "enabled" : "disabled"} · {runtimeStatus?.llm.provider ?? "unknown"} · {runtimeStatus?.llm.model ?? "unknown"}
                </p>
              </div>
              <button type="button" className="app-button app-button--ghost" onClick={testLlmConnection} disabled={llmTesting}>
                {llmTesting ? "testing" : "test"}
              </button>
            </div>
            {llmTestResult ? (
              <p className={`mt-2 rounded-xl px-2 py-2 ${llmTestResult.ok ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700"}`}>
                {llmTestResult.ok ? "connected" : "not connected"} · {llmTestResult.provider} · {llmTestResult.model}
                {llmTestResult.fallback_reason ? ` · ${llmTestResult.fallback_reason}` : ""}
              </p>
            ) : null}
          </div>
          {error ? <p className="mt-3 rounded-2xl bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}
          <div className="mt-5">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-400">
                {isKo ? "저장된 세션" : "Saved Sessions"}
              </p>
              <button type="button" className="text-[11px] font-semibold text-sky-700" onClick={refreshSavedSessions}>
                refresh
              </button>
            </div>
            <div className="mt-2 max-h-52 space-y-2 overflow-y-auto pr-1">
              {savedSessions.length ? savedSessions.map((item) => (
                <button
                  key={item.session_id}
                  type="button"
                  className="w-full rounded-2xl border border-slate-200 bg-white px-3 py-2 text-left text-xs text-slate-600 transition hover:border-sky-300 hover:bg-sky-50"
                  onClick={() => replay(item.session_id)}
                >
                  <span className="block font-semibold text-slate-900">{item.session_id.slice(0, 8)} · {item.event_count} events</span>
                  <span className="mt-1 block truncate">{item.raw_prompt || item.prompt || "Swarm V2 session"}</span>
                  <span className="mt-1 block text-[10px] uppercase tracking-[0.12em] text-slate-400">{item.llm_mode ?? "packet"} · {item.agent_count} agents</span>
                </button>
              )) : (
                <p className="rounded-2xl bg-white px-3 py-3 text-xs leading-5 text-slate-500">
                  {isKo ? "아직 저장된 세션이 없습니다." : "No saved sessions yet."}
                </p>
              )}
            </div>
          </div>
        </aside>

        <main className="flex min-w-0 flex-col bg-[#f8fbff] p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[24px] border border-slate-200 bg-white px-4 py-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-400">Live Session</p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {sessionId ? `${sessionId.slice(0, 8)} · ${status}` : isKo ? "대기 중" : "Idle"}
              </p>
            </div>
            <div className="h-2 min-w-[220px] flex-1 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-sky-500 transition-all" style={{ width: `${activePercent}%` }} />
            </div>
            <p className="text-xs font-semibold text-slate-500">
              round {Math.round(roundProgress * rounds)}/{rounds}
            </p>
          </div>
          {thinkingEvent ? (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-[22px] border border-amber-200 bg-amber-50 px-4 py-3 text-xs text-amber-900">
              <div className="flex min-w-0 items-center gap-3">
                <span className="relative flex h-2.5 w-2.5 shrink-0">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-amber-500" />
                </span>
                <div className="min-w-0">
                  <p className="font-semibold">
                    {isKo ? "LLM이 에이전트 생각을 생성 중" : "Agent LLM deliberating"}
                  </p>
                  <p className="mt-0.5 truncate text-amber-800/80">
                    {thinkingEvent.source_label || thinkingEvent.source_id} → {thinkingEvent.target_label || thinkingEvent.target_id}
                    {thinkingEvent.topic ? ` · ${thinkingEvent.topic}` : ""}
                  </p>
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-white/70 px-2 py-1 font-semibold text-amber-800">
                #{thinkingEvent.event_index}
              </span>
            </div>
          ) : null}
          <div className="mb-3 grid gap-2 md:grid-cols-5">
            {SESSION_PHASES.map((phase) => (
              <div
                key={phase}
                className={`rounded-2xl border px-3 py-2 text-xs transition ${
                  phase === currentPhase ? "border-sky-300 bg-sky-50 text-sky-900" : "border-slate-200 bg-white text-slate-400"
                }`}
              >
                <p className="font-semibold">{PHASE_LABEL[phase]}</p>
                <div className="mt-2 h-1 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-sky-500"
                    style={{ width: `${phase === currentPhase ? Math.round((latestEvent?.phase_progress ?? 0) * 100) : phaseDonePercent(phase, currentPhase)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
          <canvas ref={canvasRef} className="min-h-0 w-full flex-1 rounded-[28px] border border-slate-200 bg-white shadow-inner" />
        </main>

      </div>
    </section>
  );
}

function NumberControl({ label, value, min, max, setValue }: { label: string; value: number; min: number; max: number; setValue: (value: number) => void }) {
  return (
    <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-[0.12em] text-slate-500">
      {label}
      <input
        className="app-input"
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(event) => setValue(Number(event.target.value))}
      />
    </label>
  );
}

function resizeCanvasToDisplaySize(canvas: HTMLCanvasElement) {
  const rect = canvas.getBoundingClientRect();
  const width = Math.max(320, Math.round(rect.width || 1280));
  const height = Math.max(240, Math.round(rect.height || 720));
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
}

function drawBackground(ctx: CanvasRenderingContext2D, width: number, height: number) {
  ctx.fillStyle = "#f8fbff";
  ctx.fillRect(0, 0, width, height);
  ctx.strokeStyle = "rgba(15,23,42,0.055)";
  ctx.lineWidth = 1;
  for (let x = 48; x < width; x += 64) {
    ctx.beginPath();
    ctx.moveTo(x, 42);
    ctx.lineTo(x, height - 42);
    ctx.stroke();
  }
  for (let y = 48; y < height; y += 64) {
    ctx.beginPath();
    ctx.moveTo(42, y);
    ctx.lineTo(width - 42, y);
    ctx.stroke();
  }
}

function drawThinkingEvent(
  ctx: CanvasRenderingContext2D,
  thinking: ThinkingEvent | null,
  byId: Map<string, SwarmV2Agent>,
  bounds: ReturnType<typeof boundsFor>,
  width: number,
  height: number
) {
  if (!thinking) return;
  const source = byId.get(thinking.source_id);
  const target = byId.get(thinking.target_id);
  if (!source || !target) return;
  const a = project(source, bounds, width, height);
  const b = project(target, bounds, width, height);
  const now = performance.now();
  const phase = ((now - thinking.bornAt) % 1100) / 1100;
  const alpha = 0.18 + Math.sin(phase * Math.PI) * 0.34;
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.max(1, Math.hypot(dx, dy));
  ctx.save();
  ctx.strokeStyle = `rgba(245,158,11,${alpha})`;
  ctx.lineWidth = 1.4;
  ctx.setLineDash([3, 7]);
  ctx.beginPath();
  ctx.moveTo(a.x, a.y);
  ctx.quadraticCurveTo(mx - (dy / len) * 28, my + (dx / len) * 28, b.x, b.y);
  ctx.stroke();
  ctx.setLineDash([]);
  ctx.fillStyle = `rgba(245,158,11,${0.08 + alpha * 0.14})`;
  ctx.beginPath();
  ctx.arc(a.x, a.y, 11 + phase * 10, 0, Math.PI * 2);
  ctx.fill();
  ctx.strokeStyle = `rgba(245,158,11,${0.28 + alpha * 0.42})`;
  ctx.lineWidth = 1.1;
  ctx.beginPath();
  ctx.arc(a.x, a.y, 5 + phase * 6, 0, Math.PI * 2);
  ctx.stroke();
  ctx.fillStyle = "rgba(120,53,15,0.82)";
  ctx.font = "600 11px sans-serif";
  const label = `${thinking.source_label || thinking.source_id} thinking`;
  ctx.fillText(label.slice(0, 44), Math.min(width - 220, a.x + 12), Math.max(28, a.y - 10));
  ctx.restore();
}

function pushVisualPulses(event: SwarmV2Event, pulses: VisualPulse[]) {
  const bornAt = performance.now();
  pulses.push({ id: `${event.event_id}:wave`, event, bornAt, kind: "wave" });
  if ((event.participant_growth ?? 0) > 0) {
    pulses.push({ id: `${event.event_id}:burst`, event, bornAt, kind: "burst" });
  }
  if (event.topic && event.event_index % 9 === 0) {
    pulses.push({ id: `${event.event_id}:branch`, event, bornAt, kind: "branch" });
  }
}

function seedInitialVisibleAgents(agents: SwarmV2Agent[], visible: Set<string>, newcomers: Map<string, number>) {
  if (visible.size > 0) return;
  const initialCount = Math.max(8, Math.min(agents.length, Math.floor(agents.length * 0.06)));
  const now = performance.now();
  agents.slice(0, initialCount).forEach((agent) => {
    visible.add(agent.agent_id);
    newcomers.set(agent.agent_id, now);
  });
}

function revealAgentsFromEvent(
  event: SwarmV2Event,
  agents: SwarmV2Agent[],
  visible: Set<string>,
  newcomers: Map<string, number>,
  pulses: VisualPulse[]
) {
  const now = performance.now();
  const reveal = (agentId: string) => {
    if (visible.has(agentId)) return;
    visible.add(agentId);
    newcomers.set(agentId, now);
    pulses.push({ id: `${event.event_id}:newcomer:${agentId}`, event, bornAt: now, kind: "newcomer" });
  };
  reveal(event.source_id);
  reveal(event.target_id);
  const growth = event.participant_growth ?? 0;
  if (growth <= 0) return;
  const start = Math.max(0, (event.active_agent_count ?? visible.size) - growth);
  const end = Math.min(agents.length, start + Math.min(growth, 120));
  agents.slice(start, end).forEach((agent) => reveal(agent.agent_id));
}

function syncVisualAgents(agents: SwarmV2Agent[], states: Map<string, VisualAgentState>) {
  const known = new Set(agents.map((agent) => agent.agent_id));
  for (const agent of agents) {
    if (states.has(agent.agent_id)) continue;
    states.set(agent.agent_id, {
      x: agent.x,
      y: agent.y,
      targetX: agent.x,
      targetY: agent.y,
      heat: 0,
      lastHitAt: 0,
    });
  }
  for (const agentId of states.keys()) {
    if (!known.has(agentId)) states.delete(agentId);
  }
}

function stirVisualAgents(event: SwarmV2Event, agents: SwarmV2Agent[], states: Map<string, VisualAgentState>) {
  const byId = new Map(agents.map((agent) => [agent.agent_id, agent]));
  const source = byId.get(event.source_id);
  const target = byId.get(event.target_id);
  if (!source || !target) return;
  const sourceState = ensureVisualAgentState(source, states);
  const targetState = ensureVisualAgentState(target, states);
  const dx = target.x - source.x;
  const dy = target.y - source.y;
  const len = Math.max(0.001, Math.hypot(dx, dy));
  const pull = 0.1 + Math.min(0.45, event.intensity * 0.2);
  const repel = event.interaction_type === "hostile" || event.interaction_type === "negative" ? -0.16 : 0.08;
  const bend = Number(event.llm_action_effect ?? 0) * 0.55;
  const nx = dx / len;
  const ny = dy / len;
  const sideX = -ny;
  const sideY = nx;
  sourceState.targetX = source.x + nx * pull + sideX * bend;
  sourceState.targetY = source.y + ny * pull + sideY * bend;
  targetState.targetX = target.x - nx * (pull + repel) - sideX * bend;
  targetState.targetY = target.y - ny * (pull + repel) - sideY * bend;
  const now = performance.now();
  sourceState.heat = Math.min(1, sourceState.heat + 0.28 + event.intensity * 0.24);
  targetState.heat = Math.min(1, targetState.heat + 0.2 + event.intensity * 0.18);
  sourceState.lastHitAt = now;
  targetState.lastHitAt = now;
}

function tickVisualAgents(agents: SwarmV2Agent[], states: Map<string, VisualAgentState>) {
  for (const agent of agents) {
    const state = ensureVisualAgentState(agent, states);
    state.targetX += (agent.x - state.targetX) * 0.018;
    state.targetY += (agent.y - state.targetY) * 0.018;
    state.x += (state.targetX - state.x) * 0.18;
    state.y += (state.targetY - state.y) * 0.18;
    state.heat *= 0.94;
  }
}

function ensureVisualAgentState(agent: SwarmV2Agent, states: Map<string, VisualAgentState>) {
  let state = states.get(agent.agent_id);
  if (!state) {
    state = {
      x: agent.x,
      y: agent.y,
      targetX: agent.x,
      targetY: agent.y,
      heat: 0,
      lastHitAt: 0,
    };
    states.set(agent.agent_id, state);
  }
  return state;
}

function agentForDraw(agent: SwarmV2Agent, states: Map<string, VisualAgentState>): SwarmV2Agent {
  const state = states.get(agent.agent_id);
  if (!state) return agent;
  return { ...agent, x: state.x, y: state.y, pressure: Math.min(1, agent.pressure + state.heat * 0.28) };
}

function drawTopicBranches(
  ctx: CanvasRenderingContext2D,
  events: SwarmV2Event[],
  byId: Map<string, SwarmV2Agent>,
  bounds: ReturnType<typeof boundsFor>,
  width: number,
  height: number
) {
  const topicAnchors = new Map<string, { x: number; y: number; count: number; tone: string }>();
  for (const event of events.slice(-180)) {
    if (!event.topic) continue;
    const source = byId.get(event.source_id);
    const target = byId.get(event.target_id);
    if (!source || !target) continue;
    const a = project(source, bounds, width, height);
    const b = project(target, bounds, width, height);
    const current = topicAnchors.get(event.topic) ?? { x: 0, y: 0, count: 0, tone: event.interaction_type };
    current.x += (a.x + b.x) / 2;
    current.y += (a.y + b.y) / 2;
    current.count += 1;
    current.tone = event.interaction_type;
    topicAnchors.set(event.topic, current);
  }
  for (const [topic, anchor] of topicAnchors) {
    const x = anchor.x / anchor.count;
    const y = anchor.y / anchor.count;
    const radius = Math.min(64, 14 + anchor.count * 2.2);
    ctx.fillStyle = toneColor(anchor.tone, 0.045);
    ctx.strokeStyle = toneColor(anchor.tone, 0.12);
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.ellipse(x, y, radius * 1.35, radius * 0.72, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    if (anchor.count > 5) {
      ctx.fillStyle = "rgba(15,23,42,0.5)";
      ctx.font = "600 10px sans-serif";
      ctx.fillText(topic.slice(0, 28), x - radius, y - radius * 0.55);
    }
  }
}

function drawPulses(
  ctx: CanvasRenderingContext2D,
  pulses: VisualPulse[],
  byId: Map<string, SwarmV2Agent>,
  bounds: ReturnType<typeof boundsFor>,
  width: number,
  height: number
) {
  const now = performance.now();
  for (const pulse of pulses) {
    const source = byId.get(pulse.event.source_id);
    const target = byId.get(pulse.event.target_id);
    if (!source || !target) continue;
    const a = project(source, bounds, width, height);
    const b = project(target, bounds, width, height);
    const mx = (a.x + b.x) / 2;
    const my = (a.y + b.y) / 2;
    const elapsed = now - pulse.bornAt;
    const life = pulse.kind === "burst" ? 980 : pulse.kind === "branch" ? 1500 : 780;
    const t = Math.min(1, elapsed / life);
    const alpha = (1 - t) * (pulse.kind === "burst" ? 0.32 : 0.22);
    if (pulse.kind === "newcomer") {
      const radius = 4 + t * 28;
      ctx.strokeStyle = `rgba(14,165,233,${alpha * 1.4})`;
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.arc(mx, my, radius, 0, Math.PI * 2);
      ctx.stroke();
    } else if (pulse.kind === "wave") {
      const radius = 8 + t * (42 + pulse.event.intensity * 80);
      ctx.strokeStyle = toneColor(pulse.event.interaction_type, alpha);
      ctx.lineWidth = 1.2 + pulse.event.intensity * 1.6;
      ctx.beginPath();
      ctx.arc(mx, my, radius, 0, Math.PI * 2);
      ctx.stroke();
    } else if (pulse.kind === "burst") {
      const growth = pulse.event.participant_growth ?? 0;
      const radius = 18 + t * (56 + Math.min(120, growth * 1.4));
      ctx.fillStyle = toneColor(pulse.event.interaction_type, alpha * 0.28);
      ctx.strokeStyle = toneColor(pulse.event.interaction_type, alpha);
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.ellipse(mx, my, radius * 1.4, radius * 0.76, 0, 0, Math.PI * 2);
      ctx.fill();
      ctx.stroke();
    } else {
      ctx.strokeStyle = toneColor(pulse.event.interaction_type, alpha);
      ctx.lineWidth = 1.1;
      ctx.setLineDash([4, 8]);
      ctx.beginPath();
      ctx.moveTo(mx - 48 * t, my);
      ctx.lineTo(mx + 48 * t, my);
      ctx.moveTo(mx, my - 32 * t);
      ctx.lineTo(mx, my + 32 * t);
      ctx.stroke();
      ctx.setLineDash([]);
    }
  }
}

function drawEventLine(
  ctx: CanvasRenderingContext2D,
  source: SwarmV2Agent,
  target: SwarmV2Agent,
  event: SwarmV2Event,
  bounds: ReturnType<typeof boundsFor>,
  width: number,
  height: number,
  age: number
) {
  const a = project(source, bounds, width, height);
  const b = project(target, bounds, width, height);
  const alpha = Math.max(0.05, Math.min(0.72, age * 0.36 + event.intensity * 0.2));
  ctx.strokeStyle = toneColor(event.interaction_type, alpha);
  ctx.lineWidth = 0.55 + event.intensity * 1.1;
  ctx.beginPath();
  const mx = (a.x + b.x) / 2;
  const my = (a.y + b.y) / 2;
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len = Math.max(1, Math.hypot(dx, dy));
  ctx.moveTo(a.x, a.y);
  ctx.quadraticCurveTo(mx - (dy / len) * 20, my + (dx / len) * 20, b.x, b.y);
  ctx.stroke();
}

function drawAgent(
  ctx: CanvasRenderingContext2D,
  agent: SwarmV2Agent,
  bounds: ReturnType<typeof boundsFor>,
  width: number,
  height: number,
  newcomerBornAt?: number,
  visualState?: VisualAgentState
) {
  const p = project(agent, bounds, width, height);
  const newcomerAge = newcomerBornAt ? Math.max(0, 1 - (performance.now() - newcomerBornAt) / 1400) : 0;
  const hitAge = visualState?.lastHitAt ? Math.max(0, 1 - (performance.now() - visualState.lastHitAt) / 900) : 0;
  const heat = visualState?.heat ?? 0;
  const radius = 1.25 + agent.pressure * 2.7;
  if (newcomerAge > 0) {
    ctx.strokeStyle = `rgba(14,165,233,${newcomerAge * 0.55})`;
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.arc(p.x, p.y, radius + 5 + newcomerAge * 8, 0, Math.PI * 2);
    ctx.stroke();
  }
  if (hitAge > 0 || heat > 0.05) {
    ctx.fillStyle = `rgba(14,165,233,${Math.min(0.18, hitAge * 0.12 + heat * 0.08)})`;
    ctx.beginPath();
    ctx.arc(p.x, p.y, radius + 4 + heat * 8, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.fillStyle = `rgba(2,132,199,${0.22 + agent.pressure * 0.52 + heat * 0.16})`;
  ctx.beginPath();
  ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
  ctx.fill();
  if (hitAge > 0.2) {
    ctx.strokeStyle = `rgba(15,23,42,${hitAge * 0.16})`;
    ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.arc(p.x, p.y, radius + 1.8, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function trimVisualPulses(pulses: VisualPulse[]) {
  const now = performance.now();
  const keep = pulses.filter((pulse) => now - pulse.bornAt < 1700).slice(-180);
  pulses.length = 0;
  pulses.push(...keep);
}

function trimNewcomers(newcomers: Map<string, number>) {
  const now = performance.now();
  for (const [agentId, bornAt] of newcomers) {
    if (now - bornAt > 1600) {
      newcomers.delete(agentId);
    }
  }
}

function boundsFor(agents: SwarmV2Agent[]) {
  const xs = agents.map((agent) => agent.x);
  const ys = agents.map((agent) => agent.y);
  return {
    minX: Math.min(...xs),
    maxX: Math.max(...xs),
    minY: Math.min(...ys),
    maxY: Math.max(...ys),
  };
}

function project(agent: SwarmV2Agent, bounds: ReturnType<typeof boundsFor>, width: number, height: number) {
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const padding = 42;
  const drawableWidth = Math.max(1, width - padding * 2);
  const drawableHeight = Math.max(1, height - padding * 2);
  const scale = Math.min(drawableWidth / spanX, drawableHeight / spanY);
  const usedWidth = spanX * scale;
  const usedHeight = spanY * scale;
  const offsetX = padding + (drawableWidth - usedWidth) / 2;
  const offsetY = padding + (drawableHeight - usedHeight) / 2;
  return {
    x: offsetX + (agent.x - bounds.minX) * scale,
    y: offsetY + (bounds.maxY - agent.y) * scale,
  };
}

function toneColor(tone: SwarmV2Event["interaction_type"], alpha: number) {
  if (tone === "hostile") return `rgba(220,38,38,${alpha})`;
  if (tone === "negative") return `rgba(249,115,22,${alpha})`;
  if (tone === "positive") return `rgba(22,163,74,${alpha})`;
  return `rgba(2,132,199,${alpha})`;
}

function phaseDonePercent(phase: string, currentPhase: string) {
  const phaseIndex = SESSION_PHASES.indexOf(phase);
  const currentIndex = SESSION_PHASES.indexOf(currentPhase);
  return phaseIndex < currentIndex ? 100 : 0;
}
