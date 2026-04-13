"""Compare localized oasis persona prompt behavior.

The script is intentionally small and sample-based. By default it compares
prompt text only. Use ``--run-llm`` to run one live LLM comparison for the same
entity input.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from typing import Any

from app.services.oasis_profile_generator import OasisProfileGenerator


HAN_RE = re.compile(r"[\u4e00-\u9fff]")
DEFAULT_PAIRS = [("legacy", "ko"), ("ko", "ko"), ("en", "ko"), ("en", "en")]
PROMPT_LANGUAGES = {"legacy", "ko", "en"}
OUTPUT_LANGUAGES = {"ko", "en"}


def _han_count(value: Any) -> int:
    return len(HAN_RE.findall(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value))


def _label(prompt_language: str, output_language: str) -> str:
    return f"{prompt_language}->{output_language}"


def _make_generator(prompt_language: str, output_language: str) -> OasisProfileGenerator:
    return OasisProfileGenerator(
        persona_prompt_language=prompt_language,
        persona_output_language=output_language,
    )


def _build_prompt(generator: OasisProfileGenerator, entity_type: str) -> str:
    if entity_type == "organization":
        return generator._build_group_persona_prompt(
            entity_name="테스트 기관",
            entity_type="조직",
            entity_summary="시장 이슈에 공식 입장을 내는 기관 계정",
            entity_attributes={},
            context="",
        )

    return generator._build_individual_persona_prompt(
        entity_name="개인 투자자",
        entity_type="개인",
        entity_summary="시장 이슈에 민감하게 반응하고 커뮤니티에서 의견을 나누는 개인 투자자",
        entity_attributes={},
        context="",
    )


def _run_llm(generator: OasisProfileGenerator, entity_type: str) -> dict[str, Any]:
    if entity_type == "organization":
        return generator._generate_profile_with_llm(
            entity_name="테스트 기관",
            entity_type="조직",
            entity_summary="시장 이슈에 공식 입장을 내는 기관 계정",
            entity_attributes={},
            context="",
        )

    return generator._generate_profile_with_llm(
        entity_name="개인 투자자",
        entity_type="개인",
        entity_summary="시장 이슈에 민감하게 반응하고 커뮤니티에서 의견을 나누는 개인 투자자",
        entity_attributes={},
        context="",
    )


def _print_prompt_summary(prompt_language: str, output_language: str, prompt: str) -> None:
    label = _label(prompt_language, output_language)
    required_fields = ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if field not in prompt]
    print(f"[prompt:{label}] length={len(prompt)} han_count={_han_count(prompt)} missing_fields={missing_fields}")
    print(f"[prompt:{label}] contains_legacy_empty={'无' in prompt or '无额外上下文' in prompt}")
    print(f"[prompt:{label}] contains_korean_empty={'없음' in prompt or '추가 컨텍스트 없음' in prompt}")
    print(f"[prompt:{label}] contains_english_empty={'None' in prompt or 'No additional context' in prompt}")


def _print_llm_summary(prompt_language: str, output_language: str, started_at: float, result: dict[str, Any]) -> None:
    label = _label(prompt_language, output_language)
    elapsed = time.time() - started_at
    required_fields = ["bio", "persona", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if not result.get(field)]
    print(f"[llm:{label}] elapsed={elapsed:.1f}s han_count={_han_count(result)} missing_fields={missing_fields}")
    print(f"[llm:{label}] keys={sorted(result.keys())}")
    print(f"[llm:{label}] bio={str(result.get('bio', ''))[:180]}")
    print(f"[llm:{label}] persona={str(result.get('persona', ''))[:240]}")


def _parse_pair(raw_pair: str) -> tuple[str, str]:
    if raw_pair.count(":") != 1:
        raise SystemExit(f"Invalid --pair value {raw_pair!r}: expected prompt:output")

    prompt_language, output_language = (part.strip().lower() for part in raw_pair.split(":", 1))
    if prompt_language not in PROMPT_LANGUAGES:
        supported = ", ".join(sorted(PROMPT_LANGUAGES))
        raise SystemExit(
            f"Invalid --pair value {raw_pair!r}: unsupported prompt language {prompt_language!r}; "
            f"expected one of: {supported}"
        )
    if output_language not in OUTPUT_LANGUAGES:
        supported = ", ".join(sorted(OUTPUT_LANGUAGES))
        raise SystemExit(
            f"Invalid --pair value {raw_pair!r}: unsupported output language {output_language!r}; "
            f"expected one of: {supported}"
        )

    return prompt_language, output_language


def _parse_pairs(raw_pairs: list[str] | None) -> list[tuple[str, str]]:
    if raw_pairs is None:
        return DEFAULT_PAIRS
    return [_parse_pair(raw_pair) for raw_pair in raw_pairs]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity-type", choices=["individual", "organization"], default="individual")
    parser.add_argument("--run-llm", action="store_true")
    parser.add_argument(
        "--pair",
        action="append",
        default=None,
        help="Prompt/output language pair in prompt:output form. May be repeated. Default: legacy:ko, ko:ko, en:ko, en:en",
    )
    args = parser.parse_args()

    for prompt_language, output_language in _parse_pairs(args.pair):
        generator = _make_generator(prompt_language, output_language)
        prompt = _build_prompt(generator, args.entity_type)
        _print_prompt_summary(prompt_language, output_language, prompt)

        if args.run_llm:
            started_at = time.time()
            result = _run_llm(generator, args.entity_type)
            _print_llm_summary(prompt_language, output_language, started_at, result)


if __name__ == "__main__":
    main()
