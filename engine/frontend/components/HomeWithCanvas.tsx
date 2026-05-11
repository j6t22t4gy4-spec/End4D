"use client";

import { useEffect, useMemo, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";
import {
  deleteSession,
  getApiBase,
  getLocalRuntimeStatus,
  listSessions,
  renameSession,
  syncDataPacks,
  type LocalRuntimeStatus,
  type SessionSummary,
} from "@/lib/api";
import { AppToolbar } from "@/components/app-shell/AppToolbar";
import { RuntimeDock } from "@/components/app-shell/RuntimeDock";
import {
  type WorkbenchView,
} from "@/components/app-shell/workbench-types";
import { OverviewWorkspace } from "@/components/workbench/OverviewWorkspace";
import { DataPacksWorkspace } from "@/components/workbench/DataPacksWorkspace";
import { ReviewLabWorkspace } from "@/components/workbench/ReviewLabWorkspace";
import { FocusedWorkspace } from "@/components/workbench/FocusedWorkspace";
import { type UiLocale } from "@/lib/ui-language";

const GodView = dynamic(() => import("@/components/GodView"), {
  ssr: false,
  loading: () => <p className="text-slate-500">Simulation workspace loading…</p>,
});

export default function HomeWithCanvas() {
  const [locale, setLocale] = useState<UiLocale>("ko");
  const [runtime, setRuntime] = useState<LocalRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<WorkbenchView>("overview");
  const [selectedWorldId, setSelectedWorldId] = useState<string | null>(null);
  const [selectedSnapshotT, setSelectedSnapshotT] = useState<number | null>(null);
  const [dataPackSyncing, setDataPackSyncing] = useState(false);
  const [dataPackSyncError, setDataPackSyncError] = useState<string | null>(null);
  const [dockWidth, setDockWidth] = useState(380);
  const [resizingDock, setResizingDock] = useState(false);

  const isKo = locale === "ko";

  const refreshSessions = () =>
    listSessions()
      .then((items) => {
        setSessions(items);
        setSessionsError(null);
      })
      .catch((error: Error) => {
        setSessionsError(error.message);
      });

  const refreshRuntime = () =>
    getLocalRuntimeStatus()
      .then((status) => {
        setRuntime(status);
        setRuntimeError(null);
      })
      .catch((error: Error) => {
        setRuntimeError(error.message);
      });

  useEffect(() => {
    const saved = typeof window !== "undefined" ? window.localStorage.getItem("end4d-ui-locale") : null;
    if (saved === "ko" || saved === "en") {
      setLocale(saved);
    }
  }, []);

  useEffect(() => {
    if (typeof window !== "undefined") {
      window.localStorage.setItem("end4d-ui-locale", locale);
    }
  }, [locale]);

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

  useEffect(() => {
    let cancelled = false;
    listSessions()
      .then((items) => {
        if (!cancelled) {
          setSessions(items);
          setSessionsError(null);
        }
      })
      .catch((error: Error) => {
        if (!cancelled) {
          setSessionsError(error.message);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const countriesLabel = useMemo(() => {
    if (!runtime || runtime.available_countries.length === 0) {
      return isKo ? "지역 없음" : "No regions";
    }
    return runtime.available_countries.join(" · ").toUpperCase();
  }, [isKo, runtime]);

  useEffect(() => {
    if (!resizingDock) return;
    const handleMove = (event: MouseEvent) => {
      const nextWidth = window.innerWidth - event.clientX - 28;
      setDockWidth(Math.max(320, Math.min(520, nextWidth)));
    };
    const handleUp = () => setResizingDock(false);
    window.addEventListener("mousemove", handleMove);
    window.addEventListener("mouseup", handleUp);
    return () => {
      window.removeEventListener("mousemove", handleMove);
      window.removeEventListener("mouseup", handleUp);
    };
  }, [resizingDock]);

  const workspaceStyle = useMemo(
    () =>
      ({
        "--dock-width": `${dockWidth}px`,
      }) as CSSProperties,
    [dockWidth]
  );

  return (
    <main className="app-shell">
      <div className="app-shell__frame">
        <AppToolbar
          locale={locale}
          onChangeLocale={setLocale}
          runtimeProfile={runtime?.runtime_profile ?? "Booting"}
          installedPackCount={runtime?.installed_pack_count ?? 0}
          countriesLabel={countriesLabel}
          activeView={activeView}
          onChangeView={setActiveView}
        />

        <div className="app-shell__workspace" style={workspaceStyle}>
          <section className="min-h-0 overflow-y-auto pr-1">
            {activeView === "overview" ? (
              <OverviewWorkspace
                locale={locale}
                runtime={runtime}
                runtimeError={runtimeError}
                sessions={sessions}
                sessionsError={sessionsError}
                apiBase={getApiBase()}
                onOpenView={setActiveView}
                onOpenWorld={(worldId) => {
                  setSelectedWorldId(worldId);
                  setSelectedSnapshotT(null);
                  setActiveView("simulation");
                }}
                onRenameSession={(sessionId, title) =>
                  renameSession(sessionId, title).then(() => refreshSessions())
                }
                onDeleteSession={(sessionId) =>
                  deleteSession(sessionId).then(() => refreshSessions())
                }
              />
            ) : null}

            {activeView === "simulation" ? (
              <GodView
                key={`${selectedWorldId ?? "none"}:${selectedSnapshotT ?? "latest"}`}
                locale={locale}
                initialWorldId={selectedWorldId}
                initialT={selectedSnapshotT}
                onOpenWorkbenchView={setActiveView}
                onWorldSelected={(worldId) => {
                  setSelectedWorldId(worldId);
                  setSelectedSnapshotT(null);
                }}
              />
            ) : null}

            {activeView === "review-lab" ? (
              <ReviewLabWorkspace
                locale={locale}
                worldId={selectedWorldId ?? sessions[0]?.latest_world_id ?? null}
                sessions={sessions}
                onOpenView={setActiveView}
                onOpenWorldAt={(worldId, t) => {
                  setSelectedWorldId(worldId);
                  setSelectedSnapshotT(typeof t === "number" ? t : null);
                  setActiveView("simulation");
                }}
              />
            ) : null}

            {activeView === "data-packs" ? (
              <DataPacksWorkspace
                locale={locale}
                runtime={runtime}
                syncing={dataPackSyncing}
                syncError={dataPackSyncError}
                onSync={() => {
                  setDataPackSyncing(true);
                  setDataPackSyncError(null);
                  syncDataPacks()
                    .then(() => refreshRuntime())
                    .catch((error: Error) => setDataPackSyncError(error.message))
                    .finally(() => setDataPackSyncing(false));
                }}
              />
            ) : null}

            {activeView === "snapshots" ? (
              <FocusedWorkspace
                locale={locale}
                title={isKo ? "스냅샷" : "Snapshots"}
                subtitle={isKo ? "복원 지점과 what-if 브랜치" : "Restore points and what-if branches"}
                body={
                  isKo
                    ? "스냅샷과 복원은 엔진의 핵심 비교 워크플로우입니다. 현재는 시뮬레이션에서 세계를 먼저 만든 뒤, 저장된 t 프레임과 복원 흐름을 이 영역으로 확장해갈 수 있게 구조를 분리해 두었습니다."
                    : "Snapshots and restores are core comparison workflows. This space is separated so saved t frames and restore flows can grow beyond the simulation screen."
                }
                ctaLabel={isKo ? "시뮬레이션으로 이동" : "Go to Simulation"}
                onOpenView={setActiveView}
                targetView="simulation"
              />
            ) : null}

            {activeView === "policy-lab" ? (
              <FocusedWorkspace
                locale={locale}
                title={isKo ? "정책 실험실" : "Policy Lab"}
                subtitle={isKo ? "개입 설계와 시나리오 브랜칭" : "Intervention design and scenario branching"}
                body={
                  isKo
                    ? "정책 실험실은 이벤트 주입과 장기 신념 변화를 비교하는 공간입니다. 지금은 시뮬레이션 워크스페이스에서 실제 주입을 수행하고, 이후 이 섹션을 독립적인 실험 패널로 확장하기 좋은 형태로 나눠 두었습니다."
                    : "Policy Lab is where interventions and long-run belief change are compared. It is separated now so live injections can later grow into a dedicated experiment panel."
                }
                ctaLabel={isKo ? "시뮬레이션 제어 열기" : "Open Simulation Controls"}
                onOpenView={setActiveView}
                targetView="simulation"
              />
            ) : null}
          </section>

          <div
            className="app-shell__splitter hidden xl:block"
            role="separator"
            aria-orientation="vertical"
            aria-label={isKo ? "런타임 도크 너비 조절" : "Resize runtime dock"}
            onMouseDown={() => setResizingDock(true)}
          />

          <aside className="hidden min-h-0 overflow-y-auto xl:block">
            <RuntimeDock
              locale={locale}
              runtime={runtime}
              runtimeError={runtimeError}
              apiBase={getApiBase()}
            />
          </aside>
        </div>
      </div>
    </main>
  );
}
