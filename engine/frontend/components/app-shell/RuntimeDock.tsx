"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import type { CellSnapshot, CollectiveDynamicsSummary, LocalRuntimeStatus } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";

type SimulationDockPayload = {
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
};

type RuntimeDockProps = {
  locale: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
  activeWorldId?: string | null;
  simulationDock?: SimulationDockPayload | null;
};

export function RuntimeDock({
  locale,
  runtime,
  runtimeError,
  apiBase,
  activeWorldId = null,
  simulationDock = null,
}: RuntimeDockProps) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const [dockView, setDockView] = useState<"controls" | "runtime" | "calls" | "thoughts">(
    simulationDock ? "controls" : "runtime"
  );

  useEffect(() => {
    if (simulationDock) {
      setDockView((current) => (current === "runtime" ? "controls" : current));
    }
  }, [simulationDock]);

  const thoughtCards = useMemo(
    () =>
      (simulationDock?.thoughtCells ?? [])
        .map((agent) => ({
          agent,
          preview: getThoughtPreview(agent),
        }))
        .filter((item) => Boolean(item.preview?.summary))
        .sort((a, b) => Number(b.preview?.t ?? -1) - Number(a.preview?.t ?? -1))
        .slice(0, 10),
    [simulationDock]
  );

  const connectionState = simulationDock?.connectionState ?? {
    key: "disconnect",
    label: "disconnect",
    tone: "red" as const,
    detail: isKo ? "연결 테스트 전" : "not tested yet",
  };

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AppPanel
        title={strings.runtimeDockTitle}
        subtitle={strings.runtimeDockSubtitle}
        className="min-h-0 flex-1"
        bodyClassName="flex h-full min-h-0 flex-col gap-3"
      >
        <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
                {isKo ? "LLM 연결 상태" : "LLM Connection"}
              </p>
              <p className="mt-1 text-sm font-semibold text-slate-900">
                {runtime?.llm?.provider ?? "stub"} · {runtime?.llm?.model ?? "stub"}
              </p>
            </div>
            <span
              className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${
                connectionState.tone === "green"
                  ? "bg-emerald-50 text-emerald-700"
                  : connectionState.tone === "amber"
                    ? "bg-amber-50 text-amber-700"
                    : "bg-rose-50 text-rose-700"
              }`}
            >
              <span
                className={`inline-block h-2.5 w-2.5 rounded-full ${
                  connectionState.tone === "green"
                    ? "bg-emerald-500"
                    : connectionState.tone === "amber"
                      ? "bg-amber-500"
                      : "bg-rose-500"
                }`}
              />
              {connectionState.label}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">{connectionState.detail}</p>
        </div>

        <div className={`grid gap-2 ${simulationDock ? "grid-cols-4" : "grid-cols-3"}`}>
          {simulationDock ? (
            <button
              type="button"
              className={`app-button ${dockView === "controls" ? "app-button--primary" : "app-button--ghost"}`}
              onClick={() => setDockView("controls")}
            >
              {isKo ? "실행" : "Controls"}
            </button>
          ) : null}
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
            {isKo ? "에이전트 생각" : "Agent Thoughts"}
          </button>
        </div>

        <div className="min-h-0 flex-1 overflow-y-auto pr-1">
          {dockView === "controls" ? (
            simulationDock ? (
              <div className="space-y-3">{simulationDock.controlsContent}</div>
            ) : (
              <EmptyState text={isKo ? "실행 중인 시뮬레이션을 열면 제어 메뉴가 여기에 표시됩니다." : "Open a simulation world to show controls here."} />
            )
          ) : null}

          {dockView === "runtime" ? (
            simulationDock?.runtimeContent ? (
              <div className="space-y-3">{simulationDock.runtimeContent}</div>
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
              {!activeWorldId ? (
                <EmptyState text={isKo ? "시뮬레이션 world를 열면 현재 t 기준 thought stream이 여기에 표시됩니다." : "Open a simulation world to show current-t thought traces here."} />
              ) : thoughtCards.length ? (
                <>
                  {simulationDock?.collectiveSummary ? (
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
                  ) : null}
                  <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-600">
                    {isKo ? "현재 관측 시점" : "Current observed t"} · t={Number(simulationDock?.currentT ?? 0).toFixed(0)}
                  </div>
                  {thoughtCards.map(({ agent, preview }) => (
                    <article
                      key={`dock-thought-${agent.cell_id}`}
                      className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-semibold text-slate-900">
                            {agent.role_label ?? agent.role_key ?? "agent"}
                          </p>
                          <p className="truncate text-xs text-slate-500">
                            {(agent.persona_country ?? "unknown").toUpperCase()} · {agent.zone_label ?? agent.zone_id ?? "zone"}
                          </p>
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
                      <p className="mt-2 text-xs leading-6 text-slate-700">{preview?.summary ?? ""}</p>
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
                </>
              ) : (
                <EmptyState text={isKo ? "현재 t 기준으로 표시할 생각 흔적이 없습니다." : "No thought traces are available for the current t yet."} />
              )}
            </div>
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

function getThoughtPreview(agent: CellSnapshot): { summary: string; t?: number; continuityScore?: number; continuityState?: string } | null {
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
  const behaviorLog = Array.isArray(agent.behavior_log) ? agent.behavior_log : [];
  for (const item of [...behaviorLog].reverse()) {
    const eventType = String(item?.event_type ?? "");
    const itemSummary = String(item?.summary ?? "").trim();
    if (eventType === "thought_update" && itemSummary) {
      return {
        summary: itemSummary,
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
