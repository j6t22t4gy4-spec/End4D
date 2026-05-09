"use client";

import { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import {
  getApiBase,
  getLocalRuntimeStatus,
  type LocalRuntimeStatus,
} from "@/lib/api";
import { AppToolbar } from "@/components/app-shell/AppToolbar";
import { RuntimeDock } from "@/components/app-shell/RuntimeDock";

const GodView = dynamic(() => import("@/components/GodView"), {
  ssr: false,
  loading: () => <p className="text-slate-500">Simulation workspace loading…</p>,
});

export default function HomeWithCanvas() {
  const [runtime, setRuntime] = useState<LocalRuntimeStatus | null>(null);
  const [runtimeError, setRuntimeError] = useState<string | null>(null);

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
        />

        <div className="app-shell__workspace">
          <aside className="hidden min-h-0 xl:block">
            <RuntimeDock
              runtime={runtime}
              runtimeError={runtimeError}
              apiBase={getApiBase()}
            />
          </aside>

          <section className="min-h-0">
            <GodView />
          </section>
        </div>
      </div>
    </main>
  );
}
