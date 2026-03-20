# Organic4D — 아키텍처 본질 체크리스트

> **용도**: 코드 작성 시 구조적 아키텍처의 본질이 깨지지 않았는지 확인.  
> **참조 시점**: 코드 작성 전·중·후.  
> **위반 시**: 수정하거나 사용자와 의논.

---

## 사용 방법

1. **코드 작성 전**: 해당 Phase/영역에 해당하는 섹션 확인
2. **코드 작성 중**: 구현이 체크 항목과 충돌하는지 검토
3. **코드 작성 후 (또는 PR 전)**: 전체 체크리스트 한 번 스캔

체크리스트는 지난 세션 논의(CONCEPT, ARCHITECTURE, IMPLEMENTATION 등)를 바탕으로 작성됨.

---

## 1. 엔진 중심 (Engine-First)

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 1.1 | 핵심 코어는 엔진이다. 4D 좌표, 5대 규칙, 시간 흐름, 3계층이 전부 엔진 책임 | 제품·UI 로직이 엔진 코어에 섞여 있음 | CONCEPT §0 |
| 1.2 | 엔진 + God View = 제품으로 바로 사용 가능. 제품 확장은 엔진 API 위에 구축 | God View 없이 엔진만 쓸 수 없는 구조 | CONCEPT §0 |
| 1.3 | 엔진 격리는 `world_id` 기준. 멀티테넌시·과금은 제품 레이어 | world_id 없이 전역 상태 혼재 | ARCHITECTURE §5 |

---

## 2. 4D 시공간 & 세포 모델

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 2.1 | 세포 위치는 반드시 `(x, y, z, t)` 4차원 | 3D만 쓰거나 t를 별도 필드로 분리 | CONCEPT §2, §5 |
| 2.2 | 세포 상태에 `emotion_vec`, `thought_vec`, `worldview_vec` 포함 (3계층) | 단일 `ideology_vec` 등으로 축소 | CONCEPT §5, §6 |
| 2.3 | 4D 거리 함수는 (x,y,z)와 t에 가중치 적용 가능해야 함 | 단순 유클리드만 사용, t 무시 | CONCEPT §10.1, IMPLEMENTATION_SEQUENCE 1.2 |
| 2.4 | World → Snapshot → Cell 계층 구조 유지 | 평탄화된 단일 테이블/모델 | ARCHITECTURE §2.2 |

---

## 3. 생물학적 5대 규칙 본질

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 3.1 | 성장: 영양분 흡수 → 에너지 증가 | 다른 규칙과 혼합되거나 생략 | CONCEPT §4 |
| 3.2 | 분열: 에너지 > 임계치 → 1→2, 유전자·벡터 변이 | 변이 없이 복제만 | CONCEPT §4 |
| 3.3 | 사멸: 에너지=0 → 죽음 + 주변에 영양분 분배 | 영양분 분배 없음 | CONCEPT §4 |
| 3.4 | 융합: 가까운 거리 + **Thought 유사도 0.7+** + Worldview 호환 | Thought/Worldview 없이 거리만으로 융합 | CONCEPT §4, §6.2 |
| 3.5 | 돌연변이: 분열/융합 시 유전자·감정·생각·세계관 일부 변이 | 변이 로직 생략 | CONCEPT §4 |

---

## 4. 3계층 감정·생각 메커니즘 본질

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 4.1 | **Emotion**: 규칙 기반, **LLM 호출 0** | Emotion에 LLM 사용 | CONCEPT §6.1, IMPLEMENTATION §2.4 |
| 4.2 | Emotion 업데이트: 매 t (또는 이벤트 시 1초 이내) | 업데이트 누락 또는 과도한 스킵 | CONCEPT §6.1 |
| 4.3 | **Thought**: 10~50 t마다 LLM, 256차원 | 매 t LLM 호출 | CONCEPT §6.2 |
| 4.4 | Thought = 융합 조건의 **70%** (cosine sim 0.7+) | 비중 변경 또는 생략 | CONCEPT §6.2 |
| 4.5 | **Worldview**: t≥200 또는 메모리 100+ 시에만 갱신 | 더 자주 호출 | CONCEPT §6.3 |
| 4.6 | Worldview: 384차원, sentence-transformers | 차원·생성 방식 변경 시 문서 반영 | CONCEPT §6.3 |

---

## 5. 시간 흐름 & 입출력 레이어

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 5.1 | 입력 → 4D세계 → 에이전트 풀 → 시간 흐름 엔진 → God View 순서 유지 | 레이어 스킵·역전 | CONCEPT §7 |
| 5.2 | 매 t: 성장/분열/사멸/융합/돌연변이 + Emotion | 규칙 누락 | CONCEPT §7 |
| 5.3 | 매 10~50 t: Thought, 매 200 t+ (또는 메모리 100+): Worldview | 주기 혼동 | CONCEPT §7 |
| 5.4 | God View 주입: `(t_inject, event_type, payload)` 도달 시 적용 | 주입 무시·즉시 반영 | ARCHITECTURE §3.2 |

---

## 6. API & 엔진 계약

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 6.1 | 엔진 API: `POST /worlds`, `POST /worlds/{id}/run`, `POST /worlds/{id}/inject`, `GET /snapshots?t=` | 경로·메서드 변경 시 문서 동기화 | IMPLEMENTATION §0 |
| 6.2 | 시각화용: `(x,y,z)`, `energy`, `emotion_vec`, `thought_vec`, `worldview_vec` 제공 | 스냅샷에서 3계층 벡터 누락 | IMPLEMENTATION §0 |
| 6.3 | WebSocket: t, 세포 수, 스냅샷 델타 실시간 전송 | 폴링만 사용·스트리밍 없음 | IMPLEMENTATION_SEQUENCE 3.4 |

---

## 7. 프론트 & 시각화 본질

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 7.1 | 4D → 3D + t 슬라이더. t 변경 시 해당 t 스냅샷으로 3D 갱신 | t 무시·전체 히스토리 한 번에 렌더 | CONCEPT §8 |
| 7.2 | InstancedMesh + setMatrixAt 패턴 (세포 1K+ 필수) | 개별 Mesh로 렌더 | IMPLEMENTATION_SEQUENCE 4.3 |
| 7.3 | Emotion 시각화: 색상(빨강=분노, 파랑=안정) + 크기(강도) | 단색·크기 고정 | CONCEPT §6.1, §8 |

---

## 8. 기술 스택 & 의존성

| # | 체크 항목 | 위반 징후 | 참조 |
|---|-----------|-----------|------|
| 8.1 | tech-stack.mdc 기술 스택 준수 | 스택 외 도입 시 문서·룰 미반영 | `.cursor/rules/core/tech-stack.mdc` |
| 8.2 | IMPLEMENTATION_SEQUENCE Phase 순서·의존성 준수 | Phase 스킵·역전 | IMPLEMENTATION_SEQUENCE |
| 8.3 | 법적 준수: MiroFish 코드 0줄, MIT만 사용 | 외부 코드 복사, AGPL/GPL 도입 | `.cursor/rules/core/legal-compliance.mdc` |

---

## 9. 구현 시점별 핵심 체크

| Phase | 반드시 확인할 본질 |
|-------|---------------------|
| 1 | 2.x(세포·4D), 3.x(5대 규칙), 4.1~4.2(Emotion 규칙 기반) |
| 2 | 5.x(시간 흐름), 2.4(저장 구조) |
| 3 | 6.x(API 계약) |
| 4 | 7.1~7.2(3D+t 슬라이더, InstancedMesh) |
| 5 | 5.1(레이어 순서), 7.1(t→스냅샷→3D) |
| 6 | 4.x 전부(3계층 본질), 3.4(융합 Thought 70%) |
| 7 | 6.1(inject API), 5.4(God View 주입) |
| 8 | 1.x(엔진 분리 유지), 7.2(Instancing 유지) |

---

*문서 버전: v0.1 — 지난 세션 논의 기반 아키텍처 본질 체크리스트*
