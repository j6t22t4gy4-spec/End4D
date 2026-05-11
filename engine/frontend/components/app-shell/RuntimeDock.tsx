"use client";

import type { LocalRuntimeStatus } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";
import { UI_STRINGS, type UiLocale } from "@/lib/ui-language";

type RuntimeDockProps = {
  locale: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
};

export function RuntimeDock({
  locale,
  runtime,
  runtimeError,
  apiBase,
}: RuntimeDockProps) {
  const strings = UI_STRINGS[locale];
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AppPanel
        title={strings.runtimeDockTitle}
        subtitle={strings.runtimeDockSubtitle}
        bodyClassName="space-y-3"
      >
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
      </AppPanel>

      <AppPanel
        title={strings.llmActivityTitle}
        subtitle={strings.llmActivitySubtitle}
        className="min-h-0"
        bodyClassName="space-y-3 overflow-y-auto pr-1"
      >
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
        </div>
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
          </>
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
            {strings.noLlmActivity}
          </div>
        )}
      </AppPanel>

      <AppPanel
        title={strings.installedPacksTitle}
        subtitle={strings.installedPacksSubtitle}
        className="min-h-0 flex-1"
        bodyClassName="space-y-3 overflow-y-auto pr-1"
      >
        {runtime?.packs.length ? (
          runtime.packs.slice(0, 8).map((pack) => (
            <article
              key={`${pack.pack_id}-${pack.version}`}
              className="rounded-2xl border border-slate-200 bg-white px-4 py-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-900">
                    {pack.country.toUpperCase()} · {pack.kind}
                  </p>
                  <p className="truncate text-xs text-slate-500">{pack.pack_id}</p>
                </div>
                <span className="rounded-full bg-slate-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
                  v{pack.version}
                </span>
              </div>
              <p className="mt-2 text-xs text-slate-600">
                {pack.license || strings.licensePending}
              </p>
            </article>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
            {strings.noInstalledPacks}
          </div>
        )}
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
