"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  getApiBase,
  getLocalRuntimeStatus,
  listSessions,
  type LocalRuntimeStatus,
  type SessionSummary,
} from "@/lib/api";
import { ActivityRail } from "@/components/app-shell/ActivityRail";
import { AppToolbar } from "@/components/app-shell/AppToolbar";
import { RuntimeDock } from "@/components/app-shell/RuntimeDock";
import {
  type WorkbenchView,
} from "@/components/app-shell/workbench-types";
import { OverviewWorkspace } from "@/components/workbench/OverviewWorkspace";
import { DataPacksWorkspace } from "@/components/workbench/DataPacksWorkspace";
import { FocusedWorkspace } from "@/components/workbench/FocusedWorkspace";

const GodView = dynamic(() => import("@/components/GodView"), {
  ssr: false,
  loading: () => <p className="text-slate-500">Simulation workspace loading…</p>,
});

export default function HomeWithCanvas() {
  const [runtime, setRuntime] = useState<LocalRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [sessionsError, setSessionsError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<WorkbenchView>("overview");

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
      return "No regions";
    }
    return runtime.available_countries.join(" · ").toUpperCase();
  }, [runtime]);

  return (
    <main className="app-shell">
      <div className="app-shell__frame">
        <AppToolbar
          runtimeProfile={runtime?.runtime_profile ?? "Booting"}
          installedPackCount={runtime?.installed_pack_count ?? 0}
          countriesLabel={countriesLabel}
          activeView={activeView}
          onChangeView={setActiveView}
        />

        <div className="app-shell__workspace">
          <aside className="hidden min-h-0 xl:block">
            <ActivityRail activeView={activeView} onChange={setActiveView} />
          </aside>

          <section className="min-h-0">
            {activeView === "overview" ? (
              <OverviewWorkspace
                runtime={runtime}
                runtimeError={runtimeError}
                sessions={sessions}
                sessionsError={sessionsError}
                apiBase={getApiBase()}
                onOpenView={setActiveView}
              />
            ) : null}

            {activeView === "simulation" ? (
              <GodView />
            ) : null}

            {activeView === "data-packs" ? (
              <DataPacksWorkspace runtime={runtime} />
            ) : null}

            {activeView === "snapshots" ? (
              <FocusedWorkspace
                title="Snapshots"
                subtitle="Restore points and what-if branches"
                body="스냅샷과 복원은 엔진의 핵심 비교 워크플로우입니다. 현재는 시뮬레이션에서 세계를 먼저 만든 뒤, 저장된 t 프레임과 복원 흐름을 이 영역으로 확장해갈 수 있게 구조를 분리해 두었습니다."
                ctaLabel="Go to Simulation"
                onOpenView={setActiveView}
                targetView="simulation"
              />
            ) : null}

            {activeView === "policy-lab" ? (
              <FocusedWorkspace
                title="Policy Lab"
                subtitle="Intervention design and scenario branching"
                body="정책 실험실은 이벤트 주입과 장기 신념 변화를 비교하는 공간입니다. 지금은 시뮬레이션 워크스페이스에서 실제 주입을 수행하고, 이후 이 섹션을 독립적인 실험 패널로 확장하기 좋은 형태로 나눠 두었습니다."
                ctaLabel="Open Simulation Controls"
                onOpenView={setActiveView}
                targetView="simulation"
              />
            ) : null}
          </section>

          <aside className="hidden min-h-0 2xl:block">
            <RuntimeDock
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
