# End4D — Swarm Mode Center Map 체크리스트 + 상세 디자인 초안

> 목적: `Precision Mode`와 `Swarm Mode`를 하나의 현대적인 시뮬레이션 대시보드 안에 공존시키되, 특히 현재 약한 `Center Map` 표현을 제품의 핵심 경험으로 끌어올리기 위한 기준 문서.

---

## 0. 한 줄 정의

**Swarm Mode의 Center Map은 “많은 에이전트가 실제로 살아 움직이며 압력과 충격이 퍼져나가는 현장”을 보여줘야 하고, Precision Mode의 Center Map은 “왜 그렇게 되었는지 특정 집단과 개별 에이전트를 깊게 읽는 분석 화면”이어야 한다.**

---

## 1. 현재 문제 정의

현재 시뮬레이션은 내부 엔진 해상도에 비해 그래프와 메인 맵 표현이 약하다.

- 에이전트가 “움직이고 있다”는 감각이 약하다.
- 집단 압력, fracture, drift, policy shock이 시각적으로 충분히 읽히지 않는다.
- `RuntimeDock`, `ReviewLab`, `Timeline`은 각각 강점이 있지만 중심 시각 공간이 경험을 끌고 가지 못한다.
- `Precision Mode`와 향후 `Swarm Mode`가 같은 맵 위에서 어떻게 다른 해상도로 보일지 기준이 없다.

즉 지금 병목은 차트 몇 개가 아니라, **메인 시뮬레이션 캔버스의 존재감과 정보 전달력**이다.

---

## 2. 디자인 원칙

### 2.1 핵심 원칙

1. `Center Map`이 제품의 주인공이어야 한다.
2. `Precision`과 `Swarm`은 같은 레이아웃을 쓰되, 맵의 해상도와 강조점은 달라야 한다.
3. Review/Observer/Timeline은 맵을 보조해야지, 맵의 약함을 대신 메우는 구조가 되면 안 된다.
4. 움직임은 “예쁘기 위한 모션”이 아니라 “상태 변화가 읽히기 위한 모션”이어야 한다.
5. 시각 효과는 강해도 좋지만, 정책 충격, bloc 형성, pressure diffusion, drift 같은 엔진 개념이 우선이다.

### 2.2 하지 않을 것

- per-agent DOM 카드 렌더링
- 의미 없는 파티클 과잉
- 다크모드만 입힌 평범한 대시보드
- Precision과 Swarm을 같은 시각 밀도로 억지 통합
- Review를 맵 바깥 텍스트로만 설명하고, 맵은 여전히 정적 상태로 두는 것

---

## 3. Center Map 체크리스트

아래 체크리스트는 설계 전, 구현 중, PR 전 점검용이다.

| # | 체크 항목 | 통과 기준 | 위반 징후 |
|---|-----------|-----------|-----------|
| 3.1 | Center Map이 화면에서 가장 큰 시각적 비중을 가진다 | 첫 시선이 맵으로 간다 | 카드/패널이 더 눈에 띔 |
| 3.2 | 에이전트 또는 집단이 정적으로 박혀 있지 않고 미세한 motion을 가진다 | 살아 있는 field 감각 | 점들이 그냥 찍혀 있음 |
| 3.3 | pressure 변화가 heatmap 또는 field overlay로 읽힌다 | 어디가 뜨거운지 즉시 보임 | 수치 패널을 열어야 이해 가능 |
| 3.4 | policy shock가 “발생 지점 + 확산”으로 보인다 | shock ripple 또는 propagation path 확인 가능 | 단순 이벤트 로그만 있음 |
| 3.5 | drift는 방향성과 속도가 보인다 | 흐름, 편향, 이동 방향이 읽힘 | 값은 있는데 방향이 안 보임 |
| 3.6 | Precision Mode에서 개별 agent focus가 가능하다 | thought/action anchor 추적 가능 | 모든 점이 익명 군중처럼만 보임 |
| 3.7 | Swarm Mode에서 bloc/cluster가 우선 보인다 | 집단 형성과 분열이 먼저 읽힘 | 개별 점만 많고 구조는 안 보임 |
| 3.8 | Timeline scrub 시 맵 상태가 자연스럽게 복원된다 | t 변화에 따라 상태 전환이 이해 가능 | 프레임 점프가 거칠고 맥락이 없음 |
| 3.9 | Right Panel 클릭과 Map focus가 양방향 연동된다 | 패널 선택 시 맵 강조, 맵 선택 시 패널 갱신 | 패널과 맵이 따로 놈 |
| 3.10 | Review/Validation 정보가 맵 해석을 도와준다 | mock/live 차이가 맵 읽기와 연결됨 | 텍스트와 맵이 분리됨 |
| 3.11 | 성능 목표가 모드별로 다르다 | Precision과 Swarm에 맞는 렌더 전략 존재 | 같은 렌더 방식으로 둘 다 처리 |
| 3.12 | 애니메이션은 상태를 설명한다 | pulse, glow, ripple이 이유를 가짐 | 멋만 있고 의미가 없음 |

---

## 4. 통합 대시보드 초안

기본 레이아웃은 아래를 유지한다.

```text
┌─────────────────────────────────────────────────────────────────────┐
│ Top Bar                                                            │
│ Mode · World · Run/Stop · Speed · Layers · Settings               │
├──────────────────────┬──────────────────────────────────────────────┤
│ Left Panel           │ Center Map                                   │
│ Agents               │ Interactive Field / Heat / Clusters / Shock  │
│ Groups / Blocs       │                                              │
│ Zones                │                                              │
│ Scenarios            │                                              │
├──────────────────────┼──────────────────────────────────────────────┤
│ Bottom Timeline      │ Right Panel                                  │
│ Scrubber · Events    │ Validation · Collective · Leaderboard        │
└──────────────────────┴──────────────────────────────────────────────┘
```

핵심은 레이아웃 자체보다도 `Center Map`이 아래 4가지 역할을 동시에 해야 한다는 점이다.

1. 현재 세계 상태 표시
2. 압력/충격/드리프트의 공간적 전달 표시
3. 특정 agent/group/zone focus 진입점
4. Timeline과 Review를 연결하는 메인 앵커

---

## 5. Center Map 상세 디자인 초안

## 5.1 UX 목표

사용자가 맵을 열었을 때 아래 감각이 즉시 들어와야 한다.

1. 지금 세계가 차분한지 불안한지
2. 어디에서 압력이 쌓이고 있는지
3. 어떤 집단이 커지고, 갈라지고, 이동하는지
4. 지금 보고 있는 것이 개별 agent 중심인지, bloc 중심인지
5. 정책 충격이 어디에서 시작해 어디로 번졌는지

즉 “예쁜 사회 그래프”가 아니라 **현장감 있는 사회장 콘솔**이어야 한다.

## 5.2 레이어 구조

Center Map은 단일 그림이 아니라 레이어 합성으로 본다.

### Layer A. Base Terrain / Zone Layer

- zone boundaries
- region tint
- policy radius
- friction / accessibility backdrop

표현:

- 너무 강한 지도 느낌보다는 추상적 사회장 느낌
- 경계선은 얇고, zone 성격은 은은한 gradient로 표현
- Policy injection 시 특정 zone이 순간적으로 밝아지거나 진동

### Layer B. Pressure Field Layer

- collective pressure
- tension
- fracture likelihood
- drift field

표현:

- heatmap
- contour band
- directional flow streak

원칙:

- `pressure`는 색 온도로
- `fracture risk`는 crack-like contour 또는 disrupted noise로
- `drift`는 벡터/흐름으로

이 레이어가 없으면 Swarm Mode의 존재 이유가 반쯤 사라진다.

### Layer C. Agent / Cluster Layer

Precision Mode:

- 개별 점이 보인다
- 중요 agent는 halo 또는 thought focus ring
- role/persona/zone에 따라 모양 또는 색 규칙 부여

Swarm Mode:

- 개별 점은 최소화
- cluster/blob/bloc node 중심
- 고밀도 구간은 density cloud로 압축

즉 같은 world라도 Precision은 `micro-visible`, Swarm은 `meso-visible`이 기본이다.

### Layer D. Shock / Event Layer

- policy injection point
- event pulse
- propagation wave
- turning point marker

표현:

- shock ripple
- flash-to-fade pulse
- directional propagation arc

이 레이어는 단순 로그가 아니라 “정책이 공간적으로 번진다”는 감각을 줘야 한다.

### Layer E. Focus / Selection Layer

- 선택된 agent
- 선택된 group/bloc
- selected zone
- compare target
- review citation anchor

표현:

- active outline
- soft spotlight
- linked panel highlight

이 레이어는 Review와 Observer를 맵에 붙이는 핵심이다.

---

## 5.3 Precision Mode 맵

Precision Mode는 분석 화면이다.

### 보이는 것

- 개별 agent dots
- 선택 agent halo
- thought/action breadcrumb
- top movers
- group fracture overlay
- review grounding anchor

### 상호작용

- click agent: Right Panel에 thought/action/recent memory
- click group: 해당 group의 cohesion/tension/fracture
- hover zone: zone drift, pressure, policy sensitivity
- scrub timeline: turning point 전후 비교

### 시각 톤

- 차분한 다크 네이비 / 슬레이트 기반
- glow는 억제
- high-contrast analytic accents

### 핵심 질문

- 왜 이 집단이 갈라졌는가
- 이 에이전트는 왜 이 시점에 움직였는가
- 어떤 정책이 어떤 group drift를 유발했는가

---

## 5.4 Swarm Mode 맵

Swarm Mode는 탐색 화면이다.

### 보이는 것

- bloc cloud
- pressure heatmap
- drift stream
- shock propagation
- merge/split marker
- scenario hotspot

### 상호작용

- click bloc: bloc size / grievance / momentum / fracture risk
- drag select: 특정 zone 또는 bloc 묶음 분석
- compare branch: branch A vs B overlay
- open branch in precision: 현재 시점 snapshot export

### 시각 톤

- 더 강한 대비
- 더 빠른 motion
- pressure와 shock 강조

### 핵심 질문

- 어디서 빠르게 갈라지고 있는가
- 어떤 bloc이 확장 중인가
- 정책 충격이 어느 경로로 퍼지는가
- 어떤 branch를 Precision으로 넘겨야 하는가

---

## 5.5 모션 원칙

모션은 4종으로 제한한다.

### 1. Idle Motion

- agent 또는 cluster의 미세한 부유감
- 완전히 정지한 화면을 피함

### 2. Pressure Motion

- pressure 증가 시 pulse
- heatmap intensity가 부드럽게 변화

### 3. Shock Motion

- 정책 주입 시 ring, ripple, flash
- propagation은 확산처럼 이동

### 4. Transition Motion

- timeline scrub
- mode switch
- focus change

원칙:

- 모션 duration은 짧고 목적이 분명해야 한다
- 맵 자체가 산만해지면 실패다

---

## 5.6 정보 계층

동시에 다 보여주면 복잡해지므로 기본 노출 계층을 정한다.

### 기본 상태

- zone tint
- pressure field
- primary agents or blocs

### focus 상태

- selection halo
- detail overlay
- linked right panel cards

### expert overlay

- fracture contour
- drift vectors
- policy radius
- validation hints

즉 초보자는 기본 상태만 보고도 읽을 수 있어야 하고, 전문가만 더 깊은 레이어를 켠다.

---

## 6. Validation Readout과의 연결

이미 Review에 추가된 `Validation Readout`은 텍스트로만 끝나면 반쪽이다.

Center Map과 연결 원칙:

1. `mock long-horizon` 패턴은 과거 timeline에서 `fracture wave -> damping` 구간을 하이라이트할 수 있어야 한다.
2. `live smoke` 패턴은 `watch-level pressure`의 공간 분포가 맵에서 보이도록 해야 한다.
3. Validation 카드 클릭 시 해당 패턴을 잘 보여주는 t 또는 zone으로 점프할 수 있어야 한다.

즉 Validation은 패널 설명이 아니라 **맵을 읽는 렌즈**가 되어야 한다.

---

## 7. 구현 우선순위

## Phase A. Center Map MVP

목표: “살아 있다”는 감각 확보

- zone tint 정리
- agent motion 추가
- pressure heatmap 추가
- focus halo 추가

완료 기준:

- 정적 scatter plot 느낌이 사라진다
- pressure가 공간적으로 읽힌다

## Phase B. Policy Shock Visualization

목표: 정책이 세계를 흔드는 감각 확보

- shock ripple
- propagation path
- timeline event sync

완료 기준:

- 정책 주입 직후 맵만 봐도 어디가 흔들리는지 보인다

## Phase C. Precision Review Coupling

목표: Review와 맵 연결

- review citation anchor
- grounding jump
- selected group/agent spotlight

완료 기준:

- Review 텍스트와 맵이 분리되지 않는다

## Phase D. Swarm Overlay

목표: bloc/cluster 중심 표현 확보

- density compression
- cluster hull
- bloc formation
- drift stream

완료 기준:

- 1k agent 이상에서도 맵이 개별 점 잡음으로 보이지 않는다

---

## 8. 기술 메모

현재 프런트 구조를 기준으로 보면 아래 연결이 자연스럽다.

- 메인 world 시각화 축: [engine/frontend/components/GodView.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/GodView.tsx)
- 런타임 보조 패널: [engine/frontend/components/app-shell/RuntimeDock.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/app-shell/RuntimeDock.tsx)
- 리뷰 분석 패널: [engine/frontend/components/workbench/ReviewLabWorkspace.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/workbench/ReviewLabWorkspace.tsx)
- 타임라인: [engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/engine/frontend/components/ScenarioTimeline/ScenarioTimeline.tsx)

구현 원칙:

- Precision MVP는 기존 `GodView`를 버리지 않고 확장
- Swarm 전용 렌더러는 나중에 분리 가능하게 레이어 기반으로 설계
- heatmap과 cluster layer는 React DOM이 아니라 Canvas/WebGL 친화 구조 우선

---

## 9. 성공 기준

이 문서 기준으로 Center Map 개편이 성공했다고 보려면:

1. 사용자가 3초 안에 “어디가 뜨겁고 불안한지”를 말할 수 있다.
2. 정책 주입 후 충격 전달이 시각적으로 바로 읽힌다.
3. Precision에서는 개별 agent와 group을 깊게 추적할 수 있다.
4. Swarm에서는 개별 점보다 bloc과 흐름이 먼저 읽힌다.
5. Review/Validation/Timeline이 모두 맵을 중심으로 연결된다.

---

## 10. 다음 문서

이 문서 다음에는 아래 순서가 자연스럽다.

1. `Center Map Wireframe`
2. `Center Map Component Architecture`
3. `Swarm Mode Data Contract`
4. `Precision -> Swarm / Swarm -> Precision handoff spec`

