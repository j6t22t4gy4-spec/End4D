"use client";

import {
  WORKBENCH_ITEMS,
  type WorkbenchView,
} from "@/components/app-shell/workbench-types";
import { UI_STRINGS, type UiLocale, getWorkbenchLabels } from "@/lib/ui-language";

type AppToolbarProps = {
  locale: UiLocale;
  onChangeLocale: (locale: UiLocale) => void;
  runtimeProfile: string;
  installedPackCount: number;
  countriesLabel: string;
  activeView: WorkbenchView;
  onChangeView: (view: WorkbenchView) => void;
};

export function AppToolbar({
  locale,
  onChangeLocale,
  runtimeProfile,
  installedPackCount,
  countriesLabel,
  activeView,
  onChangeView,
}: AppToolbarProps) {
  const strings = UI_STRINGS[locale];
  const navLabels = getWorkbenchLabels(locale);
  return (
    <header className="app-toolbar">
      <div className="flex min-w-0 items-center gap-4">
        <div className="app-brand-mark">E4</div>
        <div className="min-w-0">
          <p className="app-eyebrow">{strings.shellEyebrow}</p>
          <h1 className="truncate text-lg font-semibold tracking-tight text-slate-900">
            {strings.shellTitle}
          </h1>
        </div>
      </div>

      <nav className="app-toolbar__nav" aria-label="Primary">
        {WORKBENCH_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`app-toolbar__button ${item.id === activeView ? "is-active" : ""}`}
            onClick={() => onChangeView(item.id)}
          >
            {navLabels[item.id]}
          </button>
        ))}
      </nav>

      <div className="app-toolbar__meta app-toolbar__meta--split">
        <div className="app-toolbar__language">
          <span>{strings.language}</span>
          <div className="app-toolbar__language-switch">
            {(["ko", "en"] as UiLocale[]).map((item) => (
              <button
                key={item}
                type="button"
                className={`app-toolbar__language-button ${item === locale ? "is-active" : ""}`}
                onClick={() => onChangeLocale(item)}
              >
                {item.toUpperCase()}
              </button>
            ))}
          </div>
        </div>
        <div className="app-toolbar__status-row">
          <StatusPill label={strings.runtime} value={runtimeProfile} />
          <StatusPill label={strings.packs} value={String(installedPackCount)} />
          <StatusPill label={strings.regions} value={countriesLabel} />
        </div>
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
