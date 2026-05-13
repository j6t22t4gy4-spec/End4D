# End4D — Center Map 컴포넌트 구조 초안

> 목적: [docs/CENTER_MAP_WIREFRAME.md](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/docs/CENTER_MAP_WIREFRAME.md)을 실제 프런트엔드 구조로 옮기기 위한 컴포넌트 분해 기준을 정의한다.

---

## 0. 현재 기준

현재 Center Map 관련 핵심 진입점은 아래다.

- 메인 실행 화면: [engine/frontend/components/GodView.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/GodView.tsx)
- 메인 맵: [engine/frontend/components/SimulationMap2D.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/SimulationMap2D.tsx)
- 우측 분석 패널: [engine/frontend/components/SimulationInspectorPanel.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/SimulationInspectorPanel.tsx)
- 타임라인: [engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx)
- 런타임 보조 패널: [engine/frontend/components/app-shell/RuntimeDock.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/app-shell/RuntimeDock.tsx)

지금 구조는 `GodView` 안에 `SimulationMap2D + Inspector + Timeline`이 붙어 있고, `SimulationMap2D`는 `zone`, `elevation band`, `agent node`를 한 파일 안에서 직접 그린다.

이 구조는 MVP에는 좋았지만, 이제 다음 한계가 있다.

- pressure/shock/drift/focus/validation을 같은 캔버스 시스템으로 키우기 어렵다.
- Precision과 Swarm을 같은 뷰 계층에서 전환하기 어렵다.
- Center Map이 확장될수록 `SimulationMap2D.tsx`가 비대해진다.

그래서 목표는 **지금 파일을 버리는 것**이 아니라, **현재 맵을 레이어형 서브시스템으로 점진 분해하는 것**이다.

---

## 1. 설계 원칙

1. `GodView`는 orchestration에 집중한다.
2. Center Map은 독립된 하위 시스템으로 분리한다.
3. 데이터 파생과 렌더를 분리한다.
4. 레이어별 컴포넌트는 “무엇을 그리는가” 기준으로 나눈다.
5. Precision과 Swarm 차이는 최상위 mode prop과 layer visibility로 제어한다.
6. 점진적으로 갈아탈 수 있어야 한다. 첫 단계에서는 `SimulationMap2D`를 wrapper 아래에 넣어도 된다.

---

## 2. 제안하는 상위 구조

```text
GodView
└── SimulationWorkspace
    ├── CenterMapShell
    │   ├── CenterMapToolbar
    │   ├── CenterMapViewport
    │   │   ├── ZoneLayer
    │   │   ├── PressureFieldLayer
    │   │   ├── DriftLayer
    │   │   ├── ShockLayer
    │   │   ├── AgentLayer
    │   │   ├── ClusterLayer
    │   │   ├── FocusLayer
    │   │   └── AnchorLayer
    │   └── CenterMapLegend
    ├── CenterMapSidePanel
    └── ScenarioTimeline
```

핵심은 `CenterMapViewport`가 여러 시각 레이어를 조합하는 구조가 되는 것이다.

---

## 3. 역할별 컴포넌트 분해

## 3.1 Orchestration 계층

### `GodView`

역할:

- world 상태 보유
- current `t` 보유
- snapshot fetch / run / review 연결
- 선택 상태 보유
- runtime/review/timeline 데이터 조율

하지 말아야 할 것:

- 맵 레이어 렌더 상세 로직
- 모드별 시각 토글 계산
- pressure/shock/drift 도형 계산

### `SimulationWorkspace`

신규 권장 래퍼.

역할:

- `run` stage 내부의 시뮬레이션 전용 레이아웃 담당
- `CenterMapShell`, `CenterMapSidePanel`, `ScenarioTimeline` 배치
- `layoutMode`, `autoFitLayout`, mode별 비율 제어

---

## 3.2 Center Map Shell 계층

### `CenterMapShell`

역할:

- Center Map 전체 컨테이너
- toolbar, viewport, legend 조합
- mode에 따라 visible layer와 default panel state 제어

주요 props 예시:

```ts
type CenterMapShellProps = {
  mode: "precision" | "swarm";
  cells: CellSnapshot[];
  totalCells: number;
  sampled: boolean;
  currentT: number;
  collectiveSummary: CollectiveDynamicsSummary | null;
  reviewSummary: ReviewSummaryResponse | null;
  selectedAgentId?: string | null;
  selectedZoneId?: string | null;
  selectedBandKey?: string | null;
  onSelectAgent?: (cell: CellSnapshot) => void;
  onSelectZone?: (zone: SelectedZone) => void;
  onSelectBand?: (band: SelectedBand) => void;
  onJumpToT?: (t: number) => void;
};
```

### `CenterMapToolbar`

역할:

- 레이어 칩
- mode badge
- density / labels / compare toggles
- focus reset

원칙:

- 맵에 직접 관련된 토글만 둔다
- 엔진 설정은 여기에 넣지 않는다

### `CenterMapLegend`

역할:

- pressure 색상
- shock / drift / fracture 표식 안내
- 현재 visible layer 상태 요약

---

## 3.3 Viewport 계층

### `CenterMapViewport`

역할:

- 실제 렌더 스택
- 공통 좌표계와 projection 제공
- hover / click / selection hit-test 관리

핵심:

- 이 컴포넌트는 “그리기 그 자체”보다 “레이어를 어떤 순서로 쌓는가”를 책임진다

레이어 순서 권장:

1. `ZoneLayer`
2. `PressureFieldLayer`
3. `DriftLayer`
4. `ShockLayer`
5. `AgentLayer` 또는 `ClusterLayer`
6. `FocusLayer`
7. `AnchorLayer`

---

## 4. 레이어별 컴포넌트

## 4.1 `ZoneLayer`

현재 `SimulationMap2D.tsx`의 zone rectangle 부분에서 분리 가능.

역할:

- zone boundaries
- zone label
- zone tint
- policy radius backdrop

입력:

- zone boxes / zone metadata
- selected zone

출력:

- zone click event

## 4.2 `PressureFieldLayer`

신규 핵심 레이어.

역할:

- collective pressure heat
- tension field
- fracture contour

입력:

- cells 또는 precomputed field points
- collective summary
- pressure mode

주의:

- 처음부터 완전한 heatmap 엔진을 만들기보다, 1차는 grid interpolation으로도 충분

## 4.3 `DriftLayer`

역할:

- drift vector
- migration corridor
- directional flow streak

입력:

- zone drift summary
- optional branch delta

Swarm에서 중요도가 높다.

## 4.4 `ShockLayer`

역할:

- policy injection point
- ripple effect
- propagation path
- event marker spotlight

입력:

- review annotations
- current event markers
- selected shock marker

## 4.5 `AgentLayer`

현재 `SimulationMap2D.tsx`의 agent node 부분을 담당.

역할:

- individual agent dots
- emotion color / scale
- observer halo
- selected agent ring

Precision 기본 레이어다.

## 4.6 `ClusterLayer`

Swarm 핵심 레이어.

역할:

- bloc cloud
- density compression
- cluster hull
- split / merge visual

입력:

- cluster summaries
- selected bloc

초기에는 placeholder로 시작 가능하다.

## 4.7 `FocusLayer`

역할:

- selected object spotlight
- hover outline
- compare highlight
- active trail

핵심:

- selection 시각 규칙을 한 곳에서 통일

## 4.8 `AnchorLayer`

역할:

- review grounding anchor
- validation jump marker
- “open at t” citation pin

이 레이어가 있으면 Review와 맵이 진짜로 연결된다.

---

## 5. 데이터 파생 계층

렌더 컴포넌트 안에서 모든 계산을 하면 안 된다.  
도형/요약 파생은 별도 훅 또는 selector 계층으로 분리한다.

### 권장 훅 구조

```text
hooks/center-map/
├── useCenterMapScene.ts
├── useZoneScene.ts
├── usePressureField.ts
├── useShockScene.ts
├── useFocusState.ts
└── useClusterScene.ts
```

### 역할

`useCenterMapScene`

- 상위 조합기
- mode와 visible layers를 받아 전체 scene bundle 생성

`useZoneScene`

- cells -> zone boxes, labels, bounds

`usePressureField`

- cells/action_state -> pressure grid, fracture contour candidates

`useShockScene`

- review annotations / event markers -> ripple anchors, path lines

`useFocusState`

- selected agent / zone / band / review anchor -> unified focus model

`useClusterScene`

- Swarm 또는 pseudo-swarm cluster derivation

---

## 6. 상태 모델

Center Map 전용 UI 상태는 `GodView`의 모든 상태와 섞지 않는 편이 좋다.

### 권장 상태 묶음

```ts
type CenterMapUiState = {
  mode: "precision" | "swarm";
  visibleLayers: {
    agents: boolean;
    heat: boolean;
    shock: boolean;
    drift: boolean;
    anchors: boolean;
    labels: boolean;
    clusters: boolean;
  };
  compareEnabled: boolean;
  focusTarget:
    | { kind: "agent"; id: string }
    | { kind: "zone"; id: string }
    | { kind: "band"; key: string }
    | { kind: "anchor"; id: string }
    | { kind: "bloc"; id: string }
    | null;
};
```

핵심은 selected state를 mode와 무관하게 한 모델로 다룰 수 있게 하는 것이다.

---

## 7. 폴더 구조 초안

```text
engine/frontend/components/center-map/
├── CenterMapShell.tsx
├── CenterMapToolbar.tsx
├── CenterMapLegend.tsx
├── CenterMapViewport.tsx
├── layers/
│   ├── ZoneLayer.tsx
│   ├── PressureFieldLayer.tsx
│   ├── DriftLayer.tsx
│   ├── ShockLayer.tsx
│   ├── AgentLayer.tsx
│   ├── ClusterLayer.tsx
│   ├── FocusLayer.tsx
│   └── AnchorLayer.tsx
├── hooks/
│   ├── useCenterMapScene.ts
│   ├── useZoneScene.ts
│   ├── usePressureField.ts
│   ├── useShockScene.ts
│   ├── useFocusState.ts
│   └── useClusterScene.ts
├── types.ts
└── utils.ts
```

### 기존 파일 처리

- `SimulationMap2D.tsx`
  - 1단계: 내부 로직 유지, `CenterMapViewport`에서 wrapper로 사용 가능
  - 2단계: zone/agent/band 로직을 각 layer로 분리
  - 3단계: `SimulationMap2D`를 compatibility shell 또는 제거

즉 갈아엎기보다 단계적 추출이다.

---

## 8. 단계별 마이그레이션

## Step 1

목표: 구조 껍데기 만들기

- `center-map/` 폴더 생성
- `CenterMapShell`, `CenterMapToolbar`, `CenterMapViewport` 추가
- 내부는 아직 `SimulationMap2D` wrapper로 연결

## Step 2

목표: 첫 레이어 분리

- `ZoneLayer`
- `AgentLayer`
- `FocusLayer`

이 단계에서 기존 맵과 거의 같은 결과를 유지해야 한다.

## Step 3

목표: 새로운 가치 추가

- `PressureFieldLayer`
- `ShockLayer`
- `AnchorLayer`

이 단계에서 Center Map 체감이 달라진다.

## Step 4

목표: Swarm 대비

- `ClusterLayer`
- `useClusterScene`
- compare overlay

---

## 9. 모드 공존 전략

같은 컴포넌트를 쓰되, 기본 visible layer와 side panel 해석이 다르다.

### Precision 기본

- `agents=true`
- `heat=true`
- `shock=true`
- `drift=false` 또는 low emphasis
- `anchors=true`
- `clusters=false`

### Swarm 기본

- `agents=false` 또는 deemphasized
- `heat=true`
- `shock=true`
- `drift=true`
- `anchors=false`
- `clusters=true`

즉 코드베이스는 공유하되, **기본 가시성과 우선순위가 다르다.**

---

## 10. API / 데이터 계약 메모

지금 바로 백엔드 API를 크게 바꿀 필요는 없다.

초기에는 아래 데이터로도 충분히 시작 가능하다.

- `cells`
- `action_state.collective_pressure`
- `action_state.collective_pressure_bucket`
- `action_state.fracture_signal_received`
- `collectiveSummary`
- `reviewSummary.timeline_annotations`
- `reviewSummary.validation_readout`

이후 Swarm 전용으로 필요해질 수 있는 것:

- bloc summaries
- pressure grid snapshot
- shock propagation edges
- branch delta payload

---

## 11. 가장 먼저 손대야 할 파일

구현 순서 기준 추천:

1. [engine/frontend/components/GodView.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/GodView.tsx)
2. [engine/frontend/components/SimulationMap2D.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/SimulationMap2D.tsx)
3. 신규 `engine/frontend/components/center-map/*`
4. [engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx)
5. [engine/frontend/components/SimulationInspectorPanel.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/SimulationInspectorPanel.tsx)

---

## 12. 성공 기준

이 구조가 잘 잡혔다고 보려면:

1. `GodView`가 맵 렌더 디테일에서 한 단계 가벼워진다.
2. `SimulationMap2D` 하나에 몰려 있던 책임이 layer 단위로 나뉜다.
3. pressure/shock/anchor를 추가해도 한 파일이 폭발하지 않는다.
4. Precision과 Swarm 전환이 조건문 지옥이 아니라 layer visibility로 처리된다.
5. Review/Validation/Timeline이 Center Map과 자연스럽게 연결된다.

