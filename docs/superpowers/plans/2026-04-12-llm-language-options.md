# LLM Language Options Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add backend-only LLM prompt/output language options for OASIS persona profile generation while preserving the current legacy default behavior.

**Architecture:** Extend `OasisProfileGenerator` with validated `persona_prompt_language` and `persona_output_language` fields, while keeping `persona_prompt_locale` as a compatibility alias. Prompt builders select language-specific framing and placeholders, then append explicit output-language instructions without changing JSON field names. Comparison scripts and validation docs prove legacy, Korean, and English prompt/output combinations before any UI exposure.

**Tech Stack:** Python 3, Flask backend config, OpenAI-compatible chat completions, pytest, existing `uv` workflow, markdown validation notes.

---

## Source Spec

- `docs/superpowers/specs/2026-04-12-llm-language-options-design.md`

## File Structure

- Modify: `backend/app/config.py`
  - Owns environment-backed defaults for `LLM_PROMPT_LANGUAGE` and `LLM_OUTPUT_LANGUAGE`.
- Modify: `backend/app/services/oasis_profile_generator.py`
  - Owns prompt language validation, output language validation, prompt text generation, and legacy alias compatibility.
- Modify: `backend/tests/test_oasis_profile_localization.py`
  - Owns regression coverage for default legacy behavior, Korean/English prompt candidates, output-language instruction, schema-key preservation, and invalid value handling.
- Modify: `backend/scripts/compare_oasis_persona_prompt_localization.py`
  - Owns offline and optional live LLM comparison across prompt/output language pairs.
- Create: `docs/validation/persona-language-options-eval-2026-04-12.md`
  - Owns documented comparison results and any live LLM evidence.

## Implementation Rules

- Do not change frontend settings UI in this plan.
- Do not rename JSON response keys.
- Do not remove `persona_prompt_locale`; keep it as a compatibility alias.
- Do not change default behavior away from `legacy -> ko`.
- Commit after each task using Korean markdown Lore commit messages.

---

### Task 1: Add Failing Tests for Language Options

**Files:**
- Modify: `backend/tests/test_oasis_profile_localization.py`

- [ ] **Step 1: Add tests for constructor defaults, alias precedence, invalid values, English prompt, and output-language instruction**

Append these tests to `backend/tests/test_oasis_profile_localization.py`:

```python
import pytest


def test_persona_language_defaults_preserve_legacy_prompt_and_korean_output():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.persona_prompt_language = "legacy"
    generator.persona_output_language = "ko"

    prompt = generator._build_individual_persona_prompt(
        entity_name="테스터",
        entity_type="개인",
        entity_summary="",
        entity_attributes={},
        context="",
    )

    assert generator.persona_prompt_language == "legacy"
    assert generator.persona_output_language == "ko"
    assert "엔터티 속성: 无" in prompt
    assert "문맥 정보:\n无额外上下文" in prompt
    assert "bio, persona, profession, interested_topics, country" in generator._get_system_prompt(True)
    for field_name in ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]:
        assert field_name in prompt


def test_persona_prompt_language_en_uses_english_prompt_without_renaming_json_fields():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.persona_prompt_language = "en"
    generator.persona_output_language = "en"

    prompt = generator._build_group_persona_prompt(
        entity_name="Test Institute",
        entity_type="organization",
        entity_summary="Official account explaining a public issue",
        entity_attributes={},
        context="",
    )

    assert "Create a detailed official account profile" in prompt
    assert "Entity attributes: None" in prompt
    assert "Context information:\nNo additional context" in prompt
    assert "Write string values in English" in prompt
    assert "중국어를 쓰지 마세요" not in prompt
    assert "无" not in prompt
    for field_name in ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]:
        assert field_name in prompt


def test_persona_output_language_ko_instruction_is_independent_from_english_prompt_language():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.persona_prompt_language = "en"
    generator.persona_output_language = "ko"

    prompt = generator._build_individual_persona_prompt(
        entity_name="Investor",
        entity_type="person",
        entity_summary="A retail investor reacting to market news",
        entity_attributes={},
        context="",
    )
    system_prompt = generator._get_system_prompt(True)

    assert "Create a detailed social media user persona" in prompt
    assert "Write string values in Korean" in prompt
    assert "bio, persona, profession, interested_topics, country must be written in Korean" in system_prompt
    for field_name in ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]:
        assert field_name in prompt


def test_persona_prompt_locale_alias_still_sets_prompt_language_for_compatibility():
    generator = OasisProfileGenerator.__new__(OasisProfileGenerator)
    generator.persona_prompt_language = "ko"
    generator.persona_prompt_locale = "ko"
    generator.persona_output_language = "ko"

    prompt = generator._build_group_persona_prompt(
        entity_name="테스트 기관",
        entity_type="조직",
        entity_summary="",
        entity_attributes={},
        context="",
    )

    assert "엔터티 속성: 없음" in prompt
    assert "문맥 정보:\n추가 컨텍스트 없음" in prompt


def test_invalid_persona_prompt_language_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported persona prompt language"):
        OasisProfileGenerator(
            api_key="test-key",
            base_url="http://127.0.0.1:8787/v1",
            model_name="gpt-5.4-mini",
            persona_prompt_language="fr",
        )


def test_invalid_persona_output_language_raises_clear_error():
    with pytest.raises(ValueError, match="Unsupported persona output language"):
        OasisProfileGenerator(
            api_key="test-key",
            base_url="http://127.0.0.1:8787/v1",
            model_name="gpt-5.4-mini",
            persona_output_language="zh",
        )
```

- [ ] **Step 2: Run the new tests and verify they fail for missing implementation**

Run:

```powershell
cd backend
uv run pytest tests/test_oasis_profile_localization.py -q
```

Expected before implementation:

```text
FAILED ... AttributeError or TypeError related to persona_prompt_language/persona_output_language
FAILED ... English prompt assertions not found
```

- [ ] **Step 3: Commit the failing tests**

Use a Korean markdown Lore commit message:

```powershell
git add backend/tests/test_oasis_profile_localization.py
git commit -m "LLM 언어 옵션의 기대 동작을 테스트로 고정한다"
```

---

### Task 2: Add Config Defaults and Language Validation Helpers

**Files:**
- Modify: `backend/app/config.py`
- Modify: `backend/app/services/oasis_profile_generator.py`
- Test: `backend/tests/test_oasis_profile_localization.py`

- [ ] **Step 1: Add config defaults**

In `backend/app/config.py`, below `LLM_MODEL_NAME`, add:

```python
    LLM_PROMPT_LANGUAGE = os.environ.get('LLM_PROMPT_LANGUAGE', 'legacy')
    LLM_OUTPUT_LANGUAGE = os.environ.get('LLM_OUTPUT_LANGUAGE', 'ko')
```

- [ ] **Step 2: Add supported language constants and normalizers**

In `backend/app/services/oasis_profile_generator.py`, inside `class OasisProfileGenerator` near the existing class constants, add:

```python
    SUPPORTED_PERSONA_PROMPT_LANGUAGES = {"legacy", "ko", "en", "zh"}
    SUPPORTED_PERSONA_OUTPUT_LANGUAGES = {"ko", "en"}
```

Then add these methods near `_empty_prompt_value`:

```python
    def _normalize_persona_prompt_language(self, value: Optional[str]) -> str:
        language = (value or "legacy").strip().lower()
        if language not in self.SUPPORTED_PERSONA_PROMPT_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_PERSONA_PROMPT_LANGUAGES))
            raise ValueError(f"Unsupported persona prompt language: {value}. Supported values: {supported}")
        return language

    def _normalize_persona_output_language(self, value: Optional[str]) -> str:
        language = (value or "ko").strip().lower()
        if language not in self.SUPPORTED_PERSONA_OUTPUT_LANGUAGES:
            supported = ", ".join(sorted(self.SUPPORTED_PERSONA_OUTPUT_LANGUAGES))
            raise ValueError(f"Unsupported persona output language: {value}. Supported values: {supported}")
        return language
```

- [ ] **Step 3: Extend the constructor while preserving the existing alias**

Change the constructor signature from:

```python
        graph_id: Optional[str] = None,
        persona_prompt_locale: str = "legacy"
    ):
```

to:

```python
        graph_id: Optional[str] = None,
        persona_prompt_locale: Optional[str] = None,
        persona_prompt_language: Optional[str] = None,
        persona_output_language: Optional[str] = None,
    ):
```

Replace:

```python
        self.persona_prompt_locale = persona_prompt_locale
```

with:

```python
        configured_prompt_language = persona_prompt_language or persona_prompt_locale or Config.LLM_PROMPT_LANGUAGE
        self.persona_prompt_language = self._normalize_persona_prompt_language(configured_prompt_language)
        self.persona_prompt_locale = self.persona_prompt_language
        self.persona_output_language = self._normalize_persona_output_language(
            persona_output_language or Config.LLM_OUTPUT_LANGUAGE
        )
```

- [ ] **Step 4: Update empty value helpers to use prompt language**

Replace `_empty_prompt_value` and `_empty_context_value` with:

```python
    def _prompt_language(self) -> str:
        return getattr(self, "persona_prompt_language", getattr(self, "persona_prompt_locale", "legacy"))

    def _output_language(self) -> str:
        return getattr(self, "persona_output_language", "ko")

    def _empty_prompt_value(self) -> str:
        language = self._prompt_language()
        if language == "ko":
            return "없음"
        if language == "en":
            return "None"
        return "无"

    def _empty_context_value(self) -> str:
        language = self._prompt_language()
        if language == "ko":
            return "추가 컨텍스트 없음"
        if language == "en":
            return "No additional context"
        return "无额外上下文"
```

- [ ] **Step 5: Run targeted tests**

Run:

```powershell
cd backend
uv run pytest tests/test_oasis_profile_localization.py -q
```

Expected after this task:

```text
Some tests still fail because English prompt templates and output-language instructions are not implemented yet.
```

- [ ] **Step 6: Commit config and validation helpers**

Use a Korean markdown Lore commit message:

```powershell
git add backend/app/config.py backend/app/services/oasis_profile_generator.py
git commit -m "LLM 언어 옵션의 설정값과 검증 경로를 추가한다"
```

---

### Task 3: Implement Prompt/Output Language Selection in OasisProfileGenerator

**Files:**
- Modify: `backend/app/services/oasis_profile_generator.py`
- Test: `backend/tests/test_oasis_profile_localization.py`

- [ ] **Step 1: Add output-language instruction helpers**

Add these methods above `_get_system_prompt`:

```python
    def _output_language_name(self) -> str:
        return "English" if self._output_language() == "en" else "Korean"

    def _output_language_instruction_ko(self) -> str:
        if self._output_language() == "en":
            return "bio, persona, profession, interested_topics, country 는 모두 영어로 작성하라."
        return "bio, persona, profession, interested_topics, country 는 모두 한국어로 작성하라."

    def _output_language_instruction_en(self) -> str:
        if self._output_language() == "en":
            return "Write string values in English."
        return "Write string values in Korean."
```

- [ ] **Step 2: Make system prompt output-language aware**

Replace `_get_system_prompt` with:

```python
    def _get_system_prompt(self, is_individual: bool) -> str:
        """시스템 프롬프트를 반환한다."""
        if self._prompt_language() == "en":
            output_language = self._output_language_name()
            return (
                "You are an expert persona generator for social media simulations. "
                "Create detailed, natural personas grounded in the supplied real-world context and article clues. "
                "Return only a valid JSON object and do not include unescaped line breaks inside string values. "
                f"bio, persona, profession, interested_topics, country must be written in {output_language}. "
                "Do not use Chinese. Only the gender field must use one of these English values: male, female, other."
            )

        return (
            "너는 소셜 미디어 시뮬레이션용 사용자 페르소나 생성 전문가다. "
            "현실 맥락과 기사 단서를 최대한 살려 상세하고 자연스러운 페르소나를 작성하라. "
            "반드시 유효한 JSON 객체만 반환하고, 문자열 값에는 이스케이프되지 않은 줄바꿈을 넣지 마라. "
            f"{self._output_language_instruction_ko()} "
            "중국어를 사용하지 마라. gender 필드만 male/female/other 중 하나의 영문 값으로 반환하라."
        )
```

- [ ] **Step 3: Add English individual prompt helper**

Add this method before `_build_individual_persona_prompt`:

```python
    def _build_individual_persona_prompt_en(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> str:
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_en()

        return f"""Create a detailed social media user persona from the entity below. Preserve the real-world context as much as possible. {output_instruction}

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Create a JSON object containing these fields:

1. bio: social media bio, 2-3 sentences
2. persona: one detailed continuous paragraph containing:
   - Basic information such as age range, profession, education or career, and activity region
   - Connection to the event or topic
   - Personality traits such as MBTI, emotional expression, and judgment habits
   - Social media behavior such as posting frequency, preferred content, and interaction style
   - Position on the topic and sensitive points
   - Memories or experiences explaining why this account reacts this way
3. age: integer age
4. gender: English value only - "male" or "female"
5. mbti: MBTI type
6. country: country or region name
7. profession: profession or role
8. interested_topics: array of topics

Important:
- Use only strings or numbers for field values and do not use null.
- Keep persona as one continuous paragraph.
- Do not use Chinese.
- The content must fit the entity information and context.
- age must be a valid integer, and gender must be "male" or "female".
"""
```

- [ ] **Step 4: Add English group prompt helper**

Add this method before `_build_group_persona_prompt`:

```python
    def _build_group_persona_prompt_en(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> str:
        attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else self._empty_prompt_value()
        context_str = context[:3000] if context else self._empty_context_value()
        output_instruction = self._output_language_instruction_en()

        return f"""Create a detailed official account profile for a group or institution entity below. Preserve the real-world context as much as possible. {output_instruction}

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Create a JSON object containing these fields:

1. bio: official account bio, 2-3 sentences
2. persona: one detailed continuous paragraph containing:
   - Basic institutional information such as character, background, and function
   - Account position and target audience
   - Speaking style and forbidden expressions
   - Posting pattern and active time windows
   - Position and response style for core issues
   - Existing reactions and memory related to this event
3. age: fixed value 30
4. gender: fixed value "other"
5. mbti: MBTI type describing account style
6. country: country or region name
7. profession: institutional or organizational role description
8. interested_topics: array of core topics

Important:
- Use only strings or numbers for field values and do not use null.
- Keep persona as one continuous paragraph.
- Do not use Chinese.
- age must be 30 and gender must be "other".
- The account voice must fit the organization role and status.
"""
```

- [ ] **Step 5: Route existing prompt builders to English helpers when selected**

At the start of `_build_individual_persona_prompt`, after the docstring, add:

```python
        if self._prompt_language() == "en":
            return self._build_individual_persona_prompt_en(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
```

At the start of `_build_group_persona_prompt`, after the docstring, add:

```python
        if self._prompt_language() == "en":
            return self._build_group_persona_prompt_en(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
```

- [ ] **Step 6: Make Korean prompt text use output-language instruction**

In both existing Korean prompt builders, change the opening sentence from:

```python
출력은 전부 한국어 중심으로 맞춰라.
```

to include the helper value:

```python
{self._output_language_instruction_ko()}
```

In the JSON field descriptions, keep field names unchanged. For `country`, `profession`, and `interested_topics`, remove hard-coded “한국어” wording only where it conflicts with `persona_output_language="en"`. Use neutral phrasing:

```text
6. country: 국가/지역명
7. profession: 직업/역할
8. interested_topics: 관심 주제 배열
```

For the important section, keep:

```text
- 중국어를 쓰지 마세요.
```

- [ ] **Step 7: Run targeted tests and verify pass**

Run:

```powershell
cd backend
uv run pytest tests/test_oasis_profile_localization.py -q
```

Expected:

```text
all tests in test_oasis_profile_localization.py pass
```

- [ ] **Step 8: Commit generator implementation**

Use a Korean markdown Lore commit message:

```powershell
git add backend/app/services/oasis_profile_generator.py backend/tests/test_oasis_profile_localization.py
git commit -m "OASIS 페르소나 프롬프트와 출력 언어를 분리한다"
```

---

### Task 4: Extend the Persona Prompt Comparison Script

**Files:**
- Modify: `backend/scripts/compare_oasis_persona_prompt_localization.py`
- Test: manual script execution

- [ ] **Step 1: Change generator factory to accept prompt and output languages**

Replace:

```python
def _make_generator(locale: str) -> OasisProfileGenerator:
    return OasisProfileGenerator(persona_prompt_locale=locale)
```

with:

```python
def _make_generator(prompt_language: str, output_language: str) -> OasisProfileGenerator:
    return OasisProfileGenerator(
        persona_prompt_language=prompt_language,
        persona_output_language=output_language,
    )
```

- [ ] **Step 2: Update summary labels**

Replace `_print_prompt_summary(locale: str, prompt: str)` with:

```python
def _label(prompt_language: str, output_language: str) -> str:
    return f"{prompt_language}->{output_language}"


def _print_prompt_summary(prompt_language: str, output_language: str, prompt: str) -> None:
    label = _label(prompt_language, output_language)
    required_fields = ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if field not in prompt]
    print(f"[prompt:{label}] length={len(prompt)} han_count={_han_count(prompt)} missing_fields={missing_fields}")
    print(f"[prompt:{label}] contains_legacy_empty={'无' in prompt or '无额外上下文' in prompt}")
    print(f"[prompt:{label}] contains_korean_empty={'없음' in prompt or '추가 컨텍스트 없음' in prompt}")
    print(f"[prompt:{label}] contains_english_empty={'None' in prompt or 'No additional context' in prompt}")
```

Replace `_print_llm_summary(locale: str, ...)` with:

```python
def _print_llm_summary(prompt_language: str, output_language: str, started_at: float, result: dict[str, Any]) -> None:
    label = _label(prompt_language, output_language)
    elapsed = time.time() - started_at
    required_fields = ["bio", "persona", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if not result.get(field)]
    print(f"[llm:{label}] elapsed={elapsed:.1f}s han_count={_han_count(result)} missing_fields={missing_fields}")
    print(f"[llm:{label}] keys={sorted(result.keys())}")
    print(f"[llm:{label}] bio={str(result.get('bio', ''))[:180]}")
    print(f"[llm:{label}] persona={str(result.get('persona', ''))[:240]}")
```

- [ ] **Step 3: Add CLI options for pairs**

In `main()`, after `--run-llm`, add:

```python
    parser.add_argument(
        "--pair",
        action="append",
        default=None,
        help="Prompt/output language pair in prompt:output form. May be repeated. Default: legacy:ko, ko:ko, en:ko, en:en",
    )
```

After parsing args, add:

```python
    pairs = args.pair or ["legacy:ko", "ko:ko", "en:ko", "en:en"]
    language_pairs: list[tuple[str, str]] = []
    for pair in pairs:
        if ":" not in pair:
            raise SystemExit(f"Invalid --pair value '{pair}'. Use prompt:output, for example en:ko")
        prompt_language, output_language = pair.split(":", 1)
        language_pairs.append((prompt_language.strip(), output_language.strip()))
```

Replace the loop:

```python
    for locale in ["legacy", "ko"]:
        generator = _make_generator(locale)
```

with:

```python
    for prompt_language, output_language in language_pairs:
        generator = _make_generator(prompt_language, output_language)
```

Update summary calls:

```python
        _print_prompt_summary(prompt_language, output_language, prompt)
```

and:

```python
            _print_llm_summary(prompt_language, output_language, started_at, result)
```

- [ ] **Step 4: Run offline comparison script**

Run:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Expected:

```text
[prompt:legacy->ko] ... missing_fields=[]
[prompt:ko->ko] ... missing_fields=[]
[prompt:en->ko] ... missing_fields=[]
[prompt:en->en] ... missing_fields=[]
```

- [ ] **Step 5: Commit comparison script changes**

Use a Korean markdown Lore commit message:

```powershell
git add backend/scripts/compare_oasis_persona_prompt_localization.py
git commit -m "페르소나 프롬프트 비교 스크립트에 언어 조합을 추가한다"
```

---

### Task 5: Add Validation Notes and Run Verification

**Files:**
- Create: `docs/validation/persona-language-options-eval-2026-04-12.md`
- Test: backend pytest, comparison script, optional live LLM, frontend build not required because no frontend files change

- [ ] **Step 1: Run offline comparison and capture the exact output**

Run:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual | Tee-Object ..\persona-language-options-offline.txt
```

Expected:

```text
Four lines are printed for `legacy->ko`, `ko->ko`, `en->ko`, and `en->en`; each line includes integer `length`, integer `han_count`, and `missing_fields=[]`.
```

Do not commit `persona-language-options-offline.txt`; it is a temporary capture file.

- [ ] **Step 2: Create validation note with captured offline results**

Create `docs/validation/persona-language-options-eval-2026-04-12.md`. Use this structure, but put the actual `[prompt:...]` lines captured in Step 1 inside the offline result block before committing:

````markdown
# Persona Language Options Evaluation - 2026-04-12

## Scope

This validation covers backend-only prompt/output language options for `OasisProfileGenerator`.

## Language Pairs

| Pair | Purpose |
| --- | --- |
| `legacy -> ko` | Preserve current default behavior |
| `ko -> ko` | Korean prompt candidate with Korean output |
| `en -> ko` | English prompt candidate with Korean output |
| `en -> en` | English prompt candidate with English output |

## Offline Prompt Comparison

Command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Result summary:\n\nAdd a fenced `text` block containing the exact `[prompt:...]` lines captured in Step 1.

## Live LLM Smoke Test

Command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual --run-llm
```

Result summary:

```text
Live LLM smoke test has not been attempted yet in this validation pass.
```

## Decision

- Default remains `legacy -> ko`.
- `en -> ko` is available for quality comparison without exposing UI controls.
- `en -> en` is available for English demos or overseas-user validation.
````

Before committing, ensure the offline result summary contains the real command output from Step 1. Verify the validation note contains concrete command output or a concrete bridge-unavailable reason, not instructional draft text. If live LLM is not available after Step 5, keep a concrete sentence such as `Live LLM smoke test was not run because codex-bridge returned connection refused at http://127.0.0.1:8787/health on 2026-04-12.`

- [ ] **Step 3: Run full backend tests**

Run:

```powershell
cd backend
uv run pytest tests -q
```

Expected:

```text
all backend tests pass
```

- [ ] **Step 4: Re-run offline comparison script after backend tests**

Run:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Expected:

```text
all four prompt language pairs print missing_fields=[]
```

- [ ] **Step 5: Run live LLM comparison if bridge health is available**

Check bridge:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
```

If healthy, run:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual --run-llm
```

Expected:

```text
all four llm language pairs print missing_fields=[] or document exact failures in the validation note
```

- [ ] **Step 6: Commit validation note**

Use a Korean markdown Lore commit message:

```powershell
git add docs/validation/persona-language-options-eval-2026-04-12.md
git commit -m "페르소나 언어 옵션 검증 결과를 문서화한다"
```

---
### Task 6: Final Branch Verification and Push

**Files:**
- No code changes expected unless verification finds a defect.

- [ ] **Step 1: Confirm working tree state**

Run:

```powershell
git status --short --branch
```

Expected:

```text
## fix/persona-prompt-korean-eval
```

with no unstaged or untracked implementation files except intentionally staged files during a commit step.

- [ ] **Step 2: Run backend verification one final time**

Run:

```powershell
cd backend
uv run pytest tests -q
```

Expected:

```text
all backend tests pass
```

- [ ] **Step 3: Run frontend build only if frontend files changed**

If `git diff --name-only HEAD~5..HEAD` includes `frontend/` or `dashboard/`, run:

```powershell
cd frontend
npm run build
```

Expected:

```text
build succeeds; the existing pendingUpload dynamic import warning is acceptable if unchanged
```

- [ ] **Step 4: Push branch**

Run:

```powershell
git push origin fix/persona-prompt-korean-eval
```

Expected:

```text
branch pushes successfully
```

- [ ] **Step 5: Update PR summary if PR #2 remains the target**

If PR #2 is still open, update its description or add a comment summarizing:

```markdown
## 추가 변경
- `LLM_PROMPT_LANGUAGE` / `LLM_OUTPUT_LANGUAGE` 백엔드 옵션을 추가했습니다.
- 기본값은 `legacy -> ko`로 유지했습니다.
- `en -> ko`, `en -> en` 비교 스크립트와 검증 문서를 추가했습니다.

## 검증
- `cd backend && uv run pytest tests -q`
- `cd backend && uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual`
- 가능한 경우 live LLM 비교 결과는 `docs/validation/persona-language-options-eval-2026-04-12.md`에 기록했습니다.
```

---

## Self-Review Checklist

- [ ] Spec requirement “backend-only first” maps to Tasks 2-5.
- [ ] Spec requirement “default stays legacy -> ko” maps to Tasks 1-3.
- [ ] Spec requirement “prompt language and output language are independent” maps to Tasks 1 and 3.
- [ ] Spec requirement “comparison script supports legacy -> ko, ko -> ko, en -> ko, en -> en” maps to Task 4.
- [ ] Spec requirement “document actual validation results” maps to Task 5.
- [ ] Spec exclusion “no frontend UI” is respected by all tasks.