# Ontology Naming Runtime Fix Design

## Goal

Zep graph ontology registration 단계에서 발생하는 naming validation 오류를 제거해, 프로젝트가 15% 진행률에서 멈추지 않고 graph build를 계속 진행하도록 만든다.

## Problem Summary

현재 파이프라인은 ontology generation 단계에서 한국어 중심 entity/edge 이름을 생성하고, graph build 단계에서 이를 거의 그대로 Zep `set_ontology()` API에 전달한다. Zep는 entity/source/target 이름에 PascalCase, edge 이름에 SCREAMING_SNAKE_CASE를 요구하므로, build는 ontology apply 단계(약 15%)에서 400으로 실패한다.

로그와 저장된 project.json을 보면 ontology generation 자체는 성공하지만, graph build 중 `name must be in PascalCase format`, `name must be in SCREAMING_SNAKE_CASE format`, `source/target must be in PascalCase format` 오류가 반복된다. 따라서 문제는 runtime bridge나 graph polling이 아니라 ontology naming contract mismatch다.

## Scope

이번 수정의 범위는 아래까지만 포함한다.

- graph build가 Zep ontology validation을 통과하도록 만들기
- build 직전 ontology naming을 강제 정규화/검증하기
- build 실패 시 더 명확한 오류를 남기고 가능하면 빈 graph를 정리하기
- 최소 회귀 테스트 추가

이번 수정의 범위에 포함하지 않는다.

- UI에서 한국어 display name을 유지하는 구조 개편
- ontology 프롬프트를 machine-safe/display_name 이중 구조로 전면 개편
- 기존 failed 프로젝트의 자동 마이그레이션/복구 UX 개선

## Recommended Approach

### Approach A: Build-time normalization only (recommended now)

graph build 직전 ontology를 정규화하는 전용 레이어를 추가한다. 이 레이어는 Zep에 전달할 구조만 machine-safe 하게 만들며, 저장된 project ontology 원본은 유지한다.

정규화 규칙:

- entity name -> PascalCase ASCII alphanumeric
- edge name -> SCREAMING_SNAKE_CASE ASCII
- source/target -> 정규화된 entity name으로 재매핑
- attribute name -> 기존 snake_case 유지, 예약어는 기존 safe_attr_name 규칙 유지
- 중복이 생기면 numeric suffix를 붙여 충돌 회피

장점:

- 현재 실패 원인을 가장 직접적으로 제거한다.
- 프롬프트를 당장 믿지 않아도 된다.
- 변경 범위가 graph build runtime에 집중된다.

단점:

- UI에서 즉시 보이는 타입명이 한국어 친화적이지 않을 수 있다.
- 한글 이름을 자동 정규화할 때 의미가 단순화될 수 있다.

### Approach B: Prompt-only correction

ontology generator prompt를 바꿔 entity/edge/source/target를 처음부터 영어 규칙형으로 생성하게 만든다.

장점:

- 구조가 단순하다.

단점:

- LLM 출력이 다시 규칙을 어기면 동일하게 실패한다.
- runtime safety가 없다.

결론적으로 단독 사용은 부적절하다.

### Approach C: Full dual-name model

ontology에 `name`(machine-safe)와 `display_name`(한국어)을 함께 저장하고, UI는 display_name을, build는 name을 사용한다.

장점:

- 장기적으로 가장 이상적이다.

단점:

- 지금 목표("우선 실행되게") 대비 범위가 크다.

이번 단계에서는 채택하지 않는다.

## Final Decision

이번 수정은 Approach A를 채택한다.

즉, **graph build 전에 ontology를 machine-safe 형식으로 강제 정규화/검증한 뒤에만 Zep에 전달한다.**

필요한 경우 이후 단계에서 prompt와 UI를 추가 정비한다.

## Design Details

### 1. New normalization layer

새로운 helper 또는 service를 추가한다. 위치는 아래 둘 중 하나가 가능하지만, 책임 분리를 위해 별도 파일이 낫다.

- preferred: `backend/app/services/ontology_normalizer.py`
- fallback: `backend/app/services/graph_builder.py` 내부 private helper

이 레이어의 입력은 현재 저장된 ontology JSON이고, 출력은 Zep contract를 만족하는 normalized ontology다.

출력 예시 shape:

- `entity_types[].name` 은 PascalCase
- `edge_types[].name` 은 SCREAMING_SNAKE_CASE
- `edge_types[].source_targets[].source/target` 은 normalized entity name 참조
- description/examples/analysis_summary는 그대로 보존 가능

### 2. Deterministic name normalization

정규화는 LLM 재호출 없이 deterministic 해야 한다.

엔티티 이름:

- 공백, 특수문자 제거
- 토큰화 후 PascalCase 구성
- 비ASCII/한글만 남는 경우에는 fallback prefix 사용 (`Entity1`, `Entity2` 등)
- 동일 결과 충돌 시 suffix 추가 (`Investor`, `Investor2`)

관계 이름:

- 공백, 특수문자 제거
- 토큰화 후 UPPER_SNAKE_CASE 구성
- 비ASCII/한글만 남는 경우 fallback prefix 사용 (`RELATION_1` 등)
- 충돌 시 suffix 추가 (`RELATES_TO`, `RELATES_TO_2`)

source/target:

- 기존 entity 원본 이름 -> normalized entity name 매핑 테이블을 사용해 변환
- 매핑 불가 시 build 전 validation error

### 3. Validation before Zep call

정규화 후 아래를 검증한다.

- entity name non-empty
- edge name non-empty
- source/target가 모두 normalized entity set 안에 존재
- source_targets 비어 있는 edge는 제외 또는 명확한 validation error

이번 목표는 실행 성공이므로, 지나치게 엄격하게 전체 실패를 유발하기보다:

- 복구 가능한 오류는 교정
- 치명적 오류만 실패

정책이 적절하다.

### 4. Integration point

`GraphBuilderService.set_ontology()` 시작부에서 normalization을 수행한다.

현재 raw ontology를 그대로 순회하는 대신:

1. `normalized = normalize_ontology_for_zep(ontology)`
2. normalized entity/edge를 기반으로 Zep model classes 생성
3. `self.client.graph.set_ontology(...)` 호출

이렇게 바꾼다.

### 5. Failure cleanup

현재는 `create_graph()` 후 `set_ontology()` 실패 시 graph shell이 남는다.

이번 범위에서는 worker 내부에서 ontology apply 실패가 나면:

- 가능하면 `builder.delete_graph(graph_id)` 시도
- cleanup 실패는 warning으로만 남김
- project 상태는 FAILED로 유지

이렇게 한다.

### 6. Error visibility

현재 에러는 Zep raw message만 길게 남는다. 이번 수정 후에도 raw message는 유지하되, build failure 로그 앞부분에 원인 범주를 덧붙이는 것이 좋다.

예:

- `Ontology validation failed before Zep apply`
- `Normalized ontology still invalid for Zep`

이렇게 하면 추후 디버깅이 빨라진다.

## Files Expected to Change

### New

- `backend/app/services/ontology_normalizer.py`
- `backend/tests/test_ontology_normalizer.py`

### Modify

- `backend/app/services/graph_builder.py`
- possibly `backend/app/api/graph.py` (if failure cleanup or error surface needs small coordination)

## Testing Strategy

### Unit tests

1. Korean/raw entity names normalize into non-empty PascalCase identifiers
2. Korean/raw edge names normalize into non-empty SCREAMING_SNAKE_CASE identifiers
3. source/target references are remapped to normalized entity names
4. duplicate normalized names are disambiguated deterministically
5. invalid/missing source-target references raise clear validation errors

### Integration-oriented regression

6. A fixture similar to the currently failing ontology shape can be normalized successfully before `set_ontology()` model construction
7. Existing Windows runtime tests remain green

## Risks

- Normalization can produce generic fallback names if source names are entirely Korean/non-ASCII; acceptable for this phase because build success is the priority.
- UI may show normalized English-like names if graph data comes back from Zep using those identifiers; acceptable for this phase by user approval.
- Some relation/source-target pairs may still fail if the raw ontology is structurally broken beyond naming; this should now fail with clearer validation.

## Acceptance Criteria

The fix is successful when:

1. ontology generation still succeeds
2. graph build no longer fails at 15% because of naming format errors
3. Zep `set_ontology()` receives valid identifiers
4. new normalization tests pass
5. existing Windows bridge/runtime regression tests still pass
