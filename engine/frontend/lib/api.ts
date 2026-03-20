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

export function getApiBase(): string {
  return API_BASE;
}

/** 브라우저 WebSocket URL (http → ws) */
export function getWorldWebSocketUrl(worldId: string): string {
  const wsBase = API_BASE.replace(/^http/, "ws");
  return `${wsBase}/worlds/${encodeURIComponent(worldId)}/ws`;
}

/** 스냅샷 셀 → InstancedMesh용 버퍼 */
export function cellsToInstanceBuffers(cells: CellSnapshot[]): {
  positions: Float32Array;
  colors: Float32Array;
  count: number;
} {
  const n = cells.length;
  const positions = new Float32Array(Math.max(n * 3, 3));
  const colors = new Float32Array(Math.max(n * 3, 3));
  for (let i = 0; i < n; i++) {
    const c = cells[i];
    const o = i * 3;
    positions[o] = c.x;
    positions[o + 1] = c.y;
    positions[o + 2] = c.z;
    const e = c.emotion_vec;
    colors[o] = clamp01(0.5 + 0.5 * Math.tanh(e[0] ?? 0));
    colors[o + 1] = clamp01(0.5 + 0.5 * Math.tanh(e[1] ?? 0));
    colors[o + 2] = clamp01(0.5 + 0.5 * Math.tanh(e[2] ?? 0));
  }
  return { positions, colors, count: n };
}

function clamp01(v: number): number {
  return Math.min(1, Math.max(0, v));
}
