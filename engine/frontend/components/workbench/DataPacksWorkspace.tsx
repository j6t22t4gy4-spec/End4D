"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus } from "@/lib/api";

type DataPacksWorkspaceProps = {
  runtime: LocalRuntimeStatus | null;
};

export function DataPacksWorkspace({ runtime }: DataPacksWorkspaceProps) {
  return (
    <div className="workspace-grid">
      <AppPanel
        title="Data Packs"
        subtitle="Cloud-delivered persona packs cached on this machine"
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"
      >
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
                  <PackField label="License" value={pack.license || "Pending"} />
                  <PackField
                    label="Source"
                    value={pack.source_url || "Remote manifest source unavailable"}
                  />
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              설치된 데이터 팩이 아직 없습니다.
            </div>
          )}
        </div>

        <div className="grid gap-3 content-start">
          <SummaryBox
            label="Installed Packs"
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <SummaryBox
            label="Regions"
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(", ").toUpperCase()
                : "No regions"
            }
          />
          <SummaryBox
            label="Manifest Path"
            value={runtime?.manifest_path ?? "Waiting for runtime"}
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
