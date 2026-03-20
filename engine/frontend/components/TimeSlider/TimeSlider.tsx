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
    <div className="flex flex-col gap-2 w-full max-w-xl">
      <div className="flex justify-between text-sm text-slate-300">
        <span>{label}</span>
        <span className="font-mono text-cyan-300">{t.toFixed(1)}</span>
      </div>
      <input
        type="range"
        min={tMin}
        max={tMax}
        step={step}
        value={t}
        disabled={disabled}
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 rounded-lg appearance-none bg-slate-700 accent-cyan-500 disabled:opacity-50"
      />
    </div>
  );
}
