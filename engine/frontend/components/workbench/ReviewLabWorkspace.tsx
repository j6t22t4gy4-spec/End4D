"use client";

import { useEffect, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import { getReviewSummary, type ReviewSummaryResponse } from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";

type ReviewLabWorkspaceProps = {
  worldId: string | null;
  onOpenView: (view: WorkbenchView) => void;
};

export function ReviewLabWorkspace({
  worldId,
  onOpenView,
}: ReviewLabWorkspaceProps) {
  const [data, setData] = useState<ReviewSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!worldId) {
      setData(null);
      setError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    getReviewSummary(worldId)
      .then((payload) => {
        if (!cancelled) {
          setData(payload);
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setError(reason.message);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [worldId]);

  if (!worldId) {
    return (
      <div className="workspace-grid">
        <AppPanel
          title="Review Lab"
          subtitle="LLM-assisted post-simulation analysis"
          bodyClassName="grid gap-4 lg:grid-cols-[minmax(0,1fr)_280px]"
        >
          <div className="space-y-4">
            <p className="text-sm leading-7 text-slate-600">
              아직 분석할 world가 선택되지 않았습니다. 먼저 Simulation에서 world를 실행한
              뒤, 여기서 자동 요약과 타임라인 어노테이션을 확인할 수 있습니다.
            </p>
            <button
              type="button"
              className="app-button app-button--primary"
              onClick={() => onOpenView("simulation")}
            >
              Open Simulation
            </button>
          </div>
          <div className="grid gap-3">
            <StageCard index="01" label="Run a world" />
            <StageCard index="02" label="Persist snapshots" />
            <StageCard index="03" label="Review summary + annotations" />
          </div>
        </AppPanel>
      </div>
    );
  }

  return (
    <div className="workspace-grid">
      <AppPanel
        title="Review Summary"
        subtitle={`World ${worldId}`}
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,360px)]"
      >
        <div className="space-y-4">
          {loading ? <p className="text-sm text-slate-500">Review summary loading…</p> : null}
          {error ? (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              리뷰 요약을 불러오지 못했습니다: {error}
            </p>
          ) : null}
          {data ? (
            <>
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  Headline
                </p>
                <p className="text-base font-semibold text-slate-900">{data.headline}</p>
              </div>
              <p className="text-sm leading-7 text-slate-700">{data.summary}</p>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard label="Outcome" value={String(data.outcome)} />
                <MetricCard label="Signal" value={String(data.overall_signal)} />
                <MetricCard label="Summary Mode" value={String(data.summary_mode)} />
                <MetricCard label="Annotation Mode" value={String(data.annotation_mode)} />
              </div>
            </>
          ) : null}
        </div>
        <div className="grid gap-3">
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenView("simulation")}
          >
            Back to Simulation
          </button>
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={() => onOpenView("snapshots")}
          >
            Open Snapshots
          </button>
        </div>
      </AppPanel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel title="Highlights" subtitle="Auto-generated key points" bodyClassName="space-y-3">
          {data?.watch_items?.length ? (
            data.watch_items.map((item, index) => (
              <div key={`${index}-${item}`} className="session-thread-card">
                <p className="inspector-body">{item}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">하이라이트가 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel title="Timeline Annotations" subtitle="Key turning points" bodyClassName="space-y-3">
          {data?.timeline_annotations?.length ? (
            data.timeline_annotations.map((item) => (
              <div key={`${item.t}-${item.label}`} className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">
                    t={item.t} · {item.label}
                  </p>
                  <span className="session-thread-card__meta">{item.severity}</span>
                </div>
                <p className="session-thread-card__prompt">{item.reason}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">주요 시점 어노테이션이 아직 없습니다.</p>
          )}
        </AppPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel title="Key Events" subtitle="Major events flagged by review" bodyClassName="space-y-3">
          {data?.key_events?.length ? (
            data.key_events.map((item, index) => (
              <div key={`${index}-${item}`} className="session-thread-card">
                <p className="inspector-body">{item}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">주요 사건이 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel title="Causal Analysis" subtitle="Why the drift mattered" bodyClassName="space-y-3">
          {data?.causal_analysis?.length ? (
            data.causal_analysis.map((item, index) => (
              <div key={`${index}-${item}`} className="session-thread-card">
                <p className="inspector-body">{item}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">원인 분석이 아직 없습니다.</p>
          )}
        </AppPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel title="Decision Implications" subtitle="What to watch next" bodyClassName="space-y-3">
          {data?.decision_implications?.length ? (
            data.decision_implications.map((item, index) => (
              <div key={`${index}-${item}`} className="session-thread-card">
                <p className="inspector-body">{item}</p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">의사결정 시사점이 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel title="Review Provenance" subtitle="Prompt and model trace" bodyClassName="space-y-3">
          {data ? (
            <div className="grid gap-3">
              <MetricCard
                label="Summary Prompt"
                value={String((data.review_meta.summary as Record<string, unknown>)?.prompt_version ?? "n/a")}
              />
              <MetricCard
                label="Summary Model"
                value={String((data.review_meta.summary as Record<string, unknown>)?.model ?? "n/a")}
              />
              <MetricCard
                label="Annotation Prompt"
                value={String((data.review_meta.timeline_annotation as Record<string, unknown>)?.prompt_version ?? "n/a")}
              />
              <MetricCard
                label="Annotation Model"
                value={String((data.review_meta.timeline_annotation as Record<string, unknown>)?.model ?? "n/a")}
              />
            </div>
          ) : null}
        </AppPanel>
      </div>
    </div>
  );
}

function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[16px] border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
      <p className="mt-2 text-sm font-semibold text-slate-900">{value}</p>
    </div>
  );
}

function StageCard({ index, label }: { index: string; label: string }) {
  return (
    <div className="rounded-[16px] border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] uppercase tracking-[0.18em] text-slate-500">{index}</p>
      <p className="mt-2 text-sm font-medium text-slate-900">{label}</p>
    </div>
  );
}
