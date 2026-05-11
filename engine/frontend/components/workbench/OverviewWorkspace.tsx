"use client";

import { useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus, SessionSummary } from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";

type OverviewWorkspaceProps = {
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
        bodyClassName="grid gap-3 md:grid-cols-2 xl:grid-cols-5"
      >
        <ActionCard
          title="Simulation"
          body="Setup과 Run을 나눠 세계 생성과 실행을 분리"
          onClick={() => onOpenView("simulation")}
        />
        <ActionCard
          title="Review"
          body="추후 LLM 기반 결과 해석과 비교 채팅 워크스페이스"
          onClick={() => onOpenView("review-lab")}
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
          title="Session Threads"
          subtitle="Persistent run history on this machine"
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
                        placeholder="Session title"
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
                            Save
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
                            Cancel
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
                            Rename
                          </button>
                          <button
                            type="button"
                            className="app-button app-button--ghost-danger"
                            disabled={pendingSessionId === session.session_id}
                            onClick={() => removeSession(session.session_id)}
                          >
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                  <p className="session-thread-card__meta">
                    {session.world_count} worlds · latest {session.latest_world_id || "—"}
                  </p>
                  {session.worlds[0]?.genesis_prompt ? (
                    <p className="session-thread-card__prompt">
                      {session.worlds[0].genesis_prompt}
                    </p>
                  ) : null}
                  <div className="session-thread-card__footer">
                    <span className="session-thread-card__updated">
                      updated {new Date(session.updated_at).toLocaleString()}
                    </span>
                    {session.latest_world_id ? (
                      <button
                        type="button"
                        className="app-button app-button--secondary"
                        onClick={() => onOpenWorld(session.latest_world_id)}
                      >
                        Open Latest World
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
