"use client";

import { useEffect, useRef, useState } from "react";
import {
  createSwarmV2Session,
  getSwarmV2WebSocketUrl,
  type SwarmV2Agent,
  type SwarmV2Event,
  type SwarmV2RunResponse,
  type SwarmV2StreamMessage,
} from "@/lib/api";

type Props = {
  prompt: string;
  locale?: "ko" | "en";
  primary?: boolean;
  onResult?: (result: SwarmV2RunResponse) => void;
};

export function SwarmV2Panel({ prompt, locale = "ko", primary = false, onResult }: Props) {
  const isKo = locale === "ko";
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [result, setResult] = useState<SwarmV2RunResponse | null>(null);
  const [agents, setAgents] = useState<SwarmV2Agent[]>([]);
  const [events, setEvents] = useState<SwarmV2Event[]>([]);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [streamStatus, setStreamStatus] = useState<"idle" | "connecting" | "streaming" | "complete">("idle");
  const [roundProgress, setRoundProgress] = useState(0);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agentCount, setAgentCount] = useState(1200);
  const [rounds, setRounds] = useState(48);
  const [eventsPerRound, setEventsPerRound] = useState(18);
  const [expectedEvents, setExpectedEvents] = useState(0);

  async function run() {
    wsRef.current?.close();
    setRunning(true);
    setError(null);
    setResult(null);
    setAgents([]);
    setEvents([]);
    setExpectedEvents(0);
    setRoundProgress(0);
    setStreamStatus("connecting");
    try {
      const session = await createSwarmV2Session({
        prompt,
        agent_count: agentCount,
        rounds,
        events_per_round: eventsPerRound,
        zone_count: 24,
        pace_ms: 0,
      });
      setSessionId(session.session_id);
      setAgents(session.agents);
      setExpectedEvents(session.event_count);
      const ws = new WebSocket(getSwarmV2WebSocketUrl(session.session_id));
      wsRef.current = ws;
      ws.onopen = () => setStreamStatus("streaming");
      ws.onmessage = (message) => {
        const payload = JSON.parse(message.data) as SwarmV2StreamMessage;
        if (payload.type === "session_started") {
          setAgents(payload.agents);
          setExpectedEvents(payload.event_count);
          return;
        }
        if (payload.type === "round_started") {
          setRoundProgress(payload.progress);
          return;
        }
        if (payload.type === "event") {
          setEvents((current) => [...current, payload.event]);
          return;
        }
        if (payload.type === "session_completed") {
          setAgents(payload.agents);
          setStreamStatus("complete");
          setRunning(false);
          const completed: SwarmV2RunResponse = {
            runtime: session.runtime,
            prompt: session.prompt,
            agent_count: session.agent_count,
            rounds: session.rounds,
            events_per_round: session.events_per_round,
            zone_count: session.zone_count,
            agents: payload.agents,
            events: [],
            summary: payload.summary,
          };
          setResult(completed);
          onResult?.(completed);
          ws.close();
        }
      };
      ws.onerror = () => {
        setError(isKo ? "Swarm V2 스트림 연결에 실패했습니다." : "Swarm V2 stream connection failed.");
        setRunning(false);
        setStreamStatus("idle");
      };
      ws.onclose = () => {
        wsRef.current = null;
        setRunning((current) => (streamStatus === "complete" ? false : current));
      };
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "swarm v2 failed");
      setStreamStatus("idle");
      setRunning(false);
    }
  }

  function stop() {
    wsRef.current?.close();
    wsRef.current = null;
    setRunning(false);
    setStreamStatus(events.length ? "complete" : "idle");
  }

  useEffect(() => {
    return () => {
      wsRef.current?.close();
    };
  }, []);

  const activeResult: SwarmV2RunResponse | null = agents.length
    ? {
        runtime: result?.runtime ?? "swarm-v2-cleanroom",
        prompt,
        agent_count: agentCount,
        rounds,
        events_per_round: eventsPerRound,
        zone_count: 24,
        agents,
        events,
        summary: result?.summary ?? {},
      }
    : null;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !activeResult) return;
    let frame = 0;
    let raf = 0;
    const sceneAgents = activeResult.agents;
    const sceneEvents = activeResult.events;
    const totalExpected = Math.max(expectedEvents, sceneEvents.length);
    const bounds = boundsFor(agents);
    const draw = () => {
      frame += 1;
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f8fafc";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "rgba(15,23,42,0.08)";
      ctx.lineWidth = 1;
      for (let x = 40; x < width; x += 56) {
        ctx.beginPath();
        ctx.moveTo(x, 24);
        ctx.lineTo(x, height - 24);
        ctx.stroke();
      }
      for (let y = 40; y < height; y += 56) {
        ctx.beginPath();
        ctx.moveTo(24, y);
        ctx.lineTo(width - 24, y);
        ctx.stroke();
      }
      const visibleEventCount = sceneEvents.length;
      const visibleEvents = sceneEvents.slice(Math.max(0, visibleEventCount - 360), visibleEventCount);
      const byId = new Map(sceneAgents.map((agent) => [agent.agent_id, agent]));
      for (const event of visibleEvents) {
        const source = byId.get(event.source_id);
        const target = byId.get(event.target_id);
        if (!source || !target) continue;
        const a = project(source, bounds, width, height);
        const b = project(target, bounds, width, height);
        const age = 1 - (visibleEventCount - event.event_index) / 260;
        const alpha = Math.max(0.04, Math.min(0.42, age * 0.24 + event.intensity * 0.14));
        ctx.strokeStyle = toneColor(event.interaction_type, alpha);
        ctx.lineWidth = 0.45 + event.intensity * 0.9;
        ctx.beginPath();
        const mx = (a.x + b.x) / 2;
        const my = (a.y + b.y) / 2;
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const len = Math.max(1, Math.hypot(dx, dy));
        ctx.moveTo(a.x, a.y);
        ctx.quadraticCurveTo(mx - (dy / len) * 18, my + (dx / len) * 18, b.x, b.y);
        ctx.stroke();
      }
      for (const agent of sceneAgents.slice(0, 2400)) {
        const p = project(agent, bounds, width, height);
        ctx.fillStyle = `rgba(2,132,199,${0.18 + agent.pressure * 0.48})`;
        ctx.beginPath();
        ctx.arc(p.x, p.y, 1.4 + agent.pressure * 2.3, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.fillStyle = "#0f172a";
      ctx.font = "12px sans-serif";
      ctx.fillText(`Swarm V2 · ${visibleEventCount}/${totalExpected} events · ${sceneAgents.length} agents`, 20, 24);
      raf = requestAnimationFrame(draw);
    };
    draw();
    return () => cancelAnimationFrame(raf);
  }, [activeResult, expectedEvents, agents, events]);

  return (
    <div className={`rounded-[28px] border bg-white p-4 shadow-sm ${primary ? "border-sky-300 ring-4 ring-sky-100" : "border-sky-200"}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-slate-900">{primary ? "Swarm V2 · Primary Runtime" : "Swarm V2"}</p>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            {isKo
              ? "이제 기본 실행 경로입니다. 기존 엔진과 분리된 0-base swarm session을 먼저 만듭니다."
              : "This is now the primary run path: a clean 0-base swarm session separated from the legacy engine."}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" className="app-button app-button--primary" onClick={run} disabled={running}>
            {running ? (isKo ? "스트리밍 중" : "Streaming") : isKo ? "Swarm V2 실행" : "Run Swarm V2"}
          </button>
          {running ? (
            <button type="button" className="app-button app-button--ghost" onClick={stop}>
              {isKo ? "중지" : "Stop"}
            </button>
          ) : null}
        </div>
      </div>
      <div className="mt-3 grid gap-2 md:grid-cols-3">
        <MiniNumber label="agents" value={agentCount} setValue={setAgentCount} />
        <MiniNumber label="rounds" value={rounds} setValue={setRounds} />
        <MiniNumber label="events/round" value={eventsPerRound} setValue={setEventsPerRound} />
      </div>
      {error ? <p className="mt-3 rounded-2xl bg-red-50 px-3 py-2 text-xs text-red-700">{error}</p> : null}
      {sessionId ? (
        <div className="mt-3 rounded-2xl bg-sky-50 px-3 py-2 text-xs text-sky-800">
          {isKo ? "세션" : "Session"} {sessionId.slice(0, 8)} · {streamStatus} · {events.length}/{expectedEvents || 0} events · round {Math.round(roundProgress * rounds)}/{rounds}
        </div>
      ) : null}
      <canvas ref={canvasRef} width={960} height={520} className="mt-4 w-full rounded-[24px] border border-slate-200 bg-slate-50" />
      {activeResult ? (
        <div className="mt-3 grid gap-2 text-xs text-slate-600 md:grid-cols-4">
          <Metric label="agents" value={String(activeResult.agent_count)} />
          <Metric label="events" value={`${events.length}/${expectedEvents || events.length}`} />
          <Metric label="active" value={String(result?.summary.active_agent_count ?? "-")} />
          <Metric label="avg pressure" value={String(result?.summary.avg_pressure ?? "-")} />
        </div>
      ) : null}
    </div>
  );
}

function MiniNumber({ label, value, setValue }: { label: string; value: number; setValue: (value: number) => void }) {
  return (
    <label className="flex flex-col gap-1 text-[11px] text-slate-500">
      {label}
      <input className="app-input" type="number" value={value} onChange={(event) => setValue(Number(event.target.value))} />
    </label>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-slate-50 px-3 py-2">
      <p className="uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-1 font-semibold text-slate-900">{value}</p>
    </div>
  );
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
  return {
    x: 36 + ((agent.x - bounds.minX) / spanX) * (width - 72),
    y: 36 + (1 - (agent.y - bounds.minY) / spanY) * (height - 72),
  };
}

function toneColor(tone: SwarmV2Event["interaction_type"], alpha: number) {
  if (tone === "hostile") return `rgba(220,38,38,${alpha})`;
  if (tone === "negative") return `rgba(249,115,22,${alpha})`;
  if (tone === "positive") return `rgba(22,163,74,${alpha})`;
  return `rgba(2,132,199,${alpha})`;
}
