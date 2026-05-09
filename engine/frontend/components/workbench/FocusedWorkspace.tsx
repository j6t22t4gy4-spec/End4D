"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";

type FocusedWorkspaceProps = {
  title: string;
  subtitle: string;
  body: string;
  ctaLabel: string;
  onOpenView: (view: WorkbenchView) => void;
  targetView: WorkbenchView;
};

export function FocusedWorkspace({
  title,
  subtitle,
  body,
  ctaLabel,
  onOpenView,
  targetView,
}: FocusedWorkspaceProps) {
  return (
    <div className="workspace-grid">
      <AppPanel
        title={title}
        subtitle={subtitle}
        bodyClassName="grid gap-4 lg:grid-cols-[minmax(0,1fr)_320px]"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-slate-600">{body}</p>
          <button
            type="button"
            className="app-button app-button--primary"
            onClick={() => onOpenView(targetView)}
          >
            {ctaLabel}
          </button>
        </div>
        <div className="grid gap-3">
          <StageItem index="01" label="Create or run a world" />
          <StageItem index="02" label="Persist snapshots and memory" />
          <StageItem index="03" label="Return here for comparison workflows" />
        </div>
      </AppPanel>
    </div>
  );
}

function StageItem({ index, label }: { index: string; label: string }) {
  return (
    <div className="rounded-[22px] border border-slate-200 bg-white px-4 py-4 shadow-sm">
      <p className="text-[11px] uppercase tracking-[0.2em] text-slate-500">{index}</p>
      <p className="mt-2 text-sm font-medium text-slate-900">{label}</p>
    </div>
  );
}
