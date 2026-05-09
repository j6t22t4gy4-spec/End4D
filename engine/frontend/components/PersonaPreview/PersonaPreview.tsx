"use client";

import { useEffect, useState } from "react";
import { getWorldPersonas, type PersonaPreviewResponse } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";

type PersonaPreviewProps = {
  worldId: string | null;
  refreshKey: number;
};

export function PersonaPreview({ worldId, refreshKey }: PersonaPreviewProps) {
  const [data, setData] = useState<PersonaPreviewResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!worldId) {
      setData(null);
      setErr(null);
      return;
    }
    let cancelled = false;
    setErr(null);
    getWorldPersonas(worldId, 6)
      .then((r) => {
        if (!cancelled) setData(r);
      })
      .catch((e) => {
        if (!cancelled) setErr((e as Error).message);
      });
    return () => {
      cancelled = true;
    };
  }, [worldId, refreshKey]);

  if (!worldId) return null;

  const source = data?.source;
  const items = data?.items ?? [];

  return (
    <AppPanel
      title="Persona Seeds"
      subtitle="Dataset preview for the initial world"
      action={
        data ? (
          <span className="rounded-full bg-slate-100 px-3 py-2 text-xs font-medium text-slate-600">
            {data.persona_count.toLocaleString()} seeds
          </span>
        ) : undefined
      }
      bodyClassName="space-y-3"
    >
      {err && (
        <p className="text-xs text-rose-700" role="alert">
          {err}
        </p>
      )}

      {!err && !data && (
        <p className="text-xs text-slate-500">페르소나 seed 로딩 중...</p>
      )}

      {data && (
        <>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-3 text-xs text-slate-700 space-y-1">
            <p>
              <span className="text-slate-500">source</span>{" "}
              <code className="break-all text-slate-900">{source?.source}</code>
            </p>
            {source?.license && (
              <p>
                <span className="text-slate-500">license</span>{" "}
                <code className="text-amber-700">{source.license}</code>
              </p>
            )}
            {source?.attribution_required && (
              <p className="leading-relaxed text-amber-700">
                Attribution required: {source.citation || source.url}
              </p>
            )}
          </div>

          {items.length === 0 ? (
            <p className="text-xs text-slate-500">
              설정된 persona dataset이 없어 역할 카탈로그 fallback으로 시작합니다.
            </p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {items.map((p) => (
                <article
                  key={p.persona_id}
                  className="rounded-2xl border border-slate-200 bg-white p-3 text-xs shadow-sm"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium text-slate-900">
                      {p.role_label || p.role_key}
                    </span>
                    <code className="text-[10px] text-slate-500">
                      {p.country || "?"}
                    </code>
                  </div>
                  <p className="mt-2 max-h-14 overflow-hidden leading-relaxed text-slate-600">
                    {p.persona_text}
                  </p>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </AppPanel>
  );
}
