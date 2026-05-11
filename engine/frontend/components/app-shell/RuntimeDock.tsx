"use client";

import type { LocalRuntimeStatus } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";

type RuntimeDockProps = {
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
};

export function RuntimeDock({
  runtime,
  runtimeError,
  apiBase,
}: RuntimeDockProps) {
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <AppPanel
        title="Runtime"
        subtitle="Local engine status"
        bodyClassName="space-y-3"
      >
        <InfoRow label="API" value={apiBase} />
        <InfoRow
          label="LLM"
          value={
            runtime?.llm?.enabled
              ? `${runtime.llm.provider} · ${runtime.llm.model}`
              : "Disabled"
          }
        />
        <InfoRow
          label="LLM Auth"
          value={
            runtime?.llm?.has_api_key
              ? `key set · ${runtime?.llm?.configured_via ?? "runtime-ui"}`
              : "No API key"
          }
        />
        <InfoRow
          label="Manifest"
          value={runtime?.manifest_path ?? "Waiting for runtime"}
        />
        <InfoRow
          label="Cache"
          value={runtime?.data_cache_dir ?? "Waiting for runtime"}
        />
        {runtimeError && (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            런타임 상태를 불러오지 못했습니다: {runtimeError}
          </p>
        )}
      </AppPanel>

      <AppPanel
        title="Installed Packs"
        subtitle="Cloud-fed persona packs cached locally"
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
                {pack.license || "License info pending"}
              </p>
            </article>
          ))
        ) : (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-4 py-5 text-sm text-slate-500">
            아직 설치된 데이터 팩이 없습니다.
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
