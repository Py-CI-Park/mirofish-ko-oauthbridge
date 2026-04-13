# Persona Prompt Korean Evaluation - 2026-04-12

## Branch
- `fix/persona-prompt-korean-eval`

## Change under evaluation
- `OasisProfileGenerator`에 `persona_prompt_locale` 옵션을 추가했다.
- 기본값은 `legacy`로 유지해 기존 동작을 보존한다.
- `persona_prompt_locale="ko"`일 때 빈 속성/컨텍스트 placeholder를 한국어로 사용한다.
  - legacy: `无`, `无额外上下文`
  - ko: `없음`, `추가 컨텍스트 없음`

## Static prompt comparison

Command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Result:

| locale | prompt_length | han_count | required_fields_missing | legacy_empty | korean_empty |
|---|---:|---:|---|---|---|
| legacy | 836 | 7 | none | yes | no |
| ko | 841 | 0 | none | no | yes |

## Live LLM comparison

Command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual --run-llm
```

Environment:
- local `codex-bridge`
- `CODEX_MODEL=gpt-5.4-mini`
- one individual sample entity: `개인 투자자`

Result summary:

| locale | elapsed | han_count | required_fields_missing | output_keys |
|---|---:|---:|---|---|
| legacy | 9.0s | 0 | none | age, bio, country, gender, interested_topics, mbti, persona, profession |
| ko | 9.5s | 0 | none | age, bio, country, gender, interested_topics, mbti, persona, profession |

## Output observations

### Legacy prompt output
- Korean output was produced despite legacy Chinese empty placeholders.
- Persona was detailed and coherent.
- No Chinese/Han characters remained in the parsed result.

### Korean prompt output
- Korean output was also produced.
- Persona was detailed and coherent.
- Required JSON fields were preserved.
- No Chinese/Han characters remained in the parsed result.

## Interpretation
- Replacing only empty placeholder text with Korean did not break JSON structure.
- Both legacy and Korean candidate prompts produced complete persona objects.
- In this small sample, the Korean placeholder variant showed no obvious quality regression.

## Recommendation
- The `persona_prompt_locale="ko"` candidate is safe to keep behind a feature flag.
- Do not make `ko` the default until at least one group/entity sample and one real graph actor sample are compared.
- Next experiment should compare:
  - one organization/group entity
  - one actor-like entity from a good social simulation graph

## Not tested
- Group/organization prompt output.
- Multiple domains beyond the single `개인 투자자` sample.
- Full Step2 end-to-end profile generation with many entities.
- Long-running simulation quality after using Korean prompt placeholders.
