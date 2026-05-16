# End4D (Organic4D Engine)

> "시간이 흐르면서 스스로 번식하고 사상을 만드는 살아있는 디지털 생태계"

시간축을 가진 2D 사회장 위에서 스스로 진화하는 디지털 사회 시뮬레이션 엔진. 복잡계 이해·시나리오 탐색·의사결정 지원을 위한 시뮬레이션 런타임.

## Spatial Model

- 현재 제품 방향의 기본 공간 추상화는 `2D plane + social elevation(z) + time`이다.
- `z` 축은 full 3D mesh나 camera용 물리 높이가 아니라, 저비용 `heightmap / contour / scalar field` 의미의 **사회적 고도**다.
- `zone influence`와 함께 다음을 표현할 수 있다:
  - 구역별 정책 영향력
  - 구역 간 소통 마찰
  - 중심지/주변부 차등 효과
  - 지역 타깃 정책 주입
- 기본 엔진은 여전히 2D 중심으로 계산하고, `z`는 선택적 거리 가중과 분석/시각화 오버레이에만 약하게 반영한다.
- 현재 기본 `z_mode`는 `hybrid`이며, `wealth`, `influence`, `policy`, `memory`, `flat` 같은 모드를 엔진 파라미터로 바꿀 수 있다.

## 문서

| 문서 | 설명 |
|------|------|
| [CONCEPT.md](docs/CONCEPT.md) | 핵심 개념, 5대 규칙, 3계층 감정·생각 메커니즘 |
| [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | 기술 스택, 실행 방법 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 아키텍처 고려사항, 최적화 전략 |
| [ARCHITECTURE_CHECKLIST.md](docs/ARCHITECTURE_CHECKLIST.md) | 코드 작성 시 아키텍처 본질 체크리스트 |
| [DEVELOPMENT_GAPS.md](docs/DEVELOPMENT_GAPS.md) | 핵심 결손, 리스크, 다음 개발 우선순위 |
| [BACKEND_ENGINE_REFORM_TARGET.md](docs/BACKEND_ENGINE_REFORM_TARGET.md) | MiroFish식 실시간 체감을 흡수하기 위한 현재 백엔드 개편 목표 |
| [PRODUCT_STRATEGY.md](docs/PRODUCT_STRATEGY.md) | 로컬 실행 + 클라우드 데이터 + 다국가 제품 전략 |

## Docker (Phase 8)

- **개발**: 루트에서 `docker compose up --build` — API `http://localhost:8000`, God View `http://localhost:3000`.
- **프로덕션 이미지**: `docker compose -f docker-compose.prod.yml up --build`  
  프론트 빌드 시 `NEXT_PUBLIC_API_URL`을 브라우저에서 접근 가능한 API URL로 지정 (예: `http://localhost:8000`).

## Local App Launch

- **한 번에 실행**: 루트에서 `engine/backend/.venv/bin/python scripts/launch_local_end4d.py`
- **macOS 더블클릭 실행**: [End4D Launcher.app](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/End4D%20Launcher.app)
- **대체 더블클릭 실행**: [Launch_End4D.command](/Users/sejun/Desktop/Project_endpoint/vitaswarm4D/Launch_End4D.command)
- 런처는 백엔드와 프론트를 함께 띄우고, `http://127.0.0.1:3000`이 준비되면 브라우저 클라이언트를 자동으로 연다.
- Next.js 개발 서버의 초기 컴파일 동안에도 종료되지 않도록 프론트 readiness 판정을 포트 기준으로 처리한다.
- 프론트 실행 모드는 기본 `auto`이며, `.next` 빌드보다 소스 파일이 더 최신이면 자동으로 `dev`, 그렇지 않으면 `start`를 사용한다.
- 최신 UI 변경을 바로 확인하려면 `--frontend-mode dev`를 명시할 수 있다.
- 브라우저 자동 실행을 끄려면 `--no-browser` 옵션을 사용한다.
- macOS 앱 번들을 다시 만들려면 `python3 scripts/build_macos_launcher_app.py`
- 현재 로컬 런타임 상태와 설치된 데이터 팩은 `GET /runtime/local-status`에서 확인할 수 있다.

## Persona Dataset Seed

- 국가별 페르소나 데이터셋을 초기 에이전트 seed로 사용할 수 있다.
- 예: `ORGANIC4D_PERSONA_HF_DATASET_KR=nvidia/Nemotron-Personas-Korea`
- 로컬 샘플 파일도 가능: `ORGANIC4D_PERSONA_DATASET_DIR=/path/to/personas` 아래 `kr.jsonl`, `us.csv`, `jp.json` 등.
- 대용량 HF 데이터셋은 `engine/backend/scripts/sample_personas.py`로 작은 JSONL 샘플을 먼저 만들 수 있다.
- 생성된 world의 seed는 `GET /worlds/{world_id}/personas`에서 확인한다.
- world/snapshot/memory는 기본 `disk` backend로 JSON 영속화되며, `GET /worlds/{world_id}/state`, `POST /worlds/{world_id}/restore`로 what-if 복원/fork가 가능하다.
- 저장 파일은 `organic4d-file-envelope/v1` envelope와 SHA-256 digest를 포함해 스냅샷/포크 재현성에 필요한 무결성을 검증한다.
- 메모리는 레거시 문자열 외에 `short_memory`, `long_memory`, `behavior_log`로 구조화되며, Thought/Worldview는 전용 prompt engineering 모듈을 통해 이를 반영한다.
- 각 에이전트는 `(x, y, z, t)`를 유지하며, `z`는 `social elevation`으로 저장·복원된다.
- 에이전트 집단 상태는 `GET /worlds/{world_id}/agents/summary`, `GET /worlds/{world_id}/agents/stance-summary`에서 cohesion/tension/stance까지 확인할 수 있다.
- 로컬 실행 엔진은 설치된 데이터 팩 매니페스트를 읽을 수 있고, `GET /runtime/local-status`에서 현재 런타임 프로필과 로컬 pack 상태를 확인할 수 있다.
- 클라우드/사내 manifest는 `ORGANIC4D_DATA_PACK_REMOTE_MANIFEST_URL` 또는 `POST /runtime/data-packs/sync`로 로컬 cache manifest에 병합한다.
- CC BY 등 attribution이 필요한 데이터셋은 출처·라이선스를 표시해야 한다.

## LLM Runtime

- 기본적으로 안전한 `stub` 경로를 사용하며, 활성화 시 LLM은 `Genesis`, `Thought`, `Worldview`, `action planning`, `policy interpretation`, `agent dialogue`, `group deliberation`에 연결된다.
- 장시간 실행 제어: `ORGANIC4D_LLM_MAX_PROMPTS_PER_TASK`, `ORGANIC4D_LLM_AGENT_SAMPLE_SIZE`, `ORGANIC4D_DIALOGUE_INTERVAL`, `ORGANIC4D_GROUP_DELIBERATION_INTERVAL`, `ORGANIC4D_SNAPSHOT_INTERVAL`로 비용과 저장 주기를 조절한다.
- 로컬 LLM 예시: Ollama
  - `ORGANIC4D_LLM_CHAT_ENABLED=1`
  - `ORGANIC4D_LLM_PROVIDER=ollama`
  - `ORGANIC4D_LLM_MODEL=llama3.1`
  - 선택: `ORGANIC4D_LLM_BASE_URL=http://127.0.0.1:11434`
- 클라우드/호환 API 예시: OpenAI-compatible
  - `ORGANIC4D_LLM_CHAT_ENABLED=1`
  - `ORGANIC4D_LLM_PROVIDER=openai` 또는 `openai-compatible`
  - `ORGANIC4D_LLM_MODEL=gpt-4.1-mini`
  - `OPENAI_API_KEY=...` 또는 `ORGANIC4D_LLM_API_KEY=...`
  - 선택: `ORGANIC4D_LLM_BASE_URL=https://api.openai.com/v1`
- 현재 연결 상태는 `GET /runtime/local-status`의 `llm` 필드에서 확인할 수 있다.

## 라이선스

MIT License
