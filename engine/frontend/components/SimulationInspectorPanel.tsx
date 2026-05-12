"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  postAgentInterview,
  postAgentInterviewDiff,
  type AgentInterviewResponse,
  type CellSnapshot,
} from "@/lib/api";
import { type UiLocale } from "@/lib/ui-language";

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
  locale?: UiLocale;
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
  locale = "ko",
  selectedAgent,
  selectedZone,
  selectedBand,
  worldSummary,
  agentRoster,
  onSelectAgent,
  onOpenWorldAt,
  onClearSelection,
}: SimulationInspectorPanelProps) {
  const isKo = locale === "ko";
  const hasSelection = Boolean(selectedAgent || selectedZone || selectedBand);

  return (
    <AppPanel
      title={isKo ? "필드 로그" : "Field Log"}
      subtitle={isKo ? "소셜 필드 옆에서 최근 에이전트 생각과 선택 맥락을 같이 봅니다" : "Read recent agent thoughts and selection context beside the social field"}
      bodyClassName="space-y-4"
      action={
        hasSelection ? (
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={onClearSelection}
          >
            {isKo ? "지우기" : "Clear"}
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

      <div className="space-y-4">
        {!hasSelection ? <EmptyState locale={locale} /> : null}
        <ThoughtPreviewRail locale={locale} agentRoster={agentRoster} onSelectAgent={onSelectAgent} />
        {selectedAgent ? (
          <AgentCard
            locale={locale}
            agent={selectedAgent}
            worldId={worldSummary.worldId}
            currentT={worldSummary.currentT}
            onOpenWorldAt={onOpenWorldAt}
          />
        ) : null}
        {selectedZone ? <ZoneCard zone={selectedZone} /> : null}
        {selectedBand ? <BandCard band={selectedBand} /> : null}
      </div>
    </AppPanel>
  );
}

export function AgentDirectoryPanel({
  locale = "ko",
  agentRoster,
  onSelectAgent,
}: {
  locale?: UiLocale;
  agentRoster: CellSnapshot[];
  onSelectAgent: (agent: CellSnapshot) => void;
}) {
  const isKo = locale === "ko";
  return (
    <AppPanel
      title={isKo ? "에이전트 디렉터리" : "Agent Directory"}
      subtitle={
        isKo
          ? "필요할 때만 펼쳐서 에이전트를 검색하고 선택합니다"
          : "Expand only when needed to search and select agents"
      }
      bodyClassName="space-y-3"
    >
      <details className="group rounded-[22px] border border-slate-200 bg-slate-50" open={false}>
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm font-semibold text-slate-800">
          <span>{isKo ? "에이전트 목록 열기" : "Open Agent Directory"}</span>
          <span className="text-xs font-medium text-slate-500 group-open:hidden">
            {isKo ? "기본 접힘" : "Collapsed"}
          </span>
          <span className="hidden text-xs font-medium text-slate-500 group-open:inline">
            {isKo ? "열림" : "Open"}
          </span>
        </summary>
        <div className="border-t border-slate-200 px-3 py-3">
          <AgentDirectory locale={locale} agentRoster={agentRoster} onSelectAgent={onSelectAgent} />
        </div>
      </details>
    </AppPanel>
  );
}

function ThoughtPreviewRail({
  locale = "ko",
  agentRoster,
  onSelectAgent,
}: {
  locale?: UiLocale;
  agentRoster: CellSnapshot[];
  onSelectAgent: (agent: CellSnapshot) => void;
}) {
  const isKo = locale === "ko";
  const previewAgents = useMemo(
    () =>
      agentRoster
        .map((agent) => ({
          agent,
          preview: getAgentThoughtPreview(agent),
        }))
        .filter((item) => Boolean(item.preview?.summary))
        .sort((a, b) => Number(b.preview?.t ?? -1) - Number(a.preview?.t ?? -1))
        .slice(0, 4),
    [agentRoster]
  );

  if (!previewAgents.length) return null;

  return (
    <section className="inspector-card">
      <InspectorHeading
        title={isKo ? "최근 에이전트 생각" : "Recent Agent Thoughts"}
        subtitle={isKo ? "선택하기 전에도 현재 사고 흔적을 빠르게 봅니다" : "Scan current thought traces before selecting an agent"}
      />
      <div className="grid gap-2">
        {previewAgents.map(({ agent, preview }) => (
          <button
            key={`thought-preview-${agent.cell_id}`}
            type="button"
            className="session-thread-card text-left"
            onClick={() => onSelectAgent(agent)}
          >
            <div className="session-thread-card__header">
              <p className="session-thread-card__title">{agent.role_label ?? agent.role_key ?? "agent"}</p>
              <div className="flex items-center gap-2">
                <span className="session-thread-card__meta">
                  t={Number(preview?.t ?? agent.t ?? 0).toFixed(0)}
                </span>
                <span className="session-thread-card__meta">
                  {formatObserverFocus(agent, isKo)}
                </span>
              </div>
            </div>
            <p className="session-thread-card__prompt">
              {preview?.summary ?? ""}
            </p>
            <div className="mt-2 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
              <span className={continuityPillClass(preview?.continuityState)}>
                {formatContinuity(preview, isKo)}
              </span>
              {typeof agent.action_state?.last_spatial_shift === "number" ? (
                <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-600">
                  move {Number(agent.action_state.last_spatial_shift).toFixed(2)}
                </span>
              ) : null}
            </div>
          </button>
        ))}
      </div>
    </section>
  );
}

function AgentDirectory({
  locale = "ko",
  agentRoster,
  onSelectAgent,
}: {
  locale?: UiLocale;
  agentRoster: CellSnapshot[];
  onSelectAgent: (agent: CellSnapshot) => void;
}) {
  const isKo = locale === "ko";
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
    <section className="space-y-3">
      <InspectorHeading
        title={isKo ? "에이전트 디렉터리" : "Agent Directory"}
        subtitle={isKo ? "이 스냅샷의 어떤 페르소나에게도 질문할 수 있습니다" : "Query any persona agent in this snapshot"}
      />
      <input
        className="app-input"
        value={query}
        onChange={(event) => setQuery(event.target.value)}
        placeholder={isKo ? "role, country, zone, id로 검색" : "Search by role, country, zone, or id"}
      />
      <div className="grid max-h-[24rem] gap-2 overflow-y-auto pr-1">
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
          <p className="text-sm text-slate-500">{isKo ? "검색 결과가 없습니다." : "No search results."}</p>
        ) : null}
      </div>
    </section>
  );
}

function EmptyState({ locale = "ko" }: { locale?: UiLocale }) {
  const isKo = locale === "ko";
  return (
    <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-4 py-5 text-sm leading-6 text-slate-600">
      {isKo
        ? "지도에서 agent, zone, contour band를 선택하면 이 패널에서 상세 맥락을 볼 수 있습니다. 비교 워크플로우를 위해 선택 결과를 우측으로 고정하는 구조입니다."
        : "Select an agent, zone, or contour band on the map to inspect it here. The panel keeps that context pinned for comparison work."}
    </div>
  );
}

function AgentCard({
  locale = "ko",
  agent,
  worldId,
  currentT,
  onOpenWorldAt,
}: {
  locale?: UiLocale;
  agent: CellSnapshot;
  worldId: string | null;
  currentT: number;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
}) {
  const isKo = locale === "ko";
  const strategy = String(agent.action_state?.strategy_summary ?? "n/a");
  const thoughtSummary = String(agent.action_state?.last_thought_summary ?? "").trim();
  const thoughtAt =
    typeof agent.action_state?.last_thought_t === "number"
      ? Number(agent.action_state.last_thought_t)
      : null;
  const zMode = String(agent.action_state?.z_mode ?? "hybrid");
  const continuityScore =
    typeof agent.action_state?.thought_continuity_score === "number"
      ? Number(agent.action_state.thought_continuity_score)
      : null;
  const continuityState = String(agent.action_state?.thought_continuity_state ?? "");
  const observerFocus = String(agent.action_state?.observer_focus ?? "field");
  const observerScore =
    typeof agent.action_state?.observer_score === "number"
      ? Number(agent.action_state.observer_score)
      : null;
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
        <MetricRow label="continuity" value={formatContinuityMetric(continuityState, continuityScore, isKo)} />
        <MetricRow label="observer" value={formatObserverMetric(observerFocus, observerScore, isKo)} />
        <MetricRow label="z mode" value={zMode} />
        <MetricRow label="zone influence" value={String(agent.zone_influence ?? 1)} />
        <MetricRow label="short mem" value={String(shortCount)} />
        <MetricRow label="long mem" value={String(longCount)} />
      </div>
      {agent.persona_text ? <p className="inspector-body">{agent.persona_text}</p> : null}
      <p className="inspector-note">strategy: {strategy}</p>
      <ThoughtStreamCard locale={locale} agent={agent} thoughtSummary={thoughtSummary} thoughtAt={thoughtAt} />
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
            {isKo ? "에이전트에게 묻기" : "Ask Agent"}
          </button>
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={runDiffInterview}
          >
            {isKo ? "변화에 대해 묻기" : "Ask Change"}
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

function ThoughtStreamCard({
  locale = "ko",
  agent,
  thoughtSummary,
  thoughtAt,
}: {
  locale?: UiLocale;
  agent: CellSnapshot;
  thoughtSummary: string;
  thoughtAt: number | null;
}) {
  const isKo = locale === "ko";
  const thoughtMemories = useMemo(() => extractThoughtEntries(agent), [agent]);

  return (
    <div className="space-y-3 rounded-[18px] border border-violet-200 bg-violet-50/70 px-4 py-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-violet-700">
            {isKo ? "Thought Stream" : "Thought Stream"}
          </p>
          <p className="mt-1 text-xs text-violet-700/80">
            {isKo ? "선택된 에이전트가 최근에 남긴 생각과 전략 맥락" : "Recent thought and strategy traces from the selected agent"}
          </p>
        </div>
        {thoughtAt != null ? (
          <span className="rounded-full bg-white px-2 py-1 text-[11px] font-semibold text-violet-700">
            t={thoughtAt.toFixed(0)}
          </span>
        ) : null}
      </div>
      <div className="rounded-2xl border border-violet-200 bg-white px-3 py-3 shadow-sm">
        <p className="text-[11px] uppercase tracking-[0.16em] text-violet-500">
          {isKo ? "현재 생각" : "Current Thought"}
        </p>
        <p className="mt-2 text-sm leading-6 text-slate-800">
          {thoughtSummary || (isKo ? "아직 저장된 thought summary가 없습니다. 다음 thought cadence에서 채워집니다." : "No stored thought summary yet. It will appear on the next thought cadence.")}
        </p>
      </div>
      <div className="grid gap-2">
        {thoughtMemories.length ? (
          thoughtMemories.map((item, index) => (
            <div key={`${index}-${item.summary}`} className="session-thread-card">
              <div className="session-thread-card__header">
                <p className="session-thread-card__title">{item.label}</p>
                {typeof item.t === "number" ? (
                  <span className="session-thread-card__meta">t={item.t.toFixed(0)}</span>
                ) : null}
              </div>
              <p className="session-thread-card__prompt">{item.summary}</p>
            </div>
          ))
        ) : (
          <p className="text-sm text-violet-700/80">
            {isKo ? "아직 보여줄 thought trace가 없습니다." : "No thought trace is available yet."}
          </p>
        )}
      </div>
    </div>
  );
}

type ThoughtEntry = {
  label: string;
  summary: string;
  t?: number;
};

function getAgentThoughtPreview(agent: CellSnapshot): { summary: string; t?: number; continuityScore?: number; continuityState?: string } | null {
  const summary = String(agent.action_state?.last_thought_summary ?? "").trim();
  if (summary) {
    return {
      summary,
      t: typeof agent.action_state?.last_thought_t === "number" ? Number(agent.action_state.last_thought_t) : agent.t,
      continuityScore:
        typeof agent.action_state?.thought_continuity_score === "number"
          ? Number(agent.action_state.thought_continuity_score)
          : undefined,
      continuityState: String(agent.action_state?.thought_continuity_state ?? ""),
    };
  }
  const entries = extractThoughtEntries(agent);
  const thoughtEntry = entries.find((item) => item.label === "thought") ?? entries[0];
  if (!thoughtEntry?.summary) return null;
  return {
    summary: thoughtEntry.summary,
    t: thoughtEntry.t,
    continuityScore:
      typeof agent.action_state?.thought_continuity_score === "number"
        ? Number(agent.action_state.thought_continuity_score)
        : undefined,
    continuityState: String(agent.action_state?.thought_continuity_state ?? ""),
  };
}

function formatObserverFocus(agent: CellSnapshot, isKo: boolean): string {
  const focus = String(agent.action_state?.observer_focus ?? "field");
  if (focus === "thought") return isKo ? "생각 중심" : "thought";
  if (focus === "mover") return isKo ? "이동 중심" : "mover";
  if (focus === "zone") return isKo ? "구역 대표" : "zone";
  return isKo ? "필드 대표" : "field";
}

function formatContinuity(
  preview: { continuityScore?: number; continuityState?: string } | null | undefined,
  isKo: boolean
): string {
  const state = String(preview?.continuityState ?? "");
  const score = typeof preview?.continuityScore === "number" ? Math.round(preview.continuityScore * 100) : null;
  if (state === "stable") return isKo ? `연속성 높음${score != null ? ` ${score}` : ""}` : `high continuity${score != null ? ` ${score}` : ""}`;
  if (state === "evolving") return isKo ? `연속성 변화${score != null ? ` ${score}` : ""}` : `evolving${score != null ? ` ${score}` : ""}`;
  if (state === "volatile") return isKo ? `급변${score != null ? ` ${score}` : ""}` : `volatile${score != null ? ` ${score}` : ""}`;
  return isKo ? "연속성 미측정" : "continuity n/a";
}

function continuityPillClass(state?: string): string {
  if (state === "stable") {
    return "rounded-full bg-emerald-50 px-2 py-1 font-semibold text-emerald-700";
  }
  if (state === "evolving") {
    return "rounded-full bg-amber-50 px-2 py-1 font-semibold text-amber-700";
  }
  if (state === "volatile") {
    return "rounded-full bg-rose-50 px-2 py-1 font-semibold text-rose-700";
  }
  return "rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-600";
}

function formatContinuityMetric(state: string, score: number | null, isKo: boolean): string {
  const scoreText = score != null ? ` ${Math.round(score * 100)}` : "";
  if (state === "stable") return isKo ? `높음${scoreText}` : `high${scoreText}`;
  if (state === "evolving") return isKo ? `변화${scoreText}` : `evolving${scoreText}`;
  if (state === "volatile") return isKo ? `급변${scoreText}` : `volatile${scoreText}`;
  return isKo ? "미측정" : "n/a";
}

function formatObserverMetric(focus: string, score: number | null, isKo: boolean): string {
  const focusLabel =
    focus === "thought"
      ? isKo
        ? "생각"
        : "thought"
      : focus === "mover"
        ? isKo
          ? "이동"
          : "mover"
        : focus === "zone"
          ? isKo
            ? "구역"
            : "zone"
          : isKo
            ? "필드"
            : "field";
  const scoreText = score != null ? ` ${Math.round(score * 100)}` : "";
  return `${focusLabel}${scoreText}`;
}

function extractThoughtEntries(agent: CellSnapshot): ThoughtEntry[] {
  const entries: ThoughtEntry[] = [];
  const behaviorLog = Array.isArray(agent.behavior_log) ? agent.behavior_log : [];
  const shortMemory = Array.isArray(agent.short_memory) ? agent.short_memory : [];
  const longMemory = Array.isArray(agent.long_memory) ? agent.long_memory : [];

  for (const item of [...behaviorLog].reverse()) {
    const eventType = String(item?.event_type ?? "");
    const summary = String(item?.summary ?? "").trim();
    if (!summary) continue;
    if (eventType === "thought_update") {
      entries.push({
        label: "thought",
        summary,
        t: typeof item?.t === "number" ? Number(item.t) : undefined,
      });
    } else if (eventType === "action_plan" || eventType === "agent_dialogue") {
      entries.push({
        label: eventType === "action_plan" ? "action" : "dialogue",
        summary,
        t: typeof item?.t === "number" ? Number(item.t) : undefined,
      });
    }
    if (entries.length >= 4) break;
  }

  if (entries.length < 4) {
    for (const item of [...shortMemory, ...longMemory].reverse()) {
      const kind = String(item?.kind ?? "");
      const summary = String(item?.summary ?? "").trim();
      if (!summary) continue;
      if (!["thought_update", "action_plan", "agent_dialogue"].includes(kind)) continue;
      entries.push({
        label:
          kind === "thought_update"
            ? "thought"
            : kind === "action_plan"
              ? "action"
              : "dialogue",
        summary,
        t: typeof item?.t === "number" ? Number(item.t) : undefined,
      });
      if (entries.length >= 4) break;
    }
  }

  return entries.slice(0, 4);
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
