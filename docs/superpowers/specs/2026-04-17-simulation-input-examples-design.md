# 시뮬레이션 입력 예시 문서 설계

작성일: 2026-04-17
대상 브랜치: `main`
상태: 설계 승인 후 구현 계획 작성 전

## 1. 목적

이 설계는 Step2 준비 실패를 줄이기 위해 사용자가 바로 복사해서 테스트할 수 있는 **현실 단서 예시 문서**와 **기술지표/전략 문서 변환 예시 문서**를 추가하는 작업을 정의한다.

최근 확인된 실패 사례는 `strategy.txt`가 기술지표와 매매전략 변수 중심으로 그래프를 만들었고, Step2가 시뮬레이션 가능한 행위자 엔티티를 찾지 못해 `matched_entities=0`, `relaxed_candidate_count=0`, `non_actor_text=180`으로 종료된 경우다. 이 실패는 backend/LLM/bridge 장애가 아니라 입력 문서가 사회 시뮬레이션용 행위자를 충분히 제공하지 못한 결과다.

## 2. 현재 문서 구조

이미 존재하는 문서:

- `docs/simulation-input-guide-ko.md`
  - 좋은 첨부파일, 부적합한 입력, 좋은/나쁜 프롬프트 기준을 설명한다.
- `docs/usage-guide-ko.md`
  - 첫 테스트 전에 입력 가이드를 읽도록 안내한다.
- `README.ko.md`
  - 첫 실행 추천 섹션에서 입력 가이드를 연결한다.
- `docs/superpowers/specs/2026-04-05-simulation-input-guidance-and-entity-readiness-design.md`
  - Step2 실패 원인, 입력 품질 경고, entity readiness 진단 설계를 설명한다.

현재 문서의 부족한 점:

- 사용자가 그대로 복사해 업로드할 수 있는 완성형 현실 단서 예시가 없다.
- 기술지표/전략 문서가 왜 실패하는지와 어떻게 actor 중심 문서로 바꿀지 보여주는 실전 예시가 없다.
- `matched_entities=0`, `non_actor_text=180` 같은 진단값을 입력 품질 문제와 연결해 설명하는 예시가 부족하다.

## 3. 목표

1. 사용자가 Step2에 적합한 입력을 눈으로 보고 이해하게 한다.
2. 기술지표/전략 문서도 actor 섹션을 추가하면 시뮬레이션 입력으로 쓸 수 있음을 보여준다.
3. 현재 실패 사례와 같은 `entity_matching` 실패를 문서에서 해석할 수 있게 한다.
4. 기존 UI와 backend 코드를 건드리지 않고 문서만으로 즉시 개선한다.
5. 이후 Step2 UI 링크 노출 작업을 할 수 있도록 문서 경로를 안정적으로 만든다.

## 4. 비목표

이번 작업에서는 다음을 하지 않는다.

- Step2 UI 코드 변경
- 자동 actor 생성 기능 추가
- entity matching 알고리즘 변경
- graph 재생성 자동화
- 현재 사용자의 `strategy.txt` 원본 파일 직접 수정
- 깨진 인코딩 로그 전면 수정
- ontology/config/simulation prompt 전면 다국어화

## 5. 제안 접근

### 선택한 접근: 문서 예시 2개 추가 + 기존 가이드 링크 연결

새 문서:

- `docs/examples/simulation-reality-clue-good-example.md`
- `docs/examples/strategy-actor-simulation-example.md`

수정 문서:

- `docs/simulation-input-guide-ko.md`
- `docs/usage-guide-ko.md`
- `README.ko.md`

이 접근은 코드 변경 없이 사용자가 실패 원인을 이해하고 다음 입력을 바로 만들 수 있게 한다. Step2 UI에 링크를 노출하는 작업은 별도 단계로 남긴다.

## 6. 새 문서 1: 좋은 현실 단서 예시

파일:

```text
docs/examples/simulation-reality-clue-good-example.md
```

### 목적

사회 시뮬레이션에 적합한 현실 단서의 완성형 예시를 제공한다. 사용자가 그대로 복사해 파일로 저장하거나, 자기 사례에 맞춰 수정할 수 있어야 한다.

### 주제

AI 반도체 테마주 급등과 투자자 반응.

이 주제를 선택하는 이유:

- 개인 투자자, 장기 투자자, 증권사, 감독기관, 언론, 기업 IR 담당자 등 actor가 자연스럽다.
- 갈등 구조가 명확하다.
- 시간 흐름을 만들기 쉽다.
- 커뮤니티 발화와 공식 대응을 함께 보여줄 수 있다.

### 문서 구성

```markdown
# 좋은 현실 단서 예시: AI 반도체 테마주 급등과 투자자 반응

## 사건 개요
## 주요 행위자
## 시간 흐름
## 갈등 구조
## 발화 단서
## 시뮬레이션에 적합한 이유
## 함께 쓰면 좋은 시뮬레이션 프롬프트
## 변형해서 쓰는 방법
```

### 포함할 주요 행위자

- 개인 투자자: 단기 수익 기대와 FOMO를 드러낸다.
- 장기 투자자: 실적과 밸류에이션을 근거로 과열을 경계한다.
- 증권사 애널리스트: 산업 전망과 기업 실적을 분석한다.
- 금융감독원: 테마주 과열과 불공정거래 가능성을 모니터링한다.
- 경제지 기자: 시장 반응과 투자자 심리를 기사화한다.
- 기업 IR 담당자: 실제 사업 현황과 수주 여부를 설명한다.
- 투자 커뮤니티 운영자: 과열 게시글과 허위 정보 확산을 관리한다.

### 성공 기준

이 문서만 봐도 사용자가 다음을 이해해야 한다.

- 시뮬레이션에는 사람/조직/커뮤니티 같은 actor가 필요하다.
- 사건, 갈등, 시간 흐름, 발화 단서가 들어가야 Step2가 엔티티를 만들기 쉽다.
- 좋은 프롬프트는 대상, 기간, 관찰 기준을 좁혀야 한다.

## 7. 새 문서 2: 기술지표/전략 문서 변환 예시

파일:

```text
docs/examples/strategy-actor-simulation-example.md
```

### 목적

기술지표/전략 문서가 왜 Step2에서 실패하기 쉬운지 설명하고, 같은 주제를 actor 중심 현실 단서로 바꾸는 방법을 보여준다.

### 배경 사례

실패한 입력의 성격:

- 기술지표명, 변수명, 전략 조건, 수식 중심
- `체결강도`, `매수총잔량`, `STOCHSK`, `WILLR`, `동적청산` 같은 개념 노드 중심
- 사람, 조직, 커뮤니티, 발화, 갈등 구조가 부족함
- 결과적으로 `matched_entities=0`, `relaxed_candidate_count=0`, `non_actor_text=180` 같은 준비 실패가 발생할 수 있음

### 문서 구성

```markdown
# 기술지표/전략 문서를 시뮬레이션용 현실 단서로 바꾸는 예시

## 실패하기 쉬운 입력
## 왜 Step2에서 실패하는가
## actor를 추가한 개선 입력
## 주요 행위자
## 갈등 구조
## 시간 흐름
## 함께 쓰면 좋은 시뮬레이션 프롬프트
## 체크리스트
```

### 포함할 주요 행위자

- 퀀트 개발자: 전략 로직과 지표 조건을 설계한다.
- 개인 트레이더: 체결강도와 호가잔량을 보고 단기 매매 판단을 한다.
- 리스크 관리자: 동적청산 조건이 손실을 줄이는지 검토한다.
- 증권사 시스템 운영자: 실시간 데이터 지연과 주문 처리 안정성을 점검한다.
- 투자 커뮤니티 이용자: 전략 성과와 실패 사례를 공유한다.
- 데이터 엔지니어: 틱/분봉 데이터 품질과 누락 문제를 관리한다.
- 전략 검수 담당자: 백테스트와 실거래 차이를 점검한다.

### 성공 기준

이 문서만 봐도 사용자가 다음을 이해해야 한다.

- 기술지표 자체는 actor가 아니다.
- 전략을 둘러싼 사람/조직/역할을 추가해야 시뮬레이션이 가능하다.
- 기술 문서를 버리지 않고 actor 섹션을 덧붙이면 Step2 성공 가능성이 높아진다.

## 8. 기존 가이드 업데이트

### 8.1 `docs/simulation-input-guide-ko.md`

추가할 섹션:

```markdown
## 바로 써볼 수 있는 예시

- [좋은 현실 단서 예시](./examples/simulation-reality-clue-good-example.md)
- [기술지표/전략 문서를 actor 중심 입력으로 바꾸는 예시](./examples/strategy-actor-simulation-example.md)
```

추가할 진단 해석:

```markdown
`matched_entities=0`, `relaxed_candidate_count=0`, `non_actor_text`가 높게 나오면 그래프는 만들어졌지만 시뮬레이션 가능한 행위자가 부족하다는 뜻입니다.
```

### 8.2 `docs/usage-guide-ko.md`

첫 테스트 방법에서 기존 `examples/scenarios/ko/` 안내와 함께 `docs/examples/` 예시 문서를 언급한다.

추가할 내용:

- 처음 테스트는 `docs/examples/simulation-reality-clue-good-example.md`처럼 actor가 분명한 문서로 시작한다.
- 기술지표/전략 문서를 쓰려면 `docs/examples/strategy-actor-simulation-example.md`처럼 actor 섹션을 추가한다.

### 8.3 `README.ko.md`

첫 실행 추천 섹션에 한 줄을 추가한다.

```markdown
기술지표/전략 문서를 업로드하려면 먼저 actor 중심 변환 예시를 참고하세요.
```

## 9. 데이터 흐름

사용자 흐름:

1. 사용자가 `docs/simulation-input-guide-ko.md`를 읽는다.
2. 사용자는 `docs/examples/simulation-reality-clue-good-example.md` 또는 `docs/examples/strategy-actor-simulation-example.md`를 연다.
3. 예시 문서를 복사하거나 자기 사례에 맞춰 actor, 시간 흐름, 갈등 구조를 수정한다.
4. 수정한 문서를 업로드한다.
5. 프롬프트 예시를 함께 입력한다.
6. Step2에서 actor 중심 엔티티가 추출될 가능성이 높아진다.

## 10. 오류와 한계 안내

문서에는 다음을 명확히 적는다.

- 예시를 쓴다고 모든 Step2가 성공하는 것은 아니다.
- actor가 있어도 Zep graph 생성 품질, 문서 길이, 프롬프트 명확성에 따라 결과는 달라질 수 있다.
- 기술 문서만 올리면 Step2가 실패할 수 있다.
- `완화 매칭으로 다시 시도`는 보조 수단이지 actor 부재를 자동 해결하지 않는다.

## 11. 테스트 전략

문서 작업이므로 런타임 테스트보다 형식과 연결 검증을 우선한다.

검증 항목:

- 새 문서 2개가 존재한다.
- 기존 가이드 문서에서 새 문서 링크가 상대경로로 연결된다.
- 문서에 미완성 표식이나 작성 지시문이 남아 있지 않다.
- markdown whitespace check가 통과한다.
- 필요 시 `git diff --check`를 실행한다.

선택 검증:

- 문서 내 링크 경로를 `Test-Path`로 확인한다.
- 새 문서의 주요 섹션 제목이 존재하는지 `Select-String`으로 확인한다.

## 12. 후속 작업

이번 문서 작업 이후 가능한 후속 단계:

1. Step2 실패 카드에 `docs/examples/` 링크를 노출한다.
2. UI에서 `matched_entities=0`일 때 “기술 문서를 actor 중심으로 바꾸는 방법” 링크를 보여준다.
3. 영어 버전 예시 문서를 추가한다.
4. 깨진 루트 `사용-가이드-ko.md`를 별도 작업으로 정리한다.
5. 실제 예시 문서를 업로드해 Step2 성공 여부를 검증한다.

## 13. 완료 기준

- `docs/examples/simulation-reality-clue-good-example.md` 설계 범위가 명확하다.
- `docs/examples/strategy-actor-simulation-example.md` 설계 범위가 명확하다.
- 기존 한국어 입력/사용 가이드와 README 연결 범위가 명확하다.
- UI와 backend 코드를 건드리지 않는 문서 중심 작업으로 범위가 제한된다.
- 이 스펙을 기반으로 구현 계획을 작성할 수 있다.
