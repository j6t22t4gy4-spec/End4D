"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  postAgentInterview,
  postAgentInterviewDiff,
  type AgentInterviewResponse,
  type CellSnapshot,
} from "@/lib/api";

export type SelectedZone = {
  zoneId: string;
  label: string;
  influence: number;
  friction: number;
  count: number;
};

export type SelectedBand = {
  key: string;
  label: string;
  lower: number;
  upper: number;
  agentCount: number;
  avgEnergy: number;
  avgZ: number;
  dominantRole: string;
  modeLabel: string;
};

type SimulationInspectorPanelProps = {
  selectedAgent: CellSnapshot | null;
  selectedZone: SelectedZone | null;
  selectedBand: SelectedBand | null;
  worldSummary: {
    worldId: string | null;
    currentT: number;
    visibleCount: number;
    totalCount: number;
    sampled: boolean;
  };
  agentRoster: CellSnapshot[];
  onSelectAgent: (agent: CellSnapshot) => void;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
  onClearSelection: () => void;
};

export function SimulationInspectorPanel({
  selectedAgent,
  selectedZone,
  selectedBand,
  worldSummary,
  agentRoster,
  onSelectAgent,
  onOpenWorldAt,
  onClearSelection,
}: SimulationInspectorPanelProps) {
  const hasSelection = Boolean(selectedAgent || selectedZone || selectedBand);

  return (
    <AppPanel
      title="Selection Details"
      subtitle="Agent, zone, and elevation context"
      bodyClassName="space-y-4"
      action={
        hasSelection ? (
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={onClearSelection}
          >
            Clear
          </button>
        ) : undefined
      }
    >
      <div className="grid gap-2 rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
        <MetricRow label="world" value={worldSummary.worldId ?? "none"} mono />
        <MetricRow label="current t" value={worldSummary.currentT.toFixed(1)} />
        <MetricRow
          label="visible / total"
          value={`${worldSummary.visibleCount.toLocaleString()} / ${worldSummary.totalCount.toLocaleString()}`}
        />
        <MetricRow
          label="sampling"
          value={worldSummary.sampled ? "sampled view" : "full view"}
        />
      </div>

      {!hasSelection ? (
        <div className="space-y-4">
          <EmptyState />
          <AgentDirectory agentRoster={agentRoster} onSelectAgent={onSelectAgent} />
        </div>
      ) : (
        <div className="space-y-4">
          {selectedAgent ? (
            <AgentCard
              agent={selectedAgent}
              worldId={worldSummary.worldId}
              currentT={worldSummary.currentT}
              onOpenWorldAt={onOpenWorldAt}
            />
          ) : null}
          <AgentDirectory agentRoster={agentRoster} onSelectAgent={onSelectAgent} />
          {selectedZone ? <ZoneCard zone={selectedZone} /> : null}
          {selectedBand ? <BandCard band={selectedBand} /> : null}
        </div>
      )}
    </AppPanel>
  );
}

function AgentDirectory({
  agentRoster,
  onSelectAgent,
}: {
  agentRoster: CellSnapshot[];
  onSelectAgent: (agent: CellSnapshot) => void;
}) {
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query.trim().toLowerCase());

  const indexedRoster = useMemo(
    () =>
      agentRoster.map((agent) => ({
        agent,
        haystack: [
          agent.cell_id,
          agent.role_label,
          agent.role_key,
          agent.persona_country,
          agent.zone_label,
          agent.zone_id,
        ]
          .map((item) => String(item ?? "").toLowerCase())
          .join(" "),
      })),
    [agentRoster]
  );

  const filtered = useMemo(() => {
    if (!deferredQuery) {
      return indexedRoster.slice(0, 12).map((item) => item.agent);
    }
    return indexedRoster
      .filter((item) => item.haystack.includes(deferredQuery))
      .slice(0, 12)
      .map((item) => item.agent);
  }, [deferredQuery, indexedRoster]);

  return (
    <section className="inspector-card">
      <InspectorHeading
        title="Agent Directory"
        subtitle="Query any persona agent in this snapshot"
      />
      <input
        className="app-input"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder="role, country, zone, id로 검색"
      />
      <div className="grid gap-2">
        {filtered.map((agent) => (
          <button
            key={agent.cell_id}
            type="button"
            className="session-thread-card text-left"
            onClick={() => onSelectAgent(agent)}
          >
            <div className="session-thread-card__header">
              <p className="session-thread-card__title">
                {agent.role_label ?? agent.role_key ?? "agent"}
              </p>
              <span className="session-thread-card__meta">
                {agent.persona_country ?? "unknown"}
              </span>
            </div>
            <p className="session-thread-card__prompt">
              {agent.zone_label ?? agent.zone_id ?? "zone"} · z {(agent.z ?? 0).toFixed(2)} ·{" "}
              {agent.cell_id.slice(0, 8)}
            </p>
          </button>
        ))}
        {!filtered.length ? (
          <p className="text-sm text-slate-500">검색 결과가 없습니다.</p>
        ) : null}
      </div>
    </section>
  );
}

function EmptyState() {
  return (
    <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-4 py-5 text-sm leading-6 text-slate-600">
      지도에서 agent, zone, contour band를 선택하면 이 패널에서 상세 맥락을 볼 수 있습니다.
      비교 워크플로우를 위해 선택 결과를 우측으로 고정하는 구조입니다.
    </div>
  );
}

function AgentCard({
  agent,
  worldId,
  currentT,
  onOpenWorldAt,
}: {
  agent: CellSnapshot;
  worldId: string | null;
  currentT: number;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
}) {
  const strategy = String(agent.action_state?.strategy_summary ?? "n/a");
  const zMode = String(agent.action_state?.z_mode ?? "hybrid");
  const [question, setQuestion] = useState(
    "지금 상황을 너의 입장에서 어떻게 보고 있어?"
  );
  const [response, setResponse] = useState<AgentInterviewResponse | null>(null);
  const [diffResponse, setDiffResponse] = useState<AgentInterviewResponse | null>(null);
  const [loadingMode, setLoadingMode] = useState<"direct" | "diff" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const shortCount = Array.isArray(agent.short_memory) ? agent.short_memory.length : 0;
  const longCount = Array.isArray(agent.long_memory) ? agent.long_memory.length : 0;

  useEffect(() => {
    setResponse(null);
    setDiffResponse(null);
    setError(null);
  }, [agent.cell_id]);

  const runDirectInterview = async () => {
    if (!worldId || !question.trim()) return;
    setLoadingMode("direct");
    setError(null);
    try {
      const payload = await postAgentInterview(worldId, agent.cell_id, {
        question: question.trim(),
        t: currentT,
      });
      setResponse(payload);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "unknown error";
      setError(message);
    } finally {
      setLoadingMode(null);
    }
  };

  const runDiffInterview = async () => {
    if (!worldId || !question.trim()) return;
    setLoadingMode("diff");
    setError(null);
    try {
      const payload = await postAgentInterviewDiff(worldId, agent.cell_id, {
        question: question.trim(),
        t: currentT,
        base_t: 0,
      });
      setDiffResponse(payload);
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "unknown error";
      setError(message);
    } finally {
      setLoadingMode(null);
    }
  };

  return (
    <section className="inspector-card">
      <InspectorHeading
        title={agent.role_label ?? agent.role_key ?? "agent"}
        subtitle={`Agent · ${agent.persona_country ?? "unknown"} · ${agent.zone_label ?? agent.zone_id ?? "zone"}`}
      />
      <div className="inspector-grid">
        <MetricRow label="energy" value={agent.energy.toFixed(2)} />
        <MetricRow label="z" value={(agent.z ?? 0).toFixed(2)} />
        <MetricRow label="z mode" value={zMode} />
        <MetricRow label="zone influence" value={String(agent.zone_influence ?? 1)} />
        <MetricRow label="short mem" value={String(shortCount)} />
        <MetricRow label="long mem" value={String(longCount)} />
      </div>
      {agent.persona_text ? <p className="inspector-body">{agent.persona_text}</p> : null}
      <p className="inspector-note">strategy: {strategy}</p>
      <div className="grid gap-2 pt-2">
        <textarea
          className="app-input min-h-[84px]"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          placeholder="필요할 때 이 에이전트에게 직접 질문할 수 있습니다."
        />
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={runDirectInterview}
          >
            Ask Agent
          </button>
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={runDiffInterview}
          >
            Ask Change
          </button>
        </div>
        {loadingMode ? (
          <p className="text-sm text-slate-500">
            {loadingMode === "direct" ? "Agent interview loading…" : "Agent change interview loading…"}
          </p>
        ) : null}
        {error ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            에이전트 질의를 처리하지 못했습니다: {error}
          </p>
        ) : null}
        {response ? (
          <InterviewResponseCard
            title="Agent Answer"
            response={response}
            fallbackWorldId={worldId}
            onOpenWorldAt={onOpenWorldAt}
          />
        ) : null}
        {diffResponse ? (
          <InterviewResponseCard
            title="Change Interview"
            response={diffResponse}
            fallbackWorldId={worldId}
            onOpenWorldAt={onOpenWorldAt}
          />
        ) : null}
      </div>
    </section>
  );
}

function InterviewResponseCard({
  title,
  response,
  fallbackWorldId,
  onOpenWorldAt,
}: {
  title: string;
  response: AgentInterviewResponse;
  fallbackWorldId: string | null;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
}) {
  return (
    <div className="space-y-3 rounded-[18px] border border-slate-200 bg-slate-50 px-3 py-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          {title}
        </p>
        <span className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
          {response.mode}
        </span>
      </div>
      <p className="inspector-body">{response.answer}</p>
      {response.evidence.length ? (
        <div className="grid gap-2">
          {response.evidence.map((item, index) => (
            <p key={`${index}-${item}`} className="inspector-note">
              {item}
            </p>
          ))}
        </div>
      ) : null}
      {response.citations.length ? (
        <div className="grid gap-2">
          {response.citations.map((item, index) => (
            <div key={`${index}-${item.anchor_id}`} className="session-thread-card">
              <div className="session-thread-card__header">
                <p className="session-thread-card__title">{item.label}</p>
                <span className="session-thread-card__meta">{item.kind}</span>
              </div>
              <p className="session-thread-card__prompt">{item.reason}</p>
              {typeof item.t === "number" && fallbackWorldId ? (
                <div className="session-thread-card__actions">
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onOpenWorldAt(item.world_id ?? fallbackWorldId, item.t ?? null)}
                  >
                    Open at t={item.t}
                  </button>
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ZoneCard({ zone }: { zone: SelectedZone }) {
  return (
    <section className="inspector-card">
      <InspectorHeading title={zone.label} subtitle={`Zone · ${zone.zoneId}`} />
      <div className="inspector-grid">
        <MetricRow label="agents" value={String(zone.count)} />
        <MetricRow label="influence" value={zone.influence.toFixed(2)} />
        <MetricRow label="friction" value={zone.friction.toFixed(2)} />
      </div>
    </section>
  );
}

function BandCard({ band }: { band: SelectedBand }) {
  return (
    <section className="inspector-card">
      <InspectorHeading title={band.label} subtitle={`${band.modeLabel} contour`} />
      <div className="inspector-grid">
        <MetricRow label="agents" value={String(band.agentCount)} />
        <MetricRow label="avg z" value={band.avgZ.toFixed(2)} />
        <MetricRow label="avg energy" value={band.avgEnergy.toFixed(2)} />
        <MetricRow label="dominant role" value={band.dominantRole} />
      </div>
      <p className="inspector-note">
        range: {band.lower.toFixed(2)} - {band.upper.toFixed(2)}
      </p>
    </section>
  );
}

function InspectorHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-semibold tracking-tight text-slate-900">{title}</h4>
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{subtitle}</p>
    </div>
  );
}

function MetricRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-medium text-slate-900 ${mono ? "font-mono text-[12px]" : ""}`}>
        {value}
      </p>
    </div>
  );
}
