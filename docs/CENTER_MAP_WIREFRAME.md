# End4D — Center Map Wireframe 초안

> 목적: [docs/SWARM_MODE_CENTER_MAP_DESIGN.md](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/docs/SWARM_MODE_CENTER_MAP_DESIGN.md)의 원칙을 실제 화면 배치 수준으로 내리는 1차 와이어프레임 문서.

---

## 0. 한 줄 목표

**Center Map은 End4D의 “메인 무대”여야 하며, Precision Mode에서는 분석 콘솔처럼, Swarm Mode에서는 실시간 사회장 레이더처럼 느껴져야 한다.**

---

## 1. 공통 레이아웃 와이어프레임

```text
┌────────────────────────────────────────────────────────────────────────────────────┐
│ TOP BAR                                                                            │
│ [Mode Toggle] [World] [t / Run / Pause / Speed] [Layers] [Theme] [Settings]      │
├───────────────────────┬──────────────────────────────────────────────┬─────────────┤
│ LEFT NAV              │ CENTER MAP                                   │ RIGHT PANEL │
│                       │                                              │             │
│ Search                │  ┌────────────────────────────────────────┐  │ Live        │
│                       │  │ Layer Chips                            │  │ Insights    │
│ Agents / Groups       │  │                                        │  │             │
│ Zones / Scenarios     │  │                                        │  │ Validation  │
│                       │  │                                        │  │ Collective  │
│ Quick Filters         │  │          Interactive Field             │  │ Review      │
│ role / zone / bloc    │  │                                        │  │ Quick       │
│                       │  │                                        │  │ Controls    │
│ Selection Stack       │  │                                        │  │             │
│                       │  │                                        │  │             │
│                       │  └────────────────────────────────────────┘  │             │
├───────────────────────┴──────────────────────────────────────────────┴─────────────┤
│ BOTTOM TIMELINE                                                                    │
│ [Scrubber] [Event Markers] [Shock Markers] [Bookmarks] [Compare Toggle]           │
└────────────────────────────────────────────────────────────────────────────────────┘
```

### 공통 비율 제안

- Left: `18~22%`
- Center: `52~60%`
- Right: `22~26%`
- Bottom Timeline: `96~132px`

Center가 항상 제일 커야 한다.

---

## 2. Top Bar 와이어프레임

```text
[ Precision | Swarm ]
[ World: KR_urban_shift_03 ]
[ t=128 ] [Run] [Pause] [1x 2x 4x]
[ Agents ] [Heat ] [Shock ] [Drift ] [Labels ]
[ Theme ]
[ Settings ]
```

### 역할

- 모드 전환
- world 상태 표시
- 실행 제어
- 레이어 on/off
- 시각 테마 제어

### 원칙

- 복잡한 설정을 숨기고, 맵 관련 토글만 전면 배치
- 현재 모드와 현재 `t`는 언제나 눈에 보여야 함

---

## 3. Left Panel 와이어프레임

Left Panel은 “무엇을 볼지” 정하는 곳이다.

### 3.1 Precision Mode

```text
Search

Agents
- Top Movers
- High Friction Agents
- Thought Focused

Groups
- Fracturing Groups
- Contested Groups

Zones
- High Drift Zones
- High Policy Sensitivity

Filters
- role
- zone
- country

Selection Stack
- selected agent
- selected group
- selected zone
```

### 3.2 Swarm Mode

```text
Search

Blocs
- Emerging
- Expanding
- Splitting

Zones
- Hot Zones
- Migration Corridors

Scenarios
- Branch A
- Branch B
- Best / Worst / Weirdest

Filters
- bloc type
- pressure band
- policy target

Selection Stack
- selected bloc
- selected zone
- selected branch
```

### 원칙

- Left Panel은 맵의 대체제가 아니라 맵의 탐색기여야 한다
- 항목을 클릭하면 Center와 Right가 함께 바뀌어야 한다

---

## 4. Center Map 와이어프레임

## 4.1 Precision Mode

```text
┌──────────────────────────────────────────────────────────────────┐
│ Layer Chips: Agents / Pressure / Fracture / Drift / Anchors     │
│                                                                  │
│      ·    ·        ·                                             │
│   ·     ◎ selected agent       ~ pressure contour               │
│                                                                  │
│              x review anchor                                     │
│                                                                  │
│   ─ ─ shock path ─ ─                                             │
│                                                                  │
│        zone outline                                              │
│                                                                  │
│      top mover trail: • • • •                                    │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 보여야 하는 것

- 개별 agent dot
- selected agent halo
- thought/action breadcrumb
- review anchor
- fracture contour
- shock path

### 정보 밀도

- 개별 점은 많아도 읽혀야 함
- density가 높을 때는 우선순위 agent만 강조

### 클릭 결과

- agent click → Right Panel thought/action/recent memory
- group click → group metrics + review grounding
- timeline marker click → 해당 t pulse

## 4.2 Swarm Mode

```text
┌──────────────────────────────────────────────────────────────────┐
│ Layer Chips: Blocs / Heat / Shock / Drift / Branch Compare      │
│                                                                  │
│     ███ bloc cloud                 >>> drift stream              │
│                                                                  │
│           ~~~~~ pressure heat                                  │
│                                                                  │
│   ○ shock origin                                                 │
│    ))) ripple                                                    │
│                                                                  │
│                   ████ splitting bloc                            │
│                                                                  │
│      migration corridor ====                                     │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 보여야 하는 것

- bloc cloud
- pressure heat
- drift vectors
- shock ripple
- merge/split marker
- migration corridor

### 정보 밀도

- 개별 점보다는 bloc과 흐름이 먼저 읽혀야 함
- cluster hull 또는 density cloud가 기본

### 클릭 결과

- bloc click → size, grievance, momentum, fracture risk
- drag select → 선택 영역 통계
- branch compare → overlay delta

---

## 5. Right Panel 와이어프레임

Right Panel은 “지금 보고 있는 맵을 어떻게 해석할지” 알려주는 곳이다.

### 5.1 Precision Mode

```text
Live Insights
- selected agent / group summary

Validation Readout
- mock long-horizon
- live smoke

Collective Dynamics
- cohesion
- tension
- fracture
- drift

Thought / Action
- recent thought
- recent action

Review Anchors
- why this matters
- open at t
```

### 5.2 Swarm Mode

```text
Live Insights
- selected bloc / zone summary

Validation Readout
- current confidence
- live profile limit

Collective Dynamics
- pressure band
- shock spread
- migration pressure

Scenario Leaderboard
- most unstable
- fastest drift
- best branch candidate

Quick Controls
- inject policy
- fork branch
- open in precision
```

### 원칙

- Right Panel은 텍스트 벽이 아니라 카드형 빠른 해석이어야 함
- 선택 상태가 없으면 “세계 전체 요약”, 선택 상태가 생기면 “선택 객체 요약”으로 전환

---

## 6. Bottom Timeline 와이어프레임

```text
t=0 ----|----|----|----|----|----|---- t=200
         ^ shock
                   ^ fracture wave
                              ^ damping

[Playhead]
[Event Markers]
[Shock Markers]
[Bookmarks]
[Compare Baseline]
```

### 역할

- 시간 이동
- 주요 사건 점프
- 정책 충격 표시
- fracture wave / stabilization 구간 하이라이트

### Precision Mode

- 세밀한 tick 탐색
- selected agent / group 시점 변화 강조

### Swarm Mode

- 큰 흐름 중심
- branch compare와 연동

---

## 7. 상태별 화면 시나리오

## 7.1 초기 진입

목표: 세계 분위기를 즉시 파악

- Center: pressure field + 기본 entity
- Right: world summary + collective dynamics
- Bottom: 주요 이벤트 마커만

## 7.2 정책 주입 직후

목표: 충격 전달을 시각적으로 이해

- Center: shock ripple + affected zone glow
- Right: affected group / zone summary
- Bottom: shock marker 강조

## 7.3 fracture 감지

목표: 어디가 갈라지고 있는지 이해

- Center: fracture contour + selected bloc highlight
- Right: fracture candidates card
- Bottom: fracture wave 구간 하이라이트

## 7.4 precision handoff

목표: swarm 결과를 정밀 분석으로 넘김

- Center: selected branch snapshot freeze
- Right: “open in precision”
- Bottom: export anchor marker

---

## 8. 시각 스타일 가이드

### Precision Mode

- 배경: deep navy / graphite
- 강조: cyan / amber / muted red
- motion: 억제된 pulse
- 정보 밀도: 높음

### Swarm Mode

- 배경: richer dark slate
- 강조: heat orange / electric cyan / acid lime accents
- motion: 더 강한 ripple / drift
- 정보 밀도: 중간, 대신 field 강함

### 공통

- glow는 기능적일 때만
- glass panel은 보조적
- 텍스트보다 layer contrast가 먼저 읽혀야 함

---

## 9. MVP 우선순위

### MVP-1

- Center 비중 확대
- layer chips 추가
- selected focus halo
- zone tint 개선

### MVP-2

- pressure heatmap
- policy shock ripple
- timeline marker sync

### MVP-3

- review anchor overlay
- validation jump
- right panel live coupling

### MVP-4

- swarm bloc cloud
- density compression
- branch compare overlay

---

## 10. 바로 구현으로 연결되는 작업 항목

1. `GodView`에서 Center 영역을 레이어 기반 구조로 재분해
2. `pressure / shock / drift / anchors` 토글 칩 추가
3. selected focus와 hover focus를 같은 시각 시스템으로 통일
4. `ScenarioTimeline`과 맵 선택 상태를 연결
5. `Validation Readout` 카드 클릭 시 맵/타임라인 점프 설계
6. 이후 Swarm 전용 bloc layer 추가

