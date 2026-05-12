"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus } from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import type { UiLocale } from "@/lib/ui-language";

type OverviewWorkspaceProps = {
  locale?: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  apiBase: string;
  onOpenView: (view: WorkbenchView) => void;
};

export function OverviewWorkspace({
  locale = "ko",
  runtime,
  runtimeError,
  apiBase,
  onOpenView,
}: OverviewWorkspaceProps) {
  const isKo = locale === "ko";

  return (
    <div className="workspace-grid">
      <AppPanel
        title={isKo ? "여기서 시작" : "Start Here"}
        subtitle={isKo ? "실제 시뮬레이션 워크벤치처럼 앱을 엽니다" : "Open the app like a real simulation workbench"}
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
              {isKo ? "시뮬레이션 열기" : "Open Simulation"}
            </button>
            <button
              type="button"
              className="app-button app-button--secondary"
              onClick={() => onOpenView("data-packs")}
            >
              {isKo ? "데이터 팩 보기" : "Browse Data Packs"}
            </button>
            <button
              type="button"
              className="app-button app-button--secondary"
              onClick={() => onOpenView("policy-lab")}
            >
              {isKo ? "정책 실험실 열기" : "Open Policy Lab"}
            </button>
          </div>
        </div>
        <div className="grid gap-3">
          <MetricCard label={isKo ? "런타임" : "Runtime"} value={runtime?.runtime_profile ?? (isKo ? "부팅 중" : "Booting")} />
          <MetricCard
            label={isKo ? "설치된 팩" : "Installed Packs"}
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <MetricCard
            label={isKo ? "지역" : "Regions"}
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(" · ").toUpperCase()
                : isKo ? "지역 없음" : "No regions"
            }
          />
        </div>
      </AppPanel>

      <AppPanel
        title={isKo ? "워크벤치 모듈" : "Workbench Modules"}
        subtitle={isKo ? "툴바 중심 내비게이션" : "Toolbar-driven navigation"}
        bodyClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-5"
      >
        <ActionCard
          title={isKo ? "시뮬레이션" : "Simulation"}
          body={isKo ? "Setup과 Run을 나눠 세계 생성과 실행을 분리" : "Separate world setup from live execution"}
          ctaLabel={isKo ? "열기" : "Open"}
          onClick={() => onOpenView("simulation")}
        />
        <ActionCard
          title={isKo ? "데이터 관리" : "Data Management"}
          body={isKo ? "데이터팩, 월드, 세션 스레드를 한 곳에서 정리" : "Manage data packs, worlds, and session threads together"}
          ctaLabel={isKo ? "열기" : "Open"}
          onClick={() => onOpenView("data-packs")}
        />
        <ActionCard
          title={isKo ? "스냅샷" : "Snapshots"}
          body={isKo ? "저장된 t 프레임, 복원, what-if 흐름 설계" : "Restore points and what-if branching flows"}
          ctaLabel={isKo ? "열기" : "Open"}
          onClick={() => onOpenView("snapshots")}
        />
        <ActionCard
          title={isKo ? "정책 실험실" : "Policy Lab"}
          body={isKo ? "주입 이벤트, 실험 설계, 변화 관찰" : "Interventions, experiment design, and outcome observation"}
          ctaLabel={isKo ? "열기" : "Open"}
          onClick={() => onOpenView("policy-lab")}
        />
      </AppPanel>

      <div className="grid gap-4 xl:grid-cols-1">
        <AppPanel
          title={isKo ? "런타임 상태" : "Runtime Health"}
          subtitle={isKo ? "현재 로컬 앱이 연결된 대상" : "What the local app is connected to"}
          bodyClassName="grid gap-3 md:grid-cols-2"
        >
          <InfoCard label={isKo ? "API 엔드포인트" : "API Endpoint"} value={apiBase} />
          <InfoCard
            label={isKo ? "매니페스트" : "Manifest"}
            value={runtime?.manifest_path ?? (isKo ? "런타임 대기 중" : "Waiting for runtime")}
          />
          <InfoCard
            label={isKo ? "캐시" : "Cache"}
            value={runtime?.data_cache_dir ?? (isKo ? "런타임 대기 중" : "Waiting for runtime")}
          />
          <InfoCard
            label={isKo ? "상태 디렉터리" : "State Dir"}
            value={runtime?.state_dir ?? (isKo ? "런타임 대기 중" : "Waiting for runtime")}
          />
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
  ctaLabel,
  onClick,
}: {
  title: string;
  body: string;
  ctaLabel: string;
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
      <span>{ctaLabel}</span>
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
