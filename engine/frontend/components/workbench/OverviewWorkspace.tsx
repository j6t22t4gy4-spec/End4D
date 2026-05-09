"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus } from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";

type OverviewWorkspaceProps = {
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
  onOpenView: (view: WorkbenchView) => void;
};

export function OverviewWorkspace({
  runtime,
  runtimeError,
  apiBase,
  onOpenView,
}: OverviewWorkspaceProps) {
  return (
    <div className="workspace-grid">
      <AppPanel
        title="Start Here"
        subtitle="Open the app like a real simulation workbench"
        className="workspace-grid__hero"
        bodyClassName="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_320px]"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-slate-600">
            지금 화면은 단순한 랜딩이 아니라, 엔진과 데이터팩 위에서 바로 작업하는
            워크벤치의 시작 화면입니다. 먼저 시뮬레이션 탭에서 세계를 만들고,
            데이터팩과 정책 실험실을 오가며 비교하는 흐름을 염두에 두고 구성했습니다.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              className="app-button app-button--primary"
              onClick={() => onOpenView("simulation")}
            >
              Open Simulation
            </button>
            <button
              type="button"
              className="app-button app-button--secondary"
              onClick={() => onOpenView("data-packs")}
            >
              Browse Data Packs
            </button>
            <button
              type="button"
              className="app-button app-button--secondary"
              onClick={() => onOpenView("policy-lab")}
            >
              Open Policy Lab
            </button>
          </div>
        </div>
        <div className="grid gap-3">
          <MetricCard label="Runtime" value={runtime?.runtime_profile ?? "Booting"} />
          <MetricCard
            label="Installed Packs"
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <MetricCard
            label="Regions"
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(" · ").toUpperCase()
                : "No regions"
            }
          />
        </div>
      </AppPanel>

      <AppPanel
        title="Workbench Modules"
        subtitle="Toolbar-driven navigation"
        bodyClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-4"
      >
        <ActionCard
          title="Simulation"
          body="세계 생성, 실행, 3D 필드 탐색"
          onClick={() => onOpenView("simulation")}
        />
        <ActionCard
          title="Data Packs"
          body="국가별 페르소나 팩, 캐시, 라이선스 확인"
          onClick={() => onOpenView("data-packs")}
        />
        <ActionCard
          title="Snapshots"
          body="저장된 t 프레임, 복원, what-if 흐름 설계"
          onClick={() => onOpenView("snapshots")}
        />
        <ActionCard
          title="Policy Lab"
          body="주입 이벤트, 실험 설계, 변화 관찰"
          onClick={() => onOpenView("policy-lab")}
        />
      </AppPanel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <AppPanel
          title="Runtime Health"
          subtitle="What the local app is connected to"
          bodyClassName="grid gap-3 md:grid-cols-2"
        >
          <InfoCard label="API Endpoint" value={apiBase} />
          <InfoCard
            label="Manifest"
            value={runtime?.manifest_path ?? "Waiting for runtime"}
          />
          <InfoCard
            label="Cache"
            value={runtime?.data_cache_dir ?? "Waiting for runtime"}
          />
          <InfoCard
            label="State Dir"
            value={runtime?.state_dir ?? "Waiting for runtime"}
          />
        </AppPanel>

        <AppPanel
          title="Operator Notes"
          subtitle="Why this layout is different"
          bodyClassName="space-y-3 text-sm leading-7 text-slate-600"
        >
          <p>
            디자인 레이어는 툴바, 액티비티 레일, 워크스페이스 컴포넌트로 분리되어
            있습니다.
          </p>
          <p>
            엔진 로직은 기존 시뮬레이션 컴포넌트에 남겨 두어서, 데이터팩과 에이전트
            개발에 방해가 되지 않게 했습니다.
          </p>
          {runtimeError && (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              런타임 상태를 불러오지 못했습니다: {runtimeError}
            </p>
          )}
        </AppPanel>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 text-lg font-semibold tracking-tight text-slate-900">
        {value}
      </p>
    </div>
  );
}

function ActionCard({
  title,
  body,
  onClick,
}: {
  title: string;
  body: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      className="module-card"
      onClick={onClick}
    >
      <strong>{title}</strong>
      <p>{body}</p>
      <span>Open</span>
    </button>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
        {label}
      </p>
      <p className="mt-2 break-all text-sm text-slate-800">{value}</p>
    </div>
  );
}
