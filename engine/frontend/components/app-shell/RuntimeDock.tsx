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
            label={strings.fallbackRate}
            value={`${Math.round((runtime?.llm_runtime?.health?.recent_fallback_rate ?? 0) * 100)}%`}
          />
        </div>
        {runtime?.llm_runtime?.recent_runs?.length ? (
          runtime.llm_runtime.recent_runs.slice(-6).reverse().map((run, index) => (
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
          ))
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
