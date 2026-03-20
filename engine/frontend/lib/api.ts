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
  gene_vec: number[];
  emotion_vec: number[];
  thought_vec: number[];
  worldview_vec: number[];
};

export type SnapshotResponse = {
  world_id: string;
  t: number;
  cells: CellSnapshot[];
};

export type SnapshotsListResponse = {
  world_id: string;
  available_t: number[];
};

export type WorldMeta = {
  world_id: string;
  t_max: number;
  status: string;
};

export async function createWorld(body: {
  initial_cell_count?: number;
  t_max?: number;
}): Promise<{ world_id: string }> {
  const res = await fetch(`${API_BASE}/worlds`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      initial_cell_count: body.initial_cell_count ?? 5,
      t_max: body.t_max ?? 100,
    }),
  });
  if (!res.ok) throw new Error(`createWorld: ${res.status}`);
  return res.json();
}

export async function getWorld(worldId: string): Promise<WorldMeta> {
  const res = await fetch(`${API_BASE}/worlds/${worldId}`);
  if (!res.ok) throw new Error(`getWorld: ${res.status}`);
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

export async function getTimeline(worldId: string): Promise<TimelineResponse> {
  const res = await fetch(
    `${API_BASE}/worlds/${encodeURIComponent(worldId)}/timeline`
  );
  if (!res.ok) throw new Error(`getTimeline: ${res.status}`);
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
  const totalCells = cells.length;
  const maxV = options?.maxVisualCells ?? getMaxVisualCellsLimit();
  const indices = sampleCellIndices(totalCells, maxV);
  const n = indices.length;
  const positions = new Float32Array(Math.max(n * 3, 3));
  const colors = new Float32Array(Math.max(n * 3, 3));
  const scales = new Float32Array(Math.max(n, 1));
  for (let i = 0; i < n; i++) {
    const c = cells[indices[i]!];
    const o = i * 3;
    positions[o] = c.x;
    positions[o + 1] = c.y;
    positions[o + 2] = c.z;
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
    totalCells,
    sampled: totalCells > n,
  };
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}
