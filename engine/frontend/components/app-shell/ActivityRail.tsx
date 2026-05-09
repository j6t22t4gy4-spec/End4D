"use client";

import {
  WORKBENCH_ITEMS,
  type WorkbenchView,
} from "@/components/app-shell/workbench-types";

type ActivityRailProps = {
  activeView: WorkbenchView;
  onChange: (view: WorkbenchView) => void;
};

export function ActivityRail({ activeView, onChange }: ActivityRailProps) {
  return (
    <aside className="activity-rail" aria-label="Workbench Sections">
      {WORKBENCH_ITEMS.map((item) => {
        const active = item.id === activeView;
        return (
          <button
            key={item.id}
            type="button"
            className={`activity-rail__button ${active ? "is-active" : ""}`}
            onClick={() => onChange(item.id)}
            title={item.label}
          >
            <span className="activity-rail__glyph">{item.shortLabel}</span>
            <span className="activity-rail__label">{item.label}</span>
          </button>
        );
      })}
    </aside>
  );
}
