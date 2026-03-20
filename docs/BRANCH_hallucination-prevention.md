# 할루시네이션 방지 기술 (분기)

> **상태**: 아직 우선 적용하지 않음. 향후 적용 시 검토용 분기 문서.

---

## 개요

Thought·Worldview 생성 시 LLM 할루시네이션을 줄이기 위한 기술 모음.  
우선순위·조합은 아직 미결정. 필요 시 이 문서를 참고해 단계별 도입.

---

## 기술 비교표

| 순위 | 기술 | 구현 난이도 | hallucination 감소 효과 | 비용 영향 | 아키텍처 적용 방법 |
|------|------|-------------|-------------------------|-----------|--------------------|
| 1 | **Structured Output + Pydantic Validation** | ★☆☆ (가장 쉬움) | 40~60% 감소 | 거의 없음 | LLM 프롬프트에 JSON 스키마 강제 + LangGraph node에서 Pydantic으로 즉시 검증. 불일치 시 재시도 또는 이전 벡터 유지 |
| 2 | **Worldview Consistency Check** | ★★☆ | 25~35% 추가 감소 | 거의 없음 | 새 Worldview 생성 시 이전 Worldview와 cosine similarity 0.6 미만이면 "거부"하고 이전 값 유지 |
| 3 | **Guardian Node (Multi-Agent Validation)** | ★★☆ | 30~50% 감소 | LLM 호출 1.5배 | LangGraph에 별도 "검증 노드" 추가. Thought/Worldview 생성 후 다른 작은 모델이 "이게 메모리와 맞나?" 검증 |
| 4 | **RAG-style Memory Retrieval** | ★★☆ | 20~40% 감소 | 약간 증가 | Zep/Redis에서 최근 50개 이벤트만 정확히 retrieve해서 프롬프트에 넣음 (현재는 전체 메모리 넣는 방식) |
| 5 | **Confidence Scoring + Rejection** | ★★★ | 15~30% 감소 | 약간 증가 | LLM 출력에 confidence 점수 강제하고, 0.7 미만이면 재생성 또는 규칙 기반 fallback |

---

## 상세

### 1. Structured Output + Pydantic Validation

- **방법**: JSON 스키마를 프롬프트에 명시 → LLM이 해당 형식으로만 출력 → Pydantic으로 파싱·검증
- **실패 시**: 재시도 또는 이전 벡터 유지
- **비용**: 거의 없음 (추가 LLM 호출 없음)

### 2. Worldview Consistency Check

- **방법**: 새 Worldview 생성 시 이전 Worldview와 cosine similarity 계산
- **조건**: 0.6 미만 → "급격한 신념 전환"으로 간주 → 거부, 이전 값 유지
- **비용**: 거의 없음 (벡터 연산만)

### 3. Guardian Node (Multi-Agent Validation)

- **방법**: Thought/Worldview 생성 → 별도 "검증 노드"에서 다른 작은 모델이 "메모리와 일치하는가?" 검증
- **비용**: LLM 호출 약 1.5배

### 4. RAG-style Memory Retrieval

- **방법**: 전체 메모리가 아닌 **최근 50개 이벤트**만 retrieve → 프롬프트에 포함
- **효과**: irrelevant 메모리로 인한 할루시네이션 감소
- **비용**: retrieval 비용 약간 증가

### 5. Confidence Scoring + Rejection

- **방법**: LLM 출력에 confidence 점수 포함 (예: 0~1) 강제
- **조건**: 0.7 미만 → 재생성 또는 규칙 기반 fallback
- **구현 난이도**: ★★★ (LLM이 실제로 신뢰도 낮은 답에 낮은 점수를 주는지 불확실)

---

## 적용 시점 (미결정)

- Phase 6 (3계층 생성) 구현 후 품질 이슈 발생 시 검토
- 또는 POC 전에 1번(Structured Output)만 먼저 적용 검토 가능

---

*문서 버전: v0.1 — 분기*
