# Organic4D — 구현 시퀀스

> 단계별 구현 순서. 의존성 고려.

---

## 0. 현재 기준선

이 문서는 단순한 기능 나열이 아니라, 아래 **최상위 제품 목표**를 기준으로 우선순위를 고정한다.

> **목표**: End4D를 `국가 단위 사회를 장기적으로 시뮬레이션·비교·예측`할 수 있는 범용 플랫폼으로 만든다.

이 목표 기준에서 중요한 순서는 다음과 같다.

1. **엔진 설명력**
   - 장기 시간축에서 belief dynamics가 실제로 누적·분기·군집화되어야 한다.
   - `(x, y, z, t)`에서 `z = social elevation` 의미가 계산과 저장에 남아야 한다.
2. **데이터 설명력**
   - 국가별 persona / policy / scenario 데이터가 엔진 상태를 의미 있게 바꿔야 한다.
3. **재현성과 비교 가능성**
   - 세션, 스냅샷, 설정 버전, prompt version, dataset provenance가 남아야 한다.
4. **전문가 워크플로우**
   - what-if, 복원, 비교, 리포트, 세션 스레드가 있어야 한다.
5. **제품 셸**
   - 앱형 UI, 로컬 런처, 추후 네이티브 셸은 그 다음이다.

즉, **채팅형 데모**보다 먼저 **국가 단위 장기 시뮬레이션 엔진의 정확한 루프와 재현성**을 완성해야 한다.

---

## 전체 흐름

```
Phase 0: 프로젝트 셋업
    ↓
Phase 1: 백엔드 기초 (모델·좌표·규칙) — LLM 제외
    ↓
Phase 2: 시간 흐름 엔진 (LangGraph)
    ↓
Phase 3: API 레이어 (REST + WebSocket)
    ↓
Phase 4: 프론트 기초 (2D 지도 + t 슬라이더)
    ↓
Phase 5: E2E 연결 (시뮬 실행 → 시각화)
    ↓
Phase 6: 3계층 감정·생각 생성 (Emotion, Thought, Worldview)
    ↓
Phase 7: God View 주입 + 시나리오 리포트
    ↓
Phase 8: 최적화·배포
    ↓
Phase 10A: 엔진/에이전트 데이터 플라이휠 기초
    ↓
Phase 10B: LLM 운영 코어
    ↓
Phase 11: 국가 단위 시뮬레이션 코어
    ↓
Phase 12: 비교·리포트·전문가 워크플로우
    ↓
Phase 13: 데이터 레이어 운영화
    ↓
Phase 14: 네이티브 앱 / 기관 배포
```

---

## Phase 0: 프로젝트 셋업

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 0.1 | 레포 구조 생성 | `engine/backend/`, `engine/frontend/`, `docs/` |
| 0.2 | Python venv + requirements | `requirements.txt` (FastAPI, LangGraph, numpy, pydantic) |
| 0.3 | Next.js 프로젝트 초기화 | `package.json`, 기본 App Router |
| 0.4 | Docker Compose 초안 | `docker-compose.yml` (backend, frontend) |
| 0.5 | README, .gitignore | 기본 문서 |

---

## Phase 1: 백엔드 기초 (LLM 제외)

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 1.1 | **세포 모델** | `models/cell.py` | — |
| | `(x,y,z,t)`, `zone`, `energy`, `gene_vec`, `memory`, `emotion_vec`, `thought_vec`, `worldview_vec` | Pydantic/dataclass | |
| 1.2 | **2D 좌표·상호작용 함수** | `core/coordinates.py` | 1.1 |
| | 거리 함수 `d(p1, p2)`, optional social elevation, zone friction, 시간 가중치 | | |
| 1.3 | **세계·스냅샷 모델** | `models/world.py` | 1.1 |
| | World, Snapshot, 영양분 이벤트 | | |
| 1.4 | **5대 규칙 로직 (LLM 제외)** | `core/rules.py` | 1.1, 1.2 |
| | 성장, 분열, 사멸, 융합, 돌연변이 | | |
| | emotion/thought/worldview 벡터는 임의 또는 고정 값으로 시작 | | |
| 1.5 | **단위 테스트** | `tests/test_rules.py` | 1.4 |
| | 규칙별 입력→출력 검증 | | |

---

## Phase 2: 시간 흐름 엔진 (LangGraph)

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 2.1 | **LangGraph 그래프 정의** | `graph/time_flow.py` | Phase 1 |
| | 노드: init → step_loop → (성장→분열→사멸→융합→돌연변이) | | |
| 2.2 | **t 스텝 루프** | `graph/nodes.py` | 2.1 |
| | 한 t에서 모든 규칙 적용, 다음 t로 전이 | | |
| 2.3 | **스냅샷 저장** | `core/snapshot.py` | 1.3, 2.1 |
| | 매 t (또는 N간격) 스냅샷 메모리/파일 | | |
| 2.4 | **커맨드라인 테스트** | `scripts/run_simulation.py` | 2.1 |
| | `python run_simulation.py`로 t=0..100 실행 | | |

---

## Phase 3: API 레이어

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 3.1 | **FastAPI 앱 뼈대** | `main.py` | Phase 2 |
| 3.2 | **REST 엔드포인트** | `api/worlds.py` | 3.1 |
| | `POST /worlds` 생성, `GET /worlds/{id}` 조회 | | |
| 3.3 | **시뮬 실행 API** | `api/run.py` | 2.1 |
| | `POST /worlds/{id}/run` — 동기 또는 job_id 반환 | | |
| 3.4 | **WebSocket 스트리밍** | `api/ws.py` | 3.3 |
| | t, 세포 수, 스냅샷 델타 실시간 전송 | | |
| 3.5 | **스냅샷 조회** | `api/snapshots.py` | 2.3 |
| | `GET /worlds/{id}/snapshots?t=` | | |
| 3.6 | **OpenAPI 문서** | 자동 생성 | 3.1 |

---

## Phase 4: 프론트 기초

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 4.1 | **Next.js + Three.js 설정** | `package.json` | Phase 0 |
| | React Three Fiber, 기본 Canvas | | |
| 4.2 | **SimulationMap 컴포넌트** | `components/SimulationMap/` | 4.1 |
| | 빈 2D 사회장, zone 레이어, 카메라/팬/줌 | | |
| 4.3 | **2D 대량 렌더 패턴** | `SimulationMap/AgentLayer.tsx` | 4.2 |
| | `(x,y)` 배열 → Canvas/WebGL 기반 대량 점 렌더, 세포 1K+ 대응 | | |
| 4.3a | **zone overlay** | `SimulationMap/ZoneLayer.tsx` | 4.3 |
| | 구역별 영향력, 정책 반경, 경계 시각화 | | |
| 4.3b | **typed buffer 업데이트** | 렌더 루프 | 4.3 |
| | 스냅샷 `(x,y)` / zone 상태를 TypedArray로 관리해 프레임 비용 억제 | | |
| 4.3c | **표시 개수 동적 조정** | layer capacity | 4.3 |
| | 세포 수 증가 시 샘플링/LOD 또는 레이어 재할당 | | |
| 4.3d | **emotion / zone color channel** | 인스턴스별 색상 | 4.3 |
| | 감정 색상 + 구역 영향 시각화를 함께 표현 | | |
| 4.4 | **시간 슬라이더** | `components/TimeSlider/` | 4.1 |
| | range input, t 값 상태 | | |
| 4.5 | **API 클라이언트** | `lib/api.ts` | Phase 3 |
| | fetch /worlds, /snapshots | | |

---

## Phase 5: E2E 연결

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 5.1 | **세계 생성 UI** | God View 초안 | 4.5, 3.2 |
| | 초기 세포 수, t_max 입력 → POST /worlds | | |
| 5.2 | **시뮬 실행 + WebSocket** | `hooks/useSimulation.ts` | 3.4, 4.5 |
| | run 클릭 → WS 연결 → t 업데이트 | | |
| 5.3 | **t 슬라이더 → 스냅샷 조회** | 4.4 + 3.5 | |
| | t 변경 시 GET /snapshots?t= → 2D 지도 업데이트 | | |
| 5.4 | **E2E 테스트** | 수동 또는 Playwright | 5.3 |
| | 생성 → 실행 → t 이동 → 시각화 확인 | | |

---

## Phase 6: 3계층 감정·생각 생성 (Emotion, Thought, Worldview)

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 6.1 | **Emotion Vector (규칙 기반)** | `core/emotion.py` | 1.1 |
| | 8차원(joy, anger, fear, calm 등), 매 t 업데이트. LLM 0 | | |
| 6.2 | **Emotion 시각화** | `CellInstances` setColorAt | 4.3, 6.1 |
| | 색상=주요 감정, 크기=강도 | | |
| 6.3 | **Ollama + sentence-transformers** | `llm/` | Phase 1 |
| 6.4 | **Thought Vector** | `llm/thought.py` | 6.3 |
| | 10~50 t마다 LLM → 256차원. 융합 조건 70% | | |
| 6.5 | **Worldview Vector** | `llm/worldview.py` | 6.3 |
| | t≥200 또는 메모리 100+ 시 384차원. sentence-transformers | | |
| 6.6 | **규칙에 3계층 결합** | `core/rules.py` 수정 | 1.4, 6.1, 6.4, 6.5 |
| | 융합: Thought sim 0.7+ (70%), Worldview 호환. 분열/돌연변이 시 벡터 변이 | | |
| 6.7 | **메모리 저장** | Redis 또는 in-memory | 1.1 |

---

## Phase 7: God View 주입 + 시나리오

> **진행**: 7.1~7.4 반영됨 — `POST /worlds/{id}/inject`, `GET /worlds/{id}/timeline`, `create_resume_time_flow_graph`, God View `InjectPanel`·`ScenarioTimeline`. LLM·영속 DB는 `settings.py` 환경 변수만 정의(후속 연동).

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 7.1 | **주입 API** | `POST /worlds/{id}/inject` | 2.1, 3.1 |
| | `{ t, event_type, payload }` | | |
| 7.2 | **주입 UI** | God View 모달/패널 | 5.1, 7.1 |
| | t 입력, 이벤트 타입, payload 입력 | | |
| 7.3 | **재실행 또는 포워드** | 그래프 수정 | 7.1 |
| | t 시점 주입 시 이후 t 재계산 | | |
| 7.4 | **시나리오 리포트 (선택)** | Recharts, 집계 | 5.3 |
| | t별 세포 수, 에너지 합계 차트 | | |

---

## Phase 8: 최적화·배포

> **진행**: 8.1·8.3 반영 — `docker-compose.prod.yml`, 프론트 standalone `Dockerfile`, `Dockerfile.dev`, 백엔드 HEALTHCHECK·non-root(프로덕션), `get_cors_origins`, 시각화 샘플링 + `NEXT_PUBLIC_MAX_VISUAL_CELLS`, 백엔드 `SpatialHashGrid` 기반 Emotion·Death·Fusion 인접 검색 pruning, `benchmark_simulation.py`. **8.2 PostgreSQL / 8.4 델타 저장 / 8.5 Celery** 는 선택·후속.

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 8.1 | **Docker 이미지** | backend, frontend Dockerfile | Phase 0 |
| 8.2 | **SQLite → PostgreSQL (선택)** | 마이그레이션 | Phase 1 |
| 8.3 | **2D 대량 렌더 최적화** | 세포 10K+ | 4.3 |
| | LOD, 시각화 샘플링, zone heatmap batching | | |
| 8.4 | **델타 저장 (선택)** | ARCHITECTURE 1.2 | 2.3 |
| 8.5 | **Celery 워커 (선택)** | 장기 시뮬 | 3.3 |
| 8.6 | **성능 벤치마크** | `scripts/benchmark_simulation.py` | 2.1 |

---

## 의존성 다이어그램 (요약)

```
0 → 1.1 → 1.2 → 1.3 → 1.4 → 1.5
              ↘
               2.1 → 2.2 → 2.3 → 2.4
                    ↘
                     3.1 → 3.2 → 3.3 → 3.4 → 3.5
                          ↘
4.1 → 4.2 → 4.3 → 4.4 ────→ 5.1 → 5.2 → 5.3 → 5.4
4.5 ← 3.x ─────────────────────────────────────┘
                                              ↘
                                                6.1~6.6 → 7.1~7.4 → 8.1~8.5
```

---

## 병렬 가능 구간

| Phase | 백엔드 | 프론트 | 비고 |
|-------|--------|--------|------|
| 1~2 | ○ | — | 백엔드 먼저 |
| 3 | ○ | — | API 정의 필요 |
| 4 | (대기) | ○ | API 스펙만 있으면 스텁으로 진행 가능 |
| 5 | ○ | ○ | 연동 |
| 6 | ○ | (선택) | 백엔드만 |
| 7 | ○ | ○ | 함께 |

---

---

## Phase 9 (개념 반영 후속)

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 9.1 | Genesis **실 LLM API** 연동 | `world_genesis` → JSON 스키마 고정, Ollama/OpenAI 등 |
| 9.2 | 국가별 persona dataset seed | `persona_dataset.py`, `persona_*` cell fields, `ORGANIC4D_PERSONA_*` 환경 변수 |
| 9.3 | NVIDIA Nemotron-Personas-Korea 등 국가별 데이터셋 연결 | `ORGANIC4D_PERSONA_HF_DATASET_KR=nvidia/Nemotron-Personas-Korea`, `sample_personas.py`, 타 국가 dataset 확장 |
| 9.4 | 역할별 Emotion 가중·규칙 | `emotion.py` 역할 키/페르소나 속성 분기 |
| 9.5 | God View 역할·페르소나 레이블/필터 시각화 | 색/필터로 역할·국가·페르소나 구분 |

---

## Phase 10B: LLM 운영 코어

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 10B.1 | LLM Facade / Convenient Interface | `llm/facade.py`, `llm_facade.think()`, `decide_actions()`, `interpret_policy()` |
| 10B.2 | Task별 prompt template 정규화 | `prompt_engineering.py`, `prompt_registry.py`, task contract/schema |
| 10B.3 | LLM budget & cadence 제어 | task batch cap, agent sample size, dialogue/deliberation interval |
| 10B.4 | Provider / prompt / fallback provenance 저장 | snapshot·world·behavior payload 메타 |
| 10B.5 | 엔진 모듈의 직접 provider 호출 제거 | thought/action/policy/dialogue/group_deliberation → facade 경유 |

---

## 다음 스프린트 체크리스트

| 우선순위 | 작업 | 이유 |
|----------|------|------|
| 1 | LLM Facade 표준화 | 개발자가 실제로 쓰기 편한 입구를 먼저 고정 |
| 2 | 비용 제어 & 호출 스케줄링 | 장시간 로컬 시뮬레이션 안정성 확보 |
| 3 | Storage Layer 고도화 | Snapshot/Fork/Versioning 무결성 강화 |
| 4 | Nemotron Data Pack 운영 검증 | 실제 다국가 데이터 레이어 제품화 |
| 5 | 10k+ 성능 벤치 | 반복 실행·메모리·throughput 회귀까지 비교 가능한 하네스 확보 |

## Phase 10A (엔진/에이전트 데이터 플라이휠 기초)

> 현재 우선순위: 챗봇 UI·익명화보다 먼저 시스템 본질을 강화한다. 즉, 에이전트가 서로를 관찰하고, 그 관찰이 memory → Thought → Worldview로 이어지는 내부 플라이휠을 만든 뒤 사용자 상호작용을 얹는다.

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 10A.1 | 에이전트 간 근접 관찰 memory | `agent_interactions.py`, `social_observation` memory |
| 10A.2 | Thought 입력에 최근 memory 반영 | `thought.py` prompt에 recent memory 포함 |
| 10A.3 | role/persona 그룹 관측 API | `GET /worlds/{id}/agents/summary` |
| 10A.4 | 내부 플라이휠 테스트 | `test_agent_interactions.py`, `test_agents_api.py`, Phase 6 loop test |
| 10A.5 | memory 영속화 + restart 복원 | `serialization.py`, `persistence.py`, disk-backed `WorldStore` |
| 10A.6 | snapshot export/restore + fork | `GET /worlds/{id}/state`, `POST /worlds/{id}/restore` |
| 10A.7 | Thought/Worldview reflection 품질 강화 | `memory_reflection.py`, 장기 belief 요약 |
| 10A.8 | 다음 단계: persona-aware Genesis 강화 | persona 분포가 초기 위치·energy·role mix에 반영 |
| 10A.9 | 다음 단계: group-level stance summary | role group의 갈등·합의·리스크 요약 |

---

## Phase 10B (대화 엔진·사용자 데이터 플라이휠)

> 상세 결손은 `DEVELOPMENT_GAPS.md`를 우선 참조.

| 순서 | 작업 | 산출물 |
|------|------|--------|
| 10B.1 | ChatPanel UI | God View 내부 자연어 대화 인터페이스 |
| 10B.2 | 대화 API | `POST /worlds/{id}/chat`, t/role/persona context |
| 10B.3 | 사용자 입력 → memory/event 변환 | user utterance normalization, target scope, inject event |
| 10B.4 | Thought/Worldview 업데이트 트리거 | 대화 후 선택 집단의 중기/장기 벡터 갱신 |
| 10B.5 | 동의·익명화·보존 정책 | consent flags, PII redaction, provenance |
| 10B.6 | 멀티 에이전트 그룹 대화 | role group conversation, group stance summary |

---

*문서 버전: v0.5 — Phase 10A 엔진/에이전트 우선순위 반영*

---

## Phase 11 (현재 최우선) — 국가 단위 시뮬레이션 코어

> 이 단계가 흔들리면 End4D는 “그럴듯한 에이전트 앱”으로 밀리고, 목표인 국가 단위 장기 시뮬레이션 플랫폼이 되기 어렵다.

| 순서 | 작업 | 산출물 | 이유 |
|------|------|--------|------|
| 11.1 | **persona-aware Genesis 강화** | 국가별 persona 분포 기반 `t_max`, role mix, nutrient scale, zone seed, initial energy/z bias | 초기 세계가 실제 사회 구조를 반영해야 함 |
| 11.2 | **group-level belief state** | role/persona/zone group cohesion, tension, stance, drift | 국가 단위 분석은 개별 cell보다 집단 상태가 핵심 |
| 11.3 | **policy/event semantics 강화** | 정책 이벤트 타입 체계, 강도, 범위, 지속시간 | what-if가 장난감 이벤트가 아니라 정책 실험이 되게 함 |
| 11.4 | **prompt version + provider provenance 저장** | genesis/thought/worldview 결과에 LLM 메타 저장 | 장기 예측은 재현성과 감사 가능성이 필수 |
| 11.5 | **session → world → snapshot 비교 루프 완성** | 세션 단위 비교, 최근 world reopen, fork lineage | 장기 시나리오 실험 워크플로우의 핵심 |
| 11.6 | **long-horizon calibration hooks** | 시계열·정책·충격 입력용 calibration interface | 국가 단위 장기 예측으로 확장할 발판 |

---

## Phase 12 — 비교·리포트·전문가 워크플로우

| 순서 | 작업 | 산출물 | 이유 |
|------|------|--------|------|
| 12.1 | 세션별 world comparison 화면 | baseline vs branch 비교 | 전문가 사용성 핵심 |
| 12.2 | stance/cohesion diff report | before/after 변화 요약 | 정책·시장 비교 설명력 강화 |
| 12.3 | selection-driven God View | 좌-중-우 레이아웃, 선택 상세 패널, 타임라인 마커/북마크 | 전문가 탐색 워크플로우 기반 |
| 12.4 | snapshot lineage / fork graph | 복원·분기 이력 시각화 | 실험 추적성 |
| 12.5 | exportable report payload | JSON/PDF/slide용 결과 구조 | 기관 보고 워크플로우 대응 |

---

## Phase 13 — 데이터 레이어 운영화

| 순서 | 작업 | 산출물 | 이유 |
|------|------|--------|------|
| 13.1 | 국가별 dataset registry 정식화 | registry schema, version policy | 다국가 구조의 핵심 |
| 13.2 | entitlement / subscription 메타 | 사용 가능한 pack 판정 | 구독형 제품 기반 |
| 13.3 | data provenance UI/API | 출처, 라이선스, 갱신 이력 | 기관 신뢰 확보 |
| 13.4 | sector / policy pack 구조 | persona 외 시나리오 입력 팩 | 범용 플랫폼화 |

---

## Phase 14 — 네이티브 앱 / 기관 배포

| 순서 | 작업 | 산출물 | 이유 |
|------|------|--------|------|
| 14.1 | Tauri/Electron 셸 | 브라우저 대신 전용 앱 창 | 제품 완성도 |
| 14.2 | 기관용 로컬 배포 패키지 | 오프라인/폐쇄망 고려 | 실제 판매 가능성 |
| 14.3 | 운영자 권한/로그 | 실행 추적, 설정 감사 | 엔터프라이즈 요구 |

---

## 현재 6주 체크리스트

아래는 **지금 당장 개발 집중도를 유지하기 위한 단기 체크리스트**다.

- [ ] `persona-aware Genesis`가 occupation/region/age 분포를 role mix, zone seed, energy/z bias까지 실제 반영한다
- [ ] `group stance summary`가 role/persona/zone 기준으로 world/session 비교 가능한 구조로 저장된다
- [ ] policy/event injection이 강도·범위·지속시간을 가진다
- [ ] `session comparison` 화면에서 최소 2개 world를 나란히 볼 수 있다
- [ ] LLM 결과에 `provider / model / prompt_version / timestamp`가 남는다
- [ ] dataset source / license / version이 report payload까지 전달된다
- [ ] 브라우저 런처가 아닌 네이티브 셸 PoC 방향이 문서화된다

---

*문서 버전: v0.6 — 국가 단위 장기 시뮬레이션 플랫폼 목표 기준으로 재정렬*
