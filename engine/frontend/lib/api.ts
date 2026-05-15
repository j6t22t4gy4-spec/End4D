/**
 * Organic4D Engine — API 클라이언트 (Phase 4.5)
 * IMPLEMENTATION_SEQUENCE: fetch /worlds, /snapshots
 */

const API_BASE =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_URL
    ? process.env.NEXT_PUBLIC_API_URL.replace(/\/$/, "")
    : "http://localhost:8000";

export type CellSnapshot = {
  cell_id: string;
  x: number;
  y: number;
  z: number;
  t: number;
  energy: number;
  gene_vec?: number[];
  emotion_vec: number[];
  thought_vec?: number[];
  worldview_vec?: number[];
  role_key?: string;
  role_label?: string;
  persona_id?: string;
  persona_text?: string;
  persona_country?: string;
  persona_attrs?: Record<string, unknown>;
  zone_id?: string;
  zone_label?: string;
  zone_influence?: number;
  zone_friction?: number;
  short_memory?: Array<Record<string, unknown>>;
  long_memory?: Array<Record<string, unknown>>;
  behavior_log?: Array<Record<string, unknown>>;
  interaction_events?: Array<Record<string, unknown>>;
  action_state?: Record<string, unknown>;
};

export type IntraTSceneEvent = {
  scene_id: string;
  t: number;
  start_t?: number;
  scene_t?: number;
  scene_index?: number;
  scene_count?: number;
  scene_type: string;
  interaction_type?: "positive" | "negative" | "hostile" | "dialogue" | string;
  source_id?: string;
  source_label?: string;
  target_ids?: string[];
  target_label?: string;
  group_ids?: string[];
  summary?: string;
  narrative_reason?: string;
  scenario_relevance?: string;
  agent_context?: Record<string, unknown>;
  sentiment?: string;
  pressure_delta?: number;
  relationship_delta?: number;
  visual_hint?: Record<string, unknown>;
};

export type IntraTSceneMetrics = {
  t?: number;
  start_t?: number;
  scenes_per_t?: number;
  agent_participation_rate?: number;
  relationship_event_count?: number;
  hostile_event_count?: number;
  positive_event_count?: number;
  dead_timestep_rate?: number;
  narrative_continuity_score?: number;
  narrative_specificity_score?: number;
  scenario_link_rate?: number;
  scene_quality_score?: number;
  scene_quality_grade?: string;
  quality_warnings?: string[];
  pressure_delta_abs_sum?: number;
};

export type AgentInterviewResponse = {
  world_id: string;
  cell_id: string;
  question: string;
  answer: string;
  evidence: string[];
  confidence_notes: string[];
  mode: string;
  grounding: Record<string, ReviewGroundingItem[]>;
  citations: ReviewGroundingItem[];
  interview_meta: Record<string, unknown>;
};

export type SnapshotResponse = {
  world_id: string;
  t: number;
  cells: CellSnapshot[];
  scene_events?: IntraTSceneEvent[];
  scene_metrics?: IntraTSceneMetrics;
};

export type SnapshotsListResponse = {
  world_id: string;
  available_t: number[];
};

export type WorldMeta = {
  world_id: string;
  t_max: number;
  status: string;
  genesis_prompt?: string | null;
  genesis_rationale?: string | null;
  role_catalog?: string[];
  t_step_semantic?: string;
  t_step_unit?: string;
  nutrient_per_step?: number;
  persona_country?: string;
  persona_source?: string;
  persona_count?: number;
  persona_distribution_summary?: Record<string, unknown>;
  simulation_config?: Record<string, unknown>;
  group_state?: Record<string, unknown>;
  cached_review_summary?: ReviewSummaryResponse | null;
};

export type CollectiveDynamicsListItem = {
  group_id: string;
  group_label: string;
  fracture_risk?: number;
  tension?: number;
  drift_velocity?: number;
  cohesion?: number;
};

export type CollectiveDynamicsAxisSummary = {
  count: number;
  avg_cohesion: number;
  avg_tension: number;
  avg_fracture_risk: number;
  avg_drift_velocity: number;
  top_fracturing: CollectiveDynamicsListItem[];
  top_drifting: CollectiveDynamicsListItem[];
};

export type CollectiveDynamicsSummary = {
  role: CollectiveDynamicsAxisSummary;
  zone: CollectiveDynamicsAxisSummary;
};

export type PersonaPreviewItem = {
  persona_id: string;
  persona_text: string;
  role_key: string;
  role_label: string;
  country: string;
  attrs: Record<string, unknown>;
};

export type PersonaSource = {
  country: string;
  source: string;
  dataset_id: string;
  path: string;
  license: string;
  url: string;
  attribution_required: boolean;
  citation: string;
  configured: boolean;
};

export type PersonaPreviewResponse = {
  world_id: string;
  persona_count: number;
  source: PersonaSource;
  items: PersonaPreviewItem[];
};

export type RuntimePack = {
  pack_id: string;
  kind: string;
  country: string;
  version: string;
  relative_path: string;
  path: string;
  installed: boolean;
  license: string;
  source_url: string;
  dataset_id: string;
  updated_at: string;
  installed_at?: string;
  pinned?: boolean;
  pinned_version?: string;
  validated_at?: string;
  validation?: Record<string, unknown>;
  verification?: Record<string, unknown>;
  history?: Array<Record<string, unknown>>;
  description: string;
};

export type RuntimeLlmStatus = {
  enabled: boolean;
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  configured_via: string;
  runtime_profile: string;
  strict_mode: string;
  ui_language: string;
};

export type RuntimeLlmRun = {
  task: string;
  provider: string;
  model: string;
  prompt_version: string;
  prompt_count_in: number;
  prompt_count_sent: number;
  prompt_count_skipped_by_task_budget: number;
  prompt_count_skipped_by_cycle_budget: number;
  task_budget: number;
  task_priority: number;
  cycle_key: string;
  cycle_budget_total: number;
  cycle_budget_remaining_before: number;
  cycle_budget_remaining_after: number;
  used_fallback: boolean;
  fallback_reason: string;
};

export type RuntimeLlmTotals = {
  calls: number;
  prompt_count_in: number;
  prompt_count_sent: number;
  prompt_count_skipped_by_task_budget: number;
  prompt_count_skipped_by_cycle_budget: number;
  fallback_calls: number;
};

export type RuntimeLlmHealth = {
  status: string;
  reason: string;
  recent_call_count: number;
  live_call_count: number;
  live_call_rate: number;
  recent_fallback_count: number;
  recent_fallback_rate: number;
  last_fallback_reason: string;
  dominant_failure_reason: string;
  live_streak: number;
  fallback_streak: number;
  stability_score: number;
};

export type RuntimeLlmTaskInsight = {
  task: string;
  calls: number;
  live_calls: number;
  fallback_calls: number;
  live_call_rate: number;
  prompt_live_rate: number;
  status: string;
  recommendation: string;
  top_fallback_reasons: Array<{ reason: string; count: number }>;
};

export type RuntimeLlmRepairTask = {
  task: string;
  repair_count: number;
  top_reasons: Array<{ reason: string; count: number }>;
};

export type RuntimeLlmRepairSummary = {
  total_repairs: number;
  task_repairs: RuntimeLlmRepairTask[];
  top_reasons: Array<{ reason: string; count: number }>;
};

export type RuntimeLlmRuntime = {
  provider: string;
  model: string;
  strict_mode: string;
  cycle_prompt_budget: number;
  agent_sample_size: number;
  dialogue_max_pairs: number;
  group_deliberation_max_groups: number;
  task_budgets: Record<string, number>;
  task_live_floors: Record<string, number>;
  task_priorities: Record<string, number>;
  scheduler: Record<string, unknown>;
  health: RuntimeLlmHealth;
  recent_runs: RuntimeLlmRun[];
  task_totals: Record<string, RuntimeLlmTotals>;
  task_insights: RuntimeLlmTaskInsight[];
  degraded_tasks: string[];
  fallback_reason_counts: Record<string, number>;
  recommended_actions: string[];
  repair_summary: RuntimeLlmRepairSummary;
  optimizer: Record<string, unknown>;
};

export type LocalRuntimeStatus = {
  runtime_profile: string;
  state_dir: string;
  data_cache_dir: string;
  manifest_path: string;
  remote_manifest_url: string;
  llm: RuntimeLlmStatus;
  llm_runtime: RuntimeLlmRuntime;
  installed_pack_count: number;
  available_countries: string[];
  packs: RuntimePack[];
};

export type RuntimeLlmConfigResponse = {
  enabled: boolean;
  provider: string;
  model: string;
  base_url: string;
  has_api_key: boolean;
  temperature: number;
  timeout_s: number;
  configured_via: string;
  runtime_profile: string;
  strict_mode: string;
  cycle_prompt_budget: number;
  agent_sample_size: number;
  dialogue_max_pairs: number;
  group_deliberation_max_groups: number;
  task_budgets: Record<string, number>;
  task_priorities: Record<string, number>;
  ui_language: string;
};

export type RuntimeLlmTestResponse = {
  ok: boolean;
  mode: string;
  provider: string;
  model: string;
  used_fallback: boolean;
  fallback_reason: string;
  preview: string;
  diagnosis: string;
  suggestions: string[];
};

export type DataPackVerifyResponse = {
  pack_id: string;
  exists: boolean;
  dataset_id: string;
  version: string;
  verified_at: string;
  schema_health: string;
  field_coverage: Record<string, unknown>;
  sample_roles: string[];
  sample_regions: string[];
  country_consistency: number;
  ready_for_genesis: boolean;
};

export type DataPackInstallResponse = {
  pack_id: string;
  installed: boolean;
  exists: boolean;
  row_count_estimate: number;
  sample_error: string;
  validated_at: string;
  version: string;
};

export type DataPackPinResponse = {
  pack_id: string;
  pinned: boolean;
  pinned_version: string;
  pinned_at: string;
};

export type DataPackRollbackResponse = {
  pack_id: string;
  rolled_back: boolean;
  version: string;
  history_index: number;
  updated_at: string;
};

export type DataPackDiffResponse = {
  pack_id: string;
  history_index: number;
  selected_action: string;
  selected_at: string;
  changes: Array<Record<string, unknown>>;
  verification_changes: Array<Record<string, unknown>>;
};

export type AgentGroupSummary = {
  group_id: string;
  role_key: string;
  role_label: string;
  cell_count: number;
  total_energy: number;
  avg_energy: number;
  dominant_emotion: string;
  avg_emotion_magnitude: number;
  countries: Record<string, number>;
  recent_memory_count: number;
};

export type AgentSummaryResponse = {
  world_id: string;
  t: number;
  group_count: number;
  cell_count: number;
  groups: AgentGroupSummary[];
};

export type GroupBeliefPoint = {
  t: number;
  stance: string;
  count: number;
  cohesion: number;
  tension: number;
  fracture_risk: number;
  polarization: number;
  drift_velocity: number;
  collective_pressure: number;
  pressure_bucket: string;
  stance_signature: Record<string, number>;
};

export type GroupBeliefTrajectory = {
  group_kind: "role" | "zone";
  group_id: string;
  group_label: string;
  points: GroupBeliefPoint[];
  deltas: Record<string, number>;
  latest_stance: string;
  latest_pressure: number;
  member_ids: string[];
};

export type GroupBeliefTrajectoryResponse = {
  world_id: string;
  group_kind: "role" | "zone";
  t_min: number;
  t_max: number;
  point_count: number;
  group_count: number;
  groups: GroupBeliefTrajectory[];
};

export type CreateWorldResult = {
  world_id: string;
  t_max: number;
  initial_cell_count: number;
  rationale: string;
  role_catalog: string[];
  t_step_semantic: string;
  t_step_unit: string;
  nutrient_per_step: number;
  persona_country: string;
  persona_source: string;
  persona_count: number;
  session_id: string;
  simulation_config: Record<string, unknown>;
  persona_distribution_summary: Record<string, unknown>;
};

export type GodModePayload = {
  enabled: boolean;
  auto_roles_from_personas?: boolean;
  overrides?: {
    t_max?: number;
    initial_cell_count?: number;
    role_catalog?: string[];
    simulation_mode?: "precision" | "swarm";
    t_step_semantic?: string;
    t_step_unit?: string;
    nutrient_per_step?: number;
    persona_country?: string;
    persona_source?: string;
  };
  engine_params?: {
    zone_count?: number;
    zone_layout?: string;
    zone_spacing?: number;
    zone_influence_step?: number;
    zone_friction_step?: number;
    z_mode?: string;
    z_weight?: number;
    z_scale?: number;
    simulation_mode?: "precision" | "swarm";
    swarm_llm_mode?: "packet" | "agent";
    swarm_tier_model?: Record<string, unknown>;
  };
};

export type SessionWorldSummary = {
  world_id: string;
  status: string;
  created_at: string;
  genesis_prompt?: string | null;
  persona_country: string;
  config_version: string;
  session_id: string;
};

export type SessionSummary = {
  session_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  world_count: number;
  latest_world_id: string;
  worlds: SessionWorldSummary[];
};

export type TimelineAnnotation = {
  t: number;
  label: string;
  reason: string;
  severity: string;
};

export type ReviewGroundingItem = {
  anchor_id: string;
  kind: string;
  label: string;
  reason: string;
  t?: number | null;
  group_id?: string | null;
  zone_id?: string | null;
  cell_id?: string | null;
  world_id?: string | null;
};

export type ReviewSummaryResponse = {
  world_id: string;
  headline: string;
  summary: string;
  summary_mode: string;
  key_events: string[];
  causal_analysis: string[];
  decision_implications: string[];
  watch_items: string[];
  highlights: string[];
  overall_signal: string;
  outcome: string;
  timeline_annotations: TimelineAnnotation[];
  annotation_mode: string;
  metrics: Record<string, unknown>;
  stance_groups: Array<Record<string, unknown>>;
  belief_trajectory: Record<string, unknown>;
  decision_influence: Record<string, unknown>;
  group_analysis: Record<string, unknown>;
  group_tables: Record<string, unknown>;
  lineage_summary: Record<string, unknown>;
  emergent_dynamics: Record<string, unknown>;
  validation_readout: Record<string, unknown>;
  policy_mechanisms: Record<string, unknown>;
  policy_lineage_bridge: Record<string, unknown>;
  zone_z_summary: Array<Record<string, unknown>>;
  top_z_movers: Array<Record<string, unknown>>;
  policy_events: Array<Record<string, unknown>>;
  belief_graph: Record<string, Array<Record<string, unknown>>>;
  causal_chains: Array<Record<string, unknown>>;
  next_actions: Array<Record<string, unknown>>;
  inject_presets: Array<Record<string, unknown>>;
  grounding: Record<string, ReviewGroundingItem[]>;
  citations: Record<string, ReviewGroundingItem[]>;
  review_meta: Record<string, unknown>;
};

export type ReviewDiffResponse = {
  base_world_id: string;
  target_world_id: string;
  headline: string;
  summary: string;
  diff_mode: string;
  key_deltas: string[];
  causal_comparison: string[];
  decision_implications: string[];
  compared_metrics: Record<string, unknown>;
  causal_chains: Array<Record<string, unknown>>;
  citations: Record<string, ReviewGroundingItem[]>;
  review_meta: Record<string, unknown>;
};

export type ReviewQueryResponse = {
  world_id: string;
  question: string;
  answer: string;
  evidence: string[];
  follow_up: string[];
  confidence_notes: string[];
  mode: string;
  grounding: Record<string, ReviewGroundingItem[]>;
  citations: ReviewGroundingItem[];
  review_meta: Record<string, unknown>;
};

export type ReviewDiffQueryResponse = {
  base_world_id: string;
  target_world_id: string;
  question: string;
  answer: string;
  evidence: string[];
  follow_up: string[];
  confidence_notes: string[];
  mode: string;
  grounding: Record<string, ReviewGroundingItem[]>;
  citations: ReviewGroundingItem[];
  review_meta: Record<string, unknown>;
};

export type SessionReviewResponse = {
  session_id: string;
  title: string;
  headline: string;
  summary: string;
  review_mode: string;
  key_findings: string[];
  decision_implications: string[];
  objective_explanation: string;
  metrics: Record<string, unknown>;
  group_tables: Record<string, unknown>;
  lineage_summary: Record<string, unknown>;
  policy_lineage_bridge: Record<string, unknown>;
  strongest_worlds: Array<Record<string, unknown>>;
  ranked_worlds: Array<Record<string, unknown>>;
  recommended_pairs: Array<Record<string, unknown>>;
  grounding: Record<string, Array<Record<string, unknown>>>;
  citations: Record<string, ReviewGroundingItem[]>;
  review_meta: Record<string, unknown>;
};

export type SessionReviewQueryResponse = {
  session_id: string;
  question: string;
  answer: string;
  evidence: string[];
  follow_up: string[];
  confidence_notes: string[];
  mode: string;
  grounding: Record<string, ReviewGroundingItem[]>;
  citations: ReviewGroundingItem[];
  review_meta: Record<string, unknown>;
};

export type WorldChatTargetType = "world" | "role" | "zone" | "agent";

export type WorldChatContext = {
  t?: number | null;
  compare_t?: number | null;
  target_type?: WorldChatTargetType;
  cell_id?: string | null;
  role_key?: string | null;
  zone_id?: string | null;
};

export type WorldChatGroundingItem = {
  anchor_id: string;
  kind: string;
  label: string;
  reason?: string;
  t?: number | null;
  cell_id?: string | null;
  role_key?: string | null;
  zone_id?: string | null;
};

export type WorldChatResponse = {
  world_id: string;
  session_id: string;
  message_id: string;
  question: string;
  answer: string;
  evidence: string[];
  follow_up: string[];
  confidence_notes: string[];
  mode: string;
  context: Record<string, unknown>;
  metadata: Record<string, unknown>;
  grounding: Record<string, WorldChatGroundingItem[]>;
  citations: WorldChatGroundingItem[];
  chat_meta: Record<string, unknown>;
};

export type RestoreWorldResponse = {
  source_world_id: string;
  world_id: string;
  restored_t: number;
  resumed: boolean;
  final_t: number;
  cell_count: number;
  snapshots_cleared: number;
  config_version: string;
  comparison_meta: Record<string, unknown>;
};

export type DeleteWorldResponse = {
  world_id: string;
  deleted: boolean;
};

export async function createWorld(body: {
  prompt: string;
  session_id?: string | null;
  god_mode?: GodModePayload | null;
}): Promise<CreateWorldResult> {
  const res = await fetch(`${API_BASE}/worlds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      prompt: body.prompt,
      session_id: body.session_id,
      god_mode: body.god_mode,
    }),
  });
  if (!res.ok) throw new Error(`createWorld: ${res.status}`);
  return res.json();
}

export async function restoreWorldState(
  worldId: string,
  body: {
    t: number;
    target?: "current" | "fork";
    resume?: boolean;
  }
): Promise<RestoreWorldResponse> {
  const res = await fetch(`${API_BASE}/worlds/${worldId}/restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      t: body.t,
      target: body.target ?? "fork",
      resume: body.resume ?? true,
    }),
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as RestoreWorldResponse;
}

export async function getWorld(worldId: string): Promise<WorldMeta> {
  const res = await fetch(`${API_BASE}/worlds/${worldId}`);
  if (!res.ok) throw new Error(`getWorld: ${res.status}`);
  return res.json();
}

export async function deleteWorld(worldId: string): Promise<DeleteWorldResponse> {
  const res = await fetch(`${API_BASE}/worlds/${encodeURIComponent(worldId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`deleteWorld: ${res.status}`);
  return res.json();
}

export async function getWorldPersonas(
  worldId: string,
  limit = 20
): Promise<PersonaPreviewResponse> {
  const q = new URLSearchParams({ limit: String(limit) });
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/personas?${q}`
  );
  if (!res.ok) throw new Error(`getWorldPersonas: ${res.status}`);
  return res.json();
}

export async function getAgentSummary(
  worldId: string,
  t?: number
): Promise<AgentSummaryResponse> {
  const q = new URLSearchParams();
  if (typeof t === "number") q.set("t", String(t));
  const suffix = q.toString() ? `?${q}` : "";
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/agents/summary${suffix}`
  );
  if (!res.ok) throw new Error(`getAgentSummary: ${res.status}`);
  return res.json();
}

export async function getGroupBeliefTrajectory(
  worldId: string,
  options?: {
    groupKind?: "role" | "zone";
    tMin?: number;
    tMax?: number;
    limit?: number;
    signal?: AbortSignal;
  }
): Promise<GroupBeliefTrajectoryResponse> {
  const q = new URLSearchParams();
  q.set("group_kind", options?.groupKind ?? "role");
  if (typeof options?.tMin === "number") q.set("t_min", String(options.tMin));
  if (typeof options?.tMax === "number") q.set("t_max", String(options.tMax));
  if (typeof options?.limit === "number") q.set("limit", String(options.limit));
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/agents/belief-trajectory?${q}`,
    { signal: options?.signal }
  );
  if (!res.ok) throw new Error(`getGroupBeliefTrajectory: ${res.status}`);
  return res.json();
}

export async function postAgentInterview(
  worldId: string,
  cellId: string,
  body: { question: string; t?: number | null }
): Promise<AgentInterviewResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/agents/${encodeURIComponent(cellId)}/query`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`postAgentInterview: ${res.status}`);
  return res.json();
}

export async function postAgentInterviewDiff(
  worldId: string,
  cellId: string,
  body: { question: string; t?: number | null; base_t?: number | null }
): Promise<AgentInterviewResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/agents/${encodeURIComponent(cellId)}/diff-query`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`postAgentInterviewDiff: ${res.status}`);
  return res.json();
}

export async function postAgentInterviewWorldDiff(
  worldId: string,
  baseWorldId: string,
  cellId: string,
  body: { question: string; t?: number | null; base_t?: number | null }
): Promise<AgentInterviewResponse> {
  const q = new URLSearchParams({ base_world_id: baseWorldId });
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/agents/${encodeURIComponent(cellId)}/world-diff-query?${q}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) throw new Error(`postAgentInterviewWorldDiff: ${res.status}`);
  return res.json();
}

export async function getLocalRuntimeStatus(): Promise<LocalRuntimeStatus> {
  const res = await fetch(`${API_BASE}/runtime/local-status`);
  if (!res.ok) throw new Error(`getLocalRuntimeStatus: ${res.status}`);
  return res.json();
}

export async function updateRuntimeLlmConfig(body: {
  enabled: boolean;
  provider: string;
  model: string;
  base_url?: string;
  api_key?: string;
  temperature?: number;
  timeout_s?: number;
  runtime_profile?: string;
  strict_mode?: string;
  cycle_prompt_budget?: number;
  agent_sample_size?: number;
  dialogue_max_pairs?: number;
  group_deliberation_max_groups?: number;
  task_budgets?: Record<string, number>;
  task_priorities?: Record<string, number>;
  ui_language?: string;
}): Promise<RuntimeLlmConfigResponse> {
  const res = await fetch(`${API_BASE}/runtime/llm-config`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`updateRuntimeLlmConfig: ${res.status}`);
  return res.json();
}

export async function updateRuntimeUiLanguage(language: "ko" | "en"): Promise<{ language: string }> {
  const res = await fetch(`${API_BASE}/runtime/ui-language`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language }),
  });
  if (!res.ok) throw new Error(`updateRuntimeUiLanguage: ${res.status}`);
  return res.json();
}

export async function testRuntimeLlmConfig(): Promise<RuntimeLlmTestResponse> {
  const res = await fetch(`${API_BASE}/runtime/llm-config/test`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`testRuntimeLlmConfig: ${res.status}`);
  return res.json();
}

export async function syncDataPacks(remoteUrl = ""): Promise<{
  schema_version: string;
  source: string;
  synced: boolean;
  pack_count: number;
  installed_pack_count: number;
}> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/sync`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ remote_url: remoteUrl }),
  });
  if (!res.ok) throw new Error(`syncDataPacks: ${res.status}`);
  return res.json();
}

export async function verifyRuntimeDataPack(
  packId: string
): Promise<DataPackVerifyResponse> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/verify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pack_id: packId }),
  });
  if (!res.ok) throw new Error(`verifyRuntimeDataPack: ${res.status}`);
  return res.json();
}

export async function installRuntimeDataPack(body: {
  pack_id: string;
  source_path: string;
  version?: string;
  dataset_id?: string;
  source_url?: string;
}): Promise<DataPackInstallResponse> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/install`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`installRuntimeDataPack: ${res.status}`);
  return res.json();
}

export async function pinRuntimeDataPack(
  packId: string,
  pinnedVersion: string
): Promise<DataPackPinResponse> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/pin`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pack_id: packId, pinned_version: pinnedVersion }),
  });
  if (!res.ok) throw new Error(`pinRuntimeDataPack: ${res.status}`);
  return res.json();
}

export async function rollbackRuntimeDataPack(
  packId: string,
  historyIndex: number
): Promise<DataPackRollbackResponse> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/rollback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pack_id: packId, history_index: historyIndex }),
  });
  if (!res.ok) throw new Error(`rollbackRuntimeDataPack: ${res.status}`);
  return res.json();
}

export async function diffRuntimeDataPack(
  packId: string,
  historyIndex: number
): Promise<DataPackDiffResponse> {
  const res = await fetch(`${API_BASE}/runtime/data-packs/diff`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ pack_id: packId, history_index: historyIndex }),
  });
  if (!res.ok) throw new Error(`diffRuntimeDataPack: ${res.status}`);
  return res.json();
}

export async function listSessions(): Promise<SessionSummary[]> {
  const res = await fetch(`${API_BASE}/sessions`);
  if (!res.ok) throw new Error(`listSessions: ${res.status}`);
  return res.json();
}

export async function renameSession(
  sessionId: string,
  title: string
): Promise<SessionSummary> {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) throw new Error(`renameSession: ${res.status}`);
  return res.json();
}

export async function deleteSession(
  sessionId: string
): Promise<{ session_id: string; deleted: boolean }> {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(`deleteSession: ${res.status}`);
  return res.json();
}

export async function getSessionReview(
  sessionId: string,
  objective = "balanced"
): Promise<SessionReviewResponse> {
  const q = new URLSearchParams({ objective });
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/review?${q}`);
  if (!res.ok) throw new Error(`getSessionReview: ${res.status}`);
  return res.json();
}

export async function postSessionReviewQuery(
  sessionId: string,
  question: string
): Promise<SessionReviewQueryResponse> {
  const res = await fetch(`${API_BASE}/sessions/${encodeURIComponent(sessionId)}/review/query`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ question }),
  });
  if (!res.ok) throw new Error(`postSessionReviewQuery: ${res.status}`);
  return res.json();
}

export async function getReviewSummary(
  worldId: string
): Promise<ReviewSummaryResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/review/summary`
  );
  if (!res.ok) throw new Error(`getReviewSummary: ${res.status}`);
  return res.json();
}

export async function getReviewDiff(
  worldId: string,
  baseWorldId: string
): Promise<ReviewDiffResponse> {
  const q = new URLSearchParams({ base_world_id: baseWorldId });
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/review/diff?${q}`
  );
  if (!res.ok) throw new Error(`getReviewDiff: ${res.status}`);
  return res.json();
}

export async function postReviewQuery(
  worldId: string,
  question: string
): Promise<ReviewQueryResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/review/query`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }
  );
  if (!res.ok) throw new Error(`postReviewQuery: ${res.status}`);
  return res.json();
}

export async function postReviewDiffQuery(
  worldId: string,
  baseWorldId: string,
  question: string
): Promise<ReviewDiffQueryResponse> {
  const q = new URLSearchParams({ base_world_id: baseWorldId });
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/review/diff-query?${q}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
    }
  );
  if (!res.ok) throw new Error(`postReviewDiffQuery: ${res.status}`);
  return res.json();
}

export async function postWorldChat(
  worldId: string,
  body: {
    question: string;
    session_id?: string | null;
    context?: WorldChatContext;
  }
): Promise<WorldChatResponse> {
  const res = await fetch(`${API_BASE}/worlds/${encodeURIComponent(worldId)}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`postWorldChat: ${res.status}`);
  return res.json();
}

export async function runSimulation(
  worldId: string,
  options?: { stream?: boolean }
): Promise<{
  world_id: string;
  status: string;
  final_t?: number;
  cell_count?: number;
  message?: string;
}> {
  const res = await fetch(`${API_BASE}/worlds/${worldId}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ stream: options?.stream ?? false }),
  });
  if (!res.ok) throw new Error(`runSimulation: ${res.status}`);
  return res.json();
}

/** t 미지정 시 저장된 t 목록 */
export async function listSnapshotTimes(
  worldId: string
): Promise<SnapshotsListResponse> {
  const res = await fetch(`${API_BASE}/worlds/${worldId}/snapshots`);
  if (!res.ok) throw new Error(`listSnapshotTimes: ${res.status}`);
  return res.json();
}

export async function getSnapshotAtT(
  worldId: string,
  t: number
): Promise<SnapshotResponse> {
  const q = new URLSearchParams({ t: String(t) });
  const res = await fetch(`${API_BASE}/worlds/${worldId}/snapshots?${q}`);
  if (!res.ok) throw new Error(`getSnapshotAtT: ${res.status}`);
  return res.json();
}

/** Phase 7: God View 주입 */
export type InjectBody = {
  t: number;
  event_type: string;
  payload: Record<string, unknown>;
};

export type InjectResponse = {
  world_id: string;
  t_inject: number;
  event_type: string;
  status: string;
  final_t: number;
  cell_count: number;
  snapshots_cleared: number;
  forwarded: boolean;
};

export async function injectEvent(
  worldId: string,
  body: InjectBody
): Promise<InjectResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/inject`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }
  );
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`injectEvent: ${res.status} ${text}`);
  }
  return res.json();
}

export type TimelinePoint = {
  t: number;
  cell_count: number;
  total_energy: number;
};

export type TimelineResponse = {
  world_id: string;
  points: TimelinePoint[];
};

export type TimelineSummaryResponse = {
  world_id: string;
  points_count: number;
  first_t: number;
  last_t: number;
  initial_cell_count: number;
  final_cell_count: number;
  min_cell_count: number;
  max_cell_count: number;
  initial_total_energy: number;
  final_total_energy: number;
  peak_total_energy: number;
  cell_delta: number;
  energy_delta: number;
  outcome:
    | "not_started"
    | "extinct"
    | "expanding"
    | "contracting"
    | "energy_accumulating"
    | "energy_depleted"
    | "stable";
};

export async function getTimeline(worldId: string): Promise<TimelineResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/timeline`
  );
  if (!res.ok) throw new Error(`getTimeline: ${res.status}`);
  return res.json();
}

export async function getTimelineSummary(
  worldId: string
): Promise<TimelineSummaryResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/timeline/summary`
  );
  if (!res.ok) throw new Error(`getTimelineSummary: ${res.status}`);
  return res.json();
}

export function getApiBase(): string {
  return API_BASE;
}

/** 브라우저 WebSocket URL (http → ws) */
export function getWorldWebSocketUrl(worldId: string): string {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/worlds/${encodeURIComponent(worldId)}/ws`;
}

/**
 * 8D emotion 순서는 백엔드 EMOTION_LABELS와 동일 (joy, anger, fear, calm, …)
 * Phase 6.2: 지배 감정 → 색, |값| 합 → 스케일(강도)
 */
const EMOTION_RGB: readonly (readonly [number, number, number])[] = [
  [1, 0.88, 0.22], // joy
  [0.95, 0.18, 0.14], // anger
  [0.58, 0.22, 0.78], // fear
  [0.22, 0.52, 0.95], // calm
  [0.95, 0.78, 0.25], // surprise
  [0.32, 0.72, 0.42], // trust
  [0.92, 0.58, 0.28], // anticipation
  [0.48, 0.38, 0.32], // disgust
];

export function emotionToColorAndScale(emotionVec: number[]): {
  rgb: [number, number, number];
  scale: number;
} {
  const dims = Math.min(8, emotionVec.length);
  let best = 0;
  let bestI = 0;
  for (let i = 0; i < dims; i++) {
    const v = Math.abs(emotionVec[i] ?? 0);
    if (v > best) {
      best = v;
      bestI = i;
    }
  }
  const base = EMOTION_RGB[bestI] ?? [0.35, 0.72, 0.92];
  const intensity = Math.min(1, best * 1.15 + 0.12);
  const rgb: [number, number, number] = [
    clamp01(base[0] * intensity + 0.06 * (1 - intensity)),
    clamp01(base[1] * intensity + 0.06 * (1 - intensity)),
    clamp01(base[2] * intensity + 0.06 * (1 - intensity)),
  ];
  const scale = 0.52 + 0.62 * Math.min(1, best);
  return { rgb, scale };
}

/** Phase 8: 시각화 상한 (초과 시 균등 샘플링). NEXT_PUBLIC_MAX_VISUAL_CELLS */
export function getMaxVisualCellsLimit(): number {
  if (typeof process === "undefined") return 8192;
  const v = process.env.NEXT_PUBLIC_MAX_VISUAL_CELLS;
  if (v == null || v === "") return 8192;
  const n = parseInt(v, 10);
  if (!Number.isFinite(n) || n < 64) return 8192;
  return Math.min(n, 100_000);
}

function sampleCellIndices(total: number, maxVisual: number): number[] {
  if (total <= maxVisual) {
    return Array.from({ length: total }, (_, i) => i);
  }
  const out: number[] = [];
  const step = total / maxVisual;
  for (let j = 0; j < maxVisual; j++) {
    out.push(Math.min(total - 1, Math.floor(j * step)));
  }
  return out;
}

export type CellsToInstanceBuffersOptions = {
  maxVisualCells?: number;
};

export type SampledCellsResult = {
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
};

export function sampleCellsForVisualization(
  cells: CellSnapshot[],
  maxVisualCells?: number
): SampledCellsResult {
  const totalCells = cells.length;
  const maxV = maxVisualCells ?? getMaxVisualCellsLimit();
  const indices = sampleCellIndices(totalCells, maxV);
  return {
    cells: indices.map((index) => cells[index]!),
    totalCells,
    sampled: totalCells > indices.length,
  };
}

/** 스냅샷 셀 → InstancedMesh용 버퍼 (대량 세포 시 샘플링) */
export function cellsToInstanceBuffers(
  cells: CellSnapshot[],
  options?: CellsToInstanceBuffersOptions
): {
  positions: Float32Array;
  colors: Float32Array;
  scales: Float32Array;
  count: number;
  totalCells: number;
  sampled: boolean;
} {
  const sampledCells = sampleCellsForVisualization(
    cells,
    options?.maxVisualCells
  );
  const n = sampledCells.cells.length;
  const positions = new Float32Array(Math.max(n * 3, 3));
  const colors = new Float32Array(Math.max(n * 3, 3));
  const scales = new Float32Array(Math.max(n, 1));
  for (let i = 0; i < n; i++) {
    const c = sampledCells.cells[i]!;
    const o = i * 3;
    positions[o] = c.x;
    positions[o + 1] = c.y;
    positions[o + 2] = 0;
    const { rgb, scale } = emotionToColorAndScale(c.emotion_vec);
    colors[o] = rgb[0];
    colors[o + 1] = rgb[1];
    colors[o + 2] = rgb[2];
    scales[i] = scale;
  }
  return {
    positions,
    colors,
    scales,
    count: n,
    totalCells: sampledCells.totalCells,
    sampled: sampledCells.sampled,
  };
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}
