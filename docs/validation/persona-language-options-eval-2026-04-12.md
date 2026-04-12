# Persona Language Options Evaluation - 2026-04-12

## Scope
- Branch: `fix/persona-prompt-korean-eval`
- Entity type: `individual`
- Validation target: `OasisProfileGenerator` persona prompt/output language options.
- Files changed for this task: this validation note only.
- Code changes were not made in Task 5.

## Language Pairs

| pair | persona prompt language | persona output language | validation intent |
|---|---|---|---|
| `legacy->ko` | `legacy` | `ko` | Preserve the legacy prompt text while requiring Korean output. |
| `ko->ko` | `ko` | `ko` | Use Korean prompt placeholders and require Korean output. |
| `en->ko` | `en` | `ko` | Use English prompt placeholders and require Korean output. |
| `en->en` | `en` | `en` | Use English prompt placeholders and require English output. |

## Offline Comparison Before Full Tests

Exact command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Result summary:
- Command exited with code `0`.
- All four language pairs included every required prompt field.
- `legacy->ko` retained legacy empty placeholders and was the only pair with Han characters in the prompt summary.
- `ko->ko` used Korean empty placeholders.
- `en->ko` and `en->en` used English empty placeholders.

Observed output:

```text
[prompt:legacy->ko] length=905 han_count=7 missing_fields=[]
[prompt:legacy->ko] contains_legacy_empty=True
[prompt:legacy->ko] contains_korean_empty=False
[prompt:legacy->ko] contains_english_empty=False
[prompt:ko->ko] length=910 han_count=0 missing_fields=[]
[prompt:ko->ko] contains_legacy_empty=False
[prompt:ko->ko] contains_korean_empty=True
[prompt:ko->ko] contains_english_empty=False
[prompt:en->ko] length=1460 han_count=0 missing_fields=[]
[prompt:en->ko] contains_legacy_empty=False
[prompt:en->ko] contains_korean_empty=False
[prompt:en->ko] contains_english_empty=True
[prompt:en->en] length=1461 han_count=0 missing_fields=[]
[prompt:en->en] contains_legacy_empty=False
[prompt:en->en] contains_korean_empty=False
[prompt:en->en] contains_english_empty=True
```

## Full Backend Tests

Exact command:

```powershell
cd backend
uv run pytest tests -q
```

Result:

```text
....................................                                     [100%]
36 passed in 15.71s
```

## Offline Comparison After Full Tests

Exact command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual
```

Result summary:
- Command exited with code `0`.
- The post-test offline comparison matched the pre-test prompt summary for all four language pairs.

Observed output:

```text
[prompt:legacy->ko] length=905 han_count=7 missing_fields=[]
[prompt:legacy->ko] contains_legacy_empty=True
[prompt:legacy->ko] contains_korean_empty=False
[prompt:legacy->ko] contains_english_empty=False
[prompt:ko->ko] length=910 han_count=0 missing_fields=[]
[prompt:ko->ko] contains_legacy_empty=False
[prompt:ko->ko] contains_korean_empty=True
[prompt:ko->ko] contains_english_empty=False
[prompt:en->ko] length=1460 han_count=0 missing_fields=[]
[prompt:en->ko] contains_legacy_empty=False
[prompt:en->ko] contains_korean_empty=False
[prompt:en->ko] contains_english_empty=True
[prompt:en->en] length=1461 han_count=0 missing_fields=[]
[prompt:en->en] contains_legacy_empty=False
[prompt:en->en] contains_korean_empty=False
[prompt:en->en] contains_english_empty=True
```

## Bridge Health Check

Exact command:

```powershell
Invoke-RestMethod http://127.0.0.1:8787/health
```

Result summary:
- Bridge was available.
- `ok=True`
- `busy=False`
- `provider=codex`
- `defaultModel=gpt-5.4-mini`
- `cliAvailable=True`
- `providerAvailable=True`
- `codexAvailable=True`
- `loginStatus=Logged in using ChatGPT`
- `queueDepth=0`
- `execTimeoutMs=120000`

## Live LLM Smoke Test

Exact command:

```powershell
cd backend
uv run python scripts/compare_oasis_persona_prompt_localization.py --entity-type individual --run-llm
```

Result summary:
- Command exited with code `0`.
- All four language pairs returned the expected persona keys: `age`, `bio`, `country`, `gender`, `interested_topics`, `mbti`, `persona`, `profession`.
- All live outputs had `missing_fields=[]`.
- `legacy->ko`, `ko->ko`, and `en->ko` returned Korean `bio` and `persona` text.
- `en->en` returned English `bio` and `persona` text.
- Live output Han count was `0` for every pair.

Observed output:

```text
[prompt:legacy->ko] length=905 han_count=7 missing_fields=[]
[prompt:legacy->ko] contains_legacy_empty=True
[prompt:legacy->ko] contains_korean_empty=False
[prompt:legacy->ko] contains_english_empty=False
[llm:legacy->ko] elapsed=15.3s han_count=0 missing_fields=[]
[llm:legacy->ko] keys=['age', 'bio', 'country', 'gender', 'interested_topics', 'mbti', 'persona', 'profession']
[llm:legacy->ko] bio=시장 뉴스와 수급 변화에 빠르게 반응하는 개인 투자자입니다. 혼자만의 판단보다 커뮤니티의 시각을 참고하되, 결국엔 스스로 근거를 확인하고 움직입니다. 단기 변동성도 놓치지 않지만 장기 투자 원칙은 끝까지 지키려는 편입니다.
[llm:legacy->ko] persona=38세의 개인 투자자로 서울과 수도권을 중심으로 활동하며, 대학에서 경영학을 전공한 뒤 제조업 영업과 온라인 유통 업무를 거치면서 실물 경기와 숫자 흐름을 함께 보는 습관을 길렀다. 현재는 본업을 병행하며 주식과 ETF를 중심으로 자산을 운용하고, 시장 이슈가 터지면 관련 종목과 거시 지표를 바로 확인한 뒤 커뮤니티에서 해석을 나누는 데 적극적이다. MBTI는 ENTP에 가깝고, 감정 표현은 직설적이지만 과열되기 전에 데이터를
[prompt:ko->ko] length=910 han_count=0 missing_fields=[]
[prompt:ko->ko] contains_legacy_empty=False
[prompt:ko->ko] contains_korean_empty=True
[prompt:ko->ko] contains_english_empty=False
[llm:ko->ko] elapsed=9.7s han_count=0 missing_fields=[]
[llm:ko->ko] keys=['age', 'bio', 'country', 'gender', 'interested_topics', 'mbti', 'persona', 'profession']
[llm:ko->ko] bio=시장 뉴스와 공시, 매크로 이슈를 빠르게 훑고 투자 판단에 반영하는 개인 투자자입니다. 숫자와 근거를 중시하지만, 커뮤니티에서 다른 사람들의 해석도 꼼꼼히 참고합니다.
[llm:ko->ko] persona=서울에 사는 30대 중반의 개인 투자자로, 대학에서 경영 관련 전공을 했고 직장 생활을 하며 모은 자금과 이후의 투자 경험을 바탕으로 주식과 ETF를 중심으로 포트폴리오를 운용한다. 사건과의 연결은 시장 이슈가 자신의 수익과 손실에 직접 영향을 주기 때문에 민감하게 반응하는 성향에서 비롯되며, 커뮤니티에서 비슷한 경험을 한 사람들의 의견을 비교하면서 상황을 해석한다. 성격은 INTJ에 가깝고 겉으로 감정을 과하게 드러내지 않지
[prompt:en->ko] length=1460 han_count=0 missing_fields=[]
[prompt:en->ko] contains_legacy_empty=False
[prompt:en->ko] contains_korean_empty=False
[prompt:en->ko] contains_english_empty=True
[llm:en->ko] elapsed=8.3s han_count=0 missing_fields=[]
[llm:en->ko] keys=['age', 'bio', 'country', 'gender', 'interested_topics', 'mbti', 'persona', 'profession']
[llm:en->ko] bio=시장 이슈와 수급 변화에 민감하게 반응하는 개인 투자자입니다. 커뮤니티에서 종목 의견과 뉴스 해석을 자주 나누며, 실전 경험을 바탕으로 빠르게 판단하는 편입니다.
[llm:en->ko] persona=30대 후반의 한국 거주 개인 투자자로, 중견 제조업이나 서비스업에서 직장 생활을 하며 틈틈이 주식과 ETF를 병행해 온 사람이다. 대학교 졸업 후 사회생활을 시작한 뒤 저축만으로는 자산을 늘리기 어렵다는 경험을 하면서 투자에 관심을 갖게 되었고, 특히 시장 이슈가 주가에 즉시 반영되는 순간을 여러 번 겪으며 뉴스와 커뮤니티 반응을 함께 확인하는 습관이 생겼다. 성향은 ENTP에 가까운 편으로 보이며, 새 정보에 대한 반응이 
[prompt:en->en] length=1461 han_count=0 missing_fields=[]
[prompt:en->en] contains_legacy_empty=False
[prompt:en->en] contains_korean_empty=False
[prompt:en->en] contains_english_empty=True
[llm:en->en] elapsed=9.4s han_count=0 missing_fields=[]
[llm:en->en] keys=['age', 'bio', 'country', 'gender', 'interested_topics', 'mbti', 'persona', 'profession']
[llm:en->en] bio=I am a retail investor who follows market headlines closely and shares quick reactions with online communities. I prefer practical discussion over hype and usually compare multiple
[llm:en->en] persona=He is a 34-year-old retail investor and office worker based in South Korea, with a business-related college background and several years of experience following domestic stocks, ETFs, and macro news after learning the hard way that timing a
```

## Interpretation
- The offline comparison confirms the prompt language switch changes the expected empty/context placeholder family without dropping required persona fields.
- The live smoke test confirms all four language/output combinations can return parseable persona objects with the expected keys.
- The `legacy->ko` prompt still contains legacy Han characters by design, while the `ko` and `en` prompt variants do not.
- This validation covers a single individual sample and does not establish broad persona quality parity across organizations, graph-backed context, or long-running simulations.

## Remaining Risks
- Organization/group entity prompts were not evaluated in this Task 5 run.
- Real graph actor context was not included in this sample.
- Live LLM outputs are non-deterministic and should be treated as smoke evidence, not statistical quality proof.
