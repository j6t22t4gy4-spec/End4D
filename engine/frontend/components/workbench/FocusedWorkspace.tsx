"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";
import type { UiLocale } from "@/lib/ui-language";

type FocusedWorkspaceProps = {
  locale?: UiLocale;
  title: string;
  subtitle: string;
  body: string;
  ctaLabel: string;
  onOpenView: (view: WorkbenchView) => void;
  targetView: WorkbenchView;
};

export function FocusedWorkspace({
  locale = "ko",
  title,
  subtitle,
  body,
  ctaLabel,
  onOpenView,
  targetView,
}: FocusedWorkspaceProps) {
  const isKo = locale === "ko";
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
          <StageItem index="01" label={isKo ? "월드를 생성하거나 실행합니다" : "Create or run a world"} />
          <StageItem index="02" label={isKo ? "스냅샷과 메모리를 저장합니다" : "Persist snapshots and memory"} />
          <StageItem index="03" label={isKo ? "비교 워크플로우를 위해 다시 돌아옵니다" : "Return here for comparison workflows"} />
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
