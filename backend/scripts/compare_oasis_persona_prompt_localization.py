"""Compare legacy and Korean candidate oasis persona prompt behavior.

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


def _han_count(value: Any) -> int:
    return len(HAN_RE.findall(json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value))


def _make_generator(locale: str) -> OasisProfileGenerator:
    return OasisProfileGenerator(persona_prompt_locale=locale)


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


def _print_prompt_summary(locale: str, prompt: str) -> None:
    required_fields = ["bio", "persona", "age", "gender", "mbti", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if field not in prompt]
    print(f"[prompt:{locale}] length={len(prompt)} han_count={_han_count(prompt)} missing_fields={missing_fields}")
    print(f"[prompt:{locale}] contains_legacy_empty={'无' in prompt or '无额外上下文' in prompt}")
    print(f"[prompt:{locale}] contains_korean_empty={'없음' in prompt or '추가 컨텍스트 없음' in prompt}")


def _print_llm_summary(locale: str, started_at: float, result: dict[str, Any]) -> None:
    elapsed = time.time() - started_at
    required_fields = ["bio", "persona", "country", "profession", "interested_topics"]
    missing_fields = [field for field in required_fields if not result.get(field)]
    print(f"[llm:{locale}] elapsed={elapsed:.1f}s han_count={_han_count(result)} missing_fields={missing_fields}")
    print(f"[llm:{locale}] keys={sorted(result.keys())}")
    print(f"[llm:{locale}] bio={str(result.get('bio', ''))[:180]}")
    print(f"[llm:{locale}] persona={str(result.get('persona', ''))[:240]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entity-type", choices=["individual", "organization"], default="individual")
    parser.add_argument("--run-llm", action="store_true")
    args = parser.parse_args()

    for locale in ["legacy", "ko"]:
        generator = _make_generator(locale)
        prompt = _build_prompt(generator, args.entity_type)
        _print_prompt_summary(locale, prompt)

        if args.run_llm:
            started_at = time.time()
            result = _run_llm(generator, args.entity_type)
            _print_llm_summary(locale, started_at, result)


if __name__ == "__main__":
    main()
