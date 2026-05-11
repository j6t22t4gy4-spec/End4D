"use client";

import { useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus, SessionSummary } from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import type { UiLocale } from "@/lib/ui-language";

type OverviewWorkspaceProps = {
  locale?: UiLocale;
  runtime: LocalRuntimeStatus | null;
  runtimeError: string | null;
  sessions: SessionSummary[];
  sessionsError: string | null;
  apiBase: string;
  onOpenView: (view: WorkbenchView) => void;
  onOpenWorld: (worldId: string) => void;
  onRenameSession: (sessionId: string, title: string) => Promise<unknown>;
  onDeleteSession: (sessionId: string) => Promise<unknown>;
};

export function OverviewWorkspace({
  locale = "ko",
  runtime,
  runtimeError,
  sessions,
  sessionsError,
  apiBase,
  onOpenView,
  onOpenWorld,
  onRenameSession,
  onDeleteSession,
}: OverviewWorkspaceProps) {
  const isKo = locale === "ko";
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [sessionActionError, setSessionActionError] = useState<string | null>(null);

  const startRename = (session: SessionSummary) => {
    setEditingSessionId(session.session_id);
    setDraftTitle(session.title);
    setSessionActionError(null);
  };

  const submitRename = async (sessionId: string) => {
    setPendingSessionId(sessionId);
    setSessionActionError(null);
    try {
      await onRenameSession(sessionId, draftTitle);
      setEditingSessionId(null);
    } catch (error) {
      setSessionActionError(error instanceof Error ? error.message : "Rename failed");
    } finally {
      setPendingSessionId(null);
    }
  };

  const removeSession = async (sessionId: string) => {
    if (typeof window !== "undefined") {
      const allowed = window.confirm(
        "이 세션 스레드를 목록에서 삭제할까요? 연결된 world 데이터는 그대로 남습니다."
      );
      if (!allowed) return;
    }
    setPendingSessionId(sessionId);
    setSessionActionError(null);
    try {
      await onDeleteSession(sessionId);
      if (editingSessionId === sessionId) {
        setEditingSessionId(null);
      }
    } catch (error) {
      setSessionActionError(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setPendingSessionId(null);
    }
  };

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
          title={isKo ? "리뷰" : "Review"}
          body={isKo ? "LLM 기반 결과 해석과 비교 채팅 워크스페이스" : "LLM-driven analysis and comparison workspace"}
          ctaLabel={isKo ? "열기" : "Open"}
          onClick={() => onOpenView("review-lab")}
        />
        <ActionCard
          title={isKo ? "데이터 팩" : "Data Packs"}
          body={isKo ? "국가별 페르소나 팩, 캐시, 라이선스 확인" : "Inspect packs, cache, and licenses by country"}
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

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
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

        <AppPanel
          title={isKo ? "세션 스레드" : "Session Threads"}
          subtitle={isKo ? "이 머신에 저장된 실행 이력" : "Persistent run history on this machine"}
          bodyClassName="space-y-3"
        >
          {sessionsError ? (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              세션 목록을 불러오지 못했습니다: {sessionsError}
            </p>
          ) : null}
          {sessionActionError ? (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              세션 작업 중 문제가 생겼습니다: {sessionActionError}
            </p>
          ) : null}
          {sessions.length === 0 ? (
            <p className="text-sm leading-7 text-slate-600">
              아직 저장된 실행 세션이 없습니다. 시뮬레이션에서 세계를 만들면 자동으로
              세션 스레드가 생성됩니다.
            </p>
          ) : (
            <div className="session-thread-list">
              {sessions.map((session) => (
                <div
                  key={session.session_id}
                  className="session-thread-card"
                >
                  <div className="session-thread-card__header">
                    {editingSessionId === session.session_id ? (
                      <input
                        value={draftTitle}
                        onChange={(event) => setDraftTitle(event.target.value)}
                        className="app-input"
                        placeholder={isKo ? "세션 제목" : "Session title"}
                      />
                    ) : (
                      <p className="session-thread-card__title">{session.title}</p>
                    )}
                    <div className="session-thread-card__actions">
                      {editingSessionId === session.session_id ? (
                        <>
                          <button
                            type="button"
                            className="app-button app-button--secondary"
                            disabled={pendingSessionId === session.session_id}
                            onClick={() => submitRename(session.session_id)}
                          >
                            {isKo ? "저장" : "Save"}
                          </button>
                          <button
                            type="button"
                            className="app-button app-button--ghost"
                            disabled={pendingSessionId === session.session_id}
                            onClick={() => {
                              setEditingSessionId(null);
                              setSessionActionError(null);
                            }}
                          >
                            {isKo ? "취소" : "Cancel"}
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            type="button"
                            className="app-button app-button--ghost"
                            disabled={pendingSessionId === session.session_id}
                            onClick={() => startRename(session)}
                          >
                            {isKo ? "이름 변경" : "Rename"}
                          </button>
                          <button
                            type="button"
                            className="app-button app-button--ghost-danger"
                            disabled={pendingSessionId === session.session_id}
                            onClick={() => removeSession(session.session_id)}
                          >
                            {isKo ? "삭제" : "Delete"}
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <p className="session-thread-card__meta">
                    {session.world_count} {isKo ? "월드" : "worlds"} · {isKo ? "최신" : "latest"} {session.latest_world_id || "—"}
                  </p>
                  {session.worlds[0]?.genesis_prompt ? (
                    <p className="session-thread-card__prompt">
                      {session.worlds[0].genesis_prompt}
                    </p>
                  ) : null}
                  <div className="session-thread-card__footer">
                    <span className="session-thread-card__updated">
                      {isKo ? "업데이트" : "updated"} {new Date(session.updated_at).toLocaleString()}
                    </span>
                    {session.latest_world_id ? (
                      <button
                        type="button"
                        className="app-button app-button--secondary"
                        onClick={() => onOpenWorld(session.latest_world_id)}
                      >
                        {isKo ? "최신 월드 열기" : "Open Latest World"}
                      </button>
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          )}
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
