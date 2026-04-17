# Simulation Input Examples Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Korean simulation input example documents that show users how to provide actor-rich reality clues and how to convert technical trading-strategy documents into simulation-ready inputs.

**Architecture:** This is a documentation-only change. Two new example files live under `docs/examples/`, and existing Korean entry-point docs link to them from `docs/simulation-input-guide-ko.md`, `docs/usage-guide-ko.md`, and `README.ko.md`. Verification focuses on link integrity, required section coverage, absence of unfinished authoring markers, and markdown whitespace checks.

**Tech Stack:** Markdown documentation, PowerShell verification commands, Git whitespace checks.

---

## Source Spec

- `docs/superpowers/specs/2026-04-17-simulation-input-examples-design.md`

## File Structure

- Create: `docs/examples/simulation-reality-clue-good-example.md`
  - Complete copy-ready example of an actor-rich reality clue document.
- Create: `docs/examples/strategy-actor-simulation-example.md`
  - Complete copy-ready example showing how to turn technical indicator / strategy material into an actor-centered simulation input.
- Modify: `docs/simulation-input-guide-ko.md`
  - Link to the two example documents and explain `matched_entities=0` / `non_actor_text` failure interpretation.
- Modify: `docs/usage-guide-ko.md`
  - Mention the new example documents in the first-test flow.
- Modify: `README.ko.md`
  - Add one short first-run note that points technical-strategy users to the actor conversion example.

## Implementation Rules

- Do not change frontend code.
- Do not change backend code.
- Do not change entity matching behavior.
- Keep the examples Korean-first.
- The examples must be directly copyable into a `.md` or `.txt` upload seed.
- Keep links relative and valid from the file where they are written.
- Commit after each task using Korean markdown Lore commit messages.

---

### Task 1: Create the Actor-Rich Reality Clue Example

**Files:**
- Create: `docs/examples/simulation-reality-clue-good-example.md`

- [ ] **Step 1: Create the examples directory**

Run:

```powershell
New-Item -ItemType Directory -Force -Path docs\examples
```

Expected:

```text
Directory docs\examples exists.
```

- [ ] **Step 2: Create `simulation-reality-clue-good-example.md` with complete content**

Write exactly this content to `docs/examples/simulation-reality-clue-good-example.md`:

````markdown
# 좋은 현실 단서 예시: AI 반도체 테마주 급등과 투자자 반응

이 문서는 Step2 시뮬레이션 준비에 적합한 현실 단서 예시입니다. 그대로 복사해 테스트하거나, 사건명과 행위자를 바꿔 자기 사례에 맞게 수정할 수 있습니다.

## 사건 개요

2026년 4월 12일 오전, 국내 증시에서 AI 반도체 후공정 장비 기업인 가상 기업 `네오패키지테크`의 주가가 장중 18% 급등했다. 전날 밤 미국 대형 클라우드 기업이 AI 서버 투자 확대를 발표했고, 국내 투자 커뮤니티에서는 `네오패키지테크`가 관련 공급망에 포함될 수 있다는 글이 빠르게 퍼졌다.

회사는 아직 공식 수주 공시를 내지 않았지만, 최근 IR 자료에서 “고성능 AI 칩 패키징 장비 문의가 늘고 있다”고 언급했다. 이 문장이 단기 투자자 사이에서 강한 기대를 만들었고, 일부 장기 투자자는 실적 확인 전 과열을 우려했다.

## 주요 행위자

- 개인 투자자: 급등 초기에 매수 기회를 놓칠까 불안해하며 커뮤니티에 실시간 호가와 체결 강도를 공유한다.
- 장기 투자자: 실제 수주와 매출 반영 여부를 확인해야 한다고 주장하며 단기 과열을 경계한다.
- 증권사 애널리스트: AI 반도체 후공정 산업의 성장 가능성은 인정하지만, 특정 기업 실적 반영 시점은 불확실하다고 설명한다.
- 금융감독원 시장감시 담당자: 테마주 과열과 허위 풍문 확산 가능성을 모니터링한다.
- 경제지 기자: 급등 배경, 커뮤니티 반응, 회사의 공식 입장을 종합해 기사화한다.
- 기업 IR 담당자: 공급망 포함 여부는 확인해 줄 수 없고, 확정 공시 전 추측성 보도는 조심해야 한다고 답한다.
- 투자 커뮤니티 운영자: 근거 없는 수주 확정 글과 과도한 선동성 게시글을 숨김 처리할지 고민한다.

## 시간 흐름

- D+0 09:10: 미국 AI 서버 투자 확대 뉴스가 국내 커뮤니티에 공유된다.
- D+0 09:30: `네오패키지테크` 주가가 빠르게 오르고 개인 투자자들이 체결 강도와 호가잔량을 캡처해 올린다.
- D+0 10:20: 한 커뮤니티 이용자가 “대형 고객사 납품 확정”이라고 주장하지만 출처가 불명확하다.
- D+0 11:00: 증권사 애널리스트가 “산업 방향은 긍정적이나 기업별 실적 확인이 필요하다”는 코멘트를 낸다.
- D+0 13:30: 경제지 기자가 회사 IR 담당자에게 확인 전화를 하고, 회사는 확정 수주 공시는 없다고 답한다.
- D+0 15:00: 금융감독원 시장감시 담당자가 풍문 확산 패턴을 확인한다.
- D+1 09:00: 전날 급등에 대한 차익 실현 매물이 나오고, 커뮤니티에서 매수 유지와 리스크 관리 의견이 충돌한다.

## 갈등 구조

개인 투자자는 “AI 반도체 수혜가 이제 시작됐다”고 보며 빠른 매수를 주장한다. 장기 투자자와 애널리스트는 실제 수주, 매출, 마진이 확인되지 않았다고 반박한다. 기업 IR 담당자는 확정되지 않은 내용을 말할 수 없고, 기자와 감독기관은 허위 정보 확산 가능성을 경계한다.

## 발화 단서

- 개인 투자자: “체결강도 봐라. 아직 물량 안 끝났다. 지금 못 타면 또 놓친다.”
- 장기 투자자: “수주 공시가 없는데 납품 확정처럼 말하는 건 위험하다. 실적 확인 전에는 비중 조절해야 한다.”
- 증권사 애널리스트: “AI 후공정 장비 수요는 구조적으로 늘 수 있지만, 개별 기업의 실적 반영은 분기별 수주 데이터로 확인해야 한다.”
- 금융감독원 담당자: “출처 없는 확정 표현이 반복되면 시장 감시 대상이 될 수 있다.”
- 경제지 기자: “회사 공식 입장은 아직 확정 수주 공시가 없다는 쪽입니다. 커뮤니티 풍문과 공식 확인을 구분해야 합니다.”
- 기업 IR 담당자: “문의가 늘어난 것은 맞지만 개별 고객사와 수주 여부는 공시 전 확인해 드릴 수 없습니다.”
- 커뮤니티 운영자: “출처 없는 수주 확정 글은 숨김 처리하고, 공시나 기사 링크가 있는 글만 상단에 남기겠습니다.”

## 시뮬레이션에 적합한 이유

- 행위자가 사람, 조직, 커뮤니티 역할로 명확히 나뉩니다.
- 각 행위자마다 다른 목표와 이해관계가 있습니다.
- 시간 흐름이 있어 D+0부터 D+1까지 반응 변화를 만들 수 있습니다.
- 발화 단서가 있어 소셜 미디어 계정별 말투와 반응을 만들기 쉽습니다.
- 갈등 구조가 있어 여론 증폭, 반박, 정보 검증 과정을 시뮬레이션할 수 있습니다.

## 함께 쓰면 좋은 시뮬레이션 프롬프트

```text
업로드한 현실 단서를 바탕으로 AI 반도체 테마주 급등 이후 24시간 동안의 소셜 미디어 반응을 시뮬레이션해 주세요.
개인 투자자, 장기 투자자, 증권사 애널리스트, 경제지 기자, 기업 IR 담당자, 커뮤니티 운영자, 금융감독원 담당자의 관점을 분리해 주세요.
특히 출처 없는 수주 확정 주장, 차익 실현 우려, 공식 확인 요구가 어떻게 충돌하고 확산되는지 시간대별로 보여 주세요.
```

## 변형해서 쓰는 방법

- 주식 테마를 바이오, 2차전지, 로봇, 방산 등으로 바꿀 수 있습니다.
- 기업명과 기관명은 실제 사례에 맞춰 바꿉니다.
- 행위자는 최소 5개 이상 유지하는 것이 좋습니다.
- 발화 단서는 각 행위자마다 1개 이상 넣는 것이 좋습니다.
- 기간을 D+0, D+1, D+3처럼 나누면 시뮬레이션 흐름이 더 선명해집니다.
````

- [ ] **Step 3: Verify required sections exist**

Run:

```powershell
Select-String -Path docs\examples\simulation-reality-clue-good-example.md -Pattern '^## 사건 개요|^## 주요 행위자|^## 시간 흐름|^## 갈등 구조|^## 발화 단서|^## 함께 쓰면 좋은 시뮬레이션 프롬프트'
```

Expected:

```text
All six section headings are found.
```

- [ ] **Step 4: Commit Task 1**

Use a Korean markdown Lore commit message:

```powershell
git add docs/examples/simulation-reality-clue-good-example.md
git commit -m "좋은 현실 단서 예시 문서를 추가한다"
```

---

### Task 2: Create the Technical Strategy Actor Conversion Example

**Files:**
- Create: `docs/examples/strategy-actor-simulation-example.md`

- [ ] **Step 1: Create `strategy-actor-simulation-example.md` with complete content**

Write exactly this content to `docs/examples/strategy-actor-simulation-example.md`:

````markdown
# 기술지표/전략 문서를 시뮬레이션용 현실 단서로 바꾸는 예시

이 문서는 체결강도, 호가잔량, STOCHSK, WILLR, 동적청산 같은 기술지표/전략 설명 문서가 Step2에서 왜 실패할 수 있는지와, 같은 내용을 actor 중심 입력으로 바꾸는 방법을 보여줍니다.

## 실패하기 쉬운 입력

아래와 같은 입력은 그래프 노드는 많이 만들 수 있지만, 시뮬레이션 가능한 행위자를 거의 만들지 못할 수 있습니다.

```text
체결강도는 매도수량 대비 매수수량의 비율이며 최소값은 0, 최대값은 500이다.
매수총잔량은 매수호가 1~5단계 잔량의 합계다.
STOCHSK는 이전 값을 _1 suffix로 조회할 수 있다.
동적청산 조건은 변동성과 수익률 조건을 조합해 손실을 제한한다.
WILLR, AROOND, 매도전략, 초당매도수량을 전략 변수로 사용한다.
```

## 왜 Step2에서 실패하는가

Step2는 소셜 시뮬레이션을 위해 사람, 조직, 커뮤니티, 역할, 관계를 찾습니다. 위 입력은 대부분 변수명과 계산 조건입니다. 이런 문서는 `체결강도`, `매수총잔량`, `STOCHSK` 같은 개념 노드를 만들 수 있지만, 누가 말하고 누가 반응하는지 보여 주지 않습니다.

다음과 같은 진단이 나오면 actor가 부족하다는 뜻입니다.

```text
matched_entities=0
relaxed_candidate_count=0
non_actor_text=180
```

이 경우 `완화 매칭으로 다시 시도`를 눌러도 actor 후보가 없으면 다시 실패합니다.

## actor를 추가한 개선 입력

아래처럼 기술 전략을 둘러싼 사람과 조직을 추가하면 시뮬레이션 가능한 입력이 됩니다.

```text
한 개인 트레이더가 체결강도와 매수총잔량을 활용한 단기 매매 전략을 커뮤니티에 공유했다.
전략은 STOCHSK, WILLR, 동적청산 조건을 조합해 진입과 청산 시점을 판단한다.
퀀트 개발자는 이 전략이 과거 데이터에서는 수익을 냈지만, 실시간 체결 지연과 호가 공백 상황에서는 성능이 달라질 수 있다고 설명했다.
리스크 관리자는 동적청산 조건이 손실을 줄일 수 있지만, 급락장에서는 슬리피지 때문에 예상보다 큰 손실이 날 수 있다고 경고했다.
증권사 시스템 운영자는 초당 데이터와 분봉 데이터의 차이 때문에 백테스트 결과와 실거래 결과가 다를 수 있다고 지적했다.
투자 커뮤니티 이용자들은 전략 수익률 인증, 손실 사례, 변수 튜닝 방법을 두고 논쟁했다.
데이터 엔지니어는 틱 데이터 누락과 체결 강도 계산 오류가 전략 성능을 왜곡할 수 있다고 말했다.
```

## 주요 행위자

- 퀀트 개발자: 전략 로직과 지표 조건을 설계하고 백테스트 결과를 설명한다.
- 개인 트레이더: 체결강도와 호가잔량을 보고 단기 매매 판단을 내린다.
- 리스크 관리자: 동적청산 조건이 실제 손실을 줄이는지 검토한다.
- 증권사 시스템 운영자: 실시간 데이터 지연, 주문 처리, 호가 공백 문제를 점검한다.
- 투자 커뮤니티 이용자: 전략 수익률 인증과 손실 사례를 공유하며 논쟁한다.
- 데이터 엔지니어: 틱/분봉 데이터 품질과 누락 문제를 관리한다.
- 전략 검수 담당자: 백테스트와 실거래 차이를 확인하고 운영 가능성을 평가한다.

## 갈등 구조

전략을 공유한 트레이더와 일부 커뮤니티 이용자는 높은 수익률을 강조한다. 리스크 관리자와 전략 검수 담당자는 슬리피지, 데이터 지연, 과최적화 가능성을 경계한다. 퀀트 개발자는 모델 구조를 설명하지만, 실거래 환경에서는 보수적인 검증이 필요하다고 말한다. 커뮤니티에서는 “실전 가능한 전략”이라는 주장과 “백테스트 착시”라는 반박이 충돌한다.

## 시간 흐름

- D+0 09:00: 개인 트레이더가 전략 설명과 수익률 캡처를 커뮤니티에 올린다.
- D+0 10:00: 커뮤니티 이용자들이 체결강도 조건과 매수총잔량 조건을 질문한다.
- D+0 11:30: 퀀트 개발자가 STOCHSK와 WILLR 조합의 의미를 설명한다.
- D+0 13:00: 리스크 관리자가 동적청산이 급락장에서는 늦게 작동할 수 있다고 경고한다.
- D+0 15:30: 증권사 시스템 운영자가 실시간 데이터 지연과 주문 체결 차이를 지적한다.
- D+1 09:30: 일부 이용자가 실거래 손실 사례를 공유하며 전략 신뢰도 논쟁이 커진다.

## 함께 쓰면 좋은 시뮬레이션 프롬프트

```text
업로드한 기술 전략 현실 단서를 바탕으로, 전략 공개 이후 24시간 동안 투자 커뮤니티에서 벌어지는 반응을 시뮬레이션해 주세요.
퀀트 개발자, 개인 트레이더, 리스크 관리자, 증권사 시스템 운영자, 데이터 엔지니어, 투자 커뮤니티 이용자의 관점을 분리해 주세요.
특히 백테스트 수익률 주장, 실거래 손실 우려, 데이터 지연 문제, 동적청산 신뢰성 논쟁이 어떻게 확산되는지 시간대별로 보여 주세요.
```

## 체크리스트

기술 문서를 시뮬레이션 입력으로 바꾸기 전에 아래를 확인합니다.

- 변수명만 있지 않고 사람이나 조직이 등장한다.
- 각 행위자가 무엇을 주장하는지 적혀 있다.
- 전략을 둘러싼 찬성, 반대, 검증, 운영 관점이 나뉜다.
- 시간 흐름이 최소 D+0, D+1 단위로 있다.
- 발화 단서나 커뮤니티 반응이 포함되어 있다.
- 프롬프트가 누가, 언제, 무엇을 관찰할지 좁혀 준다.
````

- [ ] **Step 2: Verify required sections exist**

Run:

```powershell
Select-String -Path docs\examples\strategy-actor-simulation-example.md -Pattern '^## 실패하기 쉬운 입력|^## 왜 Step2에서 실패하는가|^## actor를 추가한 개선 입력|^## 주요 행위자|^## 갈등 구조|^## 시간 흐름|^## 함께 쓰면 좋은 시뮬레이션 프롬프트|^## 체크리스트'
```

Expected:

```text
All eight section headings are found.
```

- [ ] **Step 3: Commit Task 2**

Use a Korean markdown Lore commit message:

```powershell
git add docs/examples/strategy-actor-simulation-example.md
git commit -m "기술 전략 문서의 actor 변환 예시를 추가한다"
```

---

### Task 3: Link Examples from Existing Korean Guides

**Files:**
- Modify: `docs/simulation-input-guide-ko.md`
- Modify: `docs/usage-guide-ko.md`
- Modify: `README.ko.md`

- [ ] **Step 1: Update `docs/simulation-input-guide-ko.md`**

Insert this section after the introductory bullet list and before `## 좋은 첨부파일 예시`:

```markdown
## 바로 써볼 수 있는 예시

- [좋은 현실 단서 예시](./examples/simulation-reality-clue-good-example.md): 사람, 조직, 커뮤니티, 사건, 시간 흐름이 모두 들어 있는 완성형 seed 예시입니다.
- [기술지표/전략 문서를 actor 중심 입력으로 바꾸는 예시](./examples/strategy-actor-simulation-example.md): 체결강도, 호가잔량, STOCHSK 같은 기술 문서를 시뮬레이션 가능한 입력으로 바꾸는 방법입니다.

`matched_entities=0`, `relaxed_candidate_count=0`, `non_actor_text`가 높게 나오면 그래프는 만들어졌지만 시뮬레이션 가능한 행위자가 부족하다는 뜻입니다. 이 경우 같은 문서를 반복 실행하기보다 위 예시처럼 행위자, 갈등, 시간 흐름, 발화 단서를 추가하는 편이 효과적입니다.
```

- [ ] **Step 2: Update `docs/usage-guide-ko.md` first-test section**

Replace the current numbered list under `## 6. 첫 테스트 방법` with:

```markdown
1. 처음에는 [좋은 현실 단서 예시](./examples/simulation-reality-clue-good-example.md)처럼 actor가 분명한 문서로 시작
2. 기술지표/전략 문서를 쓰려면 [actor 중심 변환 예시](./examples/strategy-actor-simulation-example.md)처럼 사람, 조직, 역할을 먼저 추가
3. MiroFish 홈에서 해당 문서를 업로드
4. 같은 주제의 프롬프트를 붙여넣기
5. Step1 → Step5 순서로 진행
6. 첫 실행은 라운드 수를 적게 잡기
```

Keep the preceding paragraph that links to `simulation-input-guide-ko.md`.

- [ ] **Step 3: Update `README.ko.md` first-run section**

In the `## 첫 실행 추천` section, after the paragraph that links to `docs/simulation-input-guide-ko.md`, add:

```markdown
기술지표/전략 문서를 업로드하려면 [actor 중심 변환 예시](./docs/examples/strategy-actor-simulation-example.md)를 먼저 참고하세요. 변수명과 수식만 있는 입력은 Step2에서 `matched_entities=0`으로 실패할 수 있습니다.
```

- [ ] **Step 4: Verify links resolve**

Run:

```powershell
Test-Path docs\examples\simulation-reality-clue-good-example.md
Test-Path docs\examples\strategy-actor-simulation-example.md
```

Expected:

```text
True
True
```

- [ ] **Step 5: Verify docs mention both example links**

Run:

```powershell
Select-String -Path docs\simulation-input-guide-ko.md,docs\usage-guide-ko.md,README.ko.md -Pattern 'simulation-reality-clue-good-example|strategy-actor-simulation-example'
```

Expected:

```text
The guide files contain the new links.
```

- [ ] **Step 6: Commit Task 3**

Use a Korean markdown Lore commit message:

```powershell
git add docs/simulation-input-guide-ko.md docs/usage-guide-ko.md README.ko.md
git commit -m "시뮬레이션 입력 가이드에서 예시 문서를 연결한다"
```

---

### Task 4: Final Documentation Verification

**Files:**
- No new files expected unless verification finds a documentation issue.

- [ ] **Step 1: Check unfinished authoring markers**

Run:

```powershell
Select-String -Path docs\examples\*.md,docs\simulation-input-guide-ko.md,docs\usage-guide-ko.md,README.ko.md -Pattern '작성 필요|임시 문구|초안 문구' -CaseSensitive:$false
```

Expected:

```text
No matches.
```

- [ ] **Step 2: Check markdown whitespace**

Run:

```powershell
git diff --check HEAD~3..HEAD
```

Expected:

```text
No output.
```

- [ ] **Step 3: Check example files contain actor sections**

Run:

```powershell
Select-String -Path docs\examples\simulation-reality-clue-good-example.md,docs\examples\strategy-actor-simulation-example.md -Pattern '개인 투자자|퀀트 개발자|투자 커뮤니티|금융감독원|리스크 관리자'
```

Expected:

```text
Several matches across both example files.
```

- [ ] **Step 4: Check repository status**

Run:

```powershell
git status --short --branch
```

Expected:

```text
Current branch is main and no unstaged changes remain.
```

- [ ] **Step 5: Push after verification**

Run:

```powershell
git push origin main
```

Expected:

```text
main branch pushes successfully.
```

---

## Self-Review Checklist

- [ ] Spec requirement “two copy-ready example documents” maps to Task 1 and Task 2.
- [ ] Spec requirement “existing Korean guides link to examples” maps to Task 3.
- [ ] Spec requirement “no UI/backend changes” is respected by all tasks.
- [ ] Spec requirement “diagnose matched_entities=0 / non_actor_text” maps to Task 2 and Task 3.
- [ ] Verification is documentation-focused and includes link, section, marker, and whitespace checks.