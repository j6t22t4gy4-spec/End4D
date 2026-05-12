"use client";

import {
  WORKBENCH_ITEMS,
  type WorkbenchView,
} from "@/components/app-shell/workbench-types";
import { UI_STRINGS, type UiLocale, getWorkbenchLabels } from "@/lib/ui-language";

type AppToolbarProps = {
  locale: UiLocale;
  onChangeLocale: (locale: UiLocale) => void;
  llmProvider: string;
  llmModel: string;
  llmStatusTone: "green" | "amber" | "red";
  llmStatusLabel: string;
  activeView: WorkbenchView;
  onChangeView: (view: WorkbenchView) => void;
};

export function AppToolbar({
  locale,
  onChangeLocale,
  llmProvider,
  llmModel,
  llmStatusTone,
  llmStatusLabel,
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
        <div className="app-toolbar__status-row">
          <div className="app-status-pill">
            <span>LLM</span>
            <strong>{llmProvider} · {llmModel}</strong>
            <em className={`app-status-pill__dot tone-${llmStatusTone}`} />
            <small>{llmStatusLabel}</small>
          </div>
        </div>
        <div className="app-toolbar__language">
          <span>{strings.language}</span>
          <select
            className="app-toolbar__language-select"
            value={locale}
            onChange={(event) => onChangeLocale(event.target.value as UiLocale)}
          >
            <option value="ko">한국어</option>
            <option value="en">English</option>
          </select>
        </div>
      </div>
    </header>
  );
}
