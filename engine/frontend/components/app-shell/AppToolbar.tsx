"use client";

type AppToolbarProps = {
  runtimeProfile: string;
  installedPackCount: number;
  countriesLabel: string;
};

const TOOL_ITEMS = [
  { label: "Simulation", active: true },
  { label: "Data Packs", active: false },
  { label: "Snapshots", active: false },
  { label: "Policies", active: false },
];

export function AppToolbar({
  runtimeProfile,
  installedPackCount,
  countriesLabel,
}: AppToolbarProps) {
  return (
    <header className="app-toolbar">
      <div className="flex min-w-0 items-center gap-4">
        <div className="app-brand-mark">E4</div>
        <div className="min-w-0">
          <p className="app-eyebrow">Local Simulation Client</p>
          <h1 className="truncate text-lg font-semibold tracking-tight text-slate-900">
            End4D Workbench
          </h1>
        </div>
      </div>

      <nav className="app-toolbar__nav" aria-label="Primary">
        {TOOL_ITEMS.map((item) => (
          <button
            key={item.label}
            type="button"
            className={`app-toolbar__button ${item.active ? "is-active" : ""}`}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <div className="app-toolbar__meta">
        <StatusPill label="Runtime" value={runtimeProfile} />
        <StatusPill label="Packs" value={String(installedPackCount)} />
        <StatusPill label="Regions" value={countriesLabel} />
      </div>
    </header>
  );
}

function StatusPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="app-status-pill">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}
