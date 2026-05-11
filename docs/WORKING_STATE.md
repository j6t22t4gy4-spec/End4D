# Working State

이 문서는 긴 대화 컨텍스트 없이도 현재 프로젝트 상태를 빠르게 복구하기 위한 압축 상태 문서다.

## Product Core
- 목표: 국가 단위 사회를 장기적으로 시뮬레이션하고, 정책/시장/사회 What-if를 비교·해석하는 범용 플랫폼
- 공간 모델: `x, y + social elevation(z) + time`
- 실행 구조: 로컬 엔진 실행 + 클라우드/로컬 persona data pack 공급

## Engine Status
- Persona-aware Genesis: 구현됨, persona distribution이 role/zone/energy/z seed에 반영됨
- LLM Agent Cognition: thought/worldview/action/policy/dialogue/group deliberation 연결됨
- Group Belief State: stance/cohesion/tension/trust/polarization/persistence + split/block/fracture 지표 포함
- Storage: file-based persistence + snapshot index + archive metadata + fork/restore
- Data Packs: install/validate/verify/pin/rollback/history/diff 지원

## Analyst Review Status
- World Summary: 구현됨
- Timeline Annotation: 구현됨
- World Diff Report: 구현됨
- Review Query / Diff Query: 구현됨
- Session Review / Session Query: 구현됨
- Persona Agent 1:1 Interview / World-to-World Interview Diff: 구현됨
- Grounding / Citations: section-level explicit anchor 기반

## Frontend Workbench Status
- Setup / Run / Review 분리
- Simulation Map 2D + social elevation contour overlay
- Review Lab:
  - summary
  - diff
  - query
  - session review
  - persona interview matrix
  - fracture graph
- Simulation:
  - map
  - inspector
  - timeline
  - analysis graph lane
  - review-driven injection presets

## Highest Remaining Gaps
1. analyst-grade causal grounding 강화
2. multi-world side-by-side compare 시각화
3. review/inspector 10k+ 성능 튜닝
4. strict sentence-level anchor emission
5. Nemotron 대용량 실제 운영 QA

## Recommended Next Steps
1. causal chain grounding (`event -> group -> zone -> agent`)
2. multi-world compare lane
3. review-driven feedback loop into memory/thought/worldview
4. 10k+ benchmark baseline collection
5. strict anchor-aware JSON generation
