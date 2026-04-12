# LLM 언어 옵션 1차 설계

작성일: 2026-04-12  
대상 브랜치: `fix/persona-prompt-korean-eval`  
상태: 설계 승인 후 구현 계획 작성 전

## 1. 목적

이 설계는 LLM에 전달하는 **프롬프트 언어**와 LLM이 생성하는 **출력 언어**를 분리해 설정할 수 있도록 만드는 1차 백엔드 기능을 정의한다.

현재 프로젝트는 중국어 기반의 레거시 프롬프트, 한국어 UI, 한국어 운영 로그가 섞여 있다. 이전 작업에서 UI/로그/안전 주석 일부는 한국어로 정리했고, `OasisProfileGenerator`에는 `persona_prompt_locale="ko"` 후보가 플래그로 추가되었다. 다음 단계에서는 이 흐름을 일반화해 영어 프롬프트 후보와 출력 언어 지시를 검증 가능한 설정으로 분리한다.

## 2. 핵심 원칙

- 기본값은 기존 동작을 깨지 않는다.
- 프롬프트 언어와 출력 언어는 서로 독립적으로 설정한다.
- JSON 필드명과 API 스키마는 언어 옵션과 무관하게 유지한다.
- 사용자 화면 언어 선택 UI는 이번 범위에서 제외한다.
- 프롬프트 전체 현지화는 검증 없이 한 번에 적용하지 않는다.
- 품질 차이가 날 수 있는 LLM 프롬프트 변경은 비교 스크립트와 문서화된 결과를 남긴다.

## 3. 용어 정의

| 용어 | 의미 |
| --- | --- |
| 프롬프트 언어 | LLM에게 보내는 내부 지시문과 설명 문장의 언어 |
| 출력 언어 | LLM이 생성하는 값의 목표 언어 |
| 화면 표시 언어 | 프론트엔드에서 사용자가 보는 UI 문구의 언어 |
| legacy | 기존 중국어 기반 또는 기존 혼합 프롬프트 동작을 보존하는 호환 모드 |

## 4. 1차 지원 범위

### 4.1 지원할 설정값

백엔드 설정 또는 환경변수로 다음 값을 도입한다.

```env
LLM_PROMPT_LANGUAGE=legacy
LLM_OUTPUT_LANGUAGE=ko
```

### 4.2 `LLM_PROMPT_LANGUAGE`

지원값:

| 값 | 의미 | 1차 동작 |
| --- | --- | --- |
| `legacy` | 기존 프롬프트 동작 유지 | 기본값 |
| `ko` | 한국어 프롬프트 후보 | 기존 `persona_prompt_locale="ko"` 흐름과 연결 |
| `en` | 영어 프롬프트 후보 | 새 후보로 추가 |
| `zh` | 명시적 중국어 호환 모드 | 초기에는 `legacy`와 동일하게 취급 가능 |

`legacy`는 운영 안정성을 위한 기본값이다. `zh`는 향후 레거시와 명시적 중국어 모드를 분리할 수 있도록 이름만 열어둔다. 1차 구현에서 `legacy`와 `zh`가 같은 템플릿을 사용해도 된다.

### 4.3 `LLM_OUTPUT_LANGUAGE`

지원값:

| 값 | 의미 |
| --- | --- |
| `ko` | 생성 값은 한국어로 작성 |
| `en` | 생성 값은 영어로 작성 |

출력 언어는 JSON key를 번역하지 않는다. 예를 들어 persona profile JSON의 `bio`, `age`, `profession`, `interested_topics`, `country` 같은 필드는 기존 스키마를 유지하고, 문자열 값만 목표 언어로 작성하도록 지시한다.

## 5. 이번 구현 대상

### 5.1 포함

1차 구현은 `OasisProfileGenerator`의 persona profile 생성 경로에 한정한다.

포함 대상:

- `backend/services/oasis_profile_generator.py`
  - `persona_prompt_locale`를 더 일반적인 프롬프트 언어 개념으로 확장하거나 호환 래퍼를 둔다.
  - `output_language`를 추가한다.
  - `legacy`, `ko`, `en` 프롬프트 후보를 생성할 수 있게 한다.
  - 출력 언어 지시를 prompt 안에 명시한다.

- `backend/scripts/compare_oasis_persona_prompt_localization.py`
  - 기존 비교 스크립트를 확장하거나 새 비교 스크립트를 추가한다.
  - 최소 비교 조합:
    - `legacy -> ko`
    - `ko -> ko`
    - `en -> ko`
    - `en -> en`

- `backend/tests/test_oasis_profile_localization.py`
  - 기본값이 기존 legacy 동작을 유지하는지 검증한다.
  - 영어 프롬프트 후보가 생성되는지 검증한다.
  - 출력 언어 지시가 prompt에 포함되는지 검증한다.
  - JSON key 이름은 기존 스키마를 유지하는지 검증한다.

- `docs/validation/`
  - 실제 LLM 비교 결과를 문서로 남긴다.

### 5.2 제외

이번 설계의 구현 범위에서 제외한다.

- 프론트엔드 설정 화면 추가
- 사용자 UI에서 프롬프트 언어 선택 기능 노출
- 전체 시뮬레이션 프롬프트 전면 다국어화
- ontology/config generator 등 모든 LLM prompt 즉시 변환
- 기존 중국어 legacy prompt 즉시 삭제

## 6. 권장 기본값

운영 기본값:

```env
LLM_PROMPT_LANGUAGE=legacy
LLM_OUTPUT_LANGUAGE=ko
```

영어 프롬프트 품질 비교용:

```env
LLM_PROMPT_LANGUAGE=en
LLM_OUTPUT_LANGUAGE=ko
```

영어 데모 또는 해외 사용자 검증용:

```env
LLM_PROMPT_LANGUAGE=en
LLM_OUTPUT_LANGUAGE=en
```

## 7. 아키텍처 방향

### 7.1 설정 흐름

1. 백엔드가 환경변수 또는 기본 설정에서 언어 옵션을 읽는다.
2. persona profile 생성 서비스 생성 시 설정값을 주입한다.
3. 서비스 내부는 다음 두 값을 분리해 사용한다.
   - `prompt_language`
   - `output_language`
4. prompt builder는 프롬프트 언어별 템플릿과 출력 언어 지시문을 조합한다.
5. LLM 응답 parser는 기존 JSON 스키마를 그대로 파싱한다.

### 7.2 호환성

기존 코드가 `persona_prompt_locale`를 사용하고 있으므로, 구현 시 둘 중 하나를 선택한다.

권장 방식:

- 새 이름: `persona_prompt_language`
- 기존 이름: `persona_prompt_locale`는 호환 인자로 유지
- 둘 다 전달되면 `persona_prompt_language`를 우선한다.

이렇게 하면 기존 테스트와 비교 스크립트가 깨지지 않으면서 명명은 더 정확해진다. `locale`은 보통 UI/지역 설정 의미가 강하고, 여기서는 실제로 prompt language를 제어하기 때문이다.

## 8. 오류 처리

### 8.1 알 수 없는 프롬프트 언어

허용되지 않은 값이 들어오면 명확한 예외를 발생시킨다.

예:

```text
Unsupported persona prompt language: <value>. Supported values: legacy, ko, en, zh
```

### 8.2 알 수 없는 출력 언어

허용되지 않은 값이 들어오면 명확한 예외를 발생시킨다.

예:

```text
Unsupported persona output language: <value>. Supported values: ko, en
```

### 8.3 환경변수 오타

서비스 시작 시점에 검증하거나, generator 생성 시점에 검증한다. 조용히 legacy로 fallback하지 않는다. 설정 오타를 조용히 무시하면 운영자가 다른 언어로 테스트하고 있다고 착각할 수 있다.

## 9. 테스트 전략

### 9.1 단위 테스트

검증 항목:

- 기본 생성자가 legacy prompt를 유지한다.
- `persona_prompt_language="ko"`는 한국어 placeholder를 사용한다.
- `persona_prompt_language="en"`는 영어 instruction/placeholder를 사용한다.
- `persona_output_language="ko"`는 한국어 출력 지시를 포함한다.
- `persona_output_language="en"`는 영어 출력 지시를 포함한다.
- JSON key 목록은 언어 옵션과 무관하게 동일하다.
- 잘못된 언어 값은 예외를 발생시킨다.

### 9.2 비교 스크립트

비교 스크립트는 최소한 다음 정보를 출력한다.

- prompt language
- output language
- prompt length
- prompt 내 CJK 문자 수
- LLM 실행 여부
- LLM 응답의 CJK 문자 수
- 누락된 JSON 필드
- 실행 시간

### 9.3 실제 LLM 스모크 테스트

가능한 경우 bridge를 통해 다음 조합을 한 번씩 실행한다.

```text
legacy -> ko
ko -> ko
en -> ko
en -> en
```

실패 여부보다 중요한 것은 다음이다.

- JSON 파싱 가능 여부
- 필수 필드 유지 여부
- 출력 언어가 목표와 크게 어긋나지 않는지
- 기존 legacy 대비 명백한 품질 저하가 없는지

## 10. 사용자-facing 영향

1차 구현에서는 사용자 화면에 새 선택지가 보이지 않는다. 운영자는 환경변수 또는 백엔드 설정으로만 언어 조합을 바꾼다.

따라서 일반 사용자는 기존과 동일하게 한국어 화면을 사용한다. 내부 프롬프트가 영어인지 legacy인지 여부는 사용자에게 직접 노출되지 않는다.

## 11. 후속 단계

1차 구현과 검증 후 다음 중 하나를 선택한다.

1. 영어 프롬프트가 안정적이면 `LLM_PROMPT_LANGUAGE=en`, `LLM_OUTPUT_LANGUAGE=ko`를 권장 실험값으로 문서화한다.
2. 한국어 프롬프트가 충분히 안정적이면 `ko -> ko` 조합을 확대 검증한다.
3. 프론트엔드 설정 화면에 `APP_DISPLAY_LANGUAGE`와 `LLM_OUTPUT_LANGUAGE`만 먼저 노출한다.
4. `LLM_PROMPT_LANGUAGE`는 개발자 설정으로 유지한다.

## 12. 승인된 범위 요약

이번 작업의 목표는 “영어도 가능한가”에 대한 제품 기능 전체 구현이 아니라, **프롬프트 언어와 출력 언어를 백엔드에서 안전하게 분리하고 검증 가능한 상태로 만드는 것**이다.

기본값은 기존 안정 동작을 유지하고, 영어 프롬프트와 한국어/영어 출력 조합을 실험 가능한 옵션으로 추가한다.
