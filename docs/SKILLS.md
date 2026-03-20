# Organic4D — 필요한 스킬 (Skills)

> 지금까지 토론한 CONCEPT, IMPLEMENTATION, ARCHITECTURE를 바탕으로 필요한 역량 정리

---

## 1. 백엔드 & 엔진 코어

### 1.1 Python

| 스킬 | 수준 | 용도 |
|------|------|------|
| Python 3.11+ 문법·타입 힌트 | 필수 | 전반 |
| OOP (클래스, 메서드, 상속) | 필수 | 세포·세계 모델 |
| `asyncio` / `async`·`await` | 필수 | LLM 호출, I/O 병렬 처리 |
| `TypedDict`, Pydantic, dataclass | 권장 | 상태 스키마, API 요청/응답 |
| `multiprocessing` (선택) | 권장 | 규모 확장 시 병렬화 |

### 1.2 LangGraph & 상태 머신

| 스킬 | 수준 | 용도 |
|------|------|------|
| 상태 그래프 (State Graph) 개념 | 필수 | 시간 흐름 엔진 |
| 노드 (Node): 상태 읽기 → 연산 → 업데이트 반환 | 필수 | t 스텝별 규칙 적용 |
| 엣지 (Edge): 조건부 분기·루프 | 필수 | 성장→분열→사멸 등 순서 |
| Reducer (상태 병합) | 권장 | 다중 세포 상태 집계 |
| LangChain 기초 (선택) | 선택 | LLM 체인·툴 연동 |

### 1.3 FastAPI & 실시간

| 스킬 | 수준 | 용도 |
|------|------|------|
| REST API 설계 (GET, POST, PUT, DELETE) | 필수 | worlds, cells, run, inject |
| WebSocket (연결, 메시지 송수신) | 필수 | 시뮬레이션 스트리밍 |
| Pydantic 모델 (요청/응답 검증) | 필수 | API 스키마 |
| OpenAPI/Swagger | 권장 | 문서·클라이언트 생성 |
| 백그라운드 태스크 (`BackgroundTasks`) | 권장 | 장기 시뮬 비동기 실행 |

### 1.4 4D 수학 & 공간

| 스킬 | 수준 | 용도 |
|------|------|------|
| 3D/4D 좌표계 (x, y, z, t) | 필수 | 세포 위치, 거리 |
| 거리 함수 (유클리드, 가중치) | 필수 | 융합·영양분 흡수 조건 |
| 벡터 연산 (numpy) | 필수 | 유전자·Emotion·Thought·Worldview 벡터 |
| 공간 분할: Octree, Grid, KD-Tree | 권장 | 인접 검색 O(N²)→O(N log N) |
| cosine similarity, 임베딩 유사도 | 필수 | 융합 호환성 (Thought 70%), Worldview |

---

## 2. 프론트엔드 & 3D 시각화

### 2.1 React & Next.js

| 스킬 | 수준 | 용도 |
|------|------|------|
| React (hooks, 상태, 컴포넌트) | 필수 | 전반 |
| Next.js 16+ (App Router, Turbopack·React 19) | 필수 | 라우팅, API Routes |
| TypeScript | 필수 | 타입 안전성 |
| Zustand + TanStack Query 병행 | 필수 | 시뮬 상태, t 값 (t 슬라이더 복잡 상태는 TanStack Query로) |
| Tailwind CSS | 권장 | 스타일링 |

### 2.2 Three.js & WebGL

| 스킬 | 수준 | 용도 |
|------|------|------|
| Three.js 기초 (Scene, Camera, Mesh) | 필수 | 3D 렌더링 |
| React Three Fiber | 필수 | React 컴포넌트 방식 Three.js |
| **InstancedMesh** (동일 메시 다수 렌더) | 필수 | 수천 세포 효율적 렌더링 |
| `setMatrixAt`, `setColorAt`, `needsUpdate` | 필수 | 인스턴스별 위치·색상 |
| Frustum Culling, LOD | 권장 | 최적화 |
| 4D → 3D 프로젝션 (t 슬라이더) | 필수 | 시간 축 시각화 |

### 2.3 실시간 UI & God View

| 스킬 | 수준 | 용도 |
|------|------|------|
| WebSocket 클라이언트 (브라우저) | 필수 | 시뮬 스트리밍 수신 |
| 시간 슬라이더 (range input, 드래그) | 필수 | t 값 선택 |
| 디바운스·쓰로틀 | 권장 | 슬라이더 드래그 시 API 호출 절감 |
| Recharts, Visx 등 차트 | 권장 | 시나리오 리포트, 집계 시각화 |

---

## 3. 3계층 감정·생각 & LLM

### 3.0 Emotion (규칙 기반, LLM 0)

| 스킬 | 수준 | 용도 |
|------|------|------|
| 8차원 감정 벡터 (joy, anger, fear, calm 등) | 필수 | 매 t 업데이트, God View 주입 즉시 반응 |
| 에너지·이벤트 → 감정 매핑 규칙 | 필수 | Emotion 시각화 (색상·크기) |

### 3.1 Thought·Worldview (로컬 LLM)

| 스킬 | 수준 | 용도 |
|------|------|------|
| Ollama 설치·실행·API 호출 | 필수 | Thought(전략)·Worldview(신념) 생성 |
| REST API 또는 Python SDK | 필수 | 백엔드에서 LLM 호출 |
| 프롬프트 설계 (메모리 → 전략/신념 추출) | 필수 | Thought·Worldview 품질 |
| 작은 모델 선택 (3B, 7B) | 권장 | 비용·지연 최소화 |

### 3.2 임베딩 (sentence-transformers, Thought 256d·Worldview 384d)

| 스킬 | 수준 | 용도 |
|------|------|------|
| sentence-transformers 설치·사용 | 필수 | 텍스트 → 벡터 |
| 모델 선택 (all-MiniLM, BGE, multilingual-e5) | 권장 | 언어·품질 트레이드오프 |
| 벡터 유사도 (cosine) | 필수 | 융합 호환성 |
| 배치 임베딩 | 권장 | 여러 텍스트 한 번에 처리 |

### 3.3 최적화

| 스킬 | 수준 | 용도 |
|------|------|------|
| 조건부 LLM 호출 (메모리 변경 임계치) | 권장 | 호출 수 감소 |
| 캐싱 (동일 입력 → 기존 출력 재사용) | 권장 | 중복 제거 |

---

## 4. 데이터 & 스토리지

### 4.1 관계형 DB

| 스킬 | 수준 | 용도 |
|------|------|------|
| SQL (SELECT, INSERT, UPDATE, JOIN) | 필수 | 세포·스냅샷·월드 |
| PostgreSQL 또는 SQLite | 필수 | POC는 SQLite |
| 마이그레이션 (Alembic 등) | 권장 | 스키마 버전 관리 |
| `t` 인덱스, 시계열 쿼리 | 권장 | t별 스냅샷 조회 |

### 4.2 벡터 DB

| 스킬 | 수준 | 용도 |
|------|------|------|
| pgvector (PostgreSQL 확장) | 필수(우선) | 유전자·Thought·Worldview 벡터, 유사도 검색 |
| Qdrant | 선택 | 규모 확장 시 옵션 |
| 벡터 인덱스 (IVF, HNSW) | 선택 | 10K+ 벡터 시 |

### 4.3 메모리 & 캐시

| 스킬 | 수준 | 용도 |
|------|------|------|
| Redis (키-값, TTL) | 권장 | 장기 메모리, 세션 |
| Zep (에이전트 메모리) | 선택 | LangChain 생태계 |
| in-memory dict + 직렬화 | 권장 | POC 경량화 |

---

## 5. 인프라 & 배포

### 5.1 Docker

| 스킬 | 수준 | 용도 |
|------|------|------|
| Dockerfile 작성 | 필수 | backend, frontend 이미지 |
| Docker Compose (다중 서비스) | 필수 | 로컬·스테이징 환경 |
| 볼륨, 네트워크 | 권장 | 데이터 영속성 |

### 5.2 백그라운드 작업 (선택)

| 스킬 | 수준 | 용도 |
|------|------|------|
| Celery + Redis | 권장 | 장기 시뮬 워커 |
| 또는 RQ, in-process 스레드 | 권장 | 경량 대안 |

### 5.3 프로덕션 (선택)

| 스킬 | 수준 | 용도 |
|------|------|------|
| Vercel, AWS, GCP 배포 | 권장 | SaaS 전환 시 |
| 로드밸런서, 스케일링 | 선택 | 트래픽 증가 시 |

---

## 6. 도메인 & 개념

### 6.1 복잡계 & 에이전트

| 스킬 | 수준 | 용도 |
|------|------|------|
| 에이전트 기반 모델 (ABM) 개념 | 권장 | 설계 직관 |
| Emergent 현상 이해 | 권장 | 목표·검증 |
| 복잡계 (정책·금융·기후·사회) | 선택 | 도메인 제품 확장 시 |

### 6.2 시뮬레이션 설계

| 스킬 | 수준 | 용도 |
|------|------|------|
| 이산 시뮬레이션 (t 스텝) | 필수 | 시간 흐름 엔진 |
| 초기 조건·파라미터 튜닝 | 권장 | emergent 탐색 |
| What-if 시나리오 설계 | 권장 | God View 주입 |

---

## 7. 최적화 (규모 확장 시)

| 스킬 | 수준 | 용도 |
|------|------|------|
| GPU Instancing (InstancedMesh) | 필수 | 세포 1K+ 렌더링 |
| 공간 분할 (Octree, Grid) | 권장 | 세포 2K+ 인접 검색 |
| 델타 저장 (변경분만) | 권장 | t 500+ 스토리지 |
| LLM 배치·조건부 호출 | 권장 | 비용·지연 절감 |
| LOD, 시각화 샘플링 | 선택 | 세포 10K+ |
| 멀티프로세싱 | 선택 | 세포 50K+ |

---

## 8. 우선순위 요약

### POC 단계 (필수)

- Python, LangGraph, FastAPI, WebSocket
- Next.js, React Three Fiber, InstancedMesh
- Ollama, sentence-transformers
- SQLite, Docker

### 1차 확장 (권장)

- 공간 분할, t 델타, GPU Instancing
- Redis, pgvector
- 프롬프트·3계층(Emotion/Thought/Worldview) 생성 품질

### 2차 확장 (선택)

- Celery/RQ, 멀티테넌시
- TimescaleDB, 분산 워커
- LOD, 벡터 압축

---

*문서 버전: v0.1 — 토론 내용 기반*
