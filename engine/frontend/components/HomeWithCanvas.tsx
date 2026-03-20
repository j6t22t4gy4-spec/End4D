"use client";

import dynamic from "next/dynamic";

const GodView = dynamic(() => import("@/components/GodView"), {
  ssr: false,
  loading: () => <p className="text-slate-400">God View 로딩…</p>,
});

export default function HomeWithCanvas() {
  return (
    <main className="min-h-screen bg-slate-950 text-white p-4 md:p-6">
      <h1 className="text-2xl font-semibold tracking-tight mb-1">
        Organic4D — God View
      </h1>
      <p className="text-slate-500 text-sm mb-6">
        프롬프트 기반 세계 생성 · 역할형 에이전트 · 3계층 사고
      </p>
      <GodView />
    </main>
  );
}
