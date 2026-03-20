# Organic4D — 실행 방법 & 기술 스택

> 구현 기반, 실행 흐름, 기술 선택을 정리한 문서

---

## 0. 핵심 = 엔진, 제품으로도 사용 가능

**핵심 코어는 엔진.** 4D 시뮬레이션 런타임이 중심이다.  
엔진 + God View를 합치면 **제품 그 자체로 바로 쓸 수 있다** (바로 사용·배포 가능).  
필요하면 엔진 API만 따로 다른 제품에 임베드할 수도 있다.

```
┌─────────────────────────────────────────────────────────────────┐
│  [제품으로 사용]  엔진 + God View = 바로 쓸 수 있는 시나리오 탐색 도구   │
├─────────────────────────────────────────────────────────────────┤
│  [Organic4D 엔진 — 핵심 코어]                                    │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ 4D 좌표     │  │ 5대 규칙    │  │ 시간 흐름 + 3계층 감정·생각   │  │
│  │ 시각화 API  │  │ God View API│  │ 스냅샷·이벤트 API        │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│  [인프라] Storage · Memory · LLM · Docker                        │
└─────────────────────────────────────────────────────────────────┘
```

**엔진이 제공하는 것 (예시)**
- `POST /worlds` — **프롬프트 기반 세계 생성** (`{ "prompt": "..." }` → AI/스텁이 `t_max`·초기 개체 수·역할 카탈로그 제안)
- `POST /worlds/{id}/run` — 시뮬레이션 실행 (WebSocket 스트리밍)
- `POST /worlds/{id}/inject` — t 시점에 이벤트·영양분 주입 (God View)
- `GET /worlds/{id}/snapshots?t=` — t 시점 스냅샷 조회
- 시각화용 (x,y,z, energy, emotion_vec, thought_vec, worldview_vec) 등 프리미티브

---

## 1. 전체 아키텍처 개요

```
┌─────────────────────────────────────────────────────────────────┐
│                  Organic4D Engine (런타임)                        │
├─────────────────────────────────────────────────────────────────┤
│  [엔진 API / Dev UI]    [Core Engine]                            │
│  FastAPI + God View  ←→  Python + LangGraph                      │
│  + Three.js              4D 엔진 + 시간 루프 + 5대 규칙         │
├─────────────────────────────────────────────────────────────────┤
│  [Storage]           [Memory]         [LLM]                      │
│  PostgreSQL/         Zep / Redis       Ollama / OpenAI 등         │
│  SQLite          (장기 메모리)                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. 기술 스택 (Tech Stack)

### 2.1 백엔드

| 영역 | 기술 | 용도 |
|------|------|------|
| **언어** | Python 3.11+ | 메인 로직, LangGraph, 수치 연산 |
| **오케스트레이션** | LangGraph | 시간 흐름 엔진, 4D 세계 상태 머신 |
| **API** | FastAPI | REST + WebSocket (실시간 시뮬레이션 스트리밍) |
| **비동기** | asyncio | LLM 호출·메모리 I/O 병렬 처리 |

**선택 근거**
- LangGraph: 상태 기반 워크플로우·분기·루프에 적합, t 스텝별 노드 구성 용이
- FastAPI: 비동기, WebSocket, OpenAPI 문서 자동 생성

### 2.2 프론트엔드

| 영역 | 기술 | 용도 |
|------|------|------|
| **프레임워크** | Next.js 16+ (App Router, Turbopack·React 19 안정화) | SSR, API Routes, Turbopack, 라우팅 |
| **3D 시각화** | Three.js + React Three Fiber | 4D → 3D 프로젝션 + 시간 슬라이더 |
| **상태 관리** | Zustand + TanStack Query (React Query) 병행 | 시뮬레이션 상태, t 값, God View 주입 (t 슬라이더 복잡 상태는 TanStack Query로) |
| **스타일** | Tailwind CSS | 빠른 UI 개발 |
| **차트/인사이트** | Recharts 또는 Visx | 시나리오 리포트용 시각화 |

**선택 근거**
- Next.js 16+: 2025년 말 정식 출시. Turbopack·React 19 안정화.
- Zustand + TanStack Query 병행: 실무 표준. Zustand만으로는 t 슬라이더·스냅샷 캐시 등 복잡 상태 관리에 한계 → TanStack Query로 서버 상태·캐싱.
- React Three Fiber: React 컴포넌트 방식으로 Three.js 사용, 수천 세포 렌더링 최적화 가능
- 시간 슬라이더: t를 드래그하면 해당 시점의 (x,y,z) 스냅샷을 3D로 표시

**엔진 레포 실제 버전 (God View)**: Next.js 15.x, **React 19**, `@react-three/fiber` v9, `@react-three/drei` v10 — R3F v8·drei v9 + React 18 조합은 `ReactCurrentOwner` 류 오류가 날 수 있어 상향 정렬함.

### 2.3 메모리 & 스토리지

| 영역 | 기술 | 용도 |
|------|------|------|
| **세포 상태·월드** | PostgreSQL 또는 SQLite | 에이전트 풀, 4D 세계 스냅샷 (t별) |
| **장기 메모리** | Zep 또는 Redis | 세포별 메모리 (이벤트 히스토리) |
| **벡터 DB** | **pgvector 우선**, Qdrant 옵션 | 유전자·Thought·Worldview 벡터, 유사도 검색 (융합 조건) |

**선택 근거**
- Zep: 에이전트 메모리, 요약, 검색에 특화 (LangChain 생태계)
- Redis: 단순 키-값 + TTL로 경량 장기 메모리 대체 가능
- **pgvector 우선**: 초기 프로젝트에서 비용·운영 난이도 면에서 우위. PostgreSQL 확장으로 별도 벡터 DB 불필요. Qdrant는 규모 확장 시 옵션.

### 2.4 LLM & 임베딩

> **원칙**: Thought(10~50t)·Worldview(200t+)만 LLM. **Emotion은 규칙 기반(LLM 0)**. 작은 모델로 충분.

| 영역 | 저렴·무료 옵션 | 용도 |
|------|----------------|------|
| **LLM** | **Ollama** (로컬, 무료) — Llama 3.2 3B, Mistral 7B, Qwen2.5 | Thought(전략)·Worldview(신념) 생성 |
| | Groq (무료 티어, 초고속) | API 필요 시 |
| | Together AI, Fireworks (오픈소스 호스팅, 저렴) | 클라우드 필요 시 |
| **임베딩** | **sentence-transformers** (로컬, 무료) — all-MiniLM, multilingual-e5, BGE | Thought·Worldview 벡터, 유전자 벡터 |
| | Nomic Embed, GTE (로컬) | 대안 |
| | Llama.cpp (`/v1/embeddings`) | 임베딩 전용 엔드포인트 |

**이유 없음**: 위 옵션 사용해도 됨. 품질·속도는 POC에서 검증 후 필요 시 상향.

**추천 조합 (비용 최소)**
- 로컬 개발·POC: **Ollama + sentence-transformers** → API 비용 0
- 프로덕션: 트래픽·품질에 따라 Groq / Together / OpenAI 등 선택

**엔진 구현 상태 (Phase 6 POC)**  
- **Emotion**: `engine/backend/app/core/emotion.py` — 8차원 규칙 기반, 매 t, LLM 0.  
- **Thought / Worldview**: `llm/thought.py`, `llm/worldview.py` — 세포 상태·메모리에서 만든 짧은 텍스트를 `llm/embeddings.py`로 벡터화 (기본 모델 `all-MiniLM-L6-v2`, 차원 절단). **Ollama 문장 생성**은 아직 미연동; 테스트·CI는 `ORGANIC4D_EMBED_BACKEND=stub`으로 결정적 스텁.  
- **메모리 POC**: `core/memory_step.py` — 세포 `memory` 리스트에 주기적 문자열 추가 (Redis/Zep은 후속).
- **역할·Genesis**: 세포 `role_key`/`role_label`, `world_genesis.propose_world_from_prompt` 스텁(키워드·길이 휴리스틱). `POST /worlds`는 `{ "prompt" }`만 받음. Genesis가 **`t` 스텝의 시간 의미**(`t_step_semantic`/`t_step_unit`)와 **`nutrient_per_step`**(성장·에너지 유입)을 함께 제안·저장, `run`/`inject` 시 그래프에 전달. **실 LLM Genesis**는 Phase 9.

### 2.5 인프라 & 배포

| 영역 | 기술 | 용도 |
|------|------|------|
| **컨테이너** | Docker + Docker Compose | 로컬·스테이징 환경 |
| **클라우드** | AWS / GCP / Vercel | 프로덕션 SaaS |
| **큐/워커** | Celery + Redis 또는 RQ | 장기 시뮬레이션 백그라운드 처리 |
| **실시간** | WebSocket (FastAPI) | God View 실시간 스트리밍 |

---

## 3. 실행 방법 (How to Run)

### 3.1 로컬 개발 환경

```
# 1. 저장소 클론 후
cd vitaswarm4D

# 2. 백엔드
cd engine/backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 3. 프론트엔드 (별도 터미널)
cd engine/frontend
npm install
npm run dev
# (선택) API URL — 기본 http://localhost:8000
# NEXT_PUBLIC_API_URL=http://localhost:8000

# 4. (선택) Redis, PostgreSQL — Docker로 실행
docker compose up -d redis postgres
```

**개발 시 실행 순서**
1. Redis, PostgreSQL 기동 (또는 SQLite만 사용)
2. 백엔드 `uvicorn` 기동
3. 프론트엔드 `npm run dev` 기동
4. `http://localhost:3000` 접속 → God View

**God View 수동 E2E (Phase 5)**  
1. 백엔드·프론트 모두 기동. 2. 「세계 생성」. 3. 「실행 (WebSocket 스트림)」 또는 「실행 (동기)」. 4. 슬라이더로 t 이동 → 3D 세포 위치 갱신.

**Playwright (Phase 5.4)** — `engine/frontend` 기준:

```
cd engine/frontend
npx playwright install chromium   # 최초 1회 (브라우저 바이너리)
npm run test:e2e                  # 기본 포트 3333에서 dev 자동 기동
# 이미 npm run dev(3000) 중이면: PW_PORT=3000 npm run test:e2e
# CI: npm run test:e2e:ci  → build 후 next start (시간 소요)
```

### 3.2 Docker One-Shot 실행

```
# 전체 스택 한 번에 실행
docker compose up -d

# 구성: backend, frontend, redis, postgres (또는 sqlite)
# 접속: http://localhost:3000
```

### 3.3 시뮬레이션 실행 흐름

```
1. 사용자가 God View에서 "새 세계 생성" 또는 "시나리오 로드"
2. API: POST /worlds { initial_cells, nutrients, t_max }
3. 백엔드: LangGraph로 시간 루프 시작
   - 매 t: 성장/분열/사멸/융합/돌연변이 + Emotion. 10~50t: Thought. 200t+: Worldview
   - WebSocket으로 t, 세포 수, 주요 이벤트 스트리밍
4. 프론트: t 슬라이더 움직임 → 해당 t의 (x,y,z) 스냅샷 요청 → 3D 렌더
5. 사용자가 t=500에 정책 주입 → 백엔드에서 해당 t에 영양분/이벤트 삽입 → 시뮬레이션 반영
```

### 3.4 프로덕션 (SaaS) 배포

| 컴포넌트 | 배포 옵션 |
|----------|-----------|
| Frontend | Vercel, Netlify, S3+CloudFront |
| Backend API | AWS ECS, GCP Cloud Run, Railway |
| Worker (장기 시뮬레이션) | Celery worker on ECS/EC2, Cloud Run Jobs |
| Redis | ElastiCache, Redis Cloud |
| PostgreSQL | RDS, Supabase, Neon |
| Docker | ECR → ECS, GCR → Cloud Run |

### 3.5 환경 변수 (기능 분기 — LLM·DB 후속)

| 변수 | 기본 | 설명 |
|------|------|------|
| `ORGANIC4D_LLM_CHAT_ENABLED` | (끔) | `1`/`true` 시 (후속) Ollama 등 대화형 LLM으로 Thought/Worldview 문장 생성. |
| `ORGANIC4D_PERSISTENCE_BACKEND` | `memory` | `postgres` / `redis` 선택 시 영속 어댑터 연동 예정 (`app/core/settings.py`). |
| `ORGANIC4D_DATABASE_URL` | — | PostgreSQL 등 연결 문자열 (미설정 시 인메모리 월드만). |
| `ORGANIC4D_EMBED_BACKEND` | (자동) | `stub`이면 결정적 임베딩(테스트·CI). |
| `ORGANIC4D_CORS_ORIGINS` | — | 쉼표로 구분한 추가 출처(기본 localhost:3000 유지). |
| `NEXT_PUBLIC_MAX_VISUAL_CELLS` | `8192` | God View InstancedMesh 상한; 초과 시 균등 샘플링(Phase 8). |

### 3.6a 프론트 404 (God View가 안 열릴 때)

- 증상: 브라우저에서 Next 기본 **「404 This page could not be found」**, 특히 `.next`가 깨졌거나 **EMFILE (too many open files)** 로 감시가 실패한 뒤.
- 조치: `cd engine/frontend` 후 **`npm run clean`** (또는 `rm -rf .next`) → **`npm run dev`** 다시 실행.
- EMFILE이 자주 나오면 터미널에서 `ulimit -n 10240` 후 재시도하거나, `WATCHPACK_POLLING=true npm run dev` 로 폴링 모드(느리지만 안정적)를 쓸 수 있음.

### 3.6 Docker (Phase 8)

| 파일 | 용도 |
|------|------|
| `docker-compose.yml` | 로컬 개발: 백엔드 `--reload`, 프론트 `Dockerfile.dev` + 볼륨. |
| `docker-compose.prod.yml` | 프로덕션 빌드: 백엔드 non-root + HEALTHCHECK, 프론트 Next **standalone** + `node server.js`. |

```bash
# 개발
docker compose up --build

# 프로덕션 (브라우저→API는 호스트 포트 기준 URL로 빌드)
NEXT_PUBLIC_API_URL=http://localhost:8000 docker compose -f docker-compose.prod.yml up --build
```

---

## 4. 프로젝트 구조 (예상)

```
vitaswarm4D/                  # Organic4D 엔진 레포
├── engine/                   # 엔진 코어 (제품과 분리 가능)
│   ├── backend/              # Python 엔진
│   │   ├── app/
│   │   │   ├── api/           # 엔진 API (worlds, cells, run, inject...)
│   │   │   ├── core/          # 4D 좌표, 시간 흐름, 5대 규칙
│   │   │   ├── graph/         # LangGraph 노드·엣지
│   │   │   ├── memory/
│   │   │   ├── llm/
│   │   │   └── models/
│   │   └── ...
│   └── frontend/             # God View (엔진 개발·데모용 UI)
│       ├── components/
│       │   ├── Scene3D/
│       │   ├── TimeSlider/
│       │   └── GodView/
│       └── ...
├── products/                 # (선택) 엔진 위에 구축하는 제품들
│   └── policy-explorer/      # 예: 정책 시나리오 탐색 제품
├── docs/
├── docker-compose.yml
└── README.md
```

→ `engine/`이 핵심. `products/`는 별도 레포로 분리해도 됨.

---

## 5. 기술 선택 체크리스트

### 5.1 확정·우선 검토

- [x] Python + LangGraph (백엔드 오케스트레이션)
- [x] FastAPI (REST + WebSocket)
- [x] Next.js + Three.js (프론트·3D)
- [x] Docker (로컬·배포)
- [ ] Zep vs Redis (장기 메모리 — POC 후 결정)
- [ ] PostgreSQL vs SQLite (초기에는 SQLite로 빠르게 검증 가능)

### 5.2 검토 필요

| 항목 | 옵션 | 고려 사항 |
|------|------|-----------|
| LLM | **Ollama(무료)** / Groq / Together / OpenAI | 비용 최소화 시 Ollama + sentence-transformers 우선 |
| 벡터 DB | **pgvector 우선**, Qdrant 옵션 | 비용·운영 난이도에서 pgvector 우위 |
| 시뮬레이션 큐 | Celery / RQ / in-process | 세포 수·t 범위에 따라 결정 |
| 호스팅 | Vercel / AWS / GCP | 팀 역량·비용 |

---

## 6. 단계별 구현 로드맵 (참고)

| 단계 | 내용 | 산출물 |
|------|------|--------|
| 1 | 4D 좌표·거리 함수, 세포 스키마 | `engine/coordinates.py`, `models/cell.py` |
| 2 | 5대 규칙 로직 (LLM 제외) | `engine/rules.py` |
| 3 | LangGraph 시간 루프 | `graph/time_flow.py` |
| 4 | FastAPI + WebSocket | `api/` |
| 5 | Three.js 3D + t 슬라이더 | `Scene3D`, `TimeSlider` |
| 6 | 3계층 감정·생각 (Emotion, Thought, Worldview) | `core/emotion.py`, `llm/thought.py`, `llm/worldview.py` |
| 7 | God View 주입, 타임라인 | `api/inject.py`, `api/timeline.py`, `InjectPanel`, `ScenarioTimeline` |
| 8 | Docker·시각화 상한 | `docker-compose.prod.yml`, standalone Dockerfile, 샘플링·CORS |

---

*문서 버전: v0.1 — 초안*
