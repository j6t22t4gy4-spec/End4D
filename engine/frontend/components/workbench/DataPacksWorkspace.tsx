"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus } from "@/lib/api";
import type { UiLocale } from "@/lib/ui-language";

type DataPacksWorkspaceProps = {
  locale?: UiLocale;
  runtime: LocalRuntimeStatus | null;
  syncing: boolean;
  syncError: string | null;
  onSync: () => void;
};

export function DataPacksWorkspace({
  locale = "ko",
  runtime,
  syncing,
  syncError,
  onSync,
}: DataPacksWorkspaceProps) {
  const isKo = locale === "ko";
  return (
    <div className="workspace-grid">
      <AppPanel
        title={isKo ? "데이터 팩" : "Data Packs"}
        subtitle={isKo ? "클라우드에서 내려온 페르소나 팩의 로컬 캐시" : "Cloud-delivered persona packs cached on this machine"}
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"
      >
        <div className="xl:col-span-2 flex items-center justify-between gap-3 rounded-[18px] border border-slate-200 bg-slate-50 px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">{isKo ? "매니페스트 동기화" : "Manifest Sync"}</p>
            <p className="mt-1 truncate text-xs text-slate-500">
              {runtime?.remote_manifest_url || (isKo ? "로컬 런타임 환경에서 설정됨" : "Configured from local runtime environment")}
            </p>
          </div>
          <button
            type="button"
            onClick={onSync}
            disabled={syncing}
            className="shrink-0 rounded-[8px] border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {syncing ? (isKo ? "동기화 중" : "Syncing") : isKo ? "동기화" : "Sync"}
          </button>
        </div>
        {syncError ? (
          <p className="xl:col-span-2 rounded-[12px] border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {syncError}
          </p>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2">
          {runtime?.packs.length ? (
            runtime.packs.map((pack) => (
              <article
                key={`${pack.pack_id}-${pack.version}`}
                className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-slate-900">
                      {pack.country.toUpperCase()} · {pack.kind}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">{pack.pack_id}</p>
                  </div>
                  <span className="rounded-full bg-slate-900 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-white">
                    v{pack.version}
                  </span>
                </div>
                <div className="mt-4 grid gap-2 text-sm text-slate-600">
                  <PackField label={isKo ? "라이선스" : "License"} value={pack.license || (isKo ? "대기 중" : "Pending")} />
                  <PackField
                    label={isKo ? "소스" : "Source"}
                    value={pack.source_url || (isKo ? "원격 매니페스트 소스를 아직 사용할 수 없습니다" : "Remote manifest source unavailable")}
                  />
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              {isKo ? "설치된 데이터 팩이 아직 없습니다." : "No installed data packs yet."}
            </div>
          )}
        </div>

        <div className="grid gap-3 content-start">
          <SummaryBox
            label={isKo ? "설치된 팩" : "Installed Packs"}
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <SummaryBox
            label={isKo ? "지역" : "Regions"}
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(", ").toUpperCase()
                : isKo ? "지역 없음" : "No regions"
            }
          />
          <SummaryBox
            label={isKo ? "매니페스트 경로" : "Manifest Path"}
            value={runtime?.manifest_path ?? (isKo ? "런타임 대기 중" : "Waiting for runtime")}
          />
        </div>
      </AppPanel>
    </div>
  );
}

function PackField({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 break-all text-sm text-slate-800">{value}</p>
    </div>
  );
}

function SummaryBox({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 break-all text-sm font-medium text-slate-900">{value}</p>
    </div>
  );
}
