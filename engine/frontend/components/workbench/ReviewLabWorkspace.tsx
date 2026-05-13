"use client";

import { useDeferredValue, useEffect, useMemo, useState } from "react";

import { AppPanel } from "@/components/app-shell/AppPanel";
import {
  getReviewDiff,
  getReviewSummary,
  getSessionReview,
  postAgentInterviewWorldDiff,
  postSessionReviewQuery,
  postReviewDiffQuery,
  postReviewQuery,
  restoreWorldState,
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
import type { UiLocale } from "@/lib/ui-language";

type ReviewLabWorkspaceProps = {
  locale?: UiLocale;
  worldId: string | null;
  sessions: SessionSummary[];
  onOpenView: (view: WorkbenchView) => void;
  onOpenWorldAt: (worldId: string, t?: number | null) => void;
  onQueueInjectPreset: (
    worldId: string,
    preset: ReviewSummaryResponse["inject_presets"][number]
  ) => void;
};

export function ReviewLabWorkspace({
  locale = "ko",
  worldId,
  sessions,
  onOpenView,
  onOpenWorldAt,
  onQueueInjectPreset,
}: ReviewLabWorkspaceProps) {
  const isKo = locale === "ko";
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
  const [roleFilter, setRoleFilter] = useState("all");
  const [zoneFilter, setZoneFilter] = useState("all");
  const [countryFilter, setCountryFilter] = useState("all");
  const [selectedCompareIds, setSelectedCompareIds] = useState<string[]>([]);
  const [branchLoading, setBranchLoading] = useState(false);
  const [branchError, setBranchError] = useState<string | null>(null);
  const [branchStatus, setBranchStatus] = useState<string | null>(null);
  const summaryRepairMeta = ((data?.review_meta?.summary as Record<string, unknown> | undefined) ?? {});
  const summaryRepairUsed = Boolean(summaryRepairMeta.repair_used);
  const summaryRepairCount = Number(summaryRepairMeta.repair_count ?? 0);
  const summaryRepairReason = String(summaryRepairMeta.repair_reason ?? "none");

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
  const baseWorldviewCurve = useMemo(
    () =>
      Array.isArray(diffMetrics.base_worldview_curve)
        ? (diffMetrics.base_worldview_curve as Array<Record<string, unknown>>)
        : [],
    [diffMetrics]
  );
  const targetWorldviewCurve = useMemo(
    () =>
      Array.isArray(diffMetrics.target_worldview_curve)
        ? (diffMetrics.target_worldview_curve as Array<Record<string, unknown>>)
        : [],
    [diffMetrics]
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
  const deferredCandidates = useDeferredValue(interviewCandidates);
  const roleOptions = useMemo(
    () => uniqueSorted(deferredCandidates.map((item) => String(item.role_label ?? "agent"))),
    [deferredCandidates]
  );
  const zoneOptions = useMemo(
    () => uniqueSorted(deferredCandidates.map((item) => String(item.zone_label ?? "zone"))),
    [deferredCandidates]
  );
  const countryOptions = useMemo(
    () => uniqueSorted(deferredCandidates.map((item) => String(item.persona_country ?? ""))),
    [deferredCandidates]
  );
  const filteredInterviewCandidates = useMemo(
    () =>
      deferredCandidates.filter((item) => {
        const role = String(item.role_label ?? "agent");
        const zone = String(item.zone_label ?? "zone");
        const country = String(item.persona_country ?? "");
        return (
          (roleFilter === "all" || role === roleFilter) &&
          (zoneFilter === "all" || zone === zoneFilter) &&
          (countryFilter === "all" || country === countryFilter)
        );
      }),
    [countryFilter, deferredCandidates, roleFilter, zoneFilter]
  );
  const batchInterviewSummary = useMemo(() => {
    if (!filteredInterviewCandidates.length) {
      return null;
    }
    const scores = filteredInterviewCandidates.map((item) => Number(item.belief_shift_score ?? 0));
    const zDeltas = filteredInterviewCandidates.map((item) => Math.abs(Number(item.z_delta ?? 0)));
    const worldview = filteredInterviewCandidates.map((item) => Number(item.worldview_shift ?? 0));
    return {
      count: filteredInterviewCandidates.length,
      avgShift: average(scores),
      avgZDelta: average(zDeltas),
      avgWorldview: average(worldview),
    };
  }, [filteredInterviewCandidates]);
  const selectedBatchCandidates = useMemo(
    () => filteredInterviewCandidates.filter((item) => selectedCompareIds.includes(String(item.cell_id ?? ""))),
    [filteredInterviewCandidates, selectedCompareIds]
  );
  const batchRoleSummary = useMemo(() => summarizeBatchBy(selectedBatchCandidates, "role_label"), [selectedBatchCandidates]);
  const batchZoneSummary = useMemo(() => summarizeBatchBy(selectedBatchCandidates, "zone_label"), [selectedBatchCandidates]);
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
  const emergentDynamics = useMemo(
    () => (data?.emergent_dynamics ?? {}) as Record<string, unknown>,
    [data]
  );
  const validationReadout = useMemo(
    () => (data?.validation_readout ?? {}) as Record<string, unknown>,
    [data]
  );
  const decisionInfluence = useMemo(
    () => (data?.decision_influence ?? {}) as Record<string, unknown>,
    [data]
  );
  const decisionInfluenceLatest = useMemo(
    () => (decisionInfluence.latest ?? {}) as Record<string, unknown>,
    [decisionInfluence]
  );
  const decisionInfluencePeak = useMemo(
    () => (decisionInfluence.peak ?? {}) as Record<string, unknown>,
    [decisionInfluence]
  );
  const decisionInfluenceSummary = useMemo(
    () => (decisionInfluence.summary ?? {}) as Record<string, unknown>,
    [decisionInfluence]
  );
  const mockValidation = useMemo(
    () => (validationReadout.mock_long_horizon ?? {}) as Record<string, unknown>,
    [validationReadout]
  );
  const liveValidation = useMemo(
    () => (validationReadout.live_smoke ?? {}) as Record<string, unknown>,
    [validationReadout]
  );
  const validationNotes = useMemo(
    () =>
      Array.isArray(validationReadout.interpretation_notes)
        ? (validationReadout.interpretation_notes as string[])
        : [],
    [validationReadout]
  );
  const validationNextChecks = useMemo(
    () =>
      Array.isArray(validationReadout.recommended_next_checks)
        ? (validationReadout.recommended_next_checks as string[])
        : [],
    [validationReadout]
  );
  const groupAnalysis = useMemo(
    () => (data?.group_analysis ?? {}) as Record<string, unknown>,
    [data]
  );
  const lineageSummary = useMemo(
    () => (data?.lineage_summary ?? {}) as Record<string, unknown>,
    [data]
  );
  const policyMechanisms = useMemo(
    () => (data?.policy_mechanisms ?? {}) as Record<string, unknown>,
    [data]
  );
  const policyMechanismRows = useMemo(
    () =>
      Array.isArray(policyMechanisms.dominant_channels)
        ? (policyMechanisms.dominant_channels as Array<Record<string, unknown>>)
        : [],
    [policyMechanisms]
  );
  const propagationPaths = useMemo(
    () =>
      Array.isArray(policyMechanisms.propagation_paths)
        ? (policyMechanisms.propagation_paths as Array<Record<string, unknown>>)
        : [],
    [policyMechanisms]
  );
  const groupTables = useMemo(
    () => (data?.group_tables ?? {}) as Record<string, unknown>,
    [data]
  );
  const roleTableRows = useMemo(
    () => (Array.isArray(groupTables.role_table) ? (groupTables.role_table as Array<Record<string, unknown>>) : []),
    [groupTables]
  );
  const personaCountryRows = useMemo(
    () =>
      Array.isArray(groupTables.persona_country_table)
        ? (groupTables.persona_country_table as Array<Record<string, unknown>>)
        : [],
    [groupTables]
  );
  const zoneTableRows = useMemo(
    () => (Array.isArray(groupTables.zone_table) ? (groupTables.zone_table as Array<Record<string, unknown>>) : []),
    [groupTables]
  );
  const causalChains = useMemo(
    () =>
      Array.isArray(data?.causal_chains)
        ? (data?.causal_chains as Array<Record<string, unknown>>)
        : [],
    [data]
  );
  const sessionGroupTables = useMemo(
    () => (sessionReview?.group_tables ?? {}) as Record<string, unknown>,
    [sessionReview]
  );
  const sessionLineage = useMemo(
    () => (sessionReview?.lineage_summary ?? {}) as Record<string, unknown>,
    [sessionReview]
  );
  const sessionRoleRows = useMemo(
    () =>
      Array.isArray(sessionGroupTables.role_table)
        ? (sessionGroupTables.role_table as Array<Record<string, unknown>>)
        : [],
    [sessionGroupTables]
  );
  const sessionPersonaRows = useMemo(
    () =>
      Array.isArray(sessionGroupTables.persona_country_table)
        ? (sessionGroupTables.persona_country_table as Array<Record<string, unknown>>)
        : [],
    [sessionGroupTables]
  );
  const sessionZoneRows = useMemo(
    () =>
      Array.isArray(sessionGroupTables.zone_table)
        ? (sessionGroupTables.zone_table as Array<Record<string, unknown>>)
        : [],
    [sessionGroupTables]
  );
  const sessionLineageRows = useMemo(
    () =>
      Array.isArray(sessionLineage.tracked_roles)
        ? (sessionLineage.tracked_roles as Array<Record<string, unknown>>)
        : [],
    [sessionLineage]
  );
  const sessionMigrationRows = useMemo(
    () =>
      Array.isArray(sessionLineage.ideology_migrations)
        ? (sessionLineage.ideology_migrations as Array<Record<string, unknown>>)
        : [],
    [sessionLineage]
  );
  const sessionPolicyLineage = useMemo(
    () => (sessionReview?.policy_lineage_bridge ?? {}) as Record<string, unknown>,
    [sessionReview]
  );
  const sessionPolicyBridgeRows = useMemo(
    () =>
      Array.isArray(sessionPolicyLineage.bridge_rows)
        ? (sessionPolicyLineage.bridge_rows as Array<Record<string, unknown>>)
        : [],
    [sessionPolicyLineage]
  );
  const diffGroupTableDelta = useMemo(
    () => (diffMetrics.group_table_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const diffPersonaRows = useMemo(
    () =>
      Array.isArray(diffGroupTableDelta.persona_country_delta)
        ? (diffGroupTableDelta.persona_country_delta as Array<Record<string, unknown>>)
        : [],
    [diffGroupTableDelta]
  );
  const diffPolicyMechanismDelta = useMemo(
    () => (diffMetrics.policy_mechanism_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const diffLineageDelta = useMemo(
    () => (diffMetrics.lineage_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const diffPolicyLineageDelta = useMemo(
    () => (diffMetrics.policy_lineage_delta ?? {}) as Record<string, unknown>,
    [diffMetrics]
  );
  const diffPolicyChannelRows = useMemo(
    () =>
      Array.isArray(diffPolicyMechanismDelta.channel_gaps)
        ? (diffPolicyMechanismDelta.channel_gaps as Array<Record<string, unknown>>)
        : [],
    [diffPolicyMechanismDelta]
  );
  const lineageTrackedRows = useMemo(
    () =>
      Array.isArray(lineageSummary.tracked_roles)
        ? (lineageSummary.tracked_roles as Array<Record<string, unknown>>)
        : [],
    [lineageSummary]
  );
  const ideologyMigrationRows = useMemo(
    () =>
      Array.isArray(lineageSummary.ideology_migrations)
        ? (lineageSummary.ideology_migrations as Array<Record<string, unknown>>)
        : [],
    [lineageSummary]
  );
  const policyLineageBridge = useMemo(
    () => (data?.policy_lineage_bridge ?? {}) as Record<string, unknown>,
    [data]
  );
  const policyLineageBridgeRows = useMemo(
    () =>
      Array.isArray(policyLineageBridge.bridges)
        ? (policyLineageBridge.bridges as Array<Record<string, unknown>>)
        : [],
    [policyLineageBridge]
  );
  const diffLineageRows = useMemo(
    () =>
      Array.isArray(diffLineageDelta.tracked_role_gaps)
        ? (diffLineageDelta.tracked_role_gaps as Array<Record<string, unknown>>)
        : [],
    [diffLineageDelta]
  );
  const diffPolicyLineageRows = useMemo(
    () =>
      Array.isArray(diffPolicyLineageDelta.bridge_gaps)
        ? (diffPolicyLineageDelta.bridge_gaps as Array<Record<string, unknown>>)
        : [],
    [diffPolicyLineageDelta]
  );
  const diffZoneTableRows = useMemo(
    () =>
      Array.isArray(diffGroupTableDelta.zone_table_delta)
        ? (diffGroupTableDelta.zone_table_delta as Array<Record<string, unknown>>)
        : [],
    [diffGroupTableDelta]
  );

  const createBranchAt = async (targetWorldId: string, t: number | null | undefined, sourceLabel: string) => {
    if (!targetWorldId || typeof t !== "number") return null;
    setBranchLoading(true);
    setBranchError(null);
    setBranchStatus(null);
    try {
      const restored = await restoreWorldState(targetWorldId, {
        t,
        target: "fork",
        resume: true,
      });
      const nextWorldId = restored.world_id ?? targetWorldId;
      const nextT = typeof restored.restored_t === "number" ? restored.restored_t : t;
      setBranchStatus(
        isKo
          ? `${sourceLabel} 기준 브랜치를 생성했습니다. (${nextWorldId.slice(0, 8)})`
          : `Created a branch from ${sourceLabel}. (${nextWorldId.slice(0, 8)})`
      );
      onOpenWorldAt(nextWorldId, nextT);
      return { worldId: nextWorldId, t: nextT };
    } catch (reason) {
      setBranchError(reason instanceof Error ? reason.message : isKo ? "브랜치 생성 실패" : "Failed to create branch");
      return null;
    } finally {
      setBranchLoading(false);
    }
  };

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
    if (!filteredInterviewCandidates.length) {
      setInterviewCellId("");
      return;
    }
    if (
      !interviewCellId ||
      !filteredInterviewCandidates.some((item) => String(item.cell_id ?? "") === interviewCellId)
    ) {
      setInterviewCellId(String(filteredInterviewCandidates[0]?.cell_id ?? ""));
    }
  }, [filteredInterviewCandidates, interviewCellId]);

  useEffect(() => {
    setSelectedCompareIds((prev) =>
      prev.filter((item) => filteredInterviewCandidates.some((candidate) => String(candidate.cell_id ?? "") === item))
    );
  }, [filteredInterviewCandidates]);

  if (!worldId) {
    return (
      <div className="workspace-grid">
        <AppPanel
          title={isKo ? "리뷰 랩" : "Review Lab"}
          subtitle={isKo ? "LLM 보조 시뮬레이션 후 분석" : "LLM-assisted post-simulation analysis"}
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
              {isKo ? "시뮬레이션 열기" : "Open Simulation"}
            </button>
          </div>
          <div className="grid gap-3">
            <StageCard index="01" label={isKo ? "월드 실행" : "Run a world"} />
            <StageCard index="02" label={isKo ? "스냅샷 저장" : "Persist snapshots"} />
            <StageCard index="03" label={isKo ? "리뷰 요약과 어노테이션" : "Review summary + annotations"} />
          </div>
        </AppPanel>
      </div>
    );
  }

  return (
    <div className="workspace-grid">
      <AppPanel
        title={isKo ? "리뷰 요약" : "Review Summary"}
        subtitle={`World ${worldId}`}
        bodyClassName="grid gap-4 xl:grid-cols-[minmax(0,1.3fr)_minmax(280px,360px)]"
      >
        <div className="space-y-4">
          {loading ? <p className="text-sm text-slate-500">{isKo ? "리뷰 요약 불러오는 중…" : "Review summary loading…"}</p> : null}
          {error ? (
            <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
              리뷰 요약을 불러오지 못했습니다: {error}
            </p>
          ) : null}
          {data ? (
            <>
              <div className="space-y-2">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">
                  {isKo ? "헤드라인" : "Headline"}
                </p>
                <p className="text-base font-semibold text-slate-900">{data.headline}</p>
              </div>
              <p className="text-sm leading-7 text-slate-700">{data.summary}</p>
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                <MetricCard label={isKo ? "결과" : "Outcome"} value={String(data.outcome)} />
                <MetricCard label={isKo ? "신호" : "Signal"} value={String(data.overall_signal)} />
                <MetricCard label={isKo ? "요약 모드" : "Summary Mode"} value={String(data.summary_mode)} />
                <MetricCard label={isKo ? "어노테이션 모드" : "Annotation Mode"} value={String(data.annotation_mode)} />
              </div>
              {Object.keys(decisionInfluence).length ? (
                <div className="rounded-3xl border border-amber-200 bg-amber-50/70 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-[0.18em] text-amber-700">
                        {isKo ? "Decision Pressure" : "Decision Pressure"}
                      </p>
                      <p className="mt-1 text-sm leading-6 text-amber-900">
                        {String(
                          decisionInfluenceSummary.interpretation ??
                            (isKo
                              ? "집단 압력이 의사결정 루프에 얼마나 개입했는지 요약합니다."
                              : "Summarizes how strongly collective pressure entered decision loops.")
                        )}
                      </p>
                    </div>
                    <span className="rounded-full border border-amber-300 bg-white px-3 py-1 text-xs font-semibold text-amber-800">
                      {String(decisionInfluenceSummary.latest_dominant_reason ?? decisionInfluenceLatest.dominant_reason ?? "stable")}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    <MetricCard
                      label={isKo ? "최신 평균 Δ" : "Latest Avg Δ"}
                      value={Number(decisionInfluenceLatest.avg_decision_pressure_delta ?? 0).toFixed(3)}
                    />
                    <MetricCard
                      label={isKo ? "피크 최대 Δ" : "Peak Max Δ"}
                      value={Number(decisionInfluencePeak.max_decision_pressure_delta ?? 0).toFixed(3)}
                    />
                    <MetricCard
                      label={isKo ? "적용률" : "Applied Rate"}
                      value={`${Math.round(Number(decisionInfluenceLatest.collective_influence_applied_rate ?? 0) * 100)}%`}
                    />
                  </div>
                </div>
              ) : null}
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
                <option value="">{isKo ? "기준 world 선택" : "Select baseline world"}</option>
                {comparisonCandidates.map((item) => (
                  <option key={item.world_id} value={item.world_id}>
                    {item.world_id.slice(0, 8)} · {item.status}
                  </option>
                ))}
              </select>
              {recommendedBaselineId ? (
                <p className="text-xs text-slate-500">
                  {isKo ? "추천 기준 world" : "Recommended baseline"}: <span className="font-semibold text-slate-700">{recommendedBaselineId.slice(0, 8)}</span>
                </p>
              ) : null}
            </div>
          ) : null}
          <button
            type="button"
            className="app-button app-button--secondary"
            onClick={() => onOpenView("simulation")}
          >
            {isKo ? "시뮬레이션으로 돌아가기" : "Back to Simulation"}
          </button>
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={() => onOpenView("snapshots")}
          >
            {isKo ? "스냅샷 열기" : "Open Snapshots"}
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
            {isKo ? "리뷰 질의" : "Ask Review"}
          </button>
        </div>
      </AppPanel>

      {branchLoading || branchError || branchStatus ? (
        <AppPanel
          title={isKo ? "리뷰 액션 상태" : "Review Action Status"}
          subtitle={isKo ? "리뷰에서 시뮬레이션 액션으로 이어지는 상태" : "Status while moving from review into simulation"}
          bodyClassName="space-y-2"
        >
          {branchLoading ? <p className="text-sm text-slate-500">{isKo ? "브랜치를 생성하는 중…" : "Creating branch…"}</p> : null}
          {branchStatus ? <p className="rounded-2xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">{branchStatus}</p> : null}
          {branchError ? <p className="rounded-2xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">{branchError}</p> : null}
        </AppPanel>
      ) : null}

      <AppPanel
        title={isKo ? "리뷰 질의" : "Review Query"}
        subtitle={isKo ? "시뮬레이션 분석가에게 묻기" : "Ask the simulation analyst"}
        bodyClassName="space-y-3"
      >
        <textarea
          className="app-input min-h-[84px]"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="예: 어떤 지역의 social elevation이 가장 크게 흔들렸고, 그 원인은 무엇인가?"
        />
        {queryLoading ? <p className="text-sm text-slate-500">{isKo ? "리뷰 질의 처리 중…" : "Review query loading…"}</p> : null}
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
                  <p className="session-thread-card__title">{isKo ? "답변" : "Answer"}</p>
                  <span className="session-thread-card__meta">{queryData.mode}</span>
                </div>
                <p className="session-thread-card__prompt">{queryData.answer}</p>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "근거" : "Evidence"}</p>
                <div className="mt-2 grid gap-2">
                  {queryData.evidence.map((item, index) => (
                    <p key={`${index}-${item}`} className="inspector-body">
                      {item}
                    </p>
                  ))}
                </div>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "후속 질문" : "Follow-up"}</p>
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
                title={isKo ? "그라운딩" : "Grounding"}
                items={flattenGrounding(queryData.grounding)}
                onOpenWorldAt={onOpenWorldAt}
                worldId={worldId}
              />
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "질의 출처 정보" : "Query Provenance"}</p>
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
            {isKo ? "질문을 입력하면 review payload를 기반으로 LLM 또는 heuristic analyst가 답변합니다." : "Ask a question and the LLM or heuristic analyst will answer from the review payload."}
          </p>
        )}
      </AppPanel>

      <AppPanel
        title={isKo ? "집단 분석" : "Group Analysis"}
        subtitle={isKo ? "집단 수준의 역할, 분열, emergent dynamics" : "Role, fracture, and emergent dynamics at the collective level"}
        bodyClassName="space-y-3"
      >
        <div className="grid gap-3 md:grid-cols-3">
          <MetricCard label={isKo ? "분열 위험" : "Split Risk"} value={String(emergentDynamics.split_risk ?? "0")} />
          <MetricCard label={isKo ? "블록 분기" : "Block Divergence"} value={String(emergentDynamics.block_divergence ?? "0")} />
          <MetricCard label={isKo ? "혁명 위험" : "Revolution Risk"} value={String(emergentDynamics.revolution_risk ?? "low")} />
        </div>
        <div className="grid gap-3 md:grid-cols-3">
          <MetricCard
            label={isKo ? "체제 전이" : "Regime Transition"}
            value={String(lineageSummary.regime_transition_signal ?? emergentDynamics.regime_transition_signal ?? "stable")}
          />
          <MetricCard
            label={isKo ? "이념 이동 수" : "Ideology Migrations"}
            value={String(ideologyMigrationRows.length)}
          />
          <MetricCard
            label={isKo ? "추적 역할 수" : "Tracked Roles"}
            value={String(lineageTrackedRows.length)}
          />
        </div>
        <div className="grid gap-3 xl:grid-cols-3">
          <div className="session-thread-card">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Contested Groups</p>
            <div className="mt-2 grid gap-2">
              {((groupAnalysis.contested_groups as Array<Record<string, unknown>> | undefined) ?? []).map((item) => (
                <p key={String(item.group_id ?? "group")} className="inspector-body">
                  {String(item.role_label ?? "group")} · tension {Number(item.tension_after ?? 0).toFixed(2)} · polarization {Number(item.polarization_after ?? 0).toFixed(2)}
                </p>
              ))}
            </div>
          </div>
          <div className="session-thread-card">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Fracture Groups</p>
            <div className="mt-2 grid gap-2">
              {((groupAnalysis.fracture_groups as Array<Record<string, unknown>> | undefined) ?? []).map((item) => (
                <p key={String(item.group_id ?? "group")} className="inspector-body">
                  {String(item.role_label ?? "group")} · split {Number(item.split_risk ?? 0).toFixed(2)} · fracture {Number(item.cross_zone_fracture ?? 0).toFixed(2)}
                </p>
              ))}
            </div>
          </div>
          <div className="session-thread-card">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Ideology Blocks</p>
            <div className="mt-2 grid gap-2">
              {((emergentDynamics.ideology_blocks as Array<Record<string, unknown>> | undefined) ?? []).map((item, index) => (
                <p key={`${index}-${String(item.label ?? "block")}`} className="inspector-body">
                  {String(item.label ?? "block")} · divergence {Number(item.divergence ?? 0).toFixed(2)} · {String(item.coalition_signal ?? "n/a")}
                </p>
              ))}
            </div>
          </div>
        </div>
      </AppPanel>

      <AppPanel
        title={isKo ? "Lineage / Ideology Transition" : "Lineage / Ideology Transition"}
        subtitle={isKo ? "역할 집단이 시간에 따라 어떻게 재편되고 이동했는지" : "How role groups realigned and migrated over time"}
        bodyClassName="space-y-3"
      >
        <div className="grid gap-4 xl:grid-cols-2">
          <CompactGroupTable
            title={isKo ? "추적 역할" : "Tracked Roles"}
            emptyLabel={isKo ? "아직 lineage 추적 데이터가 없습니다." : "No lineage tracking data yet."}
            rows={lineageTrackedRows}
            columns={[
              { key: "role_label", label: isKo ? "역할" : "Role" },
              { key: "first_stance", label: isKo ? "시작" : "Start" },
              { key: "last_stance", label: isKo ? "현재" : "Current" },
              { key: "transition_count", label: isKo ? "전이 수" : "Transitions", numeric: true },
              { key: "lineage_score", label: isKo ? "점수" : "Score", numeric: true },
            ]}
          />
          <CompactGroupTable
            title={isKo ? "이념 이동" : "Ideology Migrations"}
            emptyLabel={isKo ? "뚜렷한 이념 이동이 아직 없습니다." : "No strong ideology migrations yet."}
            rows={ideologyMigrationRows}
            columns={[
              { key: "role_label", label: isKo ? "역할" : "Role" },
              { key: "from_stance", label: isKo ? "이전" : "From" },
              { key: "to_stance", label: isKo ? "이후" : "To" },
              { key: "transition_count", label: isKo ? "전이 수" : "Transitions", numeric: true },
              { key: "lineage_score", label: isKo ? "점수" : "Score", numeric: true },
            ]}
          />
        </div>
      </AppPanel>

      <AppPanel
        title={isKo ? "정책 메커니즘" : "Policy Mechanisms"}
        subtitle={isKo ? "정책이 어떤 채널로 집단과 구역에 전파됐는지" : "How policy propagated through channels into groups and zones"}
        bodyClassName="space-y-3"
      >
        <div className="grid gap-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <CompactGroupTable
            title={isKo ? "지배 채널" : "Dominant Channels"}
            emptyLabel={isKo ? "정책 채널 데이터가 아직 없습니다." : "No policy channel data yet."}
            rows={policyMechanismRows}
            columns={[
              { key: "channel", label: isKo ? "채널" : "Channel" },
              { key: "score", label: isKo ? "점수" : "Score", numeric: true },
            ]}
          />
          <div className="grid gap-2">
            {propagationPaths.length ? (
              propagationPaths.slice(0, 6).map((item, index) => (
                <div key={`path-${index}-${String(item.event_name ?? 'policy')}`} className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">{String(item.event_name ?? 'policy')}</p>
                    <span className="session-thread-card__meta">{String(item.dominant_channel ?? 'resource')}</span>
                  </div>
                  <p className="session-thread-card__prompt">
                    {String(item.group_label ?? 'group')} → {String(item.zone_label ?? 'zone')} · cohesion {Number(item.group_cohesion_delta ?? 0).toFixed(2)} · tension {Number(item.group_tension_delta ?? 0).toFixed(2)} · zΔ {Number(item.zone_z_delta ?? 0).toFixed(2)}
                  </p>
                  {(item.group_id || item.zone_id) && data?.world_id ? (
                    <div className="session-thread-card__actions">
                      <button type="button" className="app-button app-button--ghost" onClick={() => onOpenWorldAt(data.world_id)}>
                        {isKo ? "시뮬레이션에서 보기" : "Open in Simulation"}
                      </button>
                    </div>
                  ) : null}
                </div>
              ))
            ) : (
              <p className="text-sm text-slate-500">{isKo ? "정책 전파 경로가 아직 없습니다." : "No policy propagation paths yet."}</p>
            )}
          </div>
        </div>
      </AppPanel>

      <AppPanel
        title={isKo ? "정책-전이 브리지" : "Policy-to-Lineage Bridge"}
        subtitle={isKo ? "정책 채널이 어떤 집단 전이로 이어졌는지" : "Which policy channels mapped into collective stance transitions"}
        bodyClassName="space-y-3"
      >
        <CompactGroupTable
          title={isKo ? "브리지 경로" : "Bridge Paths"}
          emptyLabel={isKo ? "정책-전이 브리지가 아직 없습니다." : "No policy-to-lineage bridge yet."}
          rows={policyLineageBridgeRows}
          columns={[
            { key: "event_name", label: isKo ? "이벤트" : "Event" },
            { key: "dominant_channel", label: isKo ? "채널" : "Channel" },
            { key: "role_label", label: isKo ? "역할" : "Role" },
            { key: "to_stance", label: isKo ? "도착 입장" : "To" },
            { key: "bridge_strength", label: isKo ? "강도" : "Strength", numeric: true },
          ]}
        />
      </AppPanel>

      <AppPanel
        title={isKo ? "그룹 테이블" : "Group Tables"}
        subtitle={isKo ? "역할, 국가 페르소나, 구역 기준 표준 집단 요약" : "Standardized collective summary by role, persona country, and zone"}
        bodyClassName="space-y-3"
      >
        <div className="grid gap-4 xl:grid-cols-3">
          <CompactGroupTable
            title={isKo ? "역할" : "Roles"}
            emptyLabel={isKo ? "역할 집단 테이블이 아직 없습니다." : "No role table yet."}
            rows={roleTableRows}
            columns={[
              { key: "role_label", label: isKo ? "역할" : "Role" },
              { key: "stance_after", label: isKo ? "입장" : "Stance" },
              { key: "cohesion_after", label: isKo ? "응집" : "Cohesion", numeric: true },
              { key: "tension_after", label: isKo ? "긴장" : "Tension", numeric: true },
              { key: "cross_zone_fracture", label: isKo ? "균열" : "Fracture", numeric: true },
            ]}
          />
          <CompactGroupTable
            title={isKo ? "국가 페르소나" : "Persona Countries"}
            emptyLabel={isKo ? "국가 페르소나 테이블이 아직 없습니다." : "No persona-country table yet."}
            rows={personaCountryRows}
            columns={[
              { key: "persona_country", label: isKo ? "국가" : "Country" },
              { key: "count", label: isKo ? "수" : "Count", numeric: true },
              { key: "avg_belief_shift", label: isKo ? "평균 이동" : "Avg Shift", numeric: true },
              { key: "avg_z_delta", label: isKo ? "평균 zΔ" : "Avg zΔ", numeric: true },
            ]}
          />
          <CompactGroupTable
            title={isKo ? "구역" : "Zones"}
            emptyLabel={isKo ? "구역 테이블이 아직 없습니다." : "No zone table yet."}
            rows={zoneTableRows}
            columns={[
              { key: "zone_label", label: isKo ? "구역" : "Zone" },
              { key: "avg_z_delta", label: isKo ? "평균 zΔ" : "Avg zΔ", numeric: true },
              { key: "avg_energy_after", label: isKo ? "에너지" : "Energy", numeric: true },
              { key: "cell_count_after", label: isKo ? "셀 수" : "Cells", numeric: true },
            ]}
          />
        </div>
      </AppPanel>

      <AppPanel
        title="Causal Chains"
        subtitle="Event → group → zone → agent grounding for the strongest shifts"
        bodyClassName="space-y-3"
      >
        {causalChains.length ? (
          <div className="grid gap-3 xl:grid-cols-3">
            {causalChains.slice(0, 3).map((chain, index) => {
              const event = (chain.event ?? {}) as Record<string, unknown>;
              const group = (chain.group ?? {}) as Record<string, unknown>;
              const zone = (chain.zone ?? {}) as Record<string, unknown>;
              const agent = (chain.agent ?? {}) as Record<string, unknown>;
              return (
                <div key={`${index}-${String(chain.anchor_id ?? "chain")}`} className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">{String(chain.label ?? "causal chain")}</p>
                    <span className="session-thread-card__meta">t={Number(chain.t ?? 0).toFixed(0)}</span>
                  </div>
                  <div className="grid gap-2">
                    <p className="inspector-body">event: {String(event.label ?? "event")}</p>
                    <p className="inspector-body">group: {String(group.label ?? "group")} · {String(group.stance_after ?? "n/a")}</p>
                    <p className="inspector-body">zone: {String(zone.label ?? "zone")} · zΔ {Number(zone.avg_z_delta ?? 0).toFixed(2)}</p>
                    <p className="inspector-body">agent: {String(agent.label ?? "agent")} · shift {Number(agent.belief_shift_score ?? 0).toFixed(2)}</p>
                  </div>
                  <div className="session-thread-card__actions">
                    <button
                      type="button"
                      className="app-button app-button--ghost"
                      onClick={() => onOpenWorldAt(String(chain.world_id ?? worldId), Number(chain.t ?? 0) || null)}
                    >
                      {isKo ? "원인 사슬 열기" : "Open Causal Chain"}
                    </button>
                    <button
                      type="button"
                      className="app-button app-button--secondary"
                      onClick={() => createBranchAt(String(chain.world_id ?? worldId), Number(chain.t ?? 0), String(chain.label ?? "causal chain"))}
                    >
                      {isKo ? "여기서 브랜치 만들기" : "Branch from Here"}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        ) : (
          <p className="text-sm text-slate-500">원인 사슬이 아직 생성되지 않았습니다.</p>
        )}
      </AppPanel>

      <AppPanel
        title="Next Actions"
        subtitle="Take the review back into simulation"
        bodyClassName="space-y-3"
      >
        {Array.isArray(data?.next_actions) && data.next_actions.length ? (
          <div className="grid gap-2 md:grid-cols-3">
            {data.next_actions.map((item, index) => (
              <div key={`${index}-${String(item.label ?? "action")}`} className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">{String(item.label ?? "Action")}</p>
                  <span className="session-thread-card__meta">
                    {summaryRepairUsed
                      ? isKo
                        ? `주의 · repair ${summaryRepairCount}`
                        : `Caution · repair ${summaryRepairCount}`
                      : isKo
                        ? "신뢰도 양호"
                        : "Grounding OK"}
                  </span>
                </div>
                <p className="session-thread-card__prompt">{String(item.description ?? "")}</p>
                {summaryRepairUsed ? (
                  <p className="mt-2 text-[11px] text-amber-700">
                    {isKo ? "리뷰 grounding 보정:" : "Review grounding repair:"} {summaryRepairReason}
                  </p>
                ) : null}
                <div className="session-thread-card__actions">
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onOpenWorldAt(String(item.world_id ?? worldId), Number(item.t ?? 0) || null)}
                  >
                    {isKo ? "시뮬레이션에서 열기" : "Open in Simulation"}
                  </button>
                  {typeof item.t === "number" ? (
                    <button
                      type="button"
                      className="app-button app-button--secondary"
                      onClick={() => createBranchAt(String(item.world_id ?? worldId), Number(item.t ?? 0), String(item.label ?? "next action"))}
                    >
                      {isKo ? "액션 브랜치 만들기" : "Create Branch"}
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">리뷰 기반 후속 액션이 아직 생성되지 않았습니다.</p>
        )}
      </AppPanel>

      <AppPanel
        title={isKo ? "리뷰 기반 주입 프리셋" : "Review Injection Presets"}
        subtitle={isKo ? "리뷰 인사이트를 바로 다음 실험 주입으로 넘깁니다" : "Send review insights directly into the next simulation injection"}
        bodyClassName="space-y-3"
      >
        {Array.isArray(data?.inject_presets) && data.inject_presets.length ? (
          <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
            {data.inject_presets.map((preset, index) => (
              <div key={`${index}-${String(preset.label ?? "preset")}`} className="session-thread-card">
                <div className="session-thread-card__header">
                  <p className="session-thread-card__title">{String(preset.label ?? (isKo ? "주입 프리셋" : "Inject preset"))}</p>
                  <span className="session-thread-card__meta">
                    t={Number(preset.t ?? 0).toFixed(0)} · {summaryRepairUsed ? (isKo ? `repair ${summaryRepairCount}` : `repair ${summaryRepairCount}`) : (isKo ? "ok" : "ok")}
                  </span>
                </div>
                <p className="session-thread-card__prompt">{String(preset.description ?? "")}</p>
                {summaryRepairUsed ? (
                  <p className="mt-2 text-[11px] text-amber-700">
                    {isKo ? "이 추천은 citation repair 이후 생성되었습니다." : "This recommendation was generated after citation repair."}
                  </p>
                ) : (
                  <p className="mt-2 text-[11px] text-emerald-700">
                    {isKo ? "리뷰 grounding이 안정적으로 유지되었습니다." : "Review grounding remained stable for this recommendation."}
                  </p>
                )}
                <div className="session-thread-card__actions">
                  <button
                    type="button"
                    className="app-button app-button--ghost"
                    onClick={() => onQueueInjectPreset(String(preset.world_id ?? worldId), preset)}
                  >
                    {isKo ? "주입 패널로 보내기" : "Send to Injection Panel"}
                  </button>
                  <button
                    type="button"
                    className="app-button app-button--secondary"
                    onClick={async () => {
                      const sourceWorldId = String(preset.world_id ?? worldId);
                      const t = Number(preset.t ?? 0);
                      const branch = await createBranchAt(sourceWorldId, t, String(preset.label ?? "inject preset"));
                      onQueueInjectPreset(branch?.worldId ?? sourceWorldId, {
                        ...preset,
                        t: branch?.t ?? preset.t,
                        world_id: branch?.worldId ?? sourceWorldId,
                      });
                    }}
                  >
                    {isKo ? "브랜치 후 주입 준비" : "Branch + Queue Injection"}
                  </button>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-sm text-slate-500">{isKo ? "리뷰에서 생성된 주입 프리셋이 아직 없습니다." : "No review-driven injection presets are available yet."}</p>
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
            disabled={!filteredInterviewCandidates.length}
          >
            <option value="">Select agent/persona</option>
            {filteredInterviewCandidates.map((item) => (
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
        {deferredCandidates.length ? (
          <div className="grid gap-2 rounded-2xl border border-slate-200 bg-slate-50 p-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Persona Interview Matrix</p>
            <div className="grid gap-2 md:grid-cols-3">
              <select className="app-input" value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}>
                <option value="all">All roles</option>
                {roleOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <select className="app-input" value={zoneFilter} onChange={(event) => setZoneFilter(event.target.value)}>
                <option value="all">All zones</option>
                {zoneOptions.map((item) => (
                  <option key={item} value={item}>
                    {item}
                  </option>
                ))}
              </select>
              <select
                className="app-input"
                value={countryFilter}
                onChange={(event) => setCountryFilter(event.target.value)}
              >
                <option value="all">All countries</option>
                {countryOptions.map((item) => (
                  <option key={item || "unknown"} value={item}>
                    {item || "unknown"}
                  </option>
                ))}
              </select>
            </div>
            {batchInterviewSummary ? (
              <div className="grid gap-2 md:grid-cols-4">
                <MetricCard label="Filtered" value={String(batchInterviewSummary.count)} />
                <MetricCard label="Avg Shift" value={batchInterviewSummary.avgShift.toFixed(2)} />
                <MetricCard label="Avg zΔ" value={batchInterviewSummary.avgZDelta.toFixed(2)} />
                <MetricCard label="Avg Worldview" value={batchInterviewSummary.avgWorldview.toFixed(2)} />
              </div>
            ) : null}
            {selectedBatchCandidates.length ? (
              <div className="grid gap-3 md:grid-cols-2">
                <div className="session-thread-card">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Batch Compare · Roles</p>
                  <div className="mt-2 grid gap-2">
                    {batchRoleSummary.map((item) => (
                      <p key={`role-${item.label}`} className="inspector-body">
                        {item.label}: {item.count} personas · avg shift {item.avgShift.toFixed(2)} · avg zΔ {item.avgZDelta.toFixed(2)}
                      </p>
                    ))}
                  </div>
                </div>
                <div className="session-thread-card">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">Batch Compare · Zones</p>
                  <div className="mt-2 grid gap-2">
                    {batchZoneSummary.map((item) => (
                      <p key={`zone-${item.label}`} className="inspector-body">
                        {item.label}: {item.count} personas · avg shift {item.avgShift.toFixed(2)} · avg worldview {item.avgWorldview.toFixed(2)}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
            ) : null}
            <div className="grid gap-2">
              {filteredInterviewCandidates.slice(0, 8).map((item, index) => (
                <div
                  key={`${index}-${String(item.cell_id ?? "")}`}
                  className={`session-thread-card ${String(item.cell_id ?? "") === interviewCellId ? "border-sky-300 bg-sky-50" : ""}`}
                >
                  <div className="session-thread-card__header">
                    <button
                      type="button"
                      className="text-left"
                      onClick={() => setInterviewCellId(String(item.cell_id ?? ""))}
                    >
                      <p className="session-thread-card__title">
                        {String(item.role_label ?? item.role_key ?? "agent")}
                      </p>
                    </button>
                    <span className="session-thread-card__meta">
                      shift {Number(item.belief_shift_score ?? 0).toFixed(2)}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    {String(item.zone_label ?? item.zone_id ?? "zone")} · {String(item.persona_country ?? "n/a")} · zΔ {Number(item.z_delta ?? 0).toFixed(2)} · worldview {Number(item.worldview_shift ?? 0).toFixed(2)}
                  </p>
                  <div className="session-thread-card__actions">
                    <button
                      type="button"
                      className="app-button app-button--ghost"
                      onClick={() =>
                        setSelectedCompareIds((prev) =>
                          prev.includes(String(item.cell_id ?? ""))
                            ? prev.filter((value) => value !== String(item.cell_id ?? ""))
                            : [...prev, String(item.cell_id ?? "")].slice(-4)
                        )
                      }
                    >
                      {selectedCompareIds.includes(String(item.cell_id ?? "")) ? "Remove from Batch" : "Add to Batch"}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </AppPanel>

      <AppPanel
        title={isKo ? "세션 리뷰" : "Session Review"}
        subtitle={isKo ? "여러 world를 묶은 분석가 요약" : "Multi-world analyst summary"}
        bodyClassName="space-y-3"
      >
        {sessionReviewLoading ? <p className="text-sm text-slate-500">{isKo ? "세션 리뷰 불러오는 중…" : "Session review loading…"}</p> : null}
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
              <MetricCard label={isKo ? "월드 수" : "Worlds"} value={String(sessionReview.metrics.world_count ?? 0)} />
              <MetricCard label={isKo ? "평균 분열 위험" : "Avg Split Risk"} value={String(sessionReview.metrics.avg_split_risk ?? "0")} />
              <MetricCard label={isKo ? "평균 fracture" : "Avg Fracture"} value={String(sessionReview.metrics.avg_cross_zone_fracture ?? "0")} />
            </div>
            <div className="grid gap-3 md:grid-cols-3">
              <MetricCard
                label={isKo ? "주요 체제 전이" : "Dominant Regime"}
                value={String(sessionLineage.dominant_regime_transition ?? "stable")}
              />
              <MetricCard
                label={isKo ? "추적 역할" : "Tracked Roles"}
                value={String(sessionLineageRows.length)}
              />
              <MetricCard
                label={isKo ? "이념 이동" : "Migrations"}
                value={String(sessionMigrationRows.length)}
              />
            </div>
            <div className="grid gap-2 md:grid-cols-[200px_minmax(0,1fr)]">
              <select
                className="app-input"
                value={sessionObjective}
                onChange={(event) => setSessionObjective(event.target.value)}
              >
                <option value="balanced">{isKo ? "균형" : "Balanced"}</option>
                <option value="stability">{isKo ? "안정성" : "Stability"}</option>
                <option value="cohesion">{isKo ? "응집" : "Cohesion"}</option>
                <option value="polarization">{isKo ? "양극화" : "Polarization"}</option>
                <option value="fracture">{isKo ? "fracture" : "Fracture"}</option>
              </select>
              <p className="text-sm text-slate-500">
                현재 세션 랭킹 기준: <span className="font-medium text-slate-700">{String(sessionReview.metrics.objective ?? sessionObjective)}</span>
              </p>
            </div>
            {sessionReview.objective_explanation ? (
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "목표 기준 설명" : "Objective Explanation"}</p>
                <p className="mt-2 text-sm leading-6 text-slate-700">{sessionReview.objective_explanation}</p>
              </div>
            ) : null}
            {sessionReview.ranked_worlds?.length ? (
              <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "랭크된 월드" : "Ranked Worlds"}</p>
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
                          {isKo ? "월드 열기" : "Open World"}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="space-y-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "추천 비교" : "Recommended Comparisons"}</p>
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
                          {isKo ? "타깃 열기" : "Open Target"}
                        </button>
                        <button
                          type="button"
                          className="app-button app-button--ghost"
                          onClick={() => onOpenWorldAt(String(item.base_world_id ?? worldId))}
                        >
                          {isKo ? "기준 열기" : "Open Base"}
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
            <div className="grid gap-4 xl:grid-cols-2">
              <CompactGroupTable
                title={isKo ? "세션 Lineage 역할" : "Session Lineage Roles"}
                emptyLabel={isKo ? "세션 lineage 역할 데이터가 아직 없습니다." : "No session lineage role data yet."}
                rows={sessionLineageRows}
                columns={[
                  { key: "role_label", label: isKo ? "역할" : "Role" },
                  { key: "avg_lineage_score", label: isKo ? "평균 점수" : "Avg Score", numeric: true },
                  { key: "avg_transition_count", label: isKo ? "평균 전이" : "Avg Transition", numeric: true },
                  { key: "world_coverage", label: isKo ? "월드 수" : "Worlds", numeric: true },
                ]}
              />
              <CompactGroupTable
                title={isKo ? "세션 이념 이동" : "Session Ideology Migrations"}
                emptyLabel={isKo ? "세션 이념 이동 데이터가 아직 없습니다." : "No session migration data yet."}
                rows={sessionMigrationRows}
                columns={[
                  { key: "role_label", label: isKo ? "역할" : "Role" },
                  { key: "from_stance", label: isKo ? "이전" : "From" },
                  { key: "to_stance", label: isKo ? "이후" : "To" },
                  { key: "transition_count", label: isKo ? "전이 수" : "Transitions", numeric: true },
                ]}
              />
            </div>
            <CompactGroupTable
              title={isKo ? "세션 정책-전이 브리지" : "Session Policy-Lineage Bridge"}
              emptyLabel={isKo ? "세션 정책-전이 브리지 데이터가 아직 없습니다." : "No session policy-lineage bridge data yet."}
              rows={sessionPolicyBridgeRows}
              columns={[
                { key: "event_name", label: isKo ? "이벤트" : "Event" },
                { key: "role_label", label: isKo ? "역할" : "Role" },
                { key: "dominant_channel", label: isKo ? "채널" : "Channel" },
                { key: "transition_count", label: isKo ? "전이 수" : "Transitions", numeric: true },
                { key: "avg_bridge_strength", label: isKo ? "평균 강도" : "Avg Strength", numeric: true },
              ]}
            />
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
                {isKo ? "세션 질의" : "Ask Session"}
              </button>
            </div>
            {sessionQueryLoading ? <p className="text-sm text-slate-500">{isKo ? "세션 질의 처리 중…" : "Session query loading…"}</p> : null}
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
                      <p className="session-thread-card__title">{isKo ? "세션 답변" : "Session Answer"}</p>
                      <span className="session-thread-card__meta">{sessionQueryData.mode}</span>
                    </div>
                    <p className="session-thread-card__prompt">{sessionQueryData.answer}</p>
                  </div>
                  <div className="session-thread-card">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "근거" : "Evidence"}</p>
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
                    title={isKo ? "세션 그라운딩" : "Session Grounding"}
                    items={flattenGrounding(sessionQueryData.grounding)}
                    onOpenWorldAt={onOpenWorldAt}
                    worldId={worldId}
                  />
                  <div className="session-thread-card">
                    <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "세션 질의 출처 정보" : "Session Query Provenance"}</p>
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
          <p className="text-sm text-slate-500">{isKo ? "같은 세션에 world가 쌓이면 세션 단위 리뷰를 제공합니다." : "Session review appears when multiple worlds accumulate in the same session."}</p>
        )}
      </AppPanel>

      <AppPanel
        title={isKo ? "차이 질의" : "Diff Query"}
        subtitle={isKo ? "baseline과 target 차이를 묻기" : "Ask about baseline vs target"}
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
            {isKo ? "차이 질의" : "Ask Diff"}
          </button>
        </div>
        {diffQueryLoading ? <p className="text-sm text-slate-500">{isKo ? "차이 질의 처리 중…" : "Diff query loading…"}</p> : null}
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
                  <p className="session-thread-card__title">{isKo ? "차이 답변" : "Diff Answer"}</p>
                  <span className="session-thread-card__meta">{diffQueryData.mode}</span>
                </div>
                <p className="session-thread-card__prompt">{diffQueryData.answer}</p>
              </div>
              <div className="session-thread-card">
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-slate-500">{isKo ? "근거" : "Evidence"}</p>
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
              title={isKo ? "차이 그라운딩" : "Diff Grounding"}
              items={flattenGrounding(diffQueryData.grounding)}
              onOpenWorldAt={(wid, t) => onOpenWorldAt(wid || worldId, t)}
              worldId={worldId}
            />
          </div>
        ) : (
          <p className="text-sm text-slate-500">{isKo ? "baseline과 target 차이에 대해 자연어로 질문할 수 있습니다." : "Ask natural-language questions about baseline versus target."}</p>
        )}
      </AppPanel>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <AppPanel title={isKo ? "차이 리포트" : "Diff Report"} subtitle={isKo ? "기준 world와 현재 world 비교" : "Baseline vs current world"} bodyClassName="space-y-3">
          {diffLoading ? <p className="text-sm text-slate-500">{isKo ? "차이 리포트 불러오는 중…" : "Diff report loading…"}</p> : null}
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

        <AppPanel title="Diff Graph Lane" subtitle="Top group and zone gaps as quick visual bars" bodyClassName="space-y-3">
          {groupDriftRows.length ? (
            <div className="grid gap-2">
              {groupDriftRows.slice(0, 5).map((item, index) => {
                const value =
                  Math.abs(Number(item.cohesion_gap ?? 0)) +
                  Math.abs(Number(item.tension_gap ?? 0)) +
                  Math.abs(Number(item.split_risk_gap ?? 0));
                return (
                  <div key={`group-gap-${index}`} className="session-thread-card">
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">{String(item.role_label ?? item.group_id ?? "group")}</p>
                      <span className="session-thread-card__meta">impact {value.toFixed(2)}</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-200">
                      <div
                        className="h-2 rounded-full bg-sky-500"
                        style={{ width: `${Math.min(100, value * 45)}%` }}
                      />
                    </div>
                    <p className="session-thread-card__prompt">
                      cohesion {Number(item.cohesion_gap ?? 0).toFixed(2)} · tension {Number(item.tension_gap ?? 0).toFixed(2)} · split {Number(item.split_risk_gap ?? 0).toFixed(2)}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="text-sm text-slate-500">비교 world를 선택하면 집단 gap graph가 표시됩니다.</p>
          )}
          {zoneDriftRows.length ? (
            <div className="grid gap-2">
              {zoneDriftRows.slice(0, 4).map((item, index) => {
                const value = Math.abs(Number(item.avg_z_gap ?? 0)) + Math.abs(Number(item.avg_energy_gap ?? 0)) * 0.1;
                return (
                  <div key={`zone-gap-${index}`} className="session-thread-card">
                    <div className="session-thread-card__header">
                      <p className="session-thread-card__title">{String(item.zone_label ?? item.zone_id ?? "zone")}</p>
                      <span className="session-thread-card__meta">impact {value.toFixed(2)}</span>
                    </div>
                    <div className="h-2 rounded-full bg-slate-200">
                      <div
                        className="h-2 rounded-full bg-amber-500"
                        style={{ width: `${Math.min(100, value * 32)}%` }}
                      />
                    </div>
                    <p className="session-thread-card__prompt">
                      avg z {Number(item.avg_z_gap ?? 0).toFixed(2)} · energy {Number(item.avg_energy_gap ?? 0).toFixed(2)}
                    </p>
                  </div>
                );
              })}
            </div>
          ) : null}
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

        <AppPanel
          title="Validation Readout"
          subtitle="How to interpret mock long-run vs live smoke results"
          bodyClassName="space-y-3"
        >
          {Object.keys(validationReadout).length ? (
            <>
              <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
                      Confidence
                    </p>
                    <p className="mt-1 text-sm text-slate-700">
                      {String(validationReadout.current_confidence ?? "medium")} · profile hint{" "}
                      {String(validationReadout.runtime_profile_hint ?? "balanced")}
                    </p>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 xl:grid-cols-2">
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Mock Long-Horizon</p>
                    <span className="session-thread-card__meta">
                      {String(mockValidation.status ?? "validated-in-mock")}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    {String(mockValidation.headline ?? "Mock long-run validation summary unavailable.")}
                  </p>
                  <p className="inspector-body">{String(mockValidation.pattern ?? "")}</p>
                  <p className="text-xs text-slate-500">
                    {String(mockValidation.implication ?? "")}
                  </p>
                </div>

                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Live Smoke</p>
                    <span className="session-thread-card__meta">
                      {String(liveValidation.status ?? "healthy-but-small")}
                    </span>
                  </div>
                  <p className="session-thread-card__prompt">
                    {String(liveValidation.headline ?? "Live smoke validation summary unavailable.")}
                  </p>
                  <p className="inspector-body">{String(liveValidation.pattern ?? "")}</p>
                  <p className="text-xs text-slate-500">
                    {String(liveValidation.implication ?? "")}
                  </p>
                </div>
              </div>

              {validationNotes.length ? (
                <div className="grid gap-2">
                  {validationNotes.map((item, index) => (
                    <div key={`validation-note-${index}`} className="session-thread-card">
                      <p className="inspector-body">{item}</p>
                    </div>
                  ))}
                </div>
              ) : null}

              {validationNextChecks.length ? (
                <div className="rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.16em] text-amber-700">
                    Recommended Next Checks
                  </p>
                  <div className="mt-2 grid gap-2">
                    {validationNextChecks.map((item, index) => (
                      <p key={`validation-next-${index}`} className="text-sm text-amber-900">
                        {item}
                      </p>
                    ))}
                  </div>
                </div>
              ) : null}
            </>
          ) : (
            <p className="text-sm text-slate-500">검증 해석 요약이 아직 없습니다.</p>
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
          title={isKo ? "정책 메커니즘 차이" : "Policy Mechanism Delta"}
          subtitle={isKo ? "baseline과 target 사이에 어떤 전파 채널이 달라졌는지" : "Which propagation channels changed between baseline and target"}
          bodyClassName="space-y-3"
        >
          {diff ? (
            <div className="grid gap-4 xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
              <CompactGroupTable
                title={isKo ? "채널 격차" : "Channel Gaps"}
                emptyLabel={isKo ? "정책 채널 차이가 아직 없습니다." : "No policy channel gaps yet."}
                rows={diffPolicyChannelRows}
                columns={[
                  { key: "channel", label: isKo ? "채널" : "Channel" },
                  { key: "base_score", label: isKo ? "기준" : "Base", numeric: true },
                  { key: "target_score", label: isKo ? "대상" : "Target", numeric: true },
                  { key: "score_gap", label: isKo ? "격차" : "Gap", numeric: true },
                ]}
              />
              <div className="grid gap-2">
                {Array.isArray(diffPolicyMechanismDelta.target_paths) && (diffPolicyMechanismDelta.target_paths as Array<Record<string, unknown>>).length ? (
                  (diffPolicyMechanismDelta.target_paths as Array<Record<string, unknown>>).slice(0, 4).map((item, index) => (
                    <div key={`delta-path-${index}-${String(item.event_name ?? 'policy')}`} className="session-thread-card">
                      <div className="session-thread-card__header">
                        <p className="session-thread-card__title">{String(item.event_name ?? 'policy')}</p>
                        <span className="session-thread-card__meta">{String(item.dominant_channel ?? 'resource')}</span>
                      </div>
                      <p className="session-thread-card__prompt">
                        {String(item.group_label ?? 'group')} · {String(item.zone_label ?? 'zone')} · tension {Number(item.group_tension_delta ?? 0).toFixed(2)} · zΔ {Number(item.zone_z_delta ?? 0).toFixed(2)}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-slate-500">{isKo ? "정책 메커니즘 diff 경로가 아직 없습니다." : "No policy mechanism diff paths yet."}</p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">{isKo ? "diff report 생성 후 정책 메커니즘 차이를 볼 수 있습니다." : "Generate a diff report to inspect policy mechanism deltas."}</p>
          )}
        </AppPanel>

        <AppPanel
          title={isKo ? "디프 그룹 테이블" : "Diff Group Tables"}
          subtitle={isKo ? "baseline과 target의 역할, 국가 페르소나, 구역 차이" : "Role, persona-country, and zone deltas between baseline and target"}
          bodyClassName="space-y-3"
        >
          {diff ? (
            <div className="grid gap-4 xl:grid-cols-3">
              <CompactGroupTable
                title={isKo ? "역할 차이" : "Role Gaps"}
                emptyLabel={isKo ? "역할 차이가 아직 없습니다." : "No role gaps yet."}
                rows={groupDriftRows}
                columns={[
                  { key: "role_label", label: isKo ? "역할" : "Role" },
                  { key: "cohesion_gap", label: isKo ? "응집Δ" : "CohesionΔ", numeric: true },
                  { key: "tension_gap", label: isKo ? "긴장Δ" : "TensionΔ", numeric: true },
                  { key: "split_risk_gap", label: isKo ? "분열Δ" : "SplitΔ", numeric: true },
                ]}
              />
              <CompactGroupTable
                title={isKo ? "국가 페르소나 차이" : "Persona Country Gaps"}
                emptyLabel={isKo ? "국가 페르소나 차이가 아직 없습니다." : "No persona-country gaps yet."}
                rows={diffPersonaRows}
                columns={[
                  { key: "persona_country", label: isKo ? "국가" : "Country" },
                  { key: "avg_belief_shift_gap", label: isKo ? "이동Δ" : "ShiftΔ", numeric: true },
                  { key: "avg_z_delta_gap", label: isKo ? "zΔ" : "zΔ", numeric: true },
                  { key: "count_gap", label: isKo ? "수Δ" : "CountΔ", numeric: true },
                ]}
              />
              <CompactGroupTable
                title={isKo ? "구역 차이" : "Zone Gaps"}
                emptyLabel={isKo ? "구역 차이가 아직 없습니다." : "No zone gaps yet."}
                rows={diffZoneTableRows}
                columns={[
                  { key: "zone_label", label: isKo ? "구역" : "Zone" },
                  { key: "avg_z_gap", label: isKo ? "평균 zΔ" : "Avg zΔ", numeric: true },
                  { key: "avg_energy_gap", label: isKo ? "에너지Δ" : "EnergyΔ", numeric: true },
                  { key: "cell_count_gap", label: isKo ? "셀Δ" : "CellsΔ", numeric: true },
                ]}
              />
            </div>
          ) : (
            <p className="text-sm text-slate-500">{isKo ? "diff report 생성 후 그룹 테이블 차이를 볼 수 있습니다." : "Generate a diff report to inspect group-table deltas."}</p>
          )}
        </AppPanel>

        <AppPanel
          title={isKo ? "Lineage Delta" : "Lineage Delta"}
          subtitle={isKo ? "baseline과 target 사이 이념 전이 차이" : "Ideology transition differences between baseline and target"}
          bodyClassName="space-y-3"
        >
          {diff ? (
            <>
              <div className="grid gap-3 md:grid-cols-2">
                <MetricCard
                  label={isKo ? "기준 체제 전이" : "Base Regime"}
                  value={String(diffLineageDelta.base_regime_transition ?? "stable")}
                />
                <MetricCard
                  label={isKo ? "대상 체제 전이" : "Target Regime"}
                  value={String(diffLineageDelta.target_regime_transition ?? "stable")}
                />
              </div>
              <CompactGroupTable
                title={isKo ? "전이 격차" : "Transition Gaps"}
                emptyLabel={isKo ? "lineage diff가 아직 없습니다." : "No lineage diff yet."}
                rows={diffLineageRows}
                columns={[
                  { key: "role_label", label: isKo ? "역할" : "Role" },
                  { key: "transition_gap", label: isKo ? "전이Δ" : "TransitionΔ", numeric: true },
                  { key: "lineage_score_gap", label: isKo ? "점수Δ" : "ScoreΔ", numeric: true },
                  { key: "polarization_delta_gap", label: isKo ? "분극Δ" : "PolarizationΔ", numeric: true },
                ]}
              />
            </>
          ) : (
            <p className="text-sm text-slate-500">{isKo ? "diff report 생성 후 lineage 차이를 볼 수 있습니다." : "Generate a diff report to inspect lineage deltas."}</p>
          )}
        </AppPanel>

        <AppPanel
          title={isKo ? "정책-전이 브리지 차이" : "Policy-Lineage Bridge Delta"}
          subtitle={isKo ? "어떤 정책 채널이 어떤 집단 전이를 더 강하게 만들었는지" : "Which policy channels produced stronger stance transitions"}
          bodyClassName="space-y-3"
        >
          {diff ? (
            <CompactGroupTable
              title={isKo ? "브리지 격차" : "Bridge Gaps"}
              emptyLabel={isKo ? "정책-전이 브리지 차이가 아직 없습니다." : "No policy-lineage bridge gaps yet."}
              rows={diffPolicyLineageRows}
              columns={[
                { key: "event_name", label: isKo ? "이벤트" : "Event" },
                { key: "dominant_channel", label: isKo ? "채널" : "Channel" },
                { key: "role_label", label: isKo ? "역할" : "Role" },
                { key: "transition_gap", label: isKo ? "전이Δ" : "TransitionΔ", numeric: true },
                { key: "bridge_strength_gap", label: isKo ? "강도Δ" : "StrengthΔ", numeric: true },
              ]}
            />
          ) : (
            <p className="text-sm text-slate-500">{isKo ? "diff report 생성 후 정책-전이 브리지 차이를 볼 수 있습니다." : "Generate a diff report to inspect policy-lineage bridge deltas."}</p>
          )}
        </AppPanel>

        <AppPanel
          title="Side-by-Side Worldview Lane"
          subtitle="Baseline and target emergent curves in one comparison lane"
          bodyClassName="space-y-3"
        >
          {baseWorldviewCurve.length || targetWorldviewCurve.length ? (
            <div className="grid gap-3">
              <div className="grid gap-2 md:grid-cols-2">
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Baseline Curve</p>
                    <span className="session-thread-card__meta">{diff?.base_world_id ?? "base"}</span>
                  </div>
                  <div className="grid gap-1">
                    {baseWorldviewCurve.slice(-6).map((item, index) => (
                      <p key={`base-curve-${index}`} className="inspector-body">
                        t={Number(item.t ?? 0).toFixed(0)} · avg z {Number(item.avg_z ?? 0).toFixed(2)} · cells {Number(item.cell_count ?? 0)}
                      </p>
                    ))}
                  </div>
                </div>
                <div className="session-thread-card">
                  <div className="session-thread-card__header">
                    <p className="session-thread-card__title">Target Curve</p>
                    <span className="session-thread-card__meta">{diff?.target_world_id ?? "target"}</span>
                  </div>
                  <div className="grid gap-1">
                    {targetWorldviewCurve.slice(-6).map((item, index) => (
                      <p key={`target-curve-${index}`} className="inspector-body">
                        t={Number(item.t ?? 0).toFixed(0)} · avg z {Number(item.avg_z ?? 0).toFixed(2)} · cells {Number(item.cell_count ?? 0)}
                      </p>
                    ))}
                  </div>
                </div>
              </div>
              <div className="session-thread-card">
                <p className="inspector-body">
                  baseline과 target의 worldview/elevation curve를 같은 레인에서 읽으면서, 어느 시점부터 장기 drift가 갈라졌는지 빠르게 확인할 수 있습니다.
                </p>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">나란히 비교할 worldview curve가 아직 없습니다.</p>
          )}
        </AppPanel>

        <AppPanel
          title="Diff-to-Action"
          subtitle="Use diff and review insight to decide the next intervention"
          bodyClassName="space-y-3"
        >
          {diff ? (
            <div className="grid gap-2">
              <div className="session-thread-card">
                <p className="inspector-body">
                  strongest group gap: {String(largestGroupShiftGap.target_role_label ?? largestGroupShiftGap.base_role_label ?? "n/a")} · cohesion {Number(largestGroupShiftGap.cohesion_gap ?? 0).toFixed(2)} · tension {Number(largestGroupShiftGap.tension_gap ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="session-thread-card">
                <p className="inspector-body">
                  strongest zone gap: {String(largestZoneShiftGap.target_zone_label ?? largestZoneShiftGap.base_zone_label ?? "n/a")} · avg z {Number(largestZoneShiftGap.avg_z_gap ?? 0).toFixed(2)}
                </p>
              </div>
              <div className="session-thread-card__actions">
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => onOpenWorldAt(diff.target_world_id, Number((targetTurningPoints[0] as Record<string, unknown> | undefined)?.t ?? 0) || null)}
                >
                  Open Target Turning Point
                </button>
                <button
                  type="button"
                  className="app-button app-button--ghost"
                  onClick={() => onOpenView("simulation")}
                >
                  Return to Simulation
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">diff를 만든 뒤 다음 실험 액션을 정할 수 있습니다.</p>
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

        <AppPanel title="Repair Signals" subtitle="Citation repair visibility" bodyClassName="space-y-3">
          {data ? (
            <div className="grid gap-3">
              <MetricCard
                label="Summary Repair"
                value={String(Boolean((data.review_meta.summary as Record<string, unknown>)?.repair_used))}
              />
              <MetricCard
                label="Summary Repair Count"
                value={String((data.review_meta.summary as Record<string, unknown>)?.repair_count ?? 0)}
              />
              <MetricCard
                label="Summary Repair Reason"
                value={String((data.review_meta.summary as Record<string, unknown>)?.repair_reason ?? "none")}
              />
              {diff ? (
                <>
                  <MetricCard
                    label="Diff Repair"
                    value={String(Boolean((diff.review_meta.diff as Record<string, unknown>)?.repair_used))}
                  />
                  <MetricCard
                    label="Diff Repair Count"
                    value={String((diff.review_meta.diff as Record<string, unknown>)?.repair_count ?? 0)}
                  />
                  <MetricCard
                    label="Diff Repair Reason"
                    value={String((diff.review_meta.diff as Record<string, unknown>)?.repair_reason ?? "none")}
                  />
                </>
              ) : null}
              {queryData ? (
                <>
                  <MetricCard
                    label="Query Repair"
                    value={String(Boolean((queryData.review_meta.query as Record<string, unknown>)?.repair_used))}
                  />
                  <MetricCard
                    label="Query Repair Reason"
                    value={String((queryData.review_meta.query as Record<string, unknown>)?.repair_reason ?? "none")}
                  />
                </>
              ) : null}
              {sessionReview ? (
                <>
                  <MetricCard
                    label="Session Repair"
                    value={String(Boolean((sessionReview.review_meta.summary as Record<string, unknown>)?.repair_used))}
                  />
                  <MetricCard
                    label="Session Repair Reason"
                    value={String((sessionReview.review_meta.summary as Record<string, unknown>)?.repair_reason ?? "none")}
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

function uniqueSorted(values: string[]) {
  return Array.from(new Set(values.filter((item) => item.trim().length > 0))).sort((left, right) =>
    left.localeCompare(right)
  );
}

function average(values: number[]) {
  if (!values.length) return 0;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function summarizeBatchBy(items: Array<Record<string, unknown>>, key: string) {
  const grouped = new Map<
    string,
    { count: number; shift: number; z: number; worldview: number }
  >();
  for (const item of items) {
    const label = String(item[key] ?? "unknown");
    const current = grouped.get(label) ?? { count: 0, shift: 0, z: 0, worldview: 0 };
    current.count += 1;
    current.shift += Number(item.belief_shift_score ?? 0);
    current.z += Math.abs(Number(item.z_delta ?? 0));
    current.worldview += Number(item.worldview_shift ?? 0);
    grouped.set(label, current);
  }
  return Array.from(grouped.entries())
    .map(([label, value]) => ({
      label,
      count: value.count,
      avgShift: value.shift / Math.max(1, value.count),
      avgZDelta: value.z / Math.max(1, value.count),
      avgWorldview: value.worldview / Math.max(1, value.count),
    }))
    .sort((left, right) => right.avgShift - left.avgShift)
    .slice(0, 4);
}

type CompactColumn = { key: string; label: string; numeric?: boolean };

function CompactGroupTable({
  title,
  emptyLabel,
  rows,
  columns,
}: {
  title: string;
  emptyLabel: string;
  rows: Array<Record<string, unknown>>;
  columns: CompactColumn[];
}) {
  return (
    <div className="session-thread-card">
      <div className="session-thread-card__header">
        <p className="session-thread-card__title">{title}</p>
        <span className="session-thread-card__meta">{rows.length}</span>
      </div>
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="min-w-full text-left text-xs text-slate-600">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                {columns.map((column) => (
                  <th key={column.key} className="px-2 py-2">{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 6).map((row, index) => (
                <tr key={`${index}-${String(row[columns[0]?.key ?? 'row'] ?? index)}`} className="border-b border-slate-100">
                  {columns.map((column) => {
                    const raw = row[column.key];
                    const value = column.numeric ? Number(raw ?? 0).toFixed(2) : String(raw ?? 'n/a');
                    return (
                      <td key={column.key} className="px-2 py-2">
                        {value}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="text-sm text-slate-500">{emptyLabel}</p>
      )}
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
