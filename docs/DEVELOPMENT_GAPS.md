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

## 1. 핵심 결손 표

| 영역 | 현재 상태 | 우선순위 | 문제 |
|------|-----------|----------|------|
| persona-aware Genesis | 부분 구현 | 최상 | 국가별 persona 분포가 초기 세계 구조를 충분히 결정하지 못함 |
| group-level belief state | 부분 구현 | 최상 | 국가 단위 분석에 필요한 집단 stance/cohesion/tension drift가 아직 약함 |
| session/world comparison workflow | 부분 구현 | 최상 | 저장은 되지만 장기 시나리오 비교 도구로는 아직 부족 |
| prompt/provider/dataset provenance | 부분 구현 | 높음 | LLM/provider/prompt/dataset 메타가 결과 분석 전반에 충분히 남지 않음 |
| policy/event semantics | 부분 구현 | 높음 | 이벤트 주입은 있으나 정책 단위 실험 모델로는 아직 단순함 |
| Nemotron-Personas-Korea 및 다국가 실제 운영 연동 | seed adapter + manifest sync + 운영 전 단계 | 높음 | 실제 대용량 pack 설치·품질 검증은 더 필요 |
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
| 2 | group-level belief state | 개별 agent를 넘어 사회 집단 상태를 읽을 수 있게 함 |
| 3 | policy/event semantics 강화 | 정책 시뮬레이터로서의 설명력을 높임 |
| 4 | session/world comparison | 장기 시나리오 실험을 전문가 워크플로우로 만듦 |
| 5 | prompt/provider/dataset provenance 저장 | 예측 결과의 재현성과 감사 가능성 확보 |
| 6 | Nemotron 및 다국가 registry 운영 검증 | 데이터 레이어를 제품화 가능한 수준으로 올림 |
| 7 | ChatPanel + 대화 엔진 | 코어 시뮬레이션 위에 자연어 인터페이스를 얹음 |
| 8 | 사용자 발화 → memory/event 변환 | 대화가 실제 시뮬레이션 상태를 바꾸게 함 |
| 9 | consent/anonymization | 사용자 데이터 플라이휠의 법적 안전성 확보 |
| 10 | group conversation | 집단 정책 토론/협상 시뮬레이션 강화 |

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
- [ ] role/persona group 기준의 stance/cohesion/tension drift가 저장·조회된다
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
