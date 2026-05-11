"use client";

import { AppPanel } from "@/components/app-shell/AppPanel";
import type { CellSnapshot } from "@/lib/api";

export type SelectedZone = {
  zoneId: string;
  label: string;
  influence: number;
  friction: number;
  count: number;
};

export type SelectedBand = {
  key: string;
  label: string;
  lower: number;
  upper: number;
  agentCount: number;
  avgEnergy: number;
  avgZ: number;
  dominantRole: string;
  modeLabel: string;
};

type SimulationInspectorPanelProps = {
  selectedAgent: CellSnapshot | null;
  selectedZone: SelectedZone | null;
  selectedBand: SelectedBand | null;
  worldSummary: {
    worldId: string | null;
    currentT: number;
    visibleCount: number;
    totalCount: number;
    sampled: boolean;
  };
  onClearSelection: () => void;
};

export function SimulationInspectorPanel({
  selectedAgent,
  selectedZone,
  selectedBand,
  worldSummary,
  onClearSelection,
}: SimulationInspectorPanelProps) {
  const hasSelection = Boolean(selectedAgent || selectedZone || selectedBand);

  return (
    <AppPanel
      title="Selection Details"
      subtitle="Agent, zone, and elevation context"
      bodyClassName="space-y-4"
      action={
        hasSelection ? (
          <button
            type="button"
            className="app-button app-button--ghost"
            onClick={onClearSelection}
          >
            Clear
          </button>
        ) : undefined
      }
    >
      <div className="grid gap-2 rounded-[22px] border border-slate-200 bg-slate-50 px-4 py-4">
        <MetricRow label="world" value={worldSummary.worldId ?? "none"} mono />
        <MetricRow label="current t" value={worldSummary.currentT.toFixed(1)} />
        <MetricRow
          label="visible / total"
          value={`${worldSummary.visibleCount.toLocaleString()} / ${worldSummary.totalCount.toLocaleString()}`}
        />
        <MetricRow
          label="sampling"
          value={worldSummary.sampled ? "sampled view" : "full view"}
        />
      </div>

      {!hasSelection ? (
        <EmptyState />
      ) : (
        <div className="space-y-4">
          {selectedAgent ? <AgentCard agent={selectedAgent} /> : null}
          {selectedZone ? <ZoneCard zone={selectedZone} /> : null}
          {selectedBand ? <BandCard band={selectedBand} /> : null}
        </div>
      )}
    </AppPanel>
  );
}

function EmptyState() {
  return (
    <div className="rounded-[22px] border border-dashed border-slate-300 bg-white px-4 py-5 text-sm leading-6 text-slate-600">
      지도에서 agent, zone, contour band를 선택하면 이 패널에서 상세 맥락을 볼 수 있습니다.
      비교 워크플로우를 위해 선택 결과를 우측으로 고정하는 구조입니다.
    </div>
  );
}

function AgentCard({ agent }: { agent: CellSnapshot }) {
  const strategy = String(agent.action_state?.strategy_summary ?? "n/a");
  const zMode = String(agent.action_state?.z_mode ?? "hybrid");
  return (
    <section className="inspector-card">
      <InspectorHeading
        title={agent.role_label ?? agent.role_key ?? "agent"}
        subtitle={`Agent · ${agent.persona_country ?? "unknown"} · ${agent.zone_label ?? agent.zone_id ?? "zone"}`}
      />
      <div className="inspector-grid">
        <MetricRow label="energy" value={agent.energy.toFixed(2)} />
        <MetricRow label="z" value={(agent.z ?? 0).toFixed(2)} />
        <MetricRow label="z mode" value={zMode} />
        <MetricRow label="zone influence" value={String(agent.zone_influence ?? 1)} />
      </div>
      {agent.persona_text ? (
        <p className="inspector-body">{agent.persona_text}</p>
      ) : null}
      <p className="inspector-note">strategy: {strategy}</p>
    </section>
  );
}

function ZoneCard({ zone }: { zone: SelectedZone }) {
  return (
    <section className="inspector-card">
      <InspectorHeading title={zone.label} subtitle={`Zone · ${zone.zoneId}`} />
      <div className="inspector-grid">
        <MetricRow label="agents" value={String(zone.count)} />
        <MetricRow label="influence" value={zone.influence.toFixed(2)} />
        <MetricRow label="friction" value={zone.friction.toFixed(2)} />
      </div>
    </section>
  );
}

function BandCard({ band }: { band: SelectedBand }) {
  return (
    <section className="inspector-card">
      <InspectorHeading title={band.label} subtitle={`${band.modeLabel} contour`} />
      <div className="inspector-grid">
        <MetricRow label="agents" value={String(band.agentCount)} />
        <MetricRow label="avg z" value={band.avgZ.toFixed(2)} />
        <MetricRow label="avg energy" value={band.avgEnergy.toFixed(2)} />
        <MetricRow label="dominant role" value={band.dominantRole} />
      </div>
      <p className="inspector-note">
        range: {band.lower.toFixed(2)} - {band.upper.toFixed(2)}
      </p>
    </section>
  );
}

function InspectorHeading({
  title,
  subtitle,
}: {
  title: string;
  subtitle: string;
}) {
  return (
    <div className="space-y-1">
      <h4 className="text-sm font-semibold tracking-tight text-slate-900">{title}</h4>
      <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">{subtitle}</p>
    </div>
  );
}

function MetricRow({
  label,
  value,
  mono = false,
}: {
  label: string;
  value: string;
  mono?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white px-3 py-3 shadow-sm">
      <p className="text-[10px] uppercase tracking-[0.16em] text-slate-500">{label}</p>
      <p className={`mt-1 text-sm font-medium text-slate-900 ${mono ? "font-mono text-[12px]" : ""}`}>{value}</p>
    </div>
  );
}
