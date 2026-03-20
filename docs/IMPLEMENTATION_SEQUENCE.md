# Organic4D — 구현 시퀀스

> 단계별 구현 순서. 의존성 고려.

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
Phase 4: 프론트 기초 (3D + t 슬라이더)
    ↓
Phase 5: E2E 연결 (시뮬 실행 → 시각화)
    ↓
Phase 6: 3계층 감정·생각 생성 (Emotion, Thought, Worldview)
    ↓
Phase 7: God View 주입 + 시나리오 리포트
    ↓
Phase 8: 최적화·배포
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
| | `(x,y,z,t)`, `energy`, `gene_vec`, `memory`, `emotion_vec`, `thought_vec`, `worldview_vec` | Pydantic/dataclass | |
| 1.2 | **4D 좌표·거리 함수** | `core/coordinates.py` | 1.1 |
| | 거리 함수 `d(p1, p2)`, 가중치 (x,y,z vs t) | | |
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
| 4.2 | **Scene3D 컴포넌트** | `components/Scene3D/` | 4.1 |
| | 빈 3D 씬, 카메라, 조명 | | |
| 4.3 | **InstancedMesh + setMatrixAt 패턴** | `Scene3D/CellInstances.tsx` | 4.2 |
| | `(x,y,z)` 배열 → Sphere InstancedMesh, **반드시** 아래 패턴 적용 (세포 1K 넘으면 미적용 시 병목) | | |
| 4.3a | **코드 패턴: setMatrixAt** | `setMatrixAt(i, matrix)` | 4.3 |
| | `tempObject.position.set(x,y,z)` → `tempObject.updateMatrix()` → `instancedMesh.setMatrixAt(i, tempObject.matrix)` | | |
| 4.3b | **코드 패턴: useFrame + Float32Array** | `useFrame` 내부 | 4.3 |
| | 스냅샷 `(x,y,z)[]` → Float32Array로 변환 → `setMatrixAt` 루프 → `instanceMatrix.needsUpdate = true` | | |
| 4.3c | **인스턴스 수 동적 조정** | `instancedMesh.count` | 4.3 |
| | 세포 수 변경 시 count 재할당 또는 새 InstancedMesh 생성 | | |
| 4.3d | **setColorAt (Emotion 미리 준비)** | 인스턴스별 색상 attribute | 4.3 |
| | Phase 6 Emotion 시각화 대비, 색상 슬롯 확보 | | |
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
| | t 변경 시 GET /snapshots?t= → 3D 업데이트 | | |
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

| 순서 | 작업 | 산출물 | 의존 |
|------|------|--------|------|
| 8.1 | **Docker 이미지** | backend, frontend Dockerfile | Phase 0 |
| 8.2 | **SQLite → PostgreSQL (선택)** | 마이그레이션 | Phase 1 |
| 8.3 | **InstancedMesh 추가 최적화** | 세포 10K+ | 4.3 |
| | LOD, 시각화 샘플링, setColorAt(에너지 색상) — 4.3 패턴은 Phase 4에서 이미 적용 | | |
| 8.4 | **델타 저장 (선택)** | ARCHITECTURE 1.2 | 2.3 |
| 8.5 | **Celery 워커 (선택)** | 장기 시뮬 | 3.3 |

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

*문서 버전: v0.1*
