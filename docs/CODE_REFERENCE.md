# Organic4D — 파일별 코드 역할 (Code Reference)

> 각 파일이 담당하는 역할과 책임을 정리한 문서.
>
> **룰**: 새 파일 추가 시 이 문서에 반드시 해당 파일·역할을 추가한다. (`.cursor/rules/secondary/doc-sync.mdc`, `development-reference.mdc` 참조)

---

## 1. 백엔드 (engine/backend)

### 1.1 모델 (app/models/)

| 파일 | 역할 |
|------|------|
| **cell.py** | **세포(에이전트) 모델**. 4D 좌표 (x,y,z,t), 에너지, 유전자 벡터, 메모리, 3계층 벡터(emotion/thought/worldview) 정의. `position_4d()`, `position_3d()`, `copy()` 제공. |
| **world.py** | **세계·스냅샷 모델**. World(4D 세계), Snapshot(t 시점 스냅샷), NutrientEvent(영양분 주입 이벤트) 정의. World → Snapshot → Cell 계층 구조. |
| **__init__.py** | models 패키지 진입점. Cell, World, Snapshot, NutrientEvent export. |

### 1.2 코어 (app/core/)

| 파일 | 역할 |
|------|------|
| **coordinates.py** | **4D 좌표·거리 함수**. `distance_4d()` — (x,y,z)와 t에 가중치 적용한 거리 계산. `cosine_similarity()` — 융합 조건 등에 사용. |
| **rules.py** | **5대 규칙 로직**. `apply_growth`(영양분→에너지), `apply_division`(분열+변이), `apply_death`(사멸+영양분 분배), `apply_fusion`(거리+Thought 0.7+ 융합), `apply_mutation`(벡터 변이). Phase 1: LLM 없음. |
| **snapshot.py** | **스냅샷 저장소**. `SnapshotStore` — 메모리 내 t별 스냅샷 저장·조회. `save()`, `get()`, `get_nearest()`, `list_t()`. |
| **store.py** | **월드 저장소**. `WorldStore` — world_id → {World, SnapshotStore, status} 매핑. `create()`, `get()`, `get_world()`, `get_snapshot_store()`, `set_status()`. |
| **ws_manager.py** | **WebSocket 연결 관리**. `ConnectionManager` — world_id별 연결 등록·해제, `send_to_world()` 브로드캐스트. |
| **__init__.py** | core 패키지 진입점. coordinates, rules, snapshot export. |

### 1.3 그래프 (app/graph/)

| 파일 | 역할 |
|------|------|
| **time_flow.py** | **LangGraph 시간 흐름 그래프**. `create_time_flow_graph()` — init → step_loop 루프. `_init_node`(초기 세포 생성), `_should_continue`(t < t_max 분기). |
| **nodes.py** | **t 스텝 루프 노드**. `step_loop_node` — 한 t에서 성장→분열→사멸→융합→돌연변이 순차 적용, t 증가, 스냅샷 저장. |
| **__init__.py** | graph 패키지 진입점. `create_time_flow_graph` export. |

### 1.4 API (app/)

| 파일 | 역할 |
|------|------|
| **main.py** | **FastAPI 앱 뼈대**. `/health`, worlds/run/snapshots/ws 라우터. **CORS** (localhost:3000) — God View 브라우저 fetch. |
| **api/worlds.py** | **월드 REST API**. POST /worlds (생성), GET /worlds/{id} (메타정보 조회). |
| **api/run.py** | **시뮬 실행 API**. POST /worlds/{id}/run — 동기 실행, SnapshotStore에 저장. |
| **api/snapshots.py** | **스냅샷 조회 API**. GET /worlds/{id}/snapshots?t= — t 시점 스냅샷 또는 available_t 목록. |
| **api/ws.py** | **WebSocket 스트리밍**. GET /worlds/{id}/ws — 시뮬 실행 시 t, cell_count 스트리밍. |
| **__init__.py** | app 패키지 진입점. |

### 1.5 스크립트 (scripts/)

| 파일 | 역할 |
|------|------|
| **run_simulation.py** | **커맨드라인 시뮬레이션**. `--t-max`, `--cells`, `--world-id` 옵션. LangGraph invoke → t=0..t_max 실행, 스냅샷 저장, 결과 출력. |

### 1.6 테스트 (tests/)

| 파일 | 역할 |
|------|------|
| **test_rules.py** | **5대 규칙 단위 테스트**. 성장(에너지 증가), 분열(1→2, 변이), 사멸(제거+영양분 분배), 융합(거리+유사도), 돌연변이 검증. |
| **__init__.py** | tests 패키지 진입점. |

---

## 2. 프론트엔드 (engine/frontend)

### 2.1 앱 (app/)

| 파일 | 역할 |
|------|------|
| **page.tsx** | **메인 페이지**. `HomeWithCanvas` 마운트 (서버 컴포넌트). |
| **layout.tsx** | **루트 레이아웃**. html/body 래퍼. `globals.css` import. |
| **globals.css** | **전역 스타일**. Tailwind base/components/utilities. |

### 2.2 컴포넌트 (components/)

| 파일 | 역할 |
|------|------|
| **HomeWithCanvas.tsx** | **클라이언트 셸**. `next/dynamic`으로 `GodView` 로드 (`ssr: false`, WebGL). |
| **GodView.tsx** | **God View E2E (Phase 5)**. 세계 생성·실행(WS/동기)·`TimeSlider`→`getSnapshotAtT`→`cellsToInstanceBuffers`→3D. |
| **Scene3D/Scene3DCanvas.tsx** | **R3F Canvas**. 조명, `Grid`, `OrbitControls`, `CellInstances`. |
| **Scene3D/CellInstances.tsx** | **InstancedMesh 세포**. `setMatrixAt` + `useFrame`, Float32Array 위치, `setColorAt` (Emotion 대비). |
| **TimeSlider/TimeSlider.tsx** | **t 슬라이더**. range input, 스냅샷 t 탐색. |

### 2.3 훅 (hooks/)

| 파일 | 역할 |
|------|------|
| **useSimulation.ts** | **시뮬 + WebSocket (Phase 5.2)**. `runWithWebSocketStream`, `runSync`, `liveT` / `liveCellCount` 스트림 상태. |

### 2.4 라이브러리 (lib/)

| 파일 | 역할 |
|------|------|
| **api.ts** | **엔진 API 클라이언트**. REST + `getWorldWebSocketUrl`, `cellsToInstanceBuffers` (스냅샷→InstancedMesh 버퍼). `NEXT_PUBLIC_API_URL`. |

### 2.5 설정

| 파일 | 역할 |
|------|------|
| **package.json** | **의존성 정의**. Next.js, React, Three.js, R3F, drei, Zustand, TanStack Query, Tailwind, Recharts 등. |
| **tsconfig.json** | **TypeScript 설정**. paths `@/*`, Next.js 플러그인. |
| **next.config.ts** | **Next.js 설정**. Phase 0 기본값. |
| **tailwind.config.ts** | **Tailwind 설정**. content 경로, theme 확장. |
| **postcss.config.mjs** | **PostCSS 설정**. tailwindcss, autoprefixer. |

---

## 3. 루트 설정

| 파일 | 역할 |
|------|------|
| **docker-compose.yml** | **컨테이너 오케스트레이션**. backend, frontend 서비스. Phase 0 초안. |
| **engine/backend/Dockerfile** | **백엔드 이미지**. Python 3.11, requirements 설치, uvicorn 실행. |
| **engine/frontend/Dockerfile** | **프론트 이미지**. Node 20, npm install, dev 서버. |
| **engine/backend/requirements.txt** | **Python 의존성**. FastAPI, uvicorn, LangGraph, pydantic, numpy, sentence-transformers, pytest. |
| **.gitignore** | **Git 제외 목록**. .venv, node_modules, .next, .env 등. |

---

## 4. 의존성 흐름 (참조 관계)

```
run_simulation.py → time_flow.py → nodes.py → rules.py, snapshot.py
                                    ↓
                              coordinates.py, cell.py
                                    ↓
                              world.py

api/worlds.py, api/run.py, api/snapshots.py, api/ws.py → core/store.py
api/run.py → graph/time_flow.py, core/ws_manager.py
api/snapshots.py → core/snapshot.py (store 경유)
api/ws.py → core/ws_manager.py

GodView → useSimulation → lib/api.ts (REST + WS)
GodView → Scene3DCanvas → CellInstances (Three.js)
GodView → lib/api.ts (getSnapshotAtT, cellsToInstanceBuffers)
```

---

*문서 버전: v0.5 — Phase 0~5 기준*
