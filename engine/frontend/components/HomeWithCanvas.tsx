"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  getApiBase,
  getLocalRuntimeStatus,
  type LocalRuntimeStatus,
} from "@/lib/api";

const GodView = dynamic(() => import("@/components/GodView"), {
  ssr: false,
  loading: () => <p className="text-slate-400">God View 로딩…</p>,
});

export default function HomeWithCanvas() {
  const [runtime, setRuntime] = useState<LocalRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLocalRuntimeStatus()
      .then((status) => {
        if (!cancelled) {
          setRuntime(status);
          setRuntimeError(null);
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setRuntimeError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const countriesLabel = useMemo(() => {
    if (!runtime || runtime.available_countries.length === 0) {
      return "No packs";
    }
    return runtime.available_countries.join(" · ").toUpperCase();
  }, [runtime]);

  return (
    <main className="client-shell min-h-screen text-stone-100">
      <div className="client-grid mx-auto flex min-h-screen w-full max-w-[1500px] flex-col gap-6 px-4 py-5 md:px-6 md:py-6">
        <section className="client-hero overflow-hidden rounded-[28px] border border-white/10 px-5 py-5 shadow-2xl shadow-black/30 md:px-7 md:py-6">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl space-y-3">
              <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-cyan-200/80">
                End4D Local Runtime
              </p>
              <h1 className="text-3xl font-semibold tracking-tight text-white md:text-5xl">
                로컬 머신에서 실행되는
                <br />
                시뮬레이션 클라이언트
              </h1>
              <p className="max-w-2xl text-sm leading-6 text-slate-300 md:text-base">
                게임처럼 엔진은 로컬에서 돌리고, 데이터 팩과 페르소나는 런타임이
                받아와서 시뮬레이션에 반영합니다. 아래에서 바로 세계를 생성하고,
                신념 동역학과 에이전트 집단 변화를 탐색할 수 있습니다.
              </p>
            </div>
            <div className="grid min-w-[300px] gap-3 sm:grid-cols-2">
              <StatusCard
                label="Runtime Profile"
                value={runtime?.runtime_profile ?? "Connecting"}
                tone="cyan"
              />
              <StatusCard
                label="API Endpoint"
                value={getApiBase()}
                tone="amber"
              />
              <StatusCard
                label="Installed Packs"
                value={String(runtime?.installed_pack_count ?? 0)}
                tone="emerald"
              />
              <StatusCard
                label="Countries"
                value={countriesLabel}
                tone="violet"
              />
            </div>
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-[320px_minmax(0,1fr)]">
          <aside className="space-y-6">
            <div className="client-panel rounded-[24px] border border-white/10 p-5">
              <div className="mb-4 flex items-center justify-between">
                <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-slate-200/90">
                  Launcher Status
                </h2>
                <span className="rounded-full border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-200">
                  Local
                </span>
              </div>
              <div className="space-y-3 text-sm text-slate-300">
                <InfoRow label="Frontend" value="Live client shell" />
                <InfoRow label="Backend" value={getApiBase()} />
                <InfoRow
                  label="Manifest"
                  value={runtime?.manifest_path ?? "Waiting for runtime"}
                />
                <InfoRow
                  label="Cache"
                  value={runtime?.data_cache_dir ?? "Waiting for runtime"}
                />
              </div>
              {runtimeError && (
                <p className="mt-4 rounded-2xl border border-red-500/30 bg-red-500/10 px-3 py-2 text-xs text-red-200">
                  런타임 상태를 불러오지 못했습니다: {runtimeError}
                </p>
              )}
            </div>

            <div className="client-panel rounded-[24px] border border-white/10 p-5">
              <h2 className="mb-4 text-sm font-semibold uppercase tracking-[0.22em] text-slate-200/90">
                Data Packs
              </h2>
              <div className="space-y-3">
                {runtime?.packs.length ? (
                  runtime.packs.slice(0, 6).map((pack) => (
                    <div
                      key={`${pack.pack_id}-${pack.version}`}
                      className="rounded-2xl border border-white/8 bg-white/5 px-4 py-3"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-medium text-white">
                            {pack.country.toUpperCase()} · {pack.kind}
                          </p>
                          <p className="text-xs text-slate-400">{pack.pack_id}</p>
                        </div>
                        <span className="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.2em] text-cyan-100">
                          v{pack.version}
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-slate-400">
                        {pack.license || "License info pending"}
                      </p>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-white/10 bg-black/10 px-4 py-5 text-sm text-slate-400">
                    아직 설치된 데이터 팩이 없습니다. 런타임이 준비되면 국가별 persona
                    pack이 여기에 표시됩니다.
                  </div>
                )}
              </div>
            </div>
          </aside>

          <section className="client-panel rounded-[28px] border border-white/10 p-4 md:p-5">
            <div className="mb-4 flex flex-col gap-2 border-b border-white/10 pb-4 md:flex-row md:items-end md:justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.28em] text-amber-200/80">
                  Simulation Console
                </p>
                <h2 className="mt-1 text-2xl font-semibold tracking-tight text-white">
                  God View Client
                </h2>
              </div>
              <p className="max-w-xl text-sm leading-6 text-slate-400">
                프롬프트로 세계를 만들고, 시뮬레이션을 실행하고, 스냅샷과 집단 변화의
                흐름을 바로 확인합니다.
              </p>
            </div>
            <GodView />
          </section>
        </section>
      </div>
    </main>
  );
}

function StatusCard({
  label,
  value,
  tone,
}: {
  label: string;
  value: string;
  tone: "cyan" | "amber" | "emerald" | "violet";
}) {
  const toneClass =
    {
      cyan: "from-cyan-400/18 to-cyan-400/6 text-cyan-100",
      amber: "from-amber-400/18 to-amber-400/6 text-amber-100",
      emerald: "from-emerald-400/18 to-emerald-400/6 text-emerald-100",
      violet: "from-fuchsia-400/18 to-fuchsia-400/6 text-fuchsia-100",
    }[tone] ?? "from-white/10 to-white/5 text-white";

  return (
    <div
      className={`rounded-2xl border border-white/10 bg-gradient-to-br px-4 py-3 ${toneClass}`}
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-white/60">
        {label}
      </p>
      <p className="mt-2 break-all text-sm font-medium text-white">{value}</p>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-white/8 bg-black/10 px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">
        {label}
      </p>
      <p className="mt-1 break-all text-sm text-slate-200">{value}</p>
    </div>
  );
}
