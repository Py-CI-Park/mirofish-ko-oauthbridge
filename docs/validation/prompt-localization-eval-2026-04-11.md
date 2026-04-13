# Prompt Localization Evaluation - 2026-04-11

## Branch
- `fix/prompt-localization-eval`

## Change under evaluation
- Zep search query wording changed from Chinese to Korean.
- Entity context headings changed to Korean.

## Live Zep comparison

Command:

```powershell
cd backend
uv run python scripts/compare_zep_query_localization.py --graph-id mirofish_b50c6738678f40ac --entity STOCHSK --entity 체결강도 --entity 매수총잔량 --limit 10
```

| entity | old_edges | new_edges | edge_overlap | old_nodes | new_nodes | node_overlap |
|---|---:|---:|---:|---:|---:|---:|
| STOCHSK | 10 | 10 | 8 | 10 | 10 | 8 |
| 체결강도 | 10 | 10 | 8 | 10 | 10 | 8 |
| 매수총잔량 | 10 | 10 | 10 | 10 | 10 | 8 |

## Interpretation
- The Korean query wording preserved result counts in this sampled graph.
- Edge and node overlap stayed high enough to support a minimal prompt-localization change without obvious retrieval regression.
- The sample does not prove parity for all graph domains or all persona-generation paths, but it does show the localized wording remains usable for this target graph.

## Recommendation
- Proceed with the prompt-localization change as a small experimental update.
- Keep the scope limited to the evaluated search query and headings until broader persona-quality evidence is collected.

## Not tested
- Full persona generation quality comparison.
- Other graph domains beyond the sampled strategy graph.
