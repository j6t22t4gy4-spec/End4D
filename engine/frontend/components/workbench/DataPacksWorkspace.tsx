"use client";

import { useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { LocalRuntimeStatus, SessionSummary } from "@/lib/api";
import type { UiLocale } from "@/lib/ui-language";

type DataPacksWorkspaceProps = {
  locale?: UiLocale;
  runtime: LocalRuntimeStatus | null;
  sessions: SessionSummary[];
  syncing: boolean;
  syncError: string | null;
  onSync: () => void;
  onOpenWorld: (worldId: string) => void;
  onDeleteWorld: (worldId: string) => Promise<unknown>;
  onRenameSession: (sessionId: string, title: string) => Promise<unknown>;
  onDeleteSession: (sessionId: string) => Promise<unknown>;
};

export function DataPacksWorkspace({
  locale = "ko",
  runtime,
  sessions,
  syncing,
  syncError,
  onSync,
  onOpenWorld,
  onDeleteWorld,
  onRenameSession,
  onDeleteSession,
}: DataPacksWorkspaceProps) {
  const isKo = locale === "ko";
  const [pendingWorldId, setPendingWorldId] = useState<string | null>(null);
  const [worldActionError, setWorldActionError] = useState<string | null>(null);
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [sessionActionError, setSessionActionError] = useState<string | null>(null);

  const removeWorld = async (worldId: string) => {
    if (typeof window !== "undefined") {
      const allowed = window.confirm(
        isKo
          ? "이 월드를 완전히 삭제할까요? 연결된 스냅샷과 리뷰도 함께 제거됩니다."
          : "Delete this world completely? Its snapshots and reviews will be removed too."
      );
      if (!allowed) return;
    }
    setPendingWorldId(worldId);
    setWorldActionError(null);
    try {
      await onDeleteWorld(worldId);
    } catch (error) {
      setWorldActionError(error instanceof Error ? error.message : "Delete failed");
    } finally {
      setPendingWorldId(null);
    }
  };

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
        isKo
          ? "이 세션 스레드를 목록에서 삭제할까요? 연결된 world 데이터는 그대로 남습니다."
          : "Delete this session thread from the list? Linked world data will remain."
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
        title={isKo ? "데이터 관리" : "Data Management"}
        subtitle={isKo ? "데이터팩, 월드, 세션 스레드를 한 곳에서 관리합니다" : "Manage data packs, worlds, and session threads in one place"}
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]"
      >
        <div className="xl:col-span-2 flex items-center justify-between gap-3 rounded-[18px] border border-slate-200 bg-slate-50 px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-900">{isKo ? "매니페스트 동기화" : "Manifest Sync"}</p>
            <p className="mt-1 truncate text-xs text-slate-500">
              {runtime?.remote_manifest_url || (isKo ? "로컬 런타임 환경에서 설정됨" : "Configured from local runtime environment")}
            </p>
          </div>
          <button
            type="button"
            onClick={onSync}
            disabled={syncing}
            className="shrink-0 rounded-[8px] border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-900 shadow-sm transition hover:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {syncing ? (isKo ? "동기화 중" : "Syncing") : isKo ? "동기화" : "Sync"}
          </button>
        </div>
        {syncError ? (
          <p className="xl:col-span-2 rounded-[12px] border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {syncError}
          </p>
        ) : null}

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
                  <PackField label={isKo ? "라이선스" : "License"} value={pack.license || (isKo ? "대기 중" : "Pending")} />
                  <PackField
                    label={isKo ? "소스" : "Source"}
                    value={pack.source_url || (isKo ? "원격 매니페스트 소스를 아직 사용할 수 없습니다" : "Remote manifest source unavailable")}
                  />
                </div>
              </article>
            ))
          ) : (
            <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              {isKo ? "설치된 데이터 팩이 아직 없습니다." : "No installed data packs yet."}
            </div>
          )}
        </div>

        <div className="grid gap-3 content-start">
          <SummaryBox
            label={isKo ? "설치된 팩" : "Installed Packs"}
            value={String(runtime?.installed_pack_count ?? 0)}
          />
          <SummaryBox
            label={isKo ? "지역" : "Regions"}
            value={
              runtime?.available_countries.length
                ? runtime.available_countries.join(", ").toUpperCase()
                : isKo ? "지역 없음" : "No regions"
            }
          />
          <SummaryBox
            label={isKo ? "매니페스트 경로" : "Manifest Path"}
            value={runtime?.manifest_path ?? (isKo ? "런타임 대기 중" : "Waiting for runtime")}
          />
        </div>
      </AppPanel>

      <div className="grid gap-4">
        <AppPanel
          title={isKo ? "월드 관리" : "World Management"}
          subtitle={
            isKo
              ? "세션별로 저장된 world를 열고 삭제합니다"
              : "Open or delete stored worlds grouped by session"
          }
          bodyClassName="space-y-3"
        >
          {worldActionError ? (
            <p className="rounded-[12px] border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {worldActionError}
            </p>
          ) : null}
          {sessions.length === 0 ? (
            <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              {isKo ? "저장된 세션과 world가 아직 없습니다." : "No saved sessions or worlds yet."}
            </div>
          ) : (
            <div className="grid gap-3">
              {sessions.map((session) => (
                <section
                  key={session.session_id}
                  className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-slate-900">{session.title}</p>
                      <p className="mt-1 text-xs text-slate-500">
                        {isKo ? "월드" : "Worlds"} {session.world_count} · {session.session_id.slice(0, 8)}
                      </p>
                    </div>
                    <span className="rounded-full bg-slate-100 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-700">
                      {session.latest_world_id ? session.latest_world_id.slice(0, 8) : (isKo ? "비어 있음" : "Empty")}
                    </span>
                  </div>
                  <div className="mt-4 grid gap-2">
                    {session.worlds.length ? (
                      session.worlds.map((world) => (
                        <article
                          key={world.world_id}
                          className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-slate-200 bg-slate-50 px-3 py-3"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-sm font-semibold text-slate-900">
                              {world.genesis_prompt?.trim() || `${isKo ? "월드" : "World"} ${world.world_id.slice(0, 8)}`}
                            </p>
                            <p className="mt-1 text-xs text-slate-500">
                              {world.world_id.slice(0, 8)} · {(world.persona_country || (isKo ? "국가 없음" : "No country")).toUpperCase()} · {world.status}
                            </p>
                          </div>
                          <div className="flex items-center gap-2">
                            <button
                              type="button"
                              className="app-button app-button--secondary"
                              onClick={() => onOpenWorld(world.world_id)}
                            >
                              {isKo ? "열기" : "Open"}
                            </button>
                            <button
                              type="button"
                              className="app-button app-button--ghost"
                              disabled={pendingWorldId === world.world_id}
                              onClick={() => void removeWorld(world.world_id)}
                            >
                              {pendingWorldId === world.world_id
                                ? (isKo ? "삭제 중" : "Deleting")
                                : (isKo ? "삭제" : "Delete")}
                            </button>
                          </div>
                        </article>
                      ))
                    ) : (
                      <div className="rounded-[16px] border border-dashed border-slate-300 bg-slate-50 px-4 py-4 text-sm text-slate-500">
                        {isKo ? "이 세션에는 아직 저장된 world가 없습니다." : "No saved worlds in this session yet."}
                      </div>
                    )}
                  </div>
                </section>
              ))}
            </div>
          )}
        </AppPanel>

        <AppPanel
          title={isKo ? "세션 스레드 관리" : "Session Thread Management"}
          subtitle={isKo ? "세션 이름 변경과 목록 정리를 여기서 수행합니다" : "Rename or prune saved session threads here"}
          bodyClassName="space-y-3"
        >
          {sessionActionError ? (
            <p className="rounded-2xl border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              {sessionActionError}
            </p>
          ) : null}
          {sessions.length === 0 ? (
            <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-5 py-6 text-sm text-slate-500">
              {isKo ? "저장된 실행 세션이 아직 없습니다." : "No saved session threads yet."}
            </div>
          ) : (
            <div className="session-thread-list">
              {sessions.map((session) => (
                <div key={session.session_id} className="session-thread-card">
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
                    <p className="session-thread-card__prompt">{session.worlds[0].genesis_prompt}</p>
                  ) : null}
                </div>
              ))}
            </div>
          )}
        </AppPanel>
      </div>
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
