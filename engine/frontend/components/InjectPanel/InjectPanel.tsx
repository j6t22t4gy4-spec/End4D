"use client";

/**
 * God View 주입 패널 (Phase 7.2)
 */
import { useState, useCallback, useEffect } from "react";
import { injectEvent, type InjectBody } from "@/lib/api";

const EVENT_OPTIONS: { value: string; label: string; defaultPayload: string }[] =
  [
    {
      value: "nutrient_burst",
      label: "영양 급증 (nutrient_burst)",
      defaultPayload: '{"amount": 25}',
    },
    {
      value: "append_memory",
      label: "메모리 추가 (append_memory)",
      defaultPayload: '{"text": "policy shock"}',
    },
    {
      value: "emotion_spike",
      label: "감정 스파이크 (emotion_spike)",
      defaultPayload: '{"index": 2, "delta": 0.4}',
    },
    { value: "noop", label: "변경 없음 (noop)", defaultPayload: "{}" },
  ];

type InjectPanelProps = {
  worldId: string | null;
  suggestedT: number;
  /** 시뮬 실행 중이면 비활성 */
  simRunning?: boolean;
  onInjected: () => Promise<void>;
};

export function InjectPanel({
  worldId,
  suggestedT,
  simRunning = false,
  onInjected,
}: InjectPanelProps) {
  const [injectT, setInjectT] = useState(0);
  const [eventType, setEventType] = useState("nutrient_burst");
  const [payloadJson, setPayloadJson] = useState(
    EVENT_OPTIONS[0].defaultPayload
  );
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setInjectT(suggestedT);
  }, [suggestedT]);

  useEffect(() => {
    const opt = EVENT_OPTIONS.find((o) => o.value === eventType);
    if (opt) setPayloadJson(opt.defaultPayload);
  }, [eventType]);

  const handleSubmit = useCallback(async () => {
    if (!worldId) return;
    setErr(null);
    setMsg(null);
    let payload: Record<string, unknown> = {};
    try {
      payload = JSON.parse(payloadJson) as Record<string, unknown>;
    } catch {
      setErr("payload JSON 파싱 실패");
      return;
    }
    setBusy(true);
    try {
      const body: InjectBody = {
        t: injectT,
        event_type: eventType,
        payload,
      };
      const out = await injectEvent(worldId, body);
      setMsg(
        `주입 완료 · t=${out.t_inject} · 이후 스냅샷 ${out.snapshots_cleared}개 제거 후` +
          (out.forwarded ? " 재계산됨" : " 종료") +
          ` · 세포 수 ${out.cell_count}`
      );
      await onInjected();
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }, [worldId, injectT, eventType, payloadJson, onInjected]);

  return (
    <section
      className="rounded-lg border border-slate-800 bg-slate-900/50 p-4 space-y-3"
      data-testid="inject-panel"
    >
      <h2 className="text-sm font-medium text-slate-300">
        4. God View 주입 (t 시점 → 이후 재계산)
      </h2>
      <div className="flex flex-wrap gap-4 items-end">
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          주입 t
          <input
            type="number"
            step={1}
            value={injectT}
            onChange={(e) => setInjectT(Number(e.target.value))}
            className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-white w-28"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-400">
          이벤트 타입
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-white text-sm min-w-[220px]"
          >
            {EVENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="flex flex-col gap-1 text-xs text-slate-400">
        payload (JSON)
        <textarea
          value={payloadJson}
          onChange={(e) => setPayloadJson(e.target.value)}
          rows={3}
          className="rounded bg-slate-800 border border-slate-600 px-2 py-1 text-white font-mono text-xs w-full max-w-lg"
        />
      </label>
      <button
        type="button"
        disabled={!worldId || busy || simRunning}
        onClick={handleSubmit}
        className="rounded-md bg-amber-700 hover:bg-amber-600 disabled:opacity-40 px-4 py-2 text-sm"
      >
        {busy ? "처리 중…" : "주입 실행"}
      </button>
      {err && (
        <p className="text-xs text-red-300" role="alert">
          {err}
        </p>
      )}
      {msg && <p className="text-xs text-emerald-200/90">{msg}</p>}
      <p className="text-xs text-slate-500">
        해당 t에 저장된 스냅샷이 있어야 합니다. 실행 후 슬라이더의 t를 참고하세요.
      </p>
    </section>
  );
}
