"use client";

import { useEffect, useMemo, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  getReviewDiff,
  getReviewSummary,
  getSessionReview,
  postAgentInterviewWorldDiff,
  postSessionReviewQuery,
  postReviewDiffQuery,
  postReviewQuery,
  type AgentInterviewResponse,
  type ReviewDiffResponse,
  type ReviewDiffQueryResponse,
  type ReviewGroundingItem,
  type ReviewQueryResponse,
  type ReviewSummaryResponse,
  type SessionReviewQueryResponse,
  type SessionReviewResponse,
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
  const [query, setQuery] = useState("어떤 집단의 신념 변화가 가장 컸고 왜 그런가?");
  const [queryData, setQueryData] = useState<ReviewQueryResponse | null>(null);
  const [queryLoading, setQueryLoading] = useState(false);
  const [queryError, setQueryError] = useState<string | null>(null);
  const [diffQuery, setDiffQuery] = useState("어떤 집단 분열과 정책 차이가 baseline 대비 가장 크게 갈렸나?");
  const [diffQueryData, setDiffQueryData] = useState<ReviewDiffQueryResponse | null>(null);
  const [diffQueryLoading, setDiffQueryLoading] = useState(false);
  const [diffQueryError, setDiffQueryError] = useState<string | null>(null);
  const [sessionReview, setSessionReview] = useState<SessionReviewResponse | null>(null);
  const [sessionReviewLoading, setSessionReviewLoading] = useState(false);
  const [sessionReviewError, setSessionReviewError] = useState<string | null>(null);
  const [sessionObjective, setSessionObjective] = useState("balanced");
  const [sessionQuery, setSessionQuery] = useState("이 세션에서 가장 불안정했던 정책 실험은 무엇이고 왜 그런가?");
  const [sessionQueryData, setSessionQueryData] = useState<SessionReviewQueryResponse | null>(null);
  const [sessionQueryLoading, setSessionQueryLoading] = useState(false);
  const [sessionQueryError, setSessionQueryError] = useState<string | null>(null);
  const [interviewCellId, setInterviewCellId] = useState("");
  const [interviewQuestion, setInterviewQuestion] = useState(
    "baseline world와 비교했을 때 지금 너의 입장은 어떻게 달라졌어?"
  );
  const [interviewData, setInterviewData] = useState<AgentInterviewResponse | null>(null);
  const [interviewLoading, setInterviewLoading] = useState(false);
  const [interviewError, setInterviewError] = useState<string | null>(null);
  const [selectedGraphNodeId, setSelectedGraphNodeId] = useState<string>("");

  const currentSession = sessions.find((session) =>
    session.worlds.some((item) => item.world_id === worldId)
  );
  const comparisonCandidates = (currentSession?.worlds ?? []).filter(
    (item) => item.world_id !== worldId
  );
  const recommendedBaselineId = currentSession
    ? recommendBaselineWorldId(currentSession, worldId)
    : "";
  const diffMetrics = useMemo(() => (diff?.compared_metrics ?? {}) as Record<string, unknown>, [diff]);
  const groupDriftRows = useMemo(
    () =>
      Array.isArray(diffMetrics.group_drift_deltas)
        ? (diffMetrics.group_drift_deltas as Array<Record<string, unknown>>)
        : [],
    [diffMetrics]
  );
  const zoneDriftRows = useMemo(
    () =>
      Array.isArray(diffMetrics.zone_z_delta)
        ? (diffMetrics.zone_z_delta as Array<Record<string, unknown>>)
        : [],
    [diffMetrics]
  );
  const turningPoints = useMemo(
    () => (diffMetrics.timeline_turning_point_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const baseTurningPoints = useMemo(
    () => (Array.isArray(turningPoints.base) ? (turningPoints.base as Array<Record<string, unknown>>) : []),
    [turningPoints]
  );
  const targetTurningPoints = useMemo(
    () => (Array.isArray(turningPoints.target) ? (turningPoints.target as Array<Record<string, unknown>>) : []),
    [turningPoints]
  );
  const policyImpactDelta = useMemo(
    () => (diffMetrics.policy_impact_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const sharedRoles = useMemo(
    () => (Array.isArray(policyImpactDelta.shared_roles) ? (policyImpactDelta.shared_roles as string[]) : []),
    [policyImpactDelta]
  );
  const targetOnlyRoles = useMemo(
    () => (Array.isArray(policyImpactDelta.target_only_roles) ? (policyImpactDelta.target_only_roles as string[]) : []),
    [policyImpactDelta]
  );
  const baseOnlyRoles = useMemo(
    () => (Array.isArray(policyImpactDelta.base_only_roles) ? (policyImpactDelta.base_only_roles as string[]) : []),
    [policyImpactDelta]
  );
  const sharedZones = useMemo(
    () => (Array.isArray(policyImpactDelta.shared_zones) ? (policyImpactDelta.shared_zones as string[]) : []),
    [policyImpactDelta]
  );
  const targetOnlyZones = useMemo(
    () => (Array.isArray(policyImpactDelta.target_only_zones) ? (policyImpactDelta.target_only_zones as string[]) : []),
    [policyImpactDelta]
  );
  const baseOnlyZones = useMemo(
    () => (Array.isArray(policyImpactDelta.base_only_zones) ? (policyImpactDelta.base_only_zones as string[]) : []),
    [policyImpactDelta]
  );
  const largestGroupShiftGap = useMemo(
    () => (policyImpactDelta.largest_group_shift_gap ?? {}) as Record<string, unknown>,
    [policyImpactDelta]
  );
  const largestZoneShiftGap = useMemo(
    () => (policyImpactDelta.largest_zone_shift_gap ?? {}) as Record<string, unknown>,
    [policyImpactDelta]
  );
  const graphNodes = useMemo(
    () =>
      Array.isArray(data?.belief_graph?.nodes)
        ? (data?.belief_graph?.nodes as Array<Record<string, unknown>>)
        : [],
    [data]
  );
  const graphEdges = useMemo(
    () =>
      Array.isArray(data?.belief_graph?.edges)
        ? (data?.belief_graph?.edges as Array<Record<string, unknown>>)
        : [],
    [data]
  );
  const flattenedReviewGrounding = useMemo(() => flattenGrounding(data?.grounding ?? {}), [data]);
  const interviewCandidates = useMemo(
    () =>
      Array.isArray(data?.top_z_movers)
        ? (data?.top_z_movers as Array<Record<string, unknown>>).filter(
            (item) => String(item.cell_id ?? "").trim().length > 0
          )
        : [],
    [data]
  );
  const selectedGraphNode =
    graphNodes.find((node) => String(node.id ?? "") === selectedGraphNodeId) ?? graphNodes[0] ?? null;
  const filteredGraphEdges = selectedGraphNode
    ? graphEdges.filter(
        (edge) =>
          String(edge.source ?? "") === String(selectedGraphNode.id ?? "") ||
          String(edge.target ?? "") === String(selectedGraphNode.id ?? "")
      )
    : graphEdges;
  const selectedNodeGrounding = selectedGraphNode
    ? flattenedReviewGrounding.find(
        (item) =>
          item.group_id != null && String(item.group_id) === String(selectedGraphNode.group_id ?? selectedGraphNode.id ?? "")
      ) ?? null
    : null;

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

  useEffect(() => {
    setQueryData(null);
    setQueryError(null);
  }, [worldId]);

  useEffect(() => {
    setDiffQueryData(null);
    setDiffQueryError(null);
  }, [worldId, baseWorldId]);

  useEffect(() => {
    const sessionId = currentSession?.session_id;
    if (!sessionId) {
      setSessionReview(null);
      setSessionReviewError(null);
      return;
    }
    let cancelled = false;
    setSessionReviewLoading(true);
    setSessionReviewError(null);
    getSessionReview(sessionId, sessionObjective)
      .then((payload) => {
        if (!cancelled) setSessionReview(payload);
      })
      .catch((reason: Error) => {
        if (!cancelled) setSessionReviewError(reason.message);
      })
      .finally(() => {
        if (!cancelled) setSessionReviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [currentSession?.session_id, sessionObjective]);

  useEffect(() => {
    setSessionQueryData(null);
    setSessionQueryError(null);
  }, [currentSession?.session_id]);

  useEffect(() => {
    if (!graphNodes.length) {
      setSelectedGraphNodeId("");
      return;
    }
    if (!selectedGraphNodeId || !graphNodes.some((node) => String(node.id ?? "") === selectedGraphNodeId)) {
      setSelectedGraphNodeId(String(graphNodes[0].id ?? ""));
    }
  }, [graphNodes, selectedGraphNodeId]);

  useEffect(() => {
    if (!interviewCandidates.length) {
      setInterviewCellId("");
      return;
    }
    if (!interviewCellId || !interviewCandidates.some((item) => String(item.cell_id ?? "") === interviewCellId)) {
      setInterviewCellId(String(interviewCandidates[0]?.cell_id ?? ""));
    }
  }, [interviewCandidates, interviewCellId]);

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
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={() => {
              if (!worldId || !query.trim()) return;
              setQueryLoading(true);
              setQueryError(null);
              postReviewQuery(worldId, query.trim())
                .then((payload) => setQueryData(payload))
                .catch((reason: Error) => setQueryError(reason.message))
                .finally(() => setQueryLoading(false));
            }}
          >
            Ask Review
          </button>
        </div>
      </AppPanel>

      <AppPanel
        title="Review Query"
        subtitle="Ask the simulation analyst"
        bodyClassName="space-y-3"
      >
        <textarea
          className="app-input min-h-[84px]"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="예: 어떤 지역의 social elevation이 가장 크게 흔들렸고, 그 원인은 무엇인가?"
        />
        {queryLoading ? <p className="text-sm text-slate-500">Review query loading…</p> : null}
        {queryError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            리뷰 질의를 처리하지 못했습니다: {queryError}
          </p>
        ) : null}
        {queryData ? (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <div className="space-y-3">
              <div className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">Answer</p>
                  <span className="session-thread-card__meta">{queryData.mode}</span>
                </div>
                <p className="session-thread-card__prompt">{queryData.answer}</p>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence</p>
                <div className="mt-2 grid gap-2">
                  {queryData.evidence.map((item, index) => (
                    <p key={`${index}-${item}`} className="inspector-body">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Follow-up</p>
                <div className="mt-2 grid gap-2">
                  {queryData.follow_up.map((item, index) => (
                    <p key={`${index}-${item}`} className="inspector-body">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            </div>
            <div className="space-y-3">
              <GroundingPanel
                title="Grounding"
                items={flattenGrounding(queryData.grounding)}
                onOpenWorldAt={onOpenWorldAt}
                worldId={worldId}
              />
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Query Provenance</p>
                <p className="mt-2 text-sm text-slate-700">
                  prompt {String((queryData.review_meta.query as Record<string, unknown>)?.prompt_version ?? "n/a")}
                </p>
                <p className="text-sm text-slate-700">
                  model {String((queryData.review_meta.query as Record<string, unknown>)?.model ?? "n/a")}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            질문을 입력하면 review payload를 기반으로 LLM 또는 heuristic analyst가 답변합니다.
          </p>
        )}
      </AppPanel>

      <AppPanel
        title="Persona Interview Diff"
        subtitle="Compare one persona agent across baseline and target worlds"
        bodyClassName="space-y-3"
      >
        <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_220px]">
          <textarea
            className="app-input min-h-[84px]"
            value={interviewQuestion}
            onChange={(event) => setInterviewQuestion(event.target.value)}
            placeholder="예: baseline world와 비교했을 때 지금 너의 입장은 어떻게 달라졌어?"
          />
          <select
            className="app-input"
            value={interviewCellId}
            onChange={(event) => setInterviewCellId(event.target.value)}
            disabled={!interviewCandidates.length}
          >
            <option value="">Select agent/persona</option>
            {interviewCandidates.map((item) => (
              <option key={String(item.cell_id ?? "")} value={String(item.cell_id ?? "")}>
                {String(item.role_label ?? item.role_key ?? "agent")} · {String(item.zone_label ?? item.zone_id ?? "zone")}
              </option>
            ))}
          </select>
        </div>
        <div className="session-thread-card__actions">
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={() => {
              if (!worldId || !baseWorldId || !interviewCellId || !interviewQuestion.trim()) return;
              setInterviewLoading(true);
              setInterviewError(null);
              postAgentInterviewWorldDiff(worldId, baseWorldId, interviewCellId, {
                question: interviewQuestion.trim(),
              })
                .then((payload) => setInterviewData(payload))
                .catch((reason: Error) => setInterviewError(reason.message))
                .finally(() => setInterviewLoading(false));
            }}
          >
            Ask Persona Across Worlds
          </button>
        </div>
        {interviewLoading ? <p className="text-sm text-slate-500">Persona diff interview loading…</p> : null}
        {interviewError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            persona diff interview를 처리하지 못했습니다: {interviewError}
          </p>
        ) : null}
        {interviewData ? (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
            <div className="space-y-3">
              <div className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">Agent World-Diff Answer</p>
                  <span className="session-thread-card__meta">{interviewData.mode}</span>
                </div>
                <p className="session-thread-card__prompt">{interviewData.answer}</p>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence</p>
                <div className="mt-2 grid gap-2">
                  {interviewData.evidence.map((item, index) => (
                    <p key={`${index}-${item}`} className="inspector-body">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            </div>
            <GroundingPanel
              title="Interview Grounding"
              items={flattenGrounding(interviewData.grounding)}
              onOpenWorldAt={onOpenWorldAt}
              worldId={worldId}
            />
          </div>
        ) : (
          <p className="text-sm text-slate-500">
            current world의 notable agent를 고른 뒤 baseline world와 1:1 인터뷰 비교를 실행할 수 있습니다.
          </p>
        )}
        {interviewCandidates.length ? (
          <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Persona Interview Matrix</p>
            <div className="grid gap-2">
              {interviewCandidates.slice(0, 6).map((item, index) => (
                <button
                  key={`${index}-${String(item.cell_id ?? "")}`}
                  type="button"
                  className={`session-thread-card text-left ${String(item.cell_id ?? "") === interviewCellId ? "border-sky-300 bg-sky-50" : ""}`}
                  onClick={() => setInterviewCellId(String(item.cell_id ?? ""))}
                >
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">
                      {String(item.role_label ?? item.role_key ?? "agent")}
                    </p>
                    <span className="session-thread-card__meta">
                      shift {Number(item.belief_shift_score ?? 0).toFixed(2)}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    {String(item.zone_label ?? item.zone_id ?? "zone")} · zΔ {Number(item.z_delta ?? 0).toFixed(2)} · worldview {Number(item.worldview_shift ?? 0).toFixed(2)}
                  </p>
                </button>
              ))}
            </div>
          </div>
        ) : null}
      </AppPanel>

      <AppPanel
        title="Session Review"
        subtitle="Multi-world analyst summary"
        bodyClassName="space-y-3"
      >
        {sessionReviewLoading ? <p className="text-sm text-slate-500">Session review loading…</p> : null}
        {sessionReviewError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            세션 리뷰를 불러오지 못했습니다: {sessionReviewError}
          </p>
        ) : null}
        {sessionReview ? (
          <>
            <div className="session-thread-card">
              <div className="session-thread-card__header">
                <p className="session-thread-card__title">{sessionReview.headline}</p>
                <span className="session-thread-card__meta">{sessionReview.review_mode}</span>
              </div>
              <p className="session-thread-card__prompt">{sessionReview.summary}</p>
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <MetricCard label="Worlds" value={String(sessionReview.metrics.world_count ?? 0)} />
              <MetricCard label="Avg Split Risk" value={String(sessionReview.metrics.avg_split_risk ?? "0")} />
              <MetricCard label="Avg Fracture" value={String(sessionReview.metrics.avg_cross_zone_fracture ?? "0")} />
            </div>
            <div className="grid gap-2 md:grid-cols-[200px_minmax(0,1fr)]">
              <select
                className="app-input"
                value={sessionObjective}
                onChange={(event) => setSessionObjective(event.target.value)}
              >
                <option value="balanced">Balanced</option>
                <option value="stability">Stability</option>
                <option value="cohesion">Cohesion</option>
                <option value="polarization">Polarization</option>
                <option value="fracture">Fracture</option>
              </select>
              <p className="text-sm text-slate-500">
                현재 세션 랭킹 기준: <span className="font-medium text-slate-700">{String(sessionReview.metrics.objective ?? sessionObjective)}</span>
              </p>
            </div>
            {sessionReview.objective_explanation ? (
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Objective Explanation</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{sessionReview.objective_explanation}</p>
              </div>
            ) : null}
            {sessionReview.ranked_worlds?.length ? (
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Ranked Worlds</p>
                  {sessionReview.ranked_worlds.slice(0, 5).map((item, index) => (
                    <div key={`${index}-${String(item.world_id ?? "world")}`} className="session-thread-card">
                      <div className="session-thread-card__header">
                        <p className="session-thread-card__title">{String(item.world_id ?? "world")}</p>
                        <span className="session-thread-card__meta">score {Number(item.score ?? 0).toFixed(2)}</span>
                      </div>
                      <p className="session-thread-card__prompt">
                        {String(item.overall_signal ?? "diffuse")} · split {Number(item.split_risk ?? 0).toFixed(2)} · fracture {Number(item.cross_zone_fracture ?? 0).toFixed(2)}
                      </p>
                      <div className="session-thread-card__actions">
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() => onOpenWorldAt(String(item.world_id ?? worldId))}
                        >
                          Open World
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Recommended Comparisons</p>
                  {sessionReview.recommended_pairs?.slice(0, 4).map((item, index) => (
                    <div key={`${index}-${String(item.target_world_id ?? "target")}-${String(item.base_world_id ?? "base")}`} className="session-thread-card">
                      <div className="session-thread-card__header">
                        <p className="session-thread-card__title">
                          {String(item.target_world_id ?? "target").slice(0, 8)} vs {String(item.base_world_id ?? "base").slice(0, 8)}
                        </p>
                      </div>
                      <p className="session-thread-card__prompt">{String(item.reason ?? "comparison candidate")}</p>
                      {item.recommendation ? (
                        <p className="mt-2 text-sm leading-6 text-slate-600">{String(item.recommendation)}</p>
                      ) : null}
                      <div className="session-thread-card__actions">
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() => onOpenWorldAt(String(item.target_world_id ?? worldId))}
                        >
                          Open Target
                        </button>
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() => onOpenWorldAt(String(item.base_world_id ?? worldId))}
                        >
                          Open Base
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : null}
            <div className="grid gap-3 md:grid-cols-2">
              {sessionReview.key_findings.map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="inspector-body">{item}</p>
                </div>
              ))}
            </div>
            <div className="grid gap-3 md:grid-cols-2">
              {sessionReview.decision_implications.map((item, index) => (
                <div key={`${index}-${item}`} className="session-thread-card">
                  <p className="inspector-body">{item}</p>
                </div>
              ))}
            </div>
            <textarea
              className="app-input min-h-[84px]"
              value={sessionQuery}
              onChange={(event) => setSessionQuery(event.target.value)}
              placeholder="예: 이 세션에서 가장 불안정했던 정책 실험은 무엇이고 왜 그런가?"
            />
            <div className="session-thread-card__actions">
              <button
                type="button"
                className="app-button app-button--ghost"
                onClick={() => {
                  if (!currentSession?.session_id || !sessionQuery.trim()) return;
                  setSessionQueryLoading(true);
                  setSessionQueryError(null);
                  postSessionReviewQuery(currentSession.session_id, sessionQuery.trim())
                    .then((payload) => setSessionQueryData(payload))
                    .catch((reason: Error) => setSessionQueryError(reason.message))
                    .finally(() => setSessionQueryLoading(false));
                }}
              >
                Ask Session
              </button>
            </div>
            {sessionQueryLoading ? <p className="text-sm text-slate-500">Session query loading…</p> : null}
            {sessionQueryError ? (
              <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
                세션 질의를 처리하지 못했습니다: {sessionQueryError}
              </p>
            ) : null}
            {sessionQueryData ? (
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                <div className="space-y-3">
                  <div className="session-thread-card">
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">Session Answer</p>
                      <span className="session-thread-card__meta">{sessionQueryData.mode}</span>
                    </div>
                    <p className="session-thread-card__prompt">{sessionQueryData.answer}</p>
                  </div>
                  <div className="session-thread-card">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence</p>
                    <div className="mt-2 grid gap-2">
                      {sessionQueryData.evidence.map((item, index) => (
                        <p key={`${index}-${item}`} className="inspector-body">
                          {item}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="space-y-3">
                  <GroundingPanel
                    title="Session Grounding"
                    items={flattenGrounding(sessionQueryData.grounding)}
                    onOpenWorldAt={onOpenWorldAt}
                    worldId={worldId}
                  />
                  <div className="session-thread-card">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Session Query Provenance</p>
                    <p className="mt-2 text-sm text-slate-700">
                      prompt {String((sessionQueryData.review_meta.query as Record<string, unknown>)?.prompt_version ?? "n/a")}
                    </p>
                    <p className="text-sm text-slate-700">
                      model {String((sessionQueryData.review_meta.query as Record<string, unknown>)?.model ?? "n/a")}
                    </p>
                  </div>
                </div>
              </div>
            ) : null}
          </>
        ) : (
          <p className="text-sm text-slate-500">같은 세션에 world가 쌓이면 세션 단위 리뷰를 제공합니다.</p>
        )}
      </AppPanel>

      <AppPanel
        title="Diff Query"
        subtitle="Ask about baseline vs target"
        bodyClassName="space-y-3"
      >
        <textarea
          className="app-input min-h-[84px]"
          value={diffQuery}
          onChange={(event) => setDiffQuery(event.target.value)}
          placeholder="예: 어떤 집단 분열과 정책 차이가 baseline 대비 가장 크게 갈렸나?"
        />
        <div className="session-thread-card__actions">
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={() => {
              if (!worldId || !baseWorldId || !diffQuery.trim()) return;
              setDiffQueryLoading(true);
              setDiffQueryError(null);
              postReviewDiffQuery(worldId, baseWorldId, diffQuery.trim())
                .then((payload) => setDiffQueryData(payload))
                .catch((reason: Error) => setDiffQueryError(reason.message))
                .finally(() => setDiffQueryLoading(false));
            }}
          >
            Ask Diff
          </button>
        </div>
        {diffQueryLoading ? <p className="text-sm text-slate-500">Diff query loading…</p> : null}
        {diffQueryError ? (
          <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            diff 질의를 처리하지 못했습니다: {diffQueryError}
          </p>
        ) : null}
        {diffQueryData ? (
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <div className="space-y-3">
              <div className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">Diff Answer</p>
                  <span className="session-thread-card__meta">{diffQueryData.mode}</span>
                </div>
                <p className="session-thread-card__prompt">{diffQueryData.answer}</p>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Evidence</p>
                <div className="mt-2 grid gap-2">
                  {diffQueryData.evidence.map((item, index) => (
                    <p key={`${index}-${item}`} className="inspector-body">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
            </div>
            <GroundingPanel
              title="Diff Grounding"
              items={flattenGrounding(diffQueryData.grounding)}
              onOpenWorldAt={(wid, t) => onOpenWorldAt(wid || worldId, t)}
              worldId={worldId}
            />
          </div>
        ) : (
          <p className="text-sm text-slate-500">baseline과 target 차이에 대해 자연어로 질문할 수 있습니다.</p>
        )}
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
                  {targetTurningPoints[index] || getSectionCitation(diff?.citations, "key_deltas", index)?.group_id ? (
                    <div className="session-thread-card__actions">
                      {targetTurningPoints[index] ? (
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
                      ) : null}
                      {getSectionCitation(diff?.citations, "key_deltas", index)?.t != null ? (
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() =>
                            onOpenWorldAt(
                              getSectionCitation(diff?.citations, "key_deltas", index)?.world_id ?? diff.target_world_id,
                              getSectionCitation(diff?.citations, "key_deltas", index)?.t ?? null
                            )
                          }
                        >
                          Citation
                        </button>
                      ) : null}
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
        <AppPanel
          title="Belief State"
          subtitle="Group-level stance, cohesion, tension, polarization"
          bodyClassName="space-y-3"
        >
          {Array.isArray(data?.stance_groups) && data.stance_groups.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-xs text-slate-600">
                <thead>
                  <tr className="border-b border-slate-200 text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    <th className="px-2 py-2">Group</th>
                    <th className="px-2 py-2">Stance</th>
                    <th className="px-2 py-2">Cohesion</th>
                      <th className="px-2 py-2">Tension</th>
                      <th className="px-2 py-2">Polarization</th>
                      <th className="px-2 py-2">Coalition</th>
                      <th className="px-2 py-2">Fracture</th>
                    </tr>
                </thead>
                <tbody>
                  {data.stance_groups.slice(0, 8).map((item, index) => {
                    const row = item as Record<string, unknown>;
                    return (
                      <tr key={`${index}-${String(row.group_id ?? row.role_label ?? "group")}`} className="border-b border-slate-100">
                        <td className="px-2 py-2 font-medium text-slate-800">{String(row.role_label ?? "group")}</td>
                        <td className="px-2 py-2">
                          {String(row.stance_before ?? "n/a")} → {String(row.stance_after ?? "n/a")}
                        </td>
                        <td className="px-2 py-2">
                          {Number(row.cohesion_delta ?? 0).toFixed(2)}
                        </td>
                        <td className="px-2 py-2">
                          {Number(row.tension_delta ?? 0).toFixed(2)}
                        </td>
                        <td className="px-2 py-2">
                          {Number(row.polarization_delta ?? 0).toFixed(2)}
                        </td>
                        <td className="px-2 py-2">
                          {String(row.coalition_signal ?? "n/a")} · {Number(row.coalition_persistence ?? 0).toFixed(2)}
                        </td>
                        <td className="px-2 py-2">
                          {Number(row.sub_coalition_split_risk ?? 0).toFixed(2)} / {Number(row.ideology_block_divergence ?? 0).toFixed(2)} / {Number(row.cross_zone_group_fracture ?? 0).toFixed(2)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="text-sm text-slate-500">집단 신념 상태 표가 아직 없습니다.</p>
          )}
        </AppPanel>

        <GroundingPanel
          title="Review Grounding"
          items={flattenGrounding(data?.grounding ?? {})}
          onOpenWorldAt={onOpenWorldAt}
          worldId={worldId}
        />
      </div>

      <AppPanel
        title="Coalition / Fracture Graph"
        subtitle="Role nodes and relationship edges"
        bodyClassName="space-y-3"
      >
        {graphNodes.length > 0 ? (
          <div className="grid gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,0.9fr)]">
            <div className="grid gap-3 md:grid-cols-2">
              {graphNodes.slice(0, 8).map((node, index) => {
                const item = node as Record<string, unknown>;
                const isSelected = String(item.id ?? "") === String(selectedGraphNode?.id ?? "");
                return (
                  <button
                    key={`${index}-${String(item.id ?? item.label ?? "node")}`}
                    type="button"
                    className={`session-thread-card text-left ${isSelected ? "ring-2 ring-slate-900/10 border-slate-400" : ""}`}
                    onClick={() => setSelectedGraphNodeId(String(item.id ?? ""))}
                  >
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">{String(item.label ?? "group")}</p>
                      <span className="session-thread-card__meta">{String(item.stance ?? "diffuse")}</span>
                    </div>
                    <p className="session-thread-card__prompt">
                      split {Number(item.split_risk ?? 0).toFixed(2)} · block {Number(item.block_divergence ?? 0).toFixed(2)} · fracture {Number(item.cross_zone_fracture ?? 0).toFixed(2)}
                    </p>
                  </button>
                );
              })}
            </div>
            <div className="space-y-3">
              {selectedGraphNode ? (
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">{String(selectedGraphNode.label ?? "group")}</p>
                    <span className="session-thread-card__meta">{String(selectedGraphNode.stance ?? "diffuse")}</span>
                  </div>
                  <p className="session-thread-card__prompt">
                    cohesion {Number(selectedGraphNode.cohesion ?? 0).toFixed(2)} · tension {Number(selectedGraphNode.tension ?? 0).toFixed(2)} · polarization {Number(selectedGraphNode.polarization ?? 0).toFixed(2)}
                  </p>
                  <p className="session-thread-card__prompt">
                    split {Number(selectedGraphNode.split_risk ?? 0).toFixed(2)} · block {Number(selectedGraphNode.block_divergence ?? 0).toFixed(2)} · fracture {Number(selectedGraphNode.cross_zone_fracture ?? 0).toFixed(2)}
                  </p>
                  {selectedNodeGrounding?.t != null ? (
                    <div className="session-thread-card__actions">
                      <button
                        type="button"
                        className="app-button app-button--ghost"
                        onClick={() => onOpenWorldAt(selectedNodeGrounding.world_id ?? worldId, selectedNodeGrounding.t ?? null)}
                      >
                        Open Node Anchor
                      </button>
                    </div>
                  ) : null}
                </div>
              ) : null}
              {(filteredGraphEdges ?? []).slice(0, 10).map((edge, index) => {
                const item = edge as Record<string, unknown>;
                return (
                  <div key={`${index}-${String(item.source)}-${String(item.target)}`} className="session-thread-card">
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">
                        {String(item.source ?? "source")} → {String(item.target ?? "target")}
                      </p>
                      <span className="session-thread-card__meta">{String(item.relationship ?? "aligned")}</span>
                    </div>
                    <p className="session-thread-card__prompt">weight {Number(item.weight ?? 0).toFixed(2)}</p>
                  </div>
                );
              })}
            </div>
          </div>
        ) : (
          <p className="text-sm text-slate-500">belief graph가 아직 없습니다.</p>
        )}
      </AppPanel>

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
          title="Policy Impact Delta"
          subtitle="Who and where the intervention diverged"
          bodyClassName="space-y-3"
        >
          {diff ? (
            <>
              <div className="grid gap-3 md:grid-cols-3">
                <MetricCard
                  label="Event Count Gap"
                  value={String(policyImpactDelta.event_count_gap ?? 0)}
                />
                <MetricCard
                  label="Largest Group Shift"
                  value={`${String(largestGroupShiftGap.base_role_label ?? "n/a")} -> ${String(
                    largestGroupShiftGap.target_role_label ?? "n/a"
                  )}`}
                />
                <MetricCard
                  label="Largest Zone Shift"
                  value={`${String(largestZoneShiftGap.base_zone_label ?? "n/a")} -> ${String(
                    largestZoneShiftGap.target_zone_label ?? "n/a"
                  )}`}
                />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <PolicyTokenCard title="Shared Roles" items={sharedRoles} tone="neutral" />
                <PolicyTokenCard title="Target-only Roles" items={targetOnlyRoles} tone="target" />
                <PolicyTokenCard title="Baseline-only Roles" items={baseOnlyRoles} tone="base" />
                <PolicyTokenCard title="Shared Zones" items={sharedZones} tone="neutral" />
                <PolicyTokenCard title="Target-only Zones" items={targetOnlyZones} tone="target" />
                <PolicyTokenCard title="Baseline-only Zones" items={baseOnlyZones} tone="base" />
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Group Shift Gap</p>
                    <span className="session-thread-card__meta">
                      cohesion {Number(largestGroupShiftGap.cohesion_gap ?? 0).toFixed(2)}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    tension {Number(largestGroupShiftGap.tension_gap ?? 0).toFixed(2)}
                  </p>
                </div>
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Zone Shift Gap</p>
                    <span className="session-thread-card__meta">
                      avg z {Number(largestZoneShiftGap.avg_z_gap ?? 0).toFixed(2)}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    strongest regional divergence between baseline and target interventions
                  </p>
                </div>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">정책 영향 비교는 diff report 생성 후 표시됩니다.</p>
          )}
        </AppPanel>

        <AppPanel
          title="Comparison Guidance"
          subtitle="Where to inspect next"
          bodyClassName="space-y-3"
        >
          {diff ? (
            <>
              <div className="session-thread-card">
                <p className="inspector-body">
                  target-only role과 zone은 baseline과 다른 정책 자극이 집중된 후보입니다.
                </p>
              </div>
              <div className="session-thread-card">
                <p className="inspector-body">
                  turning point와 group drift table을 함께 보면 어떤 정책 대상이 어떤 집단 변화를 일으켰는지 더 빨리 좁힐 수 있습니다.
                </p>
              </div>
              <div className="session-thread-card__actions">
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() =>
                    targetTurningPoints[0]
                      ? onOpenWorldAt(
                          diff.target_world_id,
                          Number((targetTurningPoints[0] as Record<string, unknown>).t ?? 0)
                        )
                      : onOpenWorldAt(diff.target_world_id)
                  }
                >
                  Open Strongest Target Shift
                </button>
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() =>
                    baseTurningPoints[0]
                      ? onOpenWorldAt(
                          diff.base_world_id,
                          Number((baseTurningPoints[0] as Record<string, unknown>).t ?? 0)
                        )
                      : onOpenWorldAt(diff.base_world_id)
                  }
                >
                  Open Baseline Reference
                </button>
              </div>
            </>
          ) : (
            <p className="text-sm text-slate-500">비교 결과가 생기면 다음 탐색 가이드를 제안합니다.</p>
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
                {getSectionCitation(data.citations, "key_events", index)?.t != null ? (
                  <div className="session-thread-card__actions">
                    <button
                      type="button"
                      className="app-button app-button--ghost"
                      onClick={() => onOpenWorldAt(worldId, getSectionCitation(data.citations, "key_events", index)?.t ?? null)}
                    >
                      Citation
                    </button>
                  </div>
                ) : null}
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
                {getSectionCitation(data.citations, "causal_analysis", index)?.t != null ? (
                  <div className="session-thread-card__actions">
                    <button
                      type="button"
                      className="app-button app-button--ghost"
                      onClick={() => onOpenWorldAt(worldId, getSectionCitation(data.citations, "causal_analysis", index)?.t ?? null)}
                    >
                      Citation
                    </button>
                  </div>
                ) : null}
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
                  {targetTurningPoints[index] || getSectionCitation(diff?.citations, "causal_comparison", index)?.t != null ? (
                    <div className="session-thread-card__actions">
                      {targetTurningPoints[index] ? (
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
                      ) : null}
                      {getSectionCitation(diff?.citations, "causal_comparison", index)?.t != null ? (
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() =>
                            onOpenWorldAt(
                              getSectionCitation(diff?.citations, "causal_comparison", index)?.world_id ??
                                (index === 1 ? diff.base_world_id : diff.target_world_id),
                              getSectionCitation(diff?.citations, "causal_comparison", index)?.t ?? null
                            )
                          }
                        >
                          Citation
                        </button>
                      ) : null}
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
                {getSectionCitation(data.citations, "decision_implications", index)?.t != null ? (
                  <div className="session-thread-card__actions">
                    <button
                      type="button"
                      className="app-button app-button--ghost"
                      onClick={() => onOpenWorldAt(worldId, getSectionCitation(data.citations, "decision_implications", index)?.t ?? null)}
                    >
                      Citation
                    </button>
                  </div>
                ) : null}
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
                  {getSectionCitation(diff?.citations, "decision_implications", index)?.zone_id ? (
                    <div className="session-thread-card__actions">
                      <button
                        type="button"
                        className="app-button app-button--ghost"
                        onClick={() =>
                          onOpenWorldAt(
                            getSectionCitation(diff?.citations, "decision_implications", index)?.world_id ?? diff.target_world_id,
                            getSectionCitation(diff?.citations, "decision_implications", index)?.t ?? null
                          )
                        }
                      >
                        Citation
                      </button>
                    </div>
                  ) : null}
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

function GroundingPanel({
  title,
  items,
  onOpenWorldAt,
  worldId,
}: {
  title: string;
  items: ReviewGroundingItem[];
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
  worldId: string;
}) {
  return (
    <AppPanel title={title} subtitle="Evidence anchors" bodyClassName="space-y-3">
      {items.length ? (
        items.slice(0, 8).map((item, index) => (
          <div key={`${index}-${item.kind}-${item.label}`} className="session-thread-card">
            <div className="session-thread-card__header">
              <p className="session-thread-card__title">{item.label}</p>
              <span className="session-thread-card__meta">{item.kind}</span>
            </div>
            <p className="session-thread-card__prompt">{item.reason || "grounded evidence"}</p>
            {typeof item.t === "number" ? (
              <div className="session-thread-card__actions">
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => onOpenWorldAt(item.world_id ?? worldId, item.t ?? null)}
                >
                  Open at t={item.t}
                </button>
              </div>
            ) : null}
          </div>
        ))
      ) : (
        <p className="text-sm text-slate-500">근거 anchor가 아직 없습니다.</p>
      )}
    </AppPanel>
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

function PolicyTokenCard({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "neutral" | "target" | "base";
}) {
  const toneClass =
    tone === "target"
      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
      : tone === "base"
        ? "bg-amber-50 text-amber-700 border-amber-200"
        : "bg-slate-100 text-slate-700 border-slate-200";
  return (
    <div className="session-thread-card">
      <div className="session-thread-card__header">
        <p className="session-thread-card__title">{title}</p>
        <span className="session-thread-card__meta">{items.length}</span>
      </div>
      {items.length ? (
        <div className="flex flex-wrap gap-2">
          {items.map((item) => (
            <span key={item} className={`rounded-full border px-2 py-1 text-[11px] font-medium ${toneClass}`}>
              {item}
            </span>
          ))}
        </div>
      ) : (
        <p className="session-thread-card__prompt">none</p>
      )}
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

function flattenGrounding(
  grounding: Record<string, ReviewGroundingItem[]>
): ReviewGroundingItem[] {
  return Object.values(grounding)
    .flat()
    .filter(Boolean);
}

function getSectionCitation(
  citations: Record<string, ReviewGroundingItem[]> | undefined,
  section: string,
  index: number
): ReviewGroundingItem | null {
  if (!citations) return null;
  const indexed = citations[`${section}.${index}`];
  if (Array.isArray(indexed) && indexed.length > 0) return indexed[0] ?? null;
  const plain = citations[section];
  if (Array.isArray(plain) && plain.length > index) return plain[index] ?? plain[0] ?? null;
  if (Array.isArray(plain) && plain.length > 0) return plain[0] ?? null;
  return null;
}
