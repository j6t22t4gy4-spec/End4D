# Organic4D — 핵심 결손 및 보완 로드맵

> 목적: 개발 중 방향을 잃지 않기 위해, 현재 엔진이 제품 목표에 비해 무엇이 부족한지 명시한다.  
> 기준 목표: **국가 단위 사회를 장기적으로 시뮬레이션·비교·예측**할 수 있고, 이후 다국가 데이터 레이어와 전문가 워크플로우까지 확장 가능한 범용 플랫폼.

---

## 0. 방향 고정 메모

지금 기준에서 가장 위험한 흔들림은 아래 둘이다.

1. **엔진이 장기 사회 시뮬레이터가 아니라 “에이전트 앱”처럼 흘러가는 것**
2. **제품 셸 개선이 코어 시뮬레이션 설명력보다 앞서가는 것**

따라서 모든 우선순위는 아래 질문으로 다시 판단한다.

> 이 작업이 `국가 단위 장기 시뮬레이션의 설명력 / 비교 가능성 / 재현성`을 올리는가?

`예`면 상위 우선순위,
`아니오`면 후순위다.

---

## 0.5 Swarm Mode 복구 목표

현재 Swarm Mode의 목표는 "많은 점이 움직이는 화면"이 아니다. 목표는 아래다.

> **Persona가 있는 대량 에이전트들이 시나리오를 이해하고, `t` 내부에서 계속 협의/충돌/전파하며, 그 과정을 가볍고 안정적으로 시각화하는 엔진.**

### 현재 문제 인식

| 영역 | 문제 | 결과 |
|------|------|------|
| 실행 안정성 | live stream payload가 무겁고 observer cell에 대형 vector가 포함됨 | 에이전트 수가 조금만 늘어도 WebSocket/React/Pixi 이전에 payload가 병목 |
| Swarm Genesis | `role-0` 같은 synthetic role과 단순 ring 배치가 중심 | persona/시나리오/지역/이해관계가 약해 "사람"이 아니라 랜덤 점처럼 보임 |
| Persona Grounding | persona text, attrs, scenario prompt가 thought/action/position에 충분히 고정되지 않음 | Agent Stream 생각이 추상적이고 시나리오 반영 여부가 불명확 |
| Agent Interaction | 내부 substep은 생겼지만 누가 누구와 왜 협의/충돌했는지 event가 부족 | 에이전트끼리 소통하는지 필드와 로그에서 확인하기 어려움 |
| Thought/Action 품질 | action summary가 짧고 영어 fallback이 남아 있음 | 한국어 UI에서 몰입이 깨지고 의사결정 흔적으로 보기 어려움 |
| Field Visualization | 협의/충돌/전파가 Pixi field에 transient signal로 표시되지 않음 | MiroFish식 "살아있는 필드 콘솔" 체감이 약함 |
| Runtime UX | progress, heartbeat, reconnect 상태 표현이 약함 | 긴 실행 중 멈춘 것처럼 보이고 간헐적 disconnect가 제품 신뢰를 깎음 |

### 성능 목표

| 규모 | 목표 |
|------|------|
| 1k agents | 안정적인 stream 실행, progress/heartbeat 표시, compact observer payload |
| 5k agents | compact scene + sampled observer 기준 안정 실행 |
| 10k agents | full agent detail 금지, meso/bloc 중심 표시, detail은 선택 조회 |

성능 원칙:

- WebSocket stream에 `gene_vec`, `thought_vec`, `worldview_vec` 같은 대형 vector를 싣지 않는다.
- React state에 full agent array를 상시 보관하지 않는다.
- Pixi에는 sampled scene, compact pressure grid, transient interaction edge만 전달한다.
- LLM은 기본 packet mode이며 agent mode는 sample/cap이 필수다.
- Review/trajectory는 모든 internal substep마다 만들지 않고 interval/summary 기반으로만 만든다.

### 품질 목표

- 에이전트는 persona, role, zone, scenario를 초기 상태부터 인지해야 한다.
- 한국어 UI에서는 thought/action/stream summary가 한국어로 표시되어야 한다.
- action은 `행동 + 이유 + 대상` 구조를 가져야 한다.
- agent-agent, group-group 협의/충돌은 event로 남아야 한다.
- 필드에는 협의, 충돌, rumor/policy 전파가 transient edge/pulse/ripple로 보여야 한다.
- 연결이 끊겨도 heartbeat timeout, reconnect, latest state resync로 복구 가능해야 한다.

### 실행 순서

| 순위 | 작업 | 완료 기준 |
|------|------|-----------|
| 1 | Stream Payload Diet | 완료: observer payload에서 대형 vector 제거, compact DTO 테스트 추가 |
| 2 | Run Progress & Heartbeat | 완료: `started`, `step`, `heartbeat`, `done`, `error` event와 진행률/스피너 표시 |
| 3 | Persona-aware Swarm Genesis | 완료: persona catalog 기반 role/zone/bloc/position seed, synthetic role은 fallback으로만 사용 |
| 4 | Interaction Event Layer | 완료: t 내부 협의/충돌/전파 event 생성, top-K/sample/TTL로 제한 |
| 5 | Pixi Interaction Visualization | 완료: interaction edge/pulse layer 추가, 협의/충돌 색상 분리 |
| 6 | Thought/Action Grounding | 완료: locale-aware 한국어 summary, persona/scenario/recent interaction prompt 강화 |
| 7 | Runtime Reliability | 완료: WebSocket ping/pong, heartbeat stale 감지, 1회 재연결, bounded stream queue/backpressure 적용 |

### 첫 번째 스프린트 완료 기준

- 1k agents stream이 안정적으로 돈다.
- observer payload에 대형 vector가 없다.
- 실행 탭에 진행률, 스피너, 마지막 heartbeat 시간이 보인다.
- WebSocket step event가 progress 정보를 포함한다.
- 기존 테스트 통과 + payload compact 테스트가 추가된다.

이 단계가 끝나기 전에는 시각 효과를 더 넣지 않는다. 먼저 혈관을 뚫고, 그 다음 persona와 field 체감을 올린다.

---

## 0.6 Intra-T Scene Stream 목표

현재 가장 큰 체감 결손은 `t`가 너무 "순간 이동"처럼 느껴진다는 점이다. End4D의 `t`는 한 프레임이 아니라 **한 권의 책 / 한 장(chapter) / 하나의 기간**이어야 한다. 사용자는 지금처럼 timeline에서 `t=1 → t=2 → t=3`을 클릭해서 다음 장면으로 넘어가되, 선택된 `t` 내부에서는 동영상을 보듯 에이전트들이 계속 협의하고 충돌하고 전파하는 장면 스트림을 봐야 한다.

### 핵심 철학

```text
t 선택 방식: 사용자가 현재처럼 discrete t를 클릭해서 이동
t 내부 경험: 선택된 t 안에서 scene stream이 자동 재생됨
t 의미: 순간 상태가 아니라, 한 기간 동안의 사회적 전개를 압축한 장면 묶음
```

비유:

- `t=1`은 소설의 1권이다.
- `t=1` 내부의 scene들은 1권 안의 장면, 대화, 갈등, 소문, 이동, 협상이다.
- `t=2`는 그 장면들의 결과가 누적되어 넘어간 다음 권이다.

따라서 엔진은 다음 구조를 목표로 한다.

```text
Timestep(t)
├─ Scene 1: 상황 감지 / 지역 압력 상승
├─ Scene 2: agent-agent 접촉
├─ Scene 3: group 내부 협의
├─ Scene 4: 갈등/협력/소문 전파
├─ Scene 5: 정책/충격 해석
├─ Scene 6: 행동 선택 조정
└─ Commit: t+1 상태로 수렴
```

### 현재 문제 인식

| 영역 | 문제 | 결과 |
|------|------|------|
| t 내부 전개 | internal substep은 있으나 scene/event stream으로 드러나지 않음 | t가 갑자기 건너뛰고 상태만 바뀌는 느낌 |
| 전개 속도 | 계산 완료 시점에 step이 한꺼번에 밀려옴 | 특정 t만 와다다 강조되고 살아있는 흐름이 약함 |
| 상태 변화 | scene 단위 누적이 아니라 t commit에서 급변해 보임 | 세계가 "살아 움직인다"보다 "업데이트된다"에 가까움 |
| 관계 표현 | interaction edge는 생겼지만 scene timeline과 결합되지 않음 | 누가 왜 협의/충돌했는지 시간적 서사가 약함 |
| Agent Stream | thought/action은 있으나 장면 로그가 약함 | 에이전트가 기간 안에서 무엇을 겪었는지 잘 안 보임 |

### UX 원칙

- 사용자는 timeline에서 `t`를 직접 선택한다.
- 선택된 `t` 내부에서는 `scene 1/N → scene 2/N → ...`이 자동 재생된다.
- 사용자는 scene 재생을 `pause / resume / speed`로 제어할 수 있다.
- 실행 중에는 엔진이 internal substep을 계산하는 즉시 scene event를 내보낸다. 즉, 사용자는 사후 재생이 아니라 "지금 계산되고 있는 세계"를 전지적 관찰자처럼 본다.
- 이미 계산된 snapshot을 다시 열어도 해당 `t`의 scene stream을 replay할 수 있어야 한다.
- t 내부 scene은 너무 많은 raw event를 보여주지 않고, top-K narrative event로 압축한다.

### 데이터 모델 목표

| 필드 | 의미 |
|------|------|
| `scene_id` | `t=4.scene=03` 같은 안정적 ID |
| `t` | 소속 timestep |
| `scene_index` / `scene_count` | t 내부 장면 순서 |
| `scene_type` | `observation`, `dialogue`, `group_deliberation`, `conflict`, `alignment`, `rumor`, `policy`, `movement`, `commit` |
| `source_agent_ids` | 장면을 시작한 agent들 |
| `target_agent_ids` | 영향을 받은 agent들 |
| `source_group_id` / `target_group_id` | group/bloc 단위 관계 |
| `summary` | 사용자가 읽을 수 있는 한 줄 장면 설명 |
| `sentiment` | `positive`, `neutral`, `negative`, `hostile` |
| `pressure_delta` | 장면이 압력에 준 영향 |
| `relationship_delta` | 관계/협력/갈등 신호 |
| `visual_hint` | field에서 선/pulse/ripple/heat update로 보여줄 힌트 |

### 구현 체크리스트

| 순위 | 작업 | 완료 기준 |
|------|------|-----------|
| 1 | `IntraTSceneEvent` 모델 정의 | 완료: `Snapshot.scene_events`, REST snapshot DTO, frontend `IntraTSceneEvent` 타입 추가 |
| 2 | Scene Generator | 완료: 기존 internal interaction과 group pressure를 top-K scene event로 변환 |
| 3 | Scene Accumulation | 완료: scene pressure/relationship delta를 참여 agent action_state와 collective_pressure에 소프트 누적 |
| 4 | WebSocket Scene Stream | 완료: internal substep 계산 중 `scene` event를 즉시 보내고 `t`, `scene_index`, `scene_count`, `progress` 포함 |
| 5 | Snapshot Scene Replay | 완료: snapshot 조회 응답에 `scene_events` 포함, 완료된 t에서도 관계선 replay 가능 |
| 6 | Field Playback Layer | 완료: scene event를 CenterMap interaction layer에 연결하고 live/fresh scene pulse 강조 |
| 7 | Agent/Group Scene Log | 완료: 실행 패널에 `t 내부 장면 스트림`, 선택 agent/group 기준 scene 필터 표시 |
| 8 | Playback Controls | 완료: snapshot scene scrubber, pause/resume, speed, replay 버튼 추가 |
| 9 | Narrative Quality Metrics | 완료: `scenes_per_t`, `agent_participation_rate`, `relationship_event_count`, `dead_timestep_rate`, `narrative_continuity_score` 저장/노출 |
| 10 | Performance Guard | 완료: scene event top-K, WebSocket queue backpressure, frontend 최근 scene window 제한 적용 |

### 첫 번째 스프린트 완료 기준

- 하나의 `t` 안에서 최소 6~12개의 scene event가 생성된다.
- WebSocket으로 `scene` event가 들어오며, UI가 `t=3 · scene 4/10`을 표시한다.
- 필드에서 scene 순서에 맞춰 관계선/압력 변화가 순차적으로 보인다.
- timeline에서 이미 끝난 t를 클릭해도 해당 t 내부 scene을 replay할 수 있다.
- 실행 중에는 internal substep이 계산되는 즉시 scene이 들어와 "계산 중인 세계"처럼 보인다. 완료 후 snapshot 조회에서는 같은 scene을 replay한다.
- 기존 `step` snapshot 의미는 유지한다. 즉 t 클릭/비교/리뷰 워크플로우는 깨지지 않는다.

이 단계의 목표는 "더 많은 애니메이션"이 아니다. 목표는 **상태 사이의 빈 공간을 사회적 장면으로 채워, t가 기간처럼 느껴지게 만드는 것**이다.

---

## 1. 핵심 결손 표

| 영역 | 현재 상태 | 우선순위 | 문제 |
|------|-----------|----------|------|
| intra-t scene stream | 전무~초기 | 최상 | t 내부가 장면으로 재생되지 않아 timestep이 갑자기 건너뛰는 느낌 |
| persona-aware Genesis | 부분 구현 | 최상 | 국가별 persona 분포가 role mix까지는 일부 반영되지만 zone seed, initial energy/z bias, 장기 초기 조건 반영은 더 필요 |
| LLM runtime stability / live dominance | 초기 구현 | 최상 | provider 연결은 가능하지만 task별 success rate, fallback reason, degraded task가 충분히 보이지 않아 실제로 LLM이 주도하는지 판단하기 어려움 |
| LLM 호출 입구 (Facade / Engine API) | 초기 구현 | 최상 | abstraction은 있지만 엔진 개발자가 `think()`, `decide_actions()`처럼 일관되게 쓰는 공통 입구가 더 필요 |
| Prompt Template 체계 | 부분 구현 | 높음 | registry와 contract가 생겼지만 평가 루프와 결과물 provenance 저장은 더 필요 |
| group-level belief state | 부분 구현 | 최상 | 국가 단위 분석에 필요한 role/persona/zone 집단 stance/cohesion/tension drift와 비교 리포트가 아직 약함 |
| session/world comparison workflow | 부분 구현 | 최상 | 저장은 되지만 장기 시나리오 비교 도구로는 아직 부족 |
| post-simulation LLM review layer | 초기 구현 | 최상 | 시뮬 종료 후 자동 요약, diff report, timeline annotation, 자연어 질의가 약해 “그래서 무엇이 중요한가”를 바로 답하지 못함 |
| prompt/provider/dataset provenance | 부분 구현 | 높음 | LLM/provider/prompt/dataset 메타가 결과 분석 전반에 충분히 남지 않음 |
| policy/event semantics | 부분 구현 | 높음 | 이벤트 주입은 있으나 정책 단위 실험 모델로는 아직 단순함 |
| social elevation z-field | 부분 구현 | 높음 | z는 재도입됐지만 contour 품질, z drift 비교, 정책/집단 상태와의 연결 설명력이 더 필요 |
| Nemotron-Personas-Korea 및 다국가 실제 운영 연동 | seed adapter + manifest sync + 운영 전 단계 | 높음 | 실제 대용량 pack 설치·품질 검증은 더 필요 |
| 비용 제어 & 호출 스케줄링 | 초기 구현 | 높음 | 샘플링·간격 제어는 있으나 task priority, adaptive budget, cost accounting이 더 필요 |
| Storage Layer 추상화 | 부분 구현 | 높음 | file envelope와 integrity는 있으나 snapshot index, archive, partial restore 최적화가 더 필요 |
| 대규모 에이전트 성능 최적화 | 중간 이하 | 높음 | 벤치 하네스는 강화됐지만 10k+ 실측 데이터 축적, 병렬 처리·lazy update 검증이 더 필요 |
| 챗봇 UI / 대화 엔진 | 전무 | 중 | 중요하지만 현재는 코어 시뮬레이션 설명력보다 후순위 |
| 사용자 입력 → Thought/Worldview 업데이트 파이프라인 | 전무 | 중 | 데이터 플라이휠 핵심이지만 내부 엔진 플라이휠 이후가 더 적절 |
| 사용자 데이터 수집·동의·익명화 체계 | 전무 | 중 | 제품화에는 필수지만 지금은 엔진 코어보다 후순위 |
| 멀티 에이전트 자연어 토론 | 엔진 루프 부분 구현 | 중 | 직접 대화/집단 협상은 들어갔고 UI·대규모 비용 튜닝이 남음 |

---

## 2. 왜 중요한가

### 2.1 챗봇 UI / 대화 엔진

현재 God View는 시뮬레이션을 만들고 관찰하는 도구다. 하지만 제품 목표가 “복잡계 이해·시나리오 탐색·의사결정 지원”이라면 사용자는 자연어로 세계에 질문하고, 특정 페르소나 집단에게 물어보고, 정책 주입 전후의 반응을 대화로 해석할 수 있어야 한다.

필수 산출물:
- `ChatPanel` UI
- 대화 세션 모델
- `POST /worlds/{id}/chat`
- 페르소나/역할/시점 t를 지정하는 대화 컨텍스트
- 응답 근거로 사용한 snapshot, persona, event metadata

### 2.2 사용자 입력 → Thought/Worldview 업데이트

현재 Thought/Worldview는 시뮬레이션 내부 상태와 memory 문자열을 기반으로 주기 갱신된다. 사용자의 대화 입력이 세포의 memory, emotion, thought, worldview에 들어가는 경로가 없다. 이 경로가 없으면 “사용자가 시나리오를 학습시키는 데이터 플라이휠”이 만들어지지 않는다.

필수 산출물:
- 사용자 발화 정규화
- 발화 → event/memory 변환
- 발화 대상: 전체 세계, 특정 역할, 특정 persona, 특정 cell
- Thought/Worldview 갱신 트리거
- 주입 전후 비교 로그

### 2.3 데이터 동의·익명화

대화 입력과 사용자 업로드 데이터가 들어오면 개인정보·민감정보·저작권 데이터가 섞일 수 있다. 제품화하려면 동의, 보존 기간, 익명화, 삭제 요청, 학습 사용 여부를 분리해야 한다.

필수 산출물:
- 데이터 사용 동의 플래그
- raw text와 anonymized text 분리 저장
- PII redaction pipeline
- 사용자 삭제 요청 경로
- dataset attribution과 사용자 데이터 provenance 기록

### 2.4 Nemotron-Personas-Korea 실제 연동

현재 adapter는 JSONL/JSON/CSV 및 선택적 HF streaming을 지원한다. 그러나 실제 `nvidia/Nemotron-Personas-Korea`를 설치 환경에서 end-to-end 검증한 상태는 아니다. 또한 필드가 많기 때문에 어떤 필드를 persona text, 역할, 지역, 나이, 관심사로 쓸지 품질 기준이 필요하다.

필수 산출물:
- 실제 HF streaming 검증
- `sample_personas.py`로 만든 `kr.jsonl` 샘플 검증
- 필드 매핑 테스트 fixture
- dataset license/attribution UI
- 국가별 dataset registry

### 2.5 페르소나 기반 초기 세계 자동 생성

현재 Genesis는 prompt keyword로 `t_max`, `initial_cell_count`, role catalog, nutrient scale을 고른다. Persona dataset이 연결되어도 세계 생성 판단 자체는 아직 충분히 persona-aware하지 않다.

필수 산출물:
- persona 분포 요약: occupation, region, age, interests
- 분포 기반 role mix 결정
- 분포 기반 초기 위치/energy/gene bias
- 한국/미국/일본 등 국가별 fallback 정책

### 2.7 Social Elevation z-field

현재 엔진은 `(x, y, z, t)`를 유지하며 `z`를 social elevation으로 저장·복원하고, God Mode에서 `z_mode / z_weight / z_scale`까지 제어할 수 있다. 그러나 다음이 더 필요하다.

- contour 품질 개선: 단순 밴드가 아니라 더 자연스러운 고도장 표현
- z drift 비교: session/world comparison에서 정책 전후 또는 fork 간 elevation 변화 비교
- z provenance: 현재 z가 어떤 mode와 어떤 agent state 축에서 계산됐는지 결과물에 더 명확히 노출
- group/policy linkage: coalition drift, policy sensitivity, memory accumulation과 z 변화의 관계를 리포트할 수 있어야 함

### 2.8 시뮬 후 LLM 리뷰 레이어

현재 LLM은 agent cognition에는 깊게 들어가 있지만, 시뮬 종료 후 결과를 읽어주는 분석가 레이어는 약하다. 이 결손이 크면 사용자는 시뮬레이션을 돌린 뒤 raw timeline과 기본 통계만 보고 직접 해석해야 하므로 제품이 엔진 디버거처럼 느껴질 수 있다.

필수 산출물:
- world summary generator
- timeline annotation generator
- baseline vs intervention diff report
- causal insight generation
- 자연어 review query (`review.ask(...)`)

### 2.9 LLM 호출 안정화와 실제 주도성

현재는 LLM 설정 입구와 `LLM-first` 프로필이 생겼지만, 여전히 아래 질문에 즉답하기 어렵다.

- 어떤 task가 실제로 live provider를 가장 많이 타는가?
- 어떤 task가 fallback pressure 때문에 degraded 되었는가?
- provider 오류인지, budget cap인지, adaptive priority skip인지 원인이 무엇인가?
- strict mode에서 review/action/dialogue가 안정적으로 유지되는가?

이 결손이 크면, 기능은 많아 보여도 실제 실행은 heuristic fallback 비중이 높아지고, 제품 핵심 가치인 “LLM 기반 자율 에이전트 + 의미 있는 분석”이 약해진다.

필수 산출물:
- task별 success rate / fallback rate
- top failure reason / degraded task 목록
- recent live dominance와 task priority/budget의 상관관계
- no-silent-fallback health 진단
- 최소 1개 `LLM-first` 운영 프로필에서 안정적 success baseline

### 2.6 멀티 에이전트 대화 / 집단 상호작용

현재 세포는 벡터와 규칙 상호작용에 더해, 주기적인 직접 대화(`agent_dialogue`)와 역할 집단 협상(`group_deliberation`)을 수행할 수 있다. 다음 단계는 이 결과를 UI와 장기 비교 리포트에 더 명확히 노출하는 것이다.

필수 산출물:
- role group conversation: 엔진 루프 1차 구현
- persona sample panel
- group stance summary: API 1차 구현
- conversation → event injection
- group-level memory/worldview update: memory/action_state 1차 구현

---

## 3. 현재 권장 구현 순서

| 순서 | 작업 | 이유 |
|------|------|------|
| 1 | persona-aware Genesis | 국가 단위 사회의 초기 조건 품질을 끌어올림 |
| 2 | LLM 호출 안정화 / live dominance | 실제로 LLM이 주도적으로 동작하는지 먼저 보이게 해야 함 |
| 3 | post-simulation LLM review layer | 결과를 자연어 요약·주석·비교 가능한 분석 워크플로우로 전환 |
| 4 | Review → Action 워크플로우 | 리뷰가 바로 다음 실험/주입/비교로 이어져야 함 |
| 5 | group-level belief state | 개별 agent를 넘어 사회 집단 상태를 읽을 수 있게 함 |
| 6 | policy/event semantics 강화 | 정책 시뮬레이터로서의 설명력을 높임 |
| 7 | Storage Layer 고도화 | 스냅샷, 포크, 재현성, 무결성의 기반 |
| 8 | session/world comparison | 장기 시나리오 실험을 전문가 워크플로우로 만듦 |
| 9 | Nemotron 및 다국가 registry 운영 검증 | 데이터 레이어를 제품화 가능한 수준으로 올림 |
| 10 | 대규모 성능 벤치와 최적화 | 10k+ 규모 신뢰성 확보 |
| 11 | ChatPanel + 대화 엔진 | 코어 시뮬레이션 위에 자연어 인터페이스를 얹음 |

---

## 4. 완료 기준

### Phase A — 대화 표면

- 사용자가 God View에서 자연어 입력 가능
- 특정 t, role, persona 범위를 지정 가능
- 대화 응답에 참조한 persona/source/snapshot metadata 표시

### Phase B — 상태 갱신

- 사용자 입력이 cell memory에 남음
- 조건에 따라 emotion spike 또는 inject event로 변환됨
- Thought/Worldview 재계산 트리거가 명시됨

### Phase C — 데이터 안전

- 사용자 입력 저장 전 동의 플래그 존재
- 익명화된 텍스트와 원문 보존 정책이 분리됨
- attribution 필요한 외부 dataset 출처가 UI/API에 표시됨

### Phase D — Persona 실사용

- `nvidia/Nemotron-Personas-Korea` 또는 로컬 `kr.jsonl`로 world 생성 성공
- 최소 100개 이상 persona seed preview 가능
- occupation/region/age 등 핵심 필드 매핑 테스트 통과

---

## 5. 현재 핵심 체크리스트

### 5.1 반드시 먼저 완성할 것

- [ ] persona distribution이 Genesis 결과(`t_max`, role mix, nutrient scale, initial bias)에 반영된다
- [ ] task별 `LLM success rate / fallback rate / top failure reason`이 runtime에서 보인다
- [ ] degraded task와 live dominance가 action/dialogue/review 기준으로 진단된다
- [ ] 엔진이 `llm_facade.think() / decide_actions() / interpret_policy()` 같은 일관된 LLM 입구를 사용한다
- [ ] task별 budget, sampling, cadence가 메타와 함께 추적된다
- [ ] role/persona group 기준의 stance/cohesion/tension drift가 저장·조회된다
- [ ] 시뮬 종료 후 자동 요약과 주요 시점 timeline annotation이 생성된다
- [ ] baseline vs intervention/world vs world diff report가 자연어로 생성된다
- [ ] policy/event injection이 강도, 범위, 지속시간을 가진다
- [ ] session에서 world 간 비교와 최근 world reopen이 가능하다
- [ ] 결과물에 `provider / model / prompt_version / dataset_version` 메타가 남는다

### 5.2 그 다음 완성할 것

- [x] Nemotron-KR 포함 국가별 dataset registry가 운영 가능한 구조가 된다
- [ ] 실제 대용량 데이터 pack 설치/검증과 국가별 품질 리포트가 가능하다
- [ ] sector/policy pack을 데이터 레이어로 추가할 수 있다
- [ ] report/export payload가 전문가 워크플로우에 맞게 정리된다

### 5.3 아직 후순위로 둘 것

- [ ] 챗봇형 대화 UX
- [ ] 사용자 데이터 동의/익명화
- [ ] 멀티 에이전트 자연어 토론

---

## 6. 현재 개발 목표 한 문장

> 먼저 End4D를 `국가 단위 장기 사회 시뮬레이션의 초기 조건·집단 상태·정책 비교`를 신뢰성 있게 다루는 엔진으로 만들고, 그 위에 대화형 제품 레이어를 얹는다.
