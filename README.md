# End4D (Organic4D Engine)

> "시간이 흐르면서 스스로 번식하고 사상을 만드는 살아있는 디지털 생태계"

4차원 시공간에서 스스로 진화하는 디지털 생명체 생태계 엔진. 복잡계 이해·시나리오 탐색·의사결정 지원을 위한 시뮬레이션 런타임.

## 문서

| 문서 | 설명 |
|------|------|
| [CONCEPT.md](docs/CONCEPT.md) | 핵심 개념, 5대 규칙, 3계층 감정·생각 메커니즘 |
| [IMPLEMENTATION.md](docs/IMPLEMENTATION.md) | 기술 스택, 실행 방법 |
| [IMPLEMENTATION_SEQUENCE.md](docs/IMPLEMENTATION_SEQUENCE.md) | Phase 0~8 구현 시퀀스 |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | 아키텍처 고려사항, 최적화 전략 |
| [ARCHITECTURE_CHECKLIST.md](docs/ARCHITECTURE_CHECKLIST.md) | 코드 작성 시 아키텍처 본질 체크리스트 |
| [DEVELOPMENT_GAPS.md](docs/DEVELOPMENT_GAPS.md) | 핵심 결손, 리스크, 다음 개발 우선순위 |
| [CODE_REFERENCE.md](docs/CODE_REFERENCE.md) | 파일별 코드 역할 설명 |
| [SKILLS.md](docs/SKILLS.md) | 개발에 필요한 스킬 목록 |

## Docker (Phase 8)

- **개발**: 루트에서 `docker compose up --build` — API `http://localhost:8000`, God View `http://localhost:3000`.
- **프로덕션 이미지**: `docker compose -f docker-compose.prod.yml up --build`  
  프론트 빌드 시 `NEXT_PUBLIC_API_URL`을 브라우저에서 접근 가능한 API URL로 지정 (예: `http://localhost:8000`).

## Persona Dataset Seed

- 국가별 페르소나 데이터셋을 초기 에이전트 seed로 사용할 수 있다.
- 예: `ORGANIC4D_PERSONA_HF_DATASET_KR=nvidia/Nemotron-Personas-Korea`
- 로컬 샘플 파일도 가능: `ORGANIC4D_PERSONA_DATASET_DIR=/path/to/personas` 아래 `kr.jsonl`, `us.csv`, `jp.json` 등.
- 대용량 HF 데이터셋은 `engine/backend/scripts/sample_personas.py`로 작은 JSONL 샘플을 먼저 만들 수 있다.
- 생성된 world의 seed는 `GET /worlds/{world_id}/personas`에서 확인한다.
- world/snapshot/memory는 기본 `disk` backend로 JSON 영속화되며, `GET /worlds/{world_id}/state`, `POST /worlds/{world_id}/restore`로 what-if 복원/fork가 가능하다.
- CC BY 등 attribution이 필요한 데이터셋은 출처·라이선스를 표시해야 한다.

## 라이선스

MIT License
