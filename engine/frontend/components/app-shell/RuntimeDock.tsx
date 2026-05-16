"use client";

import { useMemo, useState, type ReactNode } from "react";
import type { CellSnapshot, CollectiveDynamicsSummary, LocalRuntimeStatus, RuntimeTiming, SocialActionRecord } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { RuntimeTimingCard } from "@/components/app-shell/RuntimeTimingCard";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";
import { socialFieldActionLabel, socialFieldActionMeta } from "@/lib/socialFieldActions";

type SimulationDockPayload = {
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
};

type RuntimeDockProps = {
  locale: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
  activeView: WorkbenchView;
  activeWorldId?: string | null;
  simulationDock?: SimulationDockPayload | null;
};

export function RuntimeDock({
  locale,
  runtime,
  runtimeError,
  apiBase,
  activeView,
  activeWorldId = null,
  simulationDock = null,
}: RuntimeDockProps) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const [dockView, setDockView] = useState<"controls" | "runtime" | "calls" | "thoughts" | "chat">("runtime");
  const simulationAvailable = Boolean(simulationDock);
  const simulationActive = activeView === "simulation";
  const controlsAvailable = simulationAvailable && simulationActive;
  const useSimulationHeader = simulationActive && Boolean(simulationDock?.timeControlContent);

  const thoughtCards = useMemo(
    () =>
      (simulationDock?.thoughtCells ?? [])
        .map((agent) => ({
          agent,
          preview: getAgentStreamPreview(agent),
        }))
        .filter((item) => Boolean(item.preview?.thought || item.preview?.action))
        .sort((a, b) => Number(b.preview?.t ?? -1) - Number(a.preview?.t ?? -1))
        .slice(0, 10),
    [simulationDock]
  );
  const actionRecords = useMemo(
    () => [...(simulationDock?.actionRecords ?? [])].reverse().slice(0, 16),
    [simulationDock?.actionRecords]
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AppPanel
        title={useSimulationHeader ? undefined : strings.runtimeDockTitle}
        subtitle={useSimulationHeader ? undefined : strings.runtimeDockSubtitle}
        className="min-h-0 flex-1"
        bodyClassName="flex h-full min-h-0 flex-col gap-3"
      >
        {useSimulationHeader ? <div className="runtime-dock__global-time">{simulationDock?.timeControlContent}</div> : null}
        <div className="grid grid-cols-5 gap-2">
          <button
            type="button"
            className={`app-button ${dockView === "controls" ? "app-button--primary" : "app-button--ghost"} ${
              controlsAvailable ? "" : "cursor-not-allowed opacity-50"
            }`}
            onClick={() => {
              if (controlsAvailable) setDockView("controls");
            }}
            aria-disabled={!controlsAvailable}
            disabled={!controlsAvailable}
          >
            {isKo ? "실행" : "Controls"}
          </button>
          <button
            type="button"
            className={`app-button ${dockView === "runtime" ? "app-button--primary" : "app-button--ghost"}`}
            onClick={() => setDockView("runtime")}
          >
            {isKo ? "런타임" : "Runtime"}
          </button>
          <button
            type="button"
            className={`app-button ${dockView === "calls" ? "app-button--primary" : "app-button--ghost"}`}
            onClick={() => setDockView("calls")}
          >
            {isKo ? "LLM 호출" : "LLM Calls"}
          </button>
          <button
            type="button"
            className={`app-button ${dockView === "thoughts" ? "app-button--primary" : "app-button--ghost"}`}
            onClick={() => setDockView("thoughts")}
          >
            {isKo ? "스트림/인사이트" : "Stream/Insights"}
          </button>
          <button
            type="button"
            className={`app-button ${dockView === "chat" ? "app-button--primary" : "app-button--ghost"} ${
              controlsAvailable ? "" : "cursor-not-allowed opacity-50"
            }`}
            onClick={() => {
              if (controlsAvailable) setDockView("chat");
            }}
            aria-disabled={!controlsAvailable}
            disabled={!controlsAvailable}
          >
            {isKo ? "챗" : "Chat"}
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {dockView === "controls" ? (
            simulationDock && simulationActive ? (
              <div className="space-y-3">{simulationDock.controlsContent}</div>
            ) : (
              <EmptyState
                text={
                  simulationAvailable
                    ? isKo
                      ? "실행 제어는 시뮬레이션 탭에서만 활성화됩니다."
                      : "Simulation controls are enabled only in the simulation tab."
                    : isKo
                      ? "시뮬레이션 world를 열면 제어 메뉴가 여기에 표시됩니다."
                      : "Open a simulation world to show controls here."
                }
              />
            )
          ) : null}

          {dockView === "runtime" ? (
            simulationDock?.runtimeContent && simulationActive ? (
              <div className="space-y-3">
                <RuntimeTimingCard timing={simulationDock.runtimeTiming ?? null} isKo={isKo} />
                {simulationDock.runtimeContent}
              </div>
            ) : (
              <div className="space-y-3">
                <InfoRow label={strings.api} value={apiBase} />
                <InfoRow
                  label={strings.llm}
                  value={runtime?.llm?.enabled ? `${runtime.llm.provider} · ${runtime.llm.model}` : "Disabled"}
                />
                <InfoRow
                  label={strings.llmAuth}
                  value={
                    runtime?.llm?.has_api_key
                      ? `${strings.keySet} · ${runtime?.llm?.configured_via ?? "runtime-ui"}`
                      : strings.noApiKey
                  }
                />
                <InfoRow label={strings.llmProfile} value={runtime?.llm?.runtime_profile ?? "balanced"} />
                <InfoRow
                  label={strings.strictMode}
                  value={runtime?.llm?.strict_mode ?? runtime?.llm_runtime?.strict_mode ?? "adaptive"}
                />
                {runtimeError ? (
                  <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                    {strings.runtimeLoadError}: {runtimeError}
                  </p>
                ) : null}
              </div>
            )
          ) : null}

          {dockView === "calls" ? (
            <div className="space-y-3">
              {simulationDock?.llmCallsContent && simulationActive ? (
                <div className="runtime-dock__live-insights">{simulationDock.llmCallsContent}</div>
              ) : null}
              <div className="grid grid-cols-2 gap-2">
                <InfoRow label={strings.recentCalls} value={String(runtime?.llm_runtime?.health?.recent_call_count ?? 0)} />
                <InfoRow label={strings.liveRate} value={`${Math.round((runtime?.llm_runtime?.health?.live_call_rate ?? 0) * 100)}%`} />
                <InfoRow label={strings.fallbackRate} value={`${Math.round((runtime?.llm_runtime?.health?.recent_fallback_rate ?? 0) * 100)}%`} />
                <InfoRow label={strings.dominantFailure} value={runtime?.llm_runtime?.health?.dominant_failure_reason || "none"} />
                <InfoRow label="Stability" value={`${Math.round((runtime?.llm_runtime?.health?.stability_score ?? 0) * 100)}%`} />
                <InfoRow label="Live Streak" value={String(runtime?.llm_runtime?.health?.live_streak ?? 0)} />
              </div>

              {runtime?.llm_runtime?.repair_summary?.top_reasons?.length ? (
                <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-900">
                  <p className="font-semibold">Repair Signals</p>
                  <p className="mt-1">
                    {runtime.llm_runtime.repair_summary.top_reasons.map((item) => `${item.reason}(${item.count})`).join(" · ")}
                  </p>
                </div>
              ) : null}

              {runtime?.llm_runtime?.recent_runs?.length ? (
                <>
                  <div className="runtime-heatmap">
                    {Object.entries(runtime.llm_runtime.task_totals ?? {}).map(([task, totals]) => {
                      const intensity = Math.min(1, Math.max(0.12, (totals.prompt_count_sent || 0) / 24));
                      const hasFallback = (totals.fallback_calls || 0) > 0;
                      return (
                        <div
                          key={task}
                          className="runtime-heatmap__cell"
                          style={{
                            background: hasFallback
                              ? `linear-gradient(180deg, rgba(245, 158, 11, ${Math.min(0.9, intensity + 0.2)}), rgba(251, 191, 36, 0.18))`
                              : `linear-gradient(180deg, rgba(15, 118, 110, ${Math.min(0.9, intensity + 0.18)}), rgba(45, 212, 191, 0.12))`,
                          }}
                        >
                          <strong>{task}</strong>
                          <span>{totals.prompt_count_sent}/{totals.prompt_count_in}</span>
                        </div>
                      );
                    })}
                  </div>
                  {runtime.llm_runtime.recent_runs.slice(-6).reverse().map((run, index) => (
                    <article
                      key={`${run.task}-${index}`}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">{run.task}</p>
                          <p className="truncate text-xs text-slate-500">
                            {run.provider} · {run.model} · p{run.task_priority}
                          </p>
                        </div>
                        <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                          {run.prompt_count_sent}/{run.prompt_count_in}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-600">
                        {run.used_fallback ? `fallback · ${run.fallback_reason || "unknown"}` : "live llm"}
                      </p>
                    </article>
                  ))}
                </>
              ) : (
                <EmptyState text={strings.noLlmActivity} />
              )}
            </div>
          ) : null}

          {dockView === "thoughts" ? (
            <div className="space-y-3">
              {!activeWorldId && !simulationDock?.insightContent ? (
                <EmptyState text={isKo ? "시뮬레이션 world를 열면 현재 t 기준 thought stream이 여기에 표시됩니다." : "Open a simulation world to show current-t thought traces here."} />
              ) : (
                <>
                  {simulationDock?.insightContent && simulationActive ? (
                    <CollapsibleCard title={isKo ? "선택 상세" : "Selection Details"} defaultOpen>
                      <div className="runtime-dock__live-insights">{simulationDock.insightContent}</div>
                    </CollapsibleCard>
                  ) : null}
                  {simulationDock?.collectiveSummary ? (
                    <CollapsibleCard title="Collective Dynamics" defaultOpen>
                      <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-900">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <p className="font-semibold">{isKo ? "Collective Dynamics" : "Collective Dynamics"}</p>
                            <p className="mt-1 text-sky-800/80">
                              {isKo ? "현재 observer 시점의 집단 응집·균열·드리프트 요약" : "Collective cohesion, fracture, and drift at the current observer step"}
                            </p>
                          </div>
                          <span className="rounded-full bg-white px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-sky-700">
                            {simulationDock.collectiveSignal}
                          </span>
                        </div>
                        <div className="mt-3 grid grid-cols-2 gap-2">
                          <InfoRow
                            label={isKo ? "역할 응집" : "Role Cohesion"}
                            value={String(Math.round((simulationDock.collectiveSummary.role?.avg_cohesion ?? 0) * 100))}
                          />
                          <InfoRow
                            label={isKo ? "역할 균열" : "Role Fracture"}
                            value={String(Math.round((simulationDock.collectiveSummary.role?.avg_fracture_risk ?? 0) * 100))}
                          />
                          <InfoRow
                            label={isKo ? "구역 긴장" : "Zone Tension"}
                            value={String(Math.round((simulationDock.collectiveSummary.zone?.avg_tension ?? 0) * 100))}
                          />
                          <InfoRow
                            label={isKo ? "구역 드리프트" : "Zone Drift"}
                            value={String(Math.round((simulationDock.collectiveSummary.zone?.avg_drift_velocity ?? 0) * 100))}
                          />
                        </div>
                        <div className="mt-3 grid gap-2">
                          {simulationDock.collectiveSummary.role?.top_fracturing?.slice(0, 2).map((item) => (
                            <div key={`role-fracture-${item.group_id}`} className="rounded-2xl border border-sky-200 bg-white px-3 py-2 text-slate-700">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700">
                                {isKo ? "Top Fracturing Group" : "Top Fracturing Group"}
                              </p>
                              <p className="mt-1 text-sm">{item.group_label}</p>
                              <p className="mt-1 text-[11px] text-slate-500">
                                fracture {Number(item.fracture_risk ?? 0).toFixed(2)} · tension {Number(item.tension ?? 0).toFixed(2)}
                              </p>
                            </div>
                          ))}
                          {simulationDock.collectiveSummary.zone?.top_drifting?.slice(0, 2).map((item) => (
                            <div key={`zone-drift-${item.group_id}`} className="rounded-2xl border border-sky-200 bg-white px-3 py-2 text-slate-700">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-sky-700">
                                {isKo ? "Top Drifting Zone" : "Top Drifting Zone"}
                              </p>
                              <p className="mt-1 text-sm">{item.group_label}</p>
                              <p className="mt-1 text-[11px] text-slate-500">
                                drift {Number(item.drift_velocity ?? 0).toFixed(2)} · cohesion {Number(item.cohesion ?? 0).toFixed(2)}
                              </p>
                            </div>
                          ))}
                        </div>
                      </div>
                    </CollapsibleCard>
                  ) : null}
                  {actionRecords.length ? (
                    <CollapsibleCard
                      title={isKo ? "사회장 행동 원장" : "Social Field Ledger"}
                      meta={`${actionRecords.length} actions`}
                      defaultOpen
                    >
                      <div className="space-y-2">
                        {actionRecords.map((record, index) => {
                          const meta = socialFieldActionMeta(record.action_type);
                          return (
                            <article key={`${record.record_id ?? record.timestamp ?? "action"}-${index}`} className="rounded-2xl border border-slate-200 bg-white px-3 py-2 shadow-sm">
                              <div className="flex items-start justify-between gap-2">
                                <span className={`rounded-full px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${meta.className}`}>
                                  {socialFieldActionLabel(record, isKo ? "ko" : "en")}
                                </span>
                                <span className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-400">
                                  t={Number(record.scene_t ?? record.t ?? 0).toFixed(2)}
                                </span>
                              </div>
                              <p className="mt-2 text-xs leading-5 text-slate-700">
                                {record.agent_name ?? "field"}
                                {record.target_label ? ` → ${record.target_label}` : ""}
                              </p>
                              {record.result ? <p className="mt-1 text-xs leading-5 text-slate-500">{record.result}</p> : null}
                              {record.interpretation ? <p className="mt-1 text-[11px] leading-4 text-slate-500">{record.interpretation}</p> : null}
                            </article>
                          );
                        })}
                      </div>
                    </CollapsibleCard>
                  ) : null}
                  <CollapsibleCard title={isKo ? "현재 장면 시점" : "Current scene time"} defaultOpen={false}>
                    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
                      {isKo
                        ? "현재 관측은 t 완료 프레임이 아니라 진행 중인 MiroFish식 스트림을 기준으로 합니다"
                        : "Observation follows the active MiroFish-style stream, not completed timestep frames"} · t={Number(simulationDock?.currentT ?? 0).toFixed(2)}
                    </div>
                  </CollapsibleCard>
                  {thoughtCards.length ? (
                    <CollapsibleCard
                      title={isKo ? "에이전트 생각 스트림" : "Agent Thought Stream"}
                      meta={`${thoughtCards.length} agents`}
                      defaultOpen
                    >
                      <div className="space-y-3">
                        {thoughtCards.map(({ agent, preview }) => (
                          <article key={`dock-stream-${agent.cell_id}`} className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="truncate text-sm font-semibold text-slate-900">
                                  {formatAgentIdentity(agent)}
                                </p>
                                <p className="truncate text-xs text-slate-500">
                                  {formatAgentMeta(agent)}
                                </p>
                                <AgentIdentitySummary agent={agent} isKo={isKo} />
                              </div>
                              <div className="flex flex-col items-end gap-1">
                                <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                                  t={Number(preview?.t ?? simulationDock?.currentT ?? 0).toFixed(0)}
                                </span>
                                <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">
                                  {formatObserverFocus(agent, isKo)}
                                </span>
                              </div>
                            </div>
                            <div className="mt-3 space-y-3 rounded-2xl border border-slate-100 bg-slate-50/70 px-3 py-2 pr-2">
                              {preview?.thought ? (
                                <div>
                                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                    {isKo ? "생각" : "Thought"}
                                  </p>
                                  <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-6 text-slate-700">{preview.thought}</p>
                                </div>
                              ) : null}
                              {preview?.action ? (
                                <div>
                                  <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">
                                    {isKo ? "액션" : "Action"}
                                  </p>
                                  <p className="mt-1 whitespace-pre-wrap break-words text-xs leading-6 text-slate-700">{preview.action}</p>
                                </div>
                              ) : null}
                            </div>
                            <div className="mt-3 flex flex-wrap gap-2 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                              <span className={continuityPillClass(preview?.continuityState)}>
                                {formatContinuity(preview, isKo)}
                              </span>
                              {typeof agent.action_state?.last_spatial_shift === "number" ? (
                                <span className="rounded-full bg-slate-100 px-2 py-1 font-semibold text-slate-600">
                                  move {Number(agent.action_state.last_spatial_shift).toFixed(2)}
                                </span>
                              ) : null}
                            </div>
                          </article>
                        ))}
                      </div>
                    </CollapsibleCard>
                  ) : (
                    <EmptyState text={isKo ? "현재 t 기준으로 표시할 생각/액션 흔적이 없습니다." : "No thought or action traces are available for the current t yet."} />
                  )}
                </>
              )}
            </div>
          ) : null}

          {dockView === "chat" ? (
            simulationDock?.chatContent && simulationActive ? (
              <div className="min-h-0">{simulationDock.chatContent}</div>
            ) : (
              <EmptyState text={isKo ? "시뮬레이션 world를 열면 챗 패널이 여기에 표시됩니다." : "Open a simulation world to show chat here."} />
            )
          ) : null}
        </div>
      </AppPanel>
    </div>
  );
}

function EmptyState({ text }: { text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
      {text}
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-1 break-all text-sm text-slate-900">{value}</p>
    </div>
  );
}

function CollapsibleCard({
  title,
  meta,
  defaultOpen = false,
  children,
}: {
  title: string;
  meta?: string;
  defaultOpen?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="runtime-collapsible-card group" open={defaultOpen}>
      <summary className="runtime-collapsible-card__summary">
        <span className="runtime-collapsible-card__chevron">⌄</span>
        <span className="min-w-0 flex-1 truncate">{title}</span>
        {meta ? <span className="runtime-collapsible-card__meta">{meta}</span> : null}
      </summary>
      <div className="runtime-collapsible-card__body">{children}</div>
    </details>
  );
}

function AgentIdentitySummary({ agent, isKo }: { agent: CellSnapshot; isKo: boolean }) {
  const full = formatAgentIdentitySummary(agent);
  const short = truncateText(full, 15);
  return (
    <div className="mt-1 flex min-w-0 items-start gap-1.5">
      <p className="min-w-0 flex-1 text-[11px] leading-5 text-slate-500">{short}</p>
      {full.length > short.length ? (
        <details className="relative shrink-0">
          <summary
            className="flex h-6 w-6 cursor-pointer list-none items-center justify-center rounded-full border border-slate-200 bg-slate-50 text-[11px] font-bold text-slate-500 hover:border-slate-400 hover:text-slate-900"
            aria-label={isKo ? "페르소나 설명 전체 보기" : "Show full persona description"}
            title={isKo ? "전체 설명" : "Full description"}
          >
            i
          </summary>
          <div className="absolute right-0 z-40 mt-2 w-80 rounded-2xl border border-slate-200 bg-white p-3 text-xs leading-6 text-slate-700 shadow-xl">
            <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {isKo ? "페르소나 전문" : "Full persona"}
            </p>
            <p className="max-h-64 overflow-y-auto whitespace-pre-wrap pr-1">{full}</p>
          </div>
        </details>
      ) : null}
    </div>
  );
}

function formatAgentIdentity(agent: CellSnapshot): string {
  const attrs = agent.persona_attrs ?? {};
  const name = firstText(
    attrs.display_name,
    attrs.agent_name,
    attrs.name,
    readablePersonaId(agent.persona_id)
  ) || firstReadableName(formatAgentIdentitySummary(agent));
  const role = firstText(agent.role_label, agent.role_key, "agent");
  return name && name !== role ? `${name}(${role})` : role;
}

function formatAgentMeta(agent: CellSnapshot): string {
  const country = String(agent.persona_country ?? "unknown").toUpperCase();
  const zone = firstText(agent.zone_label, agent.zone_id, "zone");
  const attrs = agent.persona_attrs ?? {};
  const socialRole = firstText(attrs.role, attrs.occupation, attrs.social_role);
  return [country, socialRole, zone].filter(Boolean).join(" · ");
}

function formatAgentIdentitySummary(agent: CellSnapshot): string {
  const attrs = agent.persona_attrs ?? {};
  return firstText(attrs.identity_summary, attrs.persona_summary, agent.persona_text, agent.role_label, agent.role_key, "identity pending");
}

function truncateText(value: string, limit: number): string {
  const text = String(value || "").trim();
  if (text.length <= limit) return text;
  return `${text.slice(0, Math.max(0, limit - 1)).trimEnd()}…`;
}

function firstText(...values: unknown[]): string {
  for (const value of values) {
    const text = String(value ?? "").trim();
    if (text && text !== "undefined" && text !== "null" && !looksLikeMachineId(text)) return text;
  }
  return "";
}

function looksLikeMachineId(value: string): boolean {
  const text = String(value || "").trim();
  return /^[a-f0-9]{16,}$/i.test(text) || /^persona[-_:]?[a-f0-9]{16,}$/i.test(text);
}

function readablePersonaId(value: unknown): string {
  const text = String(value ?? "").trim().replace(/^persona[-_:]/, "");
  return looksLikeMachineId(text) ? "" : text;
}

function firstReadableName(value: string): string {
  const match = String(value || "").match(/([가-힣]{2,4})(?:\s*씨|은|는|이|가|\(|$)/);
  return match?.[1] ?? "";
}

function getAgentStreamPreview(agent: CellSnapshot): {
  thought?: string;
  action?: string;
  t?: number;
  continuityScore?: number;
  continuityState?: string;
} | null {
  const thought = String(agent.action_state?.last_thought_summary ?? "").trim();
  const action = getActionPreview(agent);
  if (thought || action) {
    return {
      thought: thought || undefined,
      action: action || undefined,
      t: typeof agent.action_state?.last_thought_t === "number" ? Number(agent.action_state.last_thought_t) : agent.t,
      continuityScore:
        typeof agent.action_state?.thought_continuity_score === "number"
          ? Number(agent.action_state.thought_continuity_score)
          : undefined,
      continuityState: String(agent.action_state?.thought_continuity_state ?? ""),
    };
  }
  const behaviorLog = Array.isArray(agent.behavior_log) ? agent.behavior_log : [];
  for (const item of [...behaviorLog].reverse()) {
    const eventType = String(item?.event_type ?? "");
    const itemSummary = String(item?.summary ?? "").trim();
    if ((eventType === "thought_update" || eventType === "action_plan" || eventType === "action_update") && itemSummary) {
      return {
        thought: eventType === "thought_update" ? itemSummary : undefined,
        action: eventType !== "thought_update" ? itemSummary : action || undefined,
        t: typeof item?.t === "number" ? Number(item.t) : undefined,
        continuityScore:
          typeof agent.action_state?.thought_continuity_score === "number"
            ? Number(agent.action_state.thought_continuity_score)
            : undefined,
        continuityState: String(agent.action_state?.thought_continuity_state ?? ""),
      };
    }
  }
  return null;
}

function getActionPreview(agent: CellSnapshot): string {
  const directSummary = String(
    agent.action_state?.last_action_summary ??
      agent.action_state?.strategy_summary ??
      agent.action_state?.planned_action ??
      ""
  ).trim();
  if (directSummary) {
    return normalizeActionPreview(agent, directSummary);
  }
  const behaviorLog = Array.isArray(agent.behavior_log) ? agent.behavior_log : [];
  for (const item of [...behaviorLog].reverse()) {
    const eventType = String(item?.event_type ?? "");
    const itemSummary = String(item?.summary ?? "").trim();
    if ((eventType === "action_plan" || eventType === "action_update") && itemSummary) {
      return itemSummary;
    }
  }
  return "";
}

function normalizeActionPreview(agent: CellSnapshot, value: string): string {
  const raw = String(value || "").trim();
  if (!isPlaceholderAction(raw)) return raw;
  const role = firstText(agent.role_label, agent.role_key, "agent");
  const zone = firstText(agent.zone_label, agent.zone_id, "local field");
  const attrs = agent.persona_attrs ?? {};
  const identity = firstText(attrs.identity_summary, attrs.occupation, attrs.persona_summary, agent.persona_text);
  return `행동: ${role} 입장에서 ${zone}의 가까운 사람들과 상황을 확인한다. 이유: ${truncateText(identity, 88) || "초기 페르소나 조건이 다음 선택의 기준이 된다"}. 대상: 주변 협의 대상.`;
}

function isPlaceholderAction(value: string): boolean {
  const raw = String(value || "").trim().toLowerCase();
  return raw === "persona_seeded_initial_state" || raw === "adaptive planning" || raw === "current_state_reflection";
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
