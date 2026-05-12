"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";
import dynamic from "next/dynamic";
import {
  deleteSession,
  getApiBase,
  getLocalRuntimeStatus,
  listSessions,
  renameSession,
  syncDataPacks,
  type ReviewSummaryResponse,
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
  const [pendingInjectPreset, setPendingInjectPreset] = useState<ReviewSummaryResponse["inject_presets"][number] | null>(null);
  const [dataPackSyncing, setDataPackSyncing] = useState(false);
  const [dataPackSyncError, setDataPackSyncError] = useState<string | null>(null);
  const [dockWidth, setDockWidth] = useState(380);
  const [resizingDock, setResizingDock] = useState(false);

  const isKo = locale === "ko";

  const refreshSessions = useCallback(
    () =>
      listSessions()
        .then((items) => {
          setSessions(items);
          setSessionsError(null);
        })
        .catch((error: Error) => {
          setSessionsError(error.message);
        }),
    []
  );

  const refreshRuntime = useCallback(
    () =>
      getLocalRuntimeStatus()
        .then((status) => {
          setRuntime(status);
          setRuntimeError(null);
        })
        .catch((error: Error) => {
          setRuntimeError(error.message);
        }),
    []
  );

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
    const loadRuntime = () => {
      if (document.visibilityState !== "visible") {
        return;
      }
      void refreshRuntime();
    };
    loadRuntime();
    const timer = window.setInterval(loadRuntime, 20000);
    return () => {
      window.clearInterval(timer);
    };
  }, [refreshRuntime]);

  useEffect(() => {
    refreshSessions();
  }, [refreshSessions]);

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

  const handleOpenWorld = useCallback((worldId: string, snapshotT: number | null = null) => {
    setSelectedWorldId(worldId);
    setSelectedSnapshotT(snapshotT);
    setActiveView("simulation");
  }, []);

  const handleSimulationWorldSelected = useCallback((worldId: string) => {
    setSelectedWorldId((prev) => (prev === worldId ? prev : worldId));
  }, []);

  const handleConsumeInitialInjectPreset = useCallback(() => {
    setPendingInjectPreset(null);
  }, []);

  const handleQueueInjectPreset = useCallback(
    (worldId: string, preset: ReviewSummaryResponse["inject_presets"][number]) => {
      setSelectedWorldId(worldId);
      setSelectedSnapshotT(typeof preset.t === "number" ? Number(preset.t) : null);
      setPendingInjectPreset(preset);
      setActiveView("simulation");
    },
    []
  );

  const handleSyncDataPacks = useCallback(() => {
    setDataPackSyncing(true);
    setDataPackSyncError(null);
    syncDataPacks()
      .then(() => refreshRuntime())
      .catch((error: Error) => setDataPackSyncError(error.message))
      .finally(() => setDataPackSyncing(false));
  }, [refreshRuntime]);

  return (
    <main className="app-shell">
      <div className="app-shell__frame">
        <AppToolbar
          locale={locale}
          onChangeLocale={setLocale}
          runtimeProfile={runtime?.runtime_profile ?? (isKo ? "부팅 중" : "Booting")}
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
                onOpenWorld={(worldId) => handleOpenWorld(worldId, null)}
                onRenameSession={(sessionId, title) => renameSession(sessionId, title).then(() => refreshSessions())}
                onDeleteSession={(sessionId) => deleteSession(sessionId).then(() => refreshSessions())}
              />
            ) : null}

            {activeView === "simulation" ? (
              <GodView
                locale={locale}
                initialWorldId={selectedWorldId}
                initialT={selectedSnapshotT}
                onOpenWorkbenchView={setActiveView}
                onWorldSelected={handleSimulationWorldSelected}
                initialInjectPreset={pendingInjectPreset}
                onConsumeInitialInjectPreset={handleConsumeInitialInjectPreset}
                runtimeStatusExternal={runtime}
                runtimeErrorExternal={runtimeError}
                onRefreshRuntimeExternal={refreshRuntime}
              />
            ) : null}

            {activeView === "review-lab" ? (
              <ReviewLabWorkspace
                locale={locale}
                worldId={selectedWorldId ?? sessions[0]?.latest_world_id ?? null}
                sessions={sessions}
                onOpenView={setActiveView}
                onOpenWorldAt={(worldId, t) => handleOpenWorld(worldId, typeof t === "number" ? t : null)}
                onQueueInjectPreset={handleQueueInjectPreset}
              />
            ) : null}

            {activeView === "data-packs" ? (
              <DataPacksWorkspace
                locale={locale}
                runtime={runtime}
                syncing={dataPackSyncing}
                syncError={dataPackSyncError}
                onSync={handleSyncDataPacks}
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

          <aside className="hidden min-h-0 xl:block xl:self-start xl:sticky xl:top-4 xl:max-h-[calc(100vh-7rem)]">
            <RuntimeDock
              locale={locale}
              runtime={runtime}
              runtimeError={runtimeError}
              apiBase={getApiBase()}
              activeWorldId={selectedWorldId}
            />
          </aside>
        </div>
      </div>
    </main>
  );
}
