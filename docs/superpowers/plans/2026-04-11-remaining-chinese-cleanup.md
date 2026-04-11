# Remaining Chinese Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 남은 중국어/중국어 source 의존을 사용자·운영자 노출 위험이 높은 순서로 정리하되, 기존 저장 데이터 호환성과 LLM 프롬프트 품질을 보존한다.

**Architecture:** 작업을 세 계층으로 분리한다. 첫째, backend scripts의 CLI/log/comment 문자열은 한국어화한다. 둘째, frontend/dashboard의 중국어 source mapping은 제거하지 않고 한국어 alias와 주석으로 호환성을 명확히 한다. 셋째, `oasis_profile_generator.py`의 프롬프트 민감층은 작은 실험 단위와 A/B 검증 스크립트로만 확장한다.

**Tech Stack:** Python, pytest, Vue/Vite, markdown docs, Git branches (`fix/windows-codex-bridge-runtime`, `fix/prompt-localization-eval`)

---

## Current Branch Context

- Stable cleanup branch: `fix/windows-codex-bridge-runtime`
- Experimental prompt-localization branch: `fix/prompt-localization-eval`
- Current experimental HEAD: `c3cead3`
- Already completed:
  - high-priority backend runtime messages
  - high-priority backend comments/docstrings
  - backend utils/models comments
  - graph builder / Zep memory updater logs/comments
  - minimal `oasis_profile_generator.py` Zep query/context heading experiment
  - live Zep old/new query comparison script

## File Structure

### Safe Runtime / Script Cleanup
- Modify: `backend/scripts/run_parallel_simulation.py`
  - CLI logs/comments/user-facing messages for parallel simulation runner
- Modify: `backend/scripts/run_twitter_simulation.py`
  - CLI logs/comments/user-facing messages for Twitter runner
- Modify: `backend/scripts/run_reddit_simulation.py`
  - CLI logs/comments/user-facing messages for Reddit runner
- Modify: `backend/scripts/action_logger.py`
  - action logging text/comments
- Modify: `backend/scripts/test_profile_format.py`
  - test helper output/comments

### Compatibility-Layer Cleanup
- Modify: `frontend/src/i18n/index.js`
  - preserve Chinese legacy source keys, add Korean aliases for new backend strings
- Modify: `dashboard/lib/dashboard-text.js`
  - preserve legacy replacements, document why Chinese source keys remain

### Prompt-Sensitive Experimental Cleanup
- Modify: `backend/app/services/oasis_profile_generator.py`
  - only small prompt-sensitive changes backed by tests/A-B scripts
- Test: `backend/tests/test_oasis_profile_localization.py`
- Modify: `backend/scripts/compare_zep_query_localization.py`
  - extend comparison output when needed
- Create: `docs/validation/prompt-localization-eval-2026-04-11.md`
  - record live comparison results and merge recommendation

---

### Task 1: backend scripts 사용자 노출 로그/주석 정리

**Files:**
- Modify: `backend/scripts/run_parallel_simulation.py`
- Modify: `backend/scripts/run_twitter_simulation.py`
- Modify: `backend/scripts/run_reddit_simulation.py`
- Modify: `backend/scripts/action_logger.py`
- Modify: `backend/scripts/test_profile_format.py`

- [ ] **Step 1: 잔여 중국어 라인 목록을 저장한다**

Run:

```powershell
@'
from pathlib import Path
import re
files = [
    'backend/scripts/run_parallel_simulation.py',
    'backend/scripts/run_twitter_simulation.py',
    'backend/scripts/run_reddit_simulation.py',
    'backend/scripts/action_logger.py',
    'backend/scripts/test_profile_format.py',
]
han = re.compile(r'[\u4e00-\u9fff]')
for file in files:
    print(f'--- {file} ---')
    for index, line in enumerate(Path(file).read_text(encoding='utf-8').splitlines(), start=1):
        if han.search(line):
            print(f'{index}: {line[:180]}')
'@ | python -
```

Expected: line-numbered Chinese comments/log strings for only the five script files.

- [ ] **Step 2: 기능 영향이 낮은 문자열만 번역한다**

Rules:
- Translate comments, docstrings, CLI print/log messages.
- Do not change CLI argument names.
- Do not change JSON field names.
- Do not change OASIS-required constants/actions.
- Preserve any sample data that is meant to be input content.

Examples:

```python
# Before
logger.info("开始并行模拟...")

# After
logger.info("병렬 시뮬레이션 시작...")
```

```python
# Before
# 读取配置文件

# After
# 설정 파일 읽기
```

- [ ] **Step 3: scripts 대상 중국어 잔여 확인**

Run the same scan from Step 1.

Expected:
- The five target script files should have no Chinese in comments/log strings.
- If Chinese remains in sample input text or compatibility strings, list them in the commit body as intentionally preserved.

- [ ] **Step 4: smoke syntax check**

Run:

```powershell
cd backend
uv run python -m py_compile scripts/run_parallel_simulation.py scripts/run_twitter_simulation.py scripts/run_reddit_simulation.py scripts/action_logger.py scripts/test_profile_format.py
```

Expected: command exits 0.

- [ ] **Step 5: backend regression tests**

Run:

```powershell
cd backend
uv run pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

Commit message:

```text
backend scripts의 중국어 로그와 주석을 한국어로 정리한다

## 배경
- backend scripts는 로컬 실행과 시뮬레이션 운영 중 콘솔에 직접 노출될 수 있다.
- 사용자/운영자 관점에서 중국어 로그가 남아 있으면 현재 한국어판 흐름과 충돌한다.

## 변경 내용
- 병렬/Twitter/Reddit 실행 스크립트의 안전한 로그와 주석을 한국어로 정리했다.
- action logger와 profile format 테스트 스크립트의 개발자 설명을 한국어로 정리했다.

## 검증
- py_compile 통과
- backend pytest 통과

Constraint: CLI 인자, JSON 필드, OASIS action 상수는 변경하지 않는다
Confidence: high
Scope-risk: narrow
Tested: py_compile; backend pytest
Not-tested: 실제 장시간 시뮬레이션 실행
```

---

### Task 2: i18n/dashboard 호환 레이어 정리 기준 명문화

**Files:**
- Modify: `frontend/src/i18n/index.js`
- Modify: `dashboard/lib/dashboard-text.js`
- Create: `docs/notes/chinese-compatibility-layer.md`

- [ ] **Step 1: 호환 레이어 문서 작성**

Create `docs/notes/chinese-compatibility-layer.md`:

```markdown
# 중국어 source 호환 레이어 메모

## 목적
- 기존 저장 로그/리포트/대시보드 데이터에는 중국어 source 문자열이 남아 있을 수 있다.
- `frontend/src/i18n/index.js`와 `dashboard/lib/dashboard-text.js`는 이 레거시 source를 한국어/영어 UI로 표시하기 위한 호환 레이어다.

## 원칙
1. 중국어 source key를 즉시 삭제하지 않는다.
2. 새 백엔드 한국어 로그에는 한국어 alias를 추가한다.
3. 제거하려면 저장 데이터 영향 확인 후 별도 PR에서 진행한다.

## 제거 가능 조건
- 새 로그 원천이 한국어로 완전히 전환됨
- 기존 저장 리포트에서 해당 source key가 더 이상 사용되지 않음
- dashboard rendering regression test 또는 수동 검증 완료
```

- [ ] **Step 2: frontend i18n 주석 보강**

Add a short comment near `runtimeExact` / `runtimeRules`:

```js
// 레거시 중국어 로그 source와 새 한국어 로그 source를 모두 지원하는 호환 레이어.
// 기존 저장 데이터가 중국어 source를 포함할 수 있으므로 source key를 바로 삭제하지 않는다.
```

- [ ] **Step 3: dashboard text 주석 보강**

Keep existing comment and ensure it states:

```js
// 레거시 중국어/혼합 문구를 현재 한국어 canonical 텍스트로 정규화한다.
// 기존 저장 데이터와 새 한국어 출력을 함께 허용하기 위해 source alias를 유지한다.
```

- [ ] **Step 4: frontend build**

Run:

```powershell
cd frontend
npm run build
```

Expected: build succeeds. Existing Vite chunk warning is acceptable if unchanged.

- [ ] **Step 5: Commit**

Commit message:

```text
중국어 source 호환 레이어의 유지 기준을 문서화한다

## 배경
- frontend i18n과 dashboard text layer에는 의도적으로 남겨야 하는 중국어 source key가 있다.
- 이를 단순 미정리 잔재로 오해하면 기존 저장 데이터 호환을 깨뜨릴 수 있다.

## 변경 내용
- 중국어 source 호환 레이어의 목적과 제거 조건을 문서화했다.
- i18n/dashboard 코드 주석으로 호환 원칙을 명시했다.

## 검증
- frontend build 성공

Constraint: 기존 저장 데이터 호환을 유지한다
Confidence: high
Scope-risk: narrow
Tested: frontend build
Not-tested: 과거 리포트 전체 렌더링 회귀
```

---

### Task 3: prompt-localization 실험 결과 문서화

**Files:**
- Create: `docs/validation/prompt-localization-eval-2026-04-11.md`
- Modify: `backend/scripts/compare_zep_query_localization.py` only if output needs small formatting improvement

- [ ] **Step 1: live comparison 재실행**

Run:

```powershell
cd backend
uv run python scripts/compare_zep_query_localization.py --graph-id mirofish_b50c6738678f40ac --entity STOCHSK --entity 체결강도 --entity 매수총잔량 --limit 10
```

Expected:
- old/new result counts remain non-zero
- overlap is recorded

- [ ] **Step 2: validation 문서 작성**

Create `docs/validation/prompt-localization-eval-2026-04-11.md`:

```markdown
# Prompt Localization Evaluation - 2026-04-11

## Branch
- `fix/prompt-localization-eval`

## Change under evaluation
- Zep search query changed from Chinese wording to Korean wording.
- Entity context headings changed to Korean.

## Live Zep comparison
| entity | old_edges | new_edges | edge_overlap | old_nodes | new_nodes | node_overlap |
|---|---:|---:|---:|---:|---:|---:|
| STOCHSK | 10 | 10 | 8 | 10 | 10 | 8 |
| 체결강도 | 10 | 10 | 8 | 10 | 10 | 8 |
| 매수총잔량 | 10 | 10 | 10 | 10 | 10 | 8 |

## Interpretation
- Korean query wording preserved result counts in this sample graph.
- Overlap remained high enough for a minimal query/header localization experiment.

## Recommendation
- Safe to review as a small experimental PR.
- Do not expand to full persona prompt localization until persona-output A/B is done.

## Not tested
- Full LLM persona generation quality comparison.
- Other graph domains beyond the sampled strategy graph.
```

- [ ] **Step 3: backend tests**

Run:

```powershell
cd backend
uv run pytest tests -q
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

Commit message:

```text
프롬프트 현지화 실험 결과를 문서화한다

## 배경
- Zep 검색 쿼리 한국어화는 검색 품질에 영향을 줄 수 있어 live 비교 결과를 기록해야 한다.

## 변경 내용
- prompt localization 실험 결과와 해석, 추천 병합 조건을 문서화했다.

## 검증
- Zep query comparison 재실행
- backend pytest 통과

Constraint: persona prompt 전체 현지화는 아직 검증 대상이 아니다
Confidence: medium
Scope-risk: narrow
Tested: live Zep comparison; backend pytest
Not-tested: persona output A/B
```

---

### Task 4: oasis_profile_generator 남은 비프롬프트 로그/주석 정리

**Files:**
- Modify: `backend/app/services/oasis_profile_generator.py`
- Test: `backend/tests/test_oasis_profile_localization.py`

- [ ] **Step 1: 안전 대상만 선별**

Translate only:
- comments
- docstrings
- logger messages
- print labels

Do not translate:
- `_get_system_prompt()` return body
- `_build_individual_persona_prompt()` return body
- `_build_group_persona_prompt()` return body
- any generated JSON field names
- gender mapping keys like `"男"`, `"女"`, `"机构"`, `"其他"` unless adding Korean aliases, not replacing them

- [ ] **Step 2: add/extend tests for context headings**

Extend `backend/tests/test_oasis_profile_localization.py`:

```python
def test_generated_profile_console_labels_are_korean(capsys):
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    profile = OasisAgentProfile(
        user_id=1,
        user_name="tester",
        name="테스터",
        bio="소개",
        persona="상세 페르소나",
        age=30,
        gender="other",
        mbti="ISTJ",
        country="대한민국",
        profession="테스트 계정",
        interested_topics=["테스트"],
    )

    generator._print_generated_profile("테스터", "개인", profile)
    output = capsys.readouterr().out

    assert "사용자명" in output
    assert "상세 페르소나" in output
    assert "年龄" not in output
    assert "用户名" not in output
```

- [ ] **Step 3: implement minimal Korean output labels**

Change `_print_generated_profile()` labels:

```python
f"[생성됨] {entity_name} ({entity_type})"
f"사용자명: {profile.user_name}"
f"【소개】"
f"【상세 페르소나】"
f"【기본 속성】"
f"나이: {profile.age} | 성별: {profile.gender} | MBTI: {profile.mbti}"
f"직업: {profile.profession} | 국가: {profile.country}"
f"관심 주제: {topics_str}"
```

- [ ] **Step 4: run tests**

Run:

```powershell
cd backend
uv run pytest tests/test_oasis_profile_localization.py -q
uv run pytest tests -q
```

Expected:
- localization tests pass
- full backend tests pass

- [ ] **Step 5: Commit**

Commit message:

```text
oasis profile 콘솔 출력과 안전 주석을 한국어로 정리한다

## 배경
- oasis profile 생성기는 아직 중국어 콘솔 출력과 안전한 주석이 남아 있다.
- 프롬프트 본문을 건드리지 않고, 사용자/운영자에게 보일 수 있는 출력부터 정리한다.

## 변경 내용
- profile 생성 콘솔 출력 라벨을 한국어로 정리했다.
- 비프롬프트 주석/로그 일부를 한국어로 정리했다.
- 출력 라벨 회귀 테스트를 추가했다.

## 검증
- oasis profile localization tests 통과
- backend pytest 통과

Constraint: 페르소나 생성 프롬프트 본문은 변경하지 않는다
Confidence: high
Scope-risk: narrow
Tested: unit tests; backend pytest
Not-tested: full persona generation A/B
```

---

## Self-Review

### Spec coverage
- scripts cleanup: Task 1
- compatibility layer policy: Task 2
- prompt-localization experiment documentation: Task 3
- remaining safe oasis profile output cleanup: Task 4

### Placeholder scan
- No TODO/TBD placeholders.
- Each task has exact files, commands, expected outcomes, and commit guidance.

### Type/name consistency
- Branch names:
  - stable: `fix/windows-codex-bridge-runtime`
  - experimental: `fix/prompt-localization-eval`
- Test file:
  - `backend/tests/test_oasis_profile_localization.py`
- Validation script:
  - `backend/scripts/compare_zep_query_localization.py`
- Validation doc:
  - `docs/validation/prompt-localization-eval-2026-04-11.md`

