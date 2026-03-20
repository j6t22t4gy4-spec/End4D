"use client";

import { Component, type ErrorInfo, type ReactNode } from "react";

type Props = { children: ReactNode };

type State = { error: Error | null };

/**
 * R3F / WebGL 렌더 단계 오류 격리 (헤드리스 E2E 등에서 전체 God View 붕괴 방지)
 */
export class R3fErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.warn("[R3fErrorBoundary]", error.message, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div
          data-testid="r3f-scene-fallback"
          className="rounded-lg border border-amber-900/50 bg-amber-950/30 px-4 py-8 text-center text-sm text-amber-200/90"
        >
          3D 씬을 표시할 수 없습니다. (WebGL·헤드리스 환경 제한일 수 있습니다)
        </div>
      );
    }
    return this.props.children;
  }
}
