"use client";

/**
 * God View 주입 패널 (Phase 7.2)
 */
import { useState, useCallback, useEffect } from "react";
import { injectEvent, type InjectBody } from "@/lib/api";
import { AppPanel } from "@/components/app-shell/AppPanel";

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
    {
      value: "policy_shift",
      label: "정책 변화 해석 (policy_shift)",
      defaultPayload:
        '{"name":"housing subsidy reform","summary":"정부가 주거 보조금 구조를 개편한다","intensity":0.7,"target_roles":["규제자","시민","시장참여자"]}',
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
    <AppPanel
      title="Policy Injection"
      subtitle="Apply an event and recompute from that point"
      className="space-y-0"
      bodyClassName="space-y-3"
      testId="inject-panel"
    >
      <div className="flex flex-wrap gap-4 items-end">
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          주입 t
          <input
            type="number"
            step={1}
            value={injectT}
            onChange={(e) => setInjectT(Number(e.target.value))}
            className="app-input w-28"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs text-slate-500">
          이벤트 타입
          <select
            value={eventType}
            onChange={(e) => setEventType(e.target.value)}
            className="app-input min-w-[220px] text-sm"
          >
            {EVENT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <label className="flex flex-col gap-1 text-xs text-slate-500">
        payload (JSON)
        <textarea
          value={payloadJson}
          onChange={(e) => setPayloadJson(e.target.value)}
          rows={3}
          className="app-textarea max-w-lg font-mono text-xs"
        />
      </label>
      <button
        type="button"
        disabled={!worldId || busy || simRunning}
        onClick={handleSubmit}
        className="app-button app-button--warning"
      >
        {busy ? "처리 중…" : "주입 실행"}
      </button>
      {err && (
        <p className="text-xs text-rose-700" role="alert">
          {err}
        </p>
      )}
      {msg && <p className="text-xs text-emerald-700">{msg}</p>}
      <p className="text-xs text-slate-500">
        해당 t에 저장된 스냅샷이 있어야 합니다. 실행 후 슬라이더의 t를 참고하세요.
      </p>
    </AppPanel>
  );
}
