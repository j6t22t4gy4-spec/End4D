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
        title={isKo ? "End4D 개요" : "About End4D"}
        subtitle={
          isKo
            ? "사회 동역학 시뮬레이션을 읽는 데 필요한 핵심 맥락"
            : "Core context for reading a social dynamics simulation"
        }
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-slate-600">
            {isKo
              ? "End4D는 정책, 시장, 지역, 집단 신념 변화를 한 세계 안에서 장기적으로 관찰하는 사회 동역학 워크벤치입니다. 하나의 world를 생성한 뒤 실행 중에는 필드와 집단 신호를 보고, 끝난 뒤에는 LLM 기반 리뷰로 원인과 정책 함의를 읽는 흐름으로 설계되어 있습니다."
              : "End4D is a social dynamics workbench for observing long-horizon changes in policy, markets, regions, and collective belief inside a single world. The intended flow is to generate a world, watch field and group signals during execution, and then read the causal and policy implications through an LLM-backed review."}
          </p>

          <div className="grid gap-3 lg:grid-cols-2">
            <GuideCard
              title={isKo ? "시뮬레이션 맵 읽는 법" : "How to Read the Simulation Map"}
              body={
                isKo
                  ? "각 점은 하나의 에이전트입니다. x/y 위치는 사회적 근접성과 상호작용권을 뜻하고, z는 물리 높이가 아니라 사회적 고도입니다. 가까운 에이전트일수록 서로의 thought, action, pressure를 더 직접적으로 주고받습니다."
                  : "Each point is an agent. The x/y position represents social proximity and interaction reach, while z is social elevation rather than physical height. Agents that sit closer influence one another's thoughts, actions, and pressure more directly."
              }
            />
            <GuideCard
              title={isKo ? "Zone이 의미하는 것" : "What a Zone Means"}
              body={
                isKo
                  ? "zone은 단순 배경이 아니라 지역적 제도, 마찰, 이동성, 노출 환경을 묶은 사회적 구획입니다. 같은 zone 안에서는 비슷한 압력과 규칙을 더 많이 공유하고, zone 간 이동은 집단 드리프트나 균열 신호로 해석할 수 있습니다."
                  : "A zone is not just a backdrop. It is a social partition that bundles local institutions, friction, mobility, and exposure conditions. Agents inside the same zone share more of the same pressure and rules, while movement across zones can signal drift or fracture."
              }
            />
            <GuideCard
              title={isKo ? "리뷰가 하는 일" : "What the Review Layer Does"}
              body={
                isKo
                  ? "리뷰는 실행 결과를 다시 요약하는 텍스트가 아니라, 주요 사건, 집단 균열, 정책 메커니즘, 주입 프리셋까지 읽어내는 분석 계층입니다. 이미 계산된 world는 저장된 리뷰를 우선 재사용해 불필요한 LLM 재호출을 줄입니다."
                  : "Review is not just a textual recap. It is an analysis layer that reads key events, group fracture, policy mechanisms, and suggested injections. Completed worlds now reuse stored review output first to avoid unnecessary LLM reruns."
              }
            />
            <GuideCard
              title={isKo ? "이 앱의 특징" : "What Makes This App Different"}
              body={
                isKo
                  ? "개인 thought continuity, observer focus, persona priors, collective dynamics를 같은 세계 안에서 함께 추적합니다. 즉 '누가 무슨 생각을 했는가'뿐 아니라 '어느 집단이 왜 갈라지는가'까지 한 흐름으로 읽을 수 있습니다."
                  : "It tracks individual thought continuity, observer focus, persona priors, and collective dynamics inside the same world. That means you can read not only who thought what, but also which groups are diverging and why."
              }
            />
          </div>
        </div>

        <div className="grid gap-3">
          <MetricCard
            label={isKo ? "런타임 프로필" : "Runtime Profile"}
            value={runtime?.runtime_profile ?? (isKo ? "부팅 중" : "Booting")}
          />
          <MetricCard
            label={isKo ? "설치된 팩" : "Installed Packs"}
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <MetricCard
            label={isKo ? "활성 지역" : "Active Regions"}
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(" · ").toUpperCase()
                : isKo
                  ? "지역 없음"
                  : "No regions"
            }
          />
          <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
            <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">
              {isKo ? "추천 흐름" : "Suggested Flow"}
            </p>
            <ol className="mt-2 space-y-2 text-sm leading-6 text-slate-700">
              <li>1. {isKo ? "시뮬레이션에서 world 생성" : "Generate a world in Simulation"}</li>
              <li>2. {isKo ? "Run 단계에서 필드와 집단 신호 관찰" : "Observe field and group signals in Run"}</li>
              <li>3. {isKo ? "Review 단계에서 원인과 정책 함의 해석" : "Interpret causality and policy implications in Review"}</li>
              <li>4. {isKo ? "데이터 관리에서 pack/world/session 정리" : "Manage packs, worlds, and sessions in Data Management"}</li>
            </ol>
          </div>
        </div>
      </AppPanel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel
          title={isKo ? "실시간 관찰 포인트" : "Live Observation Cues"}
          subtitle={
            isKo
              ? "실행 중에 무엇을 우선 보면 좋은지"
              : "What to watch first during a run"
          }
          bodyClassName="grid gap-3"
        >
          <InfoCard
            label={isKo ? "Observer Focus" : "Observer Focus"}
            value={
              isKo
                ? "thought / mover / zone / field 표시는 지금 관찰 가치가 높은 에이전트를 뜻합니다."
                : "thought / mover / zone / field marks the agents currently most worth observing."
            }
          />
          <InfoCard
            label={isKo ? "Continuity" : "Continuity"}
            value={
              isKo
                ? "stable / evolving / volatile은 이전 thought와 현재 thought의 의미적 연속성을 보여줍니다."
                : "stable / evolving / volatile shows the semantic continuity between previous and current thought."
            }
          />
          <InfoCard
            label={isKo ? "Collective Dynamics" : "Collective Dynamics"}
            value={
              isKo
                ? "fracture, cohesion, drift는 role/zone 집단이 지금 얼마나 결집하거나 흔들리는지 읽는 지표입니다."
                : "fracture, cohesion, and drift indicate how strongly role and zone groups are consolidating or destabilizing."
            }
          />
        </AppPanel>

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
          {runtimeError ? (
            <div className="rounded-[22px] border border-rose-200 bg-rose-50 px-4 py-4 text-sm text-rose-700 md:col-span-2">
              {runtimeError}
            </div>
          ) : null}
        </AppPanel>
      </div>

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
          {isKo ? "데이터 관리 열기" : "Open Data Management"}
        </button>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-lg font-semibold tracking-tight text-slate-900">{value}</p>
    </div>
  );
}

function GuideCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-sm font-semibold text-slate-900">{title}</p>
      <p className="mt-2 text-sm leading-7 text-slate-600">{body}</p>
    </div>
  );
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 break-words text-sm leading-6 text-slate-800">{value}</p>
    </div>
  );
}
