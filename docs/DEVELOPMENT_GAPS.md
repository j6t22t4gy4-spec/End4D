# Organic4D — 핵심 결손 및 보완 로드맵

> 목적: 개발 중 방향을 잃지 않기 위해, 현재 엔진이 제품 목표에 비해 무엇이 부족한지 명시한다.  
> 기준 목표: 국가별 실제 persona seed를 바탕으로 사용자가 대화하고, 그 대화가 Thought/Worldview와 시뮬레이션 상태를 갱신하며, 데이터 동의·익명화·피드백 루프까지 갖춘 복잡계 시나리오 엔진.

---

## 1. 핵심 결손 표

| 영역 | 현재 상태 | 우선순위 | 문제 |
|------|-----------|----------|------|
| 챗봇 UI / 대화 엔진 | 전무 | 최상 | God View는 있으나 사용자가 페르소나/세계와 대화하는 인터페이스가 없음 |
| 사용자 입력 → Thought/Worldview 업데이트 파이프라인 | 전무 | 최상 | 데이터 플라이휠의 핵심이 아직 설계·구현되지 않음 |
| 사용자 데이터 수집·동의·익명화 체계 | 전무 | 최상 | 법적 리스크와 데이터 품질 리스크가 동시에 존재 |
| Nemotron-Personas-Korea 실제 운영 연동 | seed adapter + Phase 9 계획 수준 | 높음 | HF streaming/sample script는 있으나 실데이터 연결 검증, 필드 매핑 품질, 운영 설정 검증이 부족 |
| 페르소나 기반 초기 세계 자동 생성 | 부분 구현 | 중 | Prompt Genesis는 있으나 persona 분포가 t_max, role mix, nutrient scale 등에 충분히 반영되지 않음 |
| 멀티 에이전트 대화 / 집단 상호작용 | 미비 | 중 | 현재는 규칙 기반 시뮬레이션 중심이며 페르소나 간 자연어 대화 구조가 약함 |

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

현재 세포는 벡터와 규칙으로 상호작용하지만, 자연어 대화 집단이 형성되는 구조는 없다. “시장참여자 vs 규제자 vs 시민” 같은 그룹 대화가 가능해야 의사결정 지원 제품으로 설득력이 커진다.

필수 산출물:
- role group conversation
- persona sample panel
- group stance summary
- conversation → event injection
- group-level memory/worldview update

---

## 3. 권장 구현 순서

| 순서 | 작업 | 이유 |
|------|------|------|
| 1 | 내부 에이전트 상호작용 memory | 챗 UI 없이도 엔진의 본질인 agent↔agent 변화 루프가 생김 |
| 2 | Thought 입력에 최근 memory/social observation 반영 | 관찰 데이터가 중기 전략 벡터에 실제 반영됨 |
| 3 | role/persona 그룹 관측 API | 엔진 내부 상태와 집단 형성을 제품/분석 레이어에서 확인 가능 |
| 4 | persona-aware Genesis | 단순 seed를 넘어 세계 생성 자체를 dataset 기반화 |
| 5 | Nemotron 실제 샘플 검증 + field mapping | persona seed의 품질을 현실적으로 확인 |
| 6 | ChatPanel + `POST /worlds/{id}/chat` | 엔진 내부 루프 위에 사용자 상호작용을 얹음 |
| 7 | 사용자 발화 → memory/event 변환 | 대화가 시뮬레이션 상태를 바꾸는 연결 |
| 8 | consent/anonymization 기본 모델 | 사용자 데이터 플라이휠 전에 법적 리스크 차단 |
| 9 | group conversation | 멀티 에이전트 제품 가치를 강화 |

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

## 5. 현재 우선순위 메모

현재 개발 우선순위는 **채팅 인터페이스 이전의 엔진/에이전트 본질 구현**이다.  
사용자 발화 플라이휠도 중요하지만, 그 전에 에이전트가 서로를 관찰하고, 관찰 결과가 memory에 남고, memory가 Thought/Worldview에 반영되는 내부 루프가 있어야 한다.

따라서 다음 개발 목표는 다음 한 문장으로 고정한다:

> 먼저 엔진 안에서 페르소나/역할 에이전트들이 서로를 관찰하고 memory·Thought·Worldview를 바꾸는 데이터 플라이휠을 만든 뒤, 그 위에 사용자 대화·동의·익명화 레이어를 얹는다.
