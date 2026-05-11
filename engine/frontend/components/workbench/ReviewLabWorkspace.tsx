"use client";

import { useEffect, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  getReviewDiff,
  getReviewSummary,
  type ReviewDiffResponse,
  type ReviewSummaryResponse,
  type SessionSummary,
} from "@/lib/api";
import type { WorkbenchView } from "@/components/app-shell/workbench-types";

type ReviewLabWorkspaceProps = {
  worldId: string | null;
  sessions: SessionSummary[];
  onOpenView: (view: WorkbenchView) => void;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
};

export function ReviewLabWorkspace({
  worldId,
  sessions,
  onOpenView,
  onOpenWorldAt,
}: ReviewLabWorkspaceProps) {
  const [data, setData] = useState<ReviewSummaryResponse | null>(null);
  const [diff, setDiff] = useState<ReviewDiffResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [diffLoading, setDiffLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [diffError, setDiffError] = useState<string | null>(null);
  const [baseWorldId, setBaseWorldId] = useState<string>("");

  const currentSession = sessions.find((session) =>
    session.worlds.some((item) => item.world_id === worldId)
  );
  const comparisonCandidates = (currentSession?.worlds ?? []).filter(
    (item) => item.world_id !== worldId
  );
  const recommendedBaselineId = currentSession
    ? recommendBaselineWorldId(currentSession, worldId)
    : "";
  const diffMetrics = (diff?.compared_metrics ?? {}) as Record<string, unknown>;
  const groupDriftRows = Array.isArray(diffMetrics.group_drift_deltas)
    ? (diffMetrics.group_drift_deltas as Array<Record<string, unknown>>)
    : [];
  const zoneDriftRows = Array.isArray(diffMetrics.zone_z_delta)
    ? (diffMetrics.zone_z_delta as Array<Record<string, unknown>>)
    : [];
  const turningPoints = (diffMetrics.timeline_turning_point_delta ?? {}) as Record<string, unknown>;
  const baseTurningPoints = Array.isArray(turningPoints.base)
    ? (turningPoints.base as Array<Record<string, unknown>>)
    : [];
  const targetTurningPoints = Array.isArray(turningPoints.target)
    ? (turningPoints.target as Array<Record<string, unknown>>)
    : [];

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

  useEffect(() => {
    if (!worldId) {
      setBaseWorldId("");
      return;
    }
    setBaseWorldId(recommendedBaselineId);
  }, [worldId, recommendedBaselineId]);

  useEffect(() => {
    if (!worldId || !baseWorldId) {
      setDiff(null);
      setDiffError(null);
      return;
    }
    let cancelled = false;
    setDiffLoading(true);
    setDiffError(null);
    getReviewDiff(worldId, baseWorldId)
      .then((payload) => {
        if (!cancelled) {
          setDiff(payload);
        }
      })
      .catch((reason: Error) => {
        if (!cancelled) {
          setDiff(null);
          setDiffError(reason.message);
        }
      })
      .finally(() => {
        if (!cancelled) setDiffLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [baseWorldId, worldId]);

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
          {comparisonCandidates.length > 0 ? (
            <div className="grid gap-2">
              <select
                className="app-input"
                value={baseWorldId}
                onChange={(event) => setBaseWorldId(event.target.value)}
              >
                <option value="">Select baseline world</option>
                {comparisonCandidates.map((item) => (
                  <option key={item.world_id} value={item.world_id}>
                    {item.world_id.slice(0, 8)} · {item.status}
                  </option>
                ))}
              </select>
              {recommendedBaselineId ? (
                <p className="text-xs text-slate-500">
                  Recommended baseline: <span className="font-semibold text-slate-700">{recommendedBaselineId.slice(0, 8)}</span>
                </p>
              ) : null}
            </div>
          ) : null}
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
        <AppPanel title="Diff Report" subtitle="Baseline vs current world" bodyClassName="space-y-3">
          {diffLoading ? <p className="text-sm text-slate-500">Diff report loading…</p> : null}
          {diffError ? (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              비교 리포트를 불러오지 못했습니다: {diffError}
            </p>
          ) : null}
          {diff ? (
            <>
              <div className="session-thread-card">
                <p className="session-thread-card__title">{diff.headline}</p>
                <p className="session-thread-card__prompt">{diff.summary}</p>
                <div className="session-thread-card__actions">
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onOpenWorldAt(diff.target_world_id)}
                  >
                    Open Target
                  </button>
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onOpenWorldAt(diff.base_world_id)}
                  >
                    Open Baseline
                  </button>
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard
                  label="Cell Gap"
                  value={String((diff.compared_metrics.delta as Record<string, unknown>)?.cell_delta_gap ?? "n/a")}
                />
                <MetricCard
                  label="Energy Gap"
                  value={String((diff.compared_metrics.delta as Record<string, unknown>)?.energy_delta_gap ?? "n/a")}
                />
                <MetricCard
                  label="Z Gap"
                  value={String((diff.compared_metrics.delta as Record<string, unknown>)?.z_delta_gap ?? "n/a")}
                />
              </div>
              {diff.key_deltas.map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="inspector-body">{item}</p>
                  {targetTurningPoints[index] ? (
                    <div className="session-thread-card__actions">
                      <button
                        type="button"
                        className="app-button app-button--ghost"
                        onClick={() =>
                          onOpenWorldAt(
                            diff.target_world_id,
                            Number((targetTurningPoints[index] as Record<string, unknown>).t ?? 0)
                          )
                        }
                      >
                        Open Target Shift
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </>
          ) : (
            <p className="text-sm text-slate-500">
              같은 세션 안의 다른 world를 선택하면 diff report가 생성됩니다.
            </p>
          )}
        </AppPanel>

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
                <div className="session-thread-card__actions">
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onOpenWorldAt(worldId, item.t)}
                  >
                    Open at t
                  </button>
                </div>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">주요 시점 어노테이션이 아직 없습니다.</p>
          )}
        </AppPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel title="Group Drift Gaps" subtitle="Role-level differences" bodyClassName="space-y-3">
          {groupDriftRows.length > 0 ? (
            groupDriftRows.slice(0, 5).map((item, index) => (
              <div key={`${index}-${String(item.group_id)}`} className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">{String(item.role_label ?? "group")}</p>
                  <span className="session-thread-card__meta">
                    {String(item.stance_base ?? "n/a")} → {String(item.stance_target ?? "n/a")}
                  </span>
                </div>
                <p className="session-thread-card__prompt">
                  cohesion {Number(item.cohesion_gap ?? 0).toFixed(2)} · tension{" "}
                  {Number(item.tension_gap ?? 0).toFixed(2)} · z {Number(item.z_gap ?? 0).toFixed(2)}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">집단 drift 차이가 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel title="Zone Z Gaps" subtitle="Regional elevation differences" bodyClassName="space-y-3">
          {zoneDriftRows.length > 0 ? (
            zoneDriftRows.slice(0, 5).map((item, index) => (
              <div key={`${index}-${String(item.zone_id)}`} className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">{String(item.zone_label ?? "zone")}</p>
                  <span className="session-thread-card__meta">
                    cells {String(item.cell_count_gap ?? 0)}
                  </span>
                </div>
                <p className="session-thread-card__prompt">
                  avg z {Number(item.avg_z_gap ?? 0).toFixed(2)} · avg energy{" "}
                  {Number(item.avg_energy_gap ?? 0).toFixed(2)}
                </p>
              </div>
            ))
          ) : (
            <p className="text-sm text-slate-500">zone z 차이가 아직 없습니다.</p>
          )}
        </AppPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel
          title="Group Before / After"
          subtitle="Baseline to target role comparison"
          bodyClassName="space-y-3"
        >
          {groupDriftRows.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs text-slate-600">
                <thead>
                  <tr className="border-b border-slate-200 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    <th className="px-2 py-2">Group</th>
                    <th className="px-2 py-2">Stance</th>
                    <th className="px-2 py-2">Cohesion</th>
                    <th className="px-2 py-2">Tension</th>
                    <th className="px-2 py-2">Z</th>
                    <th className="px-2 py-2">Cells</th>
                  </tr>
                </thead>
                <tbody>
                  {groupDriftRows.slice(0, 8).map((item, index) => (
                    <tr key={`${index}-${String(item.group_id)}`} className="border-b border-slate-100">
                      <td className="px-2 py-2 font-medium text-slate-800">{String(item.role_label ?? "group")}</td>
                      <td className="px-2 py-2">
                        {String(item.stance_base ?? "n/a")} → {String(item.stance_target ?? "n/a")}
                      </td>
                      <td className="px-2 py-2">{Number(item.cohesion_gap ?? 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{Number(item.tension_gap ?? 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{Number(item.z_gap ?? 0).toFixed(2)}</td>
                      <td className="px-2 py-2">{String(item.cell_gap ?? 0)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">집단 before/after 표가 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel
          title="Turning Point Delta"
          subtitle="Jump from comparison back into time"
          bodyClassName="space-y-3"
        >
          {targetTurningPoints.length > 0 || baseTurningPoints.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Target</p>
                {targetTurningPoints.slice(0, 4).map((item, index) => (
                  <TurningPointCard
                    key={`target-${index}-${String(item.t)}`}
                    worldId={diff?.target_world_id ?? ""}
                    label={String(item.label ?? "shift")}
                    reason={String(item.reason ?? "")}
                    score={Number(item.score ?? 0)}
                    t={Number(item.t ?? 0)}
                    onOpenWorldAt={onOpenWorldAt}
                  />
                ))}
              </div>
              <div className="space-y-3">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Baseline</p>
                {baseTurningPoints.slice(0, 4).map((item, index) => (
                  <TurningPointCard
                    key={`base-${index}-${String(item.t)}`}
                    worldId={diff?.base_world_id ?? ""}
                    label={String(item.label ?? "shift")}
                    reason={String(item.reason ?? "")}
                    score={Number(item.score ?? 0)}
                    t={Number(item.t ?? 0)}
                    onOpenWorldAt={onOpenWorldAt}
                  />
                ))}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">점프 가능한 turning point가 아직 없습니다.</p>
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
          {diff?.causal_comparison?.length ? (
            <>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Diff Causality
              </p>
              {diff.causal_comparison.map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="inspector-body">{item}</p>
                  {targetTurningPoints[index] ? (
                    <div className="session-thread-card__actions">
                      <button
                        type="button"
                        className="app-button app-button--ghost"
                        onClick={() =>
                          onOpenWorldAt(
                            diff.target_world_id,
                            Number((targetTurningPoints[index] as Record<string, unknown>).t ?? 0)
                          )
                        }
                      >
                        Inspect Target Cause
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
            </>
          ) : null}
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
          {diff?.decision_implications?.length ? (
            <>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                Diff Implications
              </p>
              {diff.decision_implications.map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="inspector-body">{item}</p>
                </div>
              ))}
            </>
          ) : null}
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
              {diff ? (
                <>
                  <MetricCard
                    label="Diff Prompt"
                    value={String((diff.review_meta.diff as Record<string, unknown>)?.prompt_version ?? "n/a")}
                  />
                  <MetricCard
                    label="Diff Model"
                    value={String((diff.review_meta.diff as Record<string, unknown>)?.model ?? "n/a")}
                  />
                </>
              ) : null}
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

function TurningPointCard({
  worldId,
  label,
  reason,
  score,
  t,
  onOpenWorldAt,
}: {
  worldId: string;
  label: string;
  reason: string;
  score: number;
  t: number;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
}) {
  return (
    <div className="session-thread-card">
      <div className="session-thread-card__header">
        <p className="session-thread-card__title">
          t={t} · {label}
        </p>
        <span className="session-thread-card__meta">score {score.toFixed(2)}</span>
      </div>
      <p className="session-thread-card__prompt">{reason}</p>
      <div className="session-thread-card__actions">
        <button
          type="button"
          className="app-button app-button--ghost"
          onClick={() => onOpenWorldAt(worldId, t)}
        >
          Open at t
        </button>
      </div>
    </div>
  );
}

function recommendBaselineWorldId(session: SessionSummary, worldId: string | null): string {
  if (!worldId) return "";
  const ordered = [...session.worlds].sort(
    (left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
  );
  const currentIndex = ordered.findIndex((item) => item.world_id === worldId);
  if (currentIndex > 0) {
    return ordered[currentIndex - 1]?.world_id ?? "";
  }
  return ordered.find((item) => item.world_id !== worldId)?.world_id ?? "";
}
