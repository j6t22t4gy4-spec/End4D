"use client";

import type { ReactNode } from "react";

type AppPanelProps = {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
  testId?: string;
  children: ReactNode;
};

export function AppPanel({
  title,
  subtitle,
  action,
  className = "",
  bodyClassName = "",
  testId,
  children,
}: AppPanelProps) {
  return (
    <section className={`app-panel ${className}`.trim()} data-testid={testId}>
      {(title || subtitle || action) && (
        <header className="app-panel__header">
          <div>
            {title && <h2 className="app-panel__title">{title}</h2>}
            {subtitle && <p className="app-panel__subtitle">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      <div className={bodyClassName}>{children}</div>
    </section>
  );
}
