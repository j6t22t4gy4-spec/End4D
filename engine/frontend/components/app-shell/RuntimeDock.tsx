"use client";

import { useEffect, useMemo, useState } from "react";
import type { CellSnapshot, LocalRuntimeStatus } from "@/lib/api";
import { getSnapshotAtT, listSnapshotTimes } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";

type RuntimeDockProps = {
  locale: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
  activeWorldId?: string | null;
};

export function RuntimeDock({
  locale,
  runtime,
  runtimeError,
  apiBase,
  activeWorldId = null,
}: RuntimeDockProps) {
  const strings = UI_STRINGS[locale];
  const isKo = locale === "ko";
  const [dockView, setDockView] = useState<"runtime" | "calls" | "thoughts">("runtime");
  const [thoughtAgents, setThoughtAgents] = useState<CellSnapshot[]>([]);
  const [thoughtsLoading, setThoughtsLoading] = useState(false);
  const [thoughtsError, setThoughtsError] = useState<string | null>(null);

  useEffect(() => {
    if (dockView !== "thoughts" || !activeWorldId) {
      return;
    }
    let cancelled = false;
    setThoughtsLoading(true);
    setThoughtsError(null);
    Promise.all([listSnapshotTimes(activeWorldId), Promise.resolve(activeWorldId)])
      .then(async ([times]) => {
        const latestT = times.available_t[times.available_t.length - 1];
        if (typeof latestT !== "number") {
          return { cells: [] as CellSnapshot[] };
        }
        return getSnapshotAtT(activeWorldId, latestT);
      })
      .then((snapshot) => {
        if (cancelled) return;
        setThoughtAgents(snapshot.cells ?? []);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setThoughtAgents([]);
          setThoughtsError(error.message);
        }
      })
      .finally(() => {
        if (!cancelled) {
          setThoughtsLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [activeWorldId, dockView]);

  const thoughtCards = useMemo(
    () =>
      thoughtAgents
        .map((agent) => ({
          agent,
          preview: getThoughtPreview(agent),
        }))
        .filter((item) => Boolean(item.preview?.summary))
        .sort((a, b) => Number(b.preview?.t ?? -1) - Number(a.preview?.t ?? -1))
        .slice(0, 8),
    [thoughtAgents]
  );

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AppPanel
        title={strings.runtimeDockTitle}
        subtitle={strings.runtimeDockSubtitle}
        className="min-h-0 flex-1"
        bodyClassName="flex h-full min-h-0 flex-col gap-3"
      >
        <div className="grid grid-cols-3 gap-2">
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
          {dockView === "runtime" ? (
            <div className="space-y-3">
              <InfoRow label={strings.api} value={apiBase} />
              <InfoRow
                label={strings.llm}
                value={
                  runtime?.llm?.enabled
                    ? `${runtime.llm.provider} · ${runtime.llm.model}`
                    : "Disabled"
                }
              />
              <InfoRow
                label={strings.llmAuth}
                value={
                  runtime?.llm?.has_api_key
                    ? `${strings.keySet} · ${runtime?.llm?.configured_via ?? "runtime-ui"}`
                    : strings.noApiKey
                }
              />
              <InfoRow
                label={strings.llmProfile}
                value={runtime?.llm?.runtime_profile ?? "balanced"}
              />
              <InfoRow
                label={strings.strictMode}
                value={runtime?.llm?.strict_mode ?? runtime?.llm_runtime?.strict_mode ?? "adaptive"}
              />
              <InfoRow
                label={strings.providerHealth}
                value={
                  runtime?.llm_runtime?.health
                    ? `${runtime.llm_runtime.health.status} · ${runtime.llm_runtime.health.reason || "ready"}`
                    : strings.waitingRuntime
                }
              />
              <InfoRow
                label={strings.manifest}
                value={runtime?.manifest_path ?? strings.waitingRuntime}
              />
              <InfoRow
                label={strings.cache}
                value={runtime?.data_cache_dir ?? strings.waitingRuntime}
              />
              {runtimeError && (
                <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                  {strings.runtimeLoadError}: {runtimeError}
                </p>
              )}
            </div>
          ) : null}

          {dockView === "calls" ? (
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-2">
          <InfoRow
            label={strings.recentCalls}
            value={String(runtime?.llm_runtime?.health?.recent_call_count ?? 0)}
          />
          <InfoRow
            label={strings.liveRate}
            value={`${Math.round((runtime?.llm_runtime?.health?.live_call_rate ?? 0) * 100)}%`}
          />
          <InfoRow
            label={strings.fallbackRate}
            value={`${Math.round((runtime?.llm_runtime?.health?.recent_fallback_rate ?? 0) * 100)}%`}
          />
          <InfoRow
            label={strings.dominantFailure}
            value={runtime?.llm_runtime?.health?.dominant_failure_reason || "none"}
          />
          <InfoRow
            label="Stability"
            value={`${Math.round((runtime?.llm_runtime?.health?.stability_score ?? 0) * 100)}%`}
          />
          <InfoRow
            label="Live Streak"
            value={String(runtime?.llm_runtime?.health?.live_streak ?? 0)}
          />
          <InfoRow
            label="Fallback Streak"
            value={String(runtime?.llm_runtime?.health?.fallback_streak ?? 0)}
          />
          <InfoRow
            label="Optimizer"
            value={String(runtime?.llm_runtime?.optimizer?.mode ?? "balanced-throttle")}
          />
          <InfoRow
            label="Provider Pressure"
            value={String(runtime?.llm_runtime?.optimizer?.provider_error_pressure ?? 0)}
          />
          <InfoRow
            label="Repairs"
            value={String(runtime?.llm_runtime?.repair_summary?.total_repairs ?? 0)}
          />
              </div>
              {runtime?.llm_runtime?.repair_summary?.top_reasons?.length ? (
          <div className="rounded-2xl border border-sky-200 bg-sky-50 px-3 py-3 text-xs text-sky-900">
            <p className="font-semibold">Repair Signals</p>
            <p className="mt-1">
              {runtime.llm_runtime.repair_summary.top_reasons
                .map((item) => `${item.reason}(${item.count})`)
                .join(" · ")}
            </p>
          </div>
              ) : null}
              {runtime?.llm_runtime?.degraded_tasks?.length ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-3 text-xs text-amber-800">
            <p className="font-semibold">{strings.degradedTasks}</p>
            <p className="mt-1">{runtime.llm_runtime.degraded_tasks.join(", ")}</p>
          </div>
              ) : null}
              {runtime?.llm_runtime?.recommended_actions?.length ? (
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3 text-xs text-slate-700">
            <p className="font-semibold">{strings.recommendedActions}</p>
            <ul className="mt-2 list-disc space-y-1 pl-4">
              {runtime.llm_runtime.recommended_actions.map((item, index) => (
                <li key={`${index}-${item}`}>{item}</li>
              ))}
            </ul>
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
            {runtime.llm_runtime.task_insights?.length ? (
              <div className="space-y-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    {strings.taskInsights}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">{strings.taskInsightsSubtitle}</p>
                </div>
                {runtime.llm_runtime.task_insights.map((item) => (
                  <article
                    key={`insight-${item.task}`}
                    className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">{item.task}</p>
                        <p className="truncate text-xs text-slate-500">
                          live {Math.round((item.live_call_rate ?? 0) * 100)}% · prompts {Math.round((item.prompt_live_rate ?? 0) * 100)}% · floor {runtime?.llm_runtime?.task_live_floors?.[item.task] ?? 0}
                        </p>
                      </div>
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                        {item.status}
                      </span>
                    </div>
                    <p className="mt-2 text-xs text-slate-600">{item.recommendation}</p>
                    {item.top_fallback_reasons?.length ? (
                      <p className="mt-2 text-[11px] text-slate-500">
                        {item.top_fallback_reasons.map((reason) => `${reason.reason}(${reason.count})`).join(" · ")}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
            {runtime.llm_runtime.repair_summary?.task_repairs?.length ? (
              <div className="space-y-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Review Repairs
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    Which review tasks needed citation repair most often.
                  </p>
                </div>
                {runtime.llm_runtime.repair_summary.task_repairs.map((item) => (
                  <article
                    key={`repair-${item.task}`}
                    className="rounded-2xl border border-sky-200 bg-sky-50 px-4 py-3 shadow-sm"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-slate-900">{item.task}</p>
                        <p className="truncate text-xs text-slate-500">
                          repairs {item.repair_count}
                        </p>
                      </div>
                    </div>
                    {item.top_reasons?.length ? (
                      <p className="mt-2 text-[11px] text-slate-600">
                        {item.top_reasons.map((reason) => `${reason.reason}(${reason.count})`).join(" · ")}
                      </p>
                    ) : null}
                  </article>
                ))}
              </div>
            ) : null}
          </>
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
                  {strings.noLlmActivity}
                </div>
              )}
            </div>
          ) : null}

          {dockView === "thoughts" ? (
            <div className="space-y-3">
              {!activeWorldId ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
                  {isKo ? "시뮬레이션 world를 열면 최신 에이전트 생각이 여기에 표시됩니다." : "Open a simulation world to show recent agent thoughts here."}
                </div>
              ) : thoughtsLoading ? (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
                  {isKo ? "에이전트 생각을 불러오는 중..." : "Loading agent thoughts..."}
                </div>
              ) : thoughtsError ? (
                <div className="rounded-2xl border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-700">
                  {thoughtsError}
                </div>
              ) : thoughtCards.length ? (
                thoughtCards.map(({ agent, preview }) => (
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
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                        t={Number(preview?.t ?? 0).toFixed(0)}
                      </span>
                    </div>
                    <p className="mt-2 text-xs leading-6 text-slate-700">
                      {preview?.summary ?? ""}
                    </p>
                  </article>
                ))
              ) : (
                <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
                  {isKo ? "아직 표시할 생각 흔적이 없습니다." : "No thought traces are available yet."}
                </div>
              )}
            </div>
          ) : null}
        </div>
      </AppPanel>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50 px-3 py-3">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 break-all text-sm text-slate-900">{value}</p>
    </div>
  );
}

function getThoughtPreview(agent: CellSnapshot): { summary: string; t?: number } | null {
  const summary = String(agent.action_state?.last_thought_summary ?? "").trim();
  if (summary) {
    return {
      summary,
      t: typeof agent.action_state?.last_thought_t === "number" ? Number(agent.action_state.last_thought_t) : agent.t,
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
      };
    }
  }
  return null;
}
