"use client";

import { useEffect, useState } from "react";
import { getWorldPersonas, type PersonaPreviewResponse } from "@/lib/api";

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
    <section className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-medium text-slate-300">
          Persona Seed
        </h2>
        {data && (
          <span className="text-xs text-slate-500">
            {data.persona_count.toLocaleString()} seeds
          </span>
        )}
      </div>

      {err && (
        <p className="text-xs text-red-300" role="alert">
          {err}
        </p>
      )}

      {!err && !data && (
        <p className="text-xs text-slate-500">페르소나 seed 로딩 중...</p>
      )}

      {data && (
        <>
          <div className="rounded border border-slate-700/80 bg-slate-950/50 p-3 text-xs text-slate-300 space-y-1">
            <p>
              <span className="text-slate-500">source</span>{" "}
              <code className="text-cyan-300 break-all">{source?.source}</code>
            </p>
            {source?.license && (
              <p>
                <span className="text-slate-500">license</span>{" "}
                <code className="text-amber-200">{source.license}</code>
              </p>
            )}
            {source?.attribution_required && (
              <p className="text-amber-200/90 leading-relaxed">
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
                  className="rounded border border-slate-800 bg-slate-950/40 p-3 text-xs"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-slate-200 truncate">
                      {p.role_label || p.role_key}
                    </span>
                    <code className="text-[10px] text-slate-500">
                      {p.country || "?"}
                    </code>
                  </div>
                  <p className="mt-2 max-h-14 overflow-hidden leading-relaxed text-slate-400">
                    {p.persona_text}
                  </p>
                </article>
              ))}
            </div>
          )}
        </>
      )}
    </section>
  );
}
