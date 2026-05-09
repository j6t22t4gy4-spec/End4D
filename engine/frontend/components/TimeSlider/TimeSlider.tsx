"use client";

/**
 * 시간 t 슬라이더 (Phase 4.4)
 * Phase 5에서 스냅샷 조회와 연동
 */
export type TimeSliderProps = {
  t: number;
  tMin: number;
  tMax: number;
  step?: number;
  onChange: (t: number) => void;
  disabled?: boolean;
  label?: string;
};

export function TimeSlider({
  t,
  tMin,
  tMax,
  step = 0.5,
  onChange,
  disabled = false,
  label = "시간 t",
}: TimeSliderProps) {
  return (
    <div className="flex w-full flex-col gap-2">
      <div className="flex justify-between text-sm text-slate-600">
        <span>{label}</span>
        <span className="font-mono text-slate-900">{t.toFixed(1)}</span>
      </div>
      <input
        type="range"
        min={tMin}
        max={tMax}
        step={step}
        value={t}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="app-range"
      />
    </div>
  );
}
