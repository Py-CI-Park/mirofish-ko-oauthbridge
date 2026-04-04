# Ontology Naming Runtime Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make graph builds pass Zep ontology validation so projects no longer fail around 15% progress.

**Architecture:** Add a deterministic ontology normalization/validation layer in the backend before Zep `set_ontology()` is called. Keep generated ontology input as-is for now, but transform runtime names into Zep-safe identifiers, validate references, and clean up partially created graphs on ontology-apply failure.

**Tech Stack:** Python 3.11/3.12, Flask backend, unittest, existing Zep SDK integration.

---

## File Structure

- Create: `backend/app/services/ontology_normalizer.py`
  - Single-purpose runtime helper for converting ontology names into Zep-safe identifiers.
- Modify: `backend/app/services/graph_builder.py`
  - Use the normalizer before `set_ontology()`, improve failure reporting, and attempt graph cleanup on ontology-apply failure.
- Create: `backend/tests/test_ontology_normalizer.py`
  - Unit coverage for normalization, deduplication, and source/target remapping.
- Test existing: `backend/tests/test_config_env_precedence.py`
  - Ensure backend env precedence regression still passes.
- Test existing: `codex-bridge/providers/codex.test.js`, `scripts/windows-launcher.test.mjs`
  - Ensure recent Windows runtime fixes remain green.

---

### Task 1: Add failing normalization tests

**Files:**
- Create: `backend/tests/test_ontology_normalizer.py`
- Test: `backend/tests/test_ontology_normalizer.py`

- [ ] **Step 1: Write the failing tests**

```python
import unittest

from backend.app.services.ontology_normalizer import normalize_ontology_for_zep


class OntologyNormalizerTest(unittest.TestCase):
    def test_normalizes_entity_and_edge_names_for_zep(self):
        ontology = {
            "entity_types": [
                {"name": "개인 투자자", "attributes": [], "examples": []},
                {"name": "기관 투자자", "attributes": [], "examples": []},
            ],
            "edge_types": [
                {
                    "name": "정보 공유",
                    "attributes": [],
                    "source_targets": [
                        {"source": "개인 투자자", "target": "기관 투자자"}
                    ],
                }
            ],
        }

        normalized = normalize_ontology_for_zep(ontology)

        self.assertEqual(normalized["entity_types"][0]["name"], "Entity1")
        self.assertEqual(normalized["entity_types"][1]["name"], "Entity2")
        self.assertEqual(normalized["edge_types"][0]["name"], "RELATION_1")
        self.assertEqual(
            normalized["edge_types"][0]["source_targets"],
            [{"source": "Entity1", "target": "Entity2"}],
        )

    def test_disambiguates_duplicate_names(self):
        ontology = {
            "entity_types": [
                {"name": "Investor", "attributes": [], "examples": []},
                {"name": "Investor", "attributes": [], "examples": []},
            ],
            "edge_types": [],
        }

        normalized = normalize_ontology_for_zep(ontology)

        self.assertEqual(normalized["entity_types"][0]["name"], "Investor")
        self.assertEqual(normalized["entity_types"][1]["name"], "Investor2")

    def test_raises_when_source_target_references_unknown_entity(self):
        ontology = {
            "entity_types": [{"name": "Investor", "attributes": [], "examples": []}],
            "edge_types": [
                {
                    "name": "RELATES TO",
                    "attributes": [],
                    "source_targets": [{"source": "Missing", "target": "Investor"}],
                }
            ],
        }

        with self.assertRaises(ValueError):
            normalize_ontology_for_zep(ontology)
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```bash
uv run python -m unittest backend.tests.test_ontology_normalizer
```

Expected: FAIL with `ModuleNotFoundError` or missing `normalize_ontology_for_zep`.

- [ ] **Step 3: Commit test scaffold only if desired**

```bash
git add backend/tests/test_ontology_normalizer.py
git commit -m "Add failing tests for Zep ontology normalization"
```

---

### Task 2: Implement ontology normalizer

**Files:**
- Create: `backend/app/services/ontology_normalizer.py`
- Test: `backend/tests/test_ontology_normalizer.py`

- [ ] **Step 1: Write minimal implementation**

```python
import re
from copy import deepcopy


ENTITY_FALLBACK_PREFIX = "Entity"
EDGE_FALLBACK_PREFIX = "RELATION"


_pascal_cleanup = re.compile(r"[^A-Za-z0-9]+")
_upper_cleanup = re.compile(r"[^A-Za-z0-9]+")


def _dedupe(name: str, used: set[str]) -> str:
    candidate = name
    index = 2
    while candidate in used:
        candidate = f"{name}{index}"
        index += 1
    used.add(candidate)
    return candidate


def _dedupe_edge(name: str, used: set[str]) -> str:
    candidate = name
    index = 2
    while candidate in used:
        candidate = f"{name}_{index}"
        index += 1
    used.add(candidate)
    return candidate


def _to_pascal_case(raw: str, fallback_index: int) -> str:
    cleaned = _pascal_cleanup.sub(" ", raw or "").strip()
    parts = [part for part in cleaned.split() if part]
    ascii_parts = [part for part in parts if part.isascii()]
    if ascii_parts:
        base = "".join(part[:1].upper() + part[1:] for part in ascii_parts)
        base = re.sub(r"[^A-Za-z0-9]", "", base)
        if base and base[0].isdigit():
            base = f"{ENTITY_FALLBACK_PREFIX}{base}"
        if base:
            return base
    return f"{ENTITY_FALLBACK_PREFIX}{fallback_index}"


def _to_screaming_snake(raw: str, fallback_index: int) -> str:
    cleaned = _upper_cleanup.sub("_", raw or "").strip("_")
    parts = [part.upper() for part in cleaned.split("_") if part and part.isascii()]
    if parts:
        base = "_".join(parts)
        if base and base[0].isdigit():
            base = f"{EDGE_FALLBACK_PREFIX}_{base}"
        return base
    return f"{EDGE_FALLBACK_PREFIX}_{fallback_index}"


def normalize_ontology_for_zep(ontology: dict) -> dict:
    normalized = deepcopy(ontology or {})
    entity_defs = normalized.get("entity_types", [])
    edge_defs = normalized.get("edge_types", [])

    used_entities = set()
    entity_name_map = {}

    for idx, entity_def in enumerate(entity_defs, start=1):
        original_name = entity_def.get("name", "")
        candidate = _to_pascal_case(original_name, idx)
        final_name = _dedupe(candidate, used_entities)
        entity_name_map[original_name] = final_name
        entity_def["name"] = final_name

    used_edges = set()
    for idx, edge_def in enumerate(edge_defs, start=1):
        edge_def["name"] = _dedupe_edge(_to_screaming_snake(edge_def.get("name", ""), idx), used_edges)
        remapped = []
        for pair in edge_def.get("source_targets", []):
            source_original = pair.get("source", "")
            target_original = pair.get("target", "")
            if source_original not in entity_name_map or target_original not in entity_name_map:
                raise ValueError(f"Unknown source/target reference: {source_original} -> {target_original}")
            remapped.append({
                "source": entity_name_map[source_original],
                "target": entity_name_map[target_original],
            })
        edge_def["source_targets"] = remapped

    return normalized
```

- [ ] **Step 2: Run test to verify it passes**

Run:
```bash
uv run python -m unittest backend.tests.test_ontology_normalizer
```

Expected: PASS.

- [ ] **Step 3: Refactor only if needed**

Keep the module focused on deterministic normalization and validation. Do not add UI-oriented fields or prompt changes in this task.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ontology_normalizer.py backend/tests/test_ontology_normalizer.py
git commit -m "Normalize ontology names before Zep graph build"
```

---

### Task 3: Wire normalizer into graph build and clean up failed graphs

**Files:**
- Modify: `backend/app/services/graph_builder.py`
- Test: `backend/tests/test_ontology_normalizer.py`

- [ ] **Step 1: Add the import and normalize before `set_ontology` model construction**

Apply this edit near the imports and at the start of `set_ontology`:

```python
from .ontology_normalizer import normalize_ontology_for_zep
```

```python
def set_ontology(self, graph_id: str, ontology: Dict[str, Any]):
    import warnings
    from typing import Optional
    from pydantic import Field
    from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel

    normalized_ontology = normalize_ontology_for_zep(ontology)
```

Then replace downstream loops to iterate over `normalized_ontology` instead of `ontology`:

```python
for entity_def in normalized_ontology.get("entity_types", []):
    ...

for edge_def in normalized_ontology.get("edge_types", []):
    ...
```

- [ ] **Step 2: Add failure cleanup in the build worker**

Replace the exception block in `_build_graph_worker` with this shape:

```python
        except Exception as e:
            import traceback
            error_msg = f"{str(e)}\n{traceback.format_exc()}"

            if 'graph_id' in locals() and graph_id:
                try:
                    self.delete_graph(graph_id)
                except Exception:
                    pass

            self.task_manager.fail_task(task_id, error_msg)
```

And in the API-layer worker (`backend/app/api/graph.py`) inside `build_task`, wrap `builder.set_ontology(graph_id, ontology)` failures with clearer logging:

```python
                try:
                    builder.set_ontology(graph_id, ontology)
                except Exception as ontology_error:
                    build_logger.error(f"[{task_id}] Ontology validation/apply failed: {ontology_error}")
                    try:
                        builder.delete_graph(graph_id)
                    except Exception as cleanup_error:
                        build_logger.warning(f"[{task_id}] Failed to cleanup graph shell {graph_id}: {cleanup_error}")
                    raise
```

- [ ] **Step 3: Run targeted tests**

Run:
```bash
uv run python -m unittest backend.tests.test_ontology_normalizer backend.tests.test_config_env_precedence
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/graph_builder.py backend/app/api/graph.py backend/tests/test_ontology_normalizer.py
git commit -m "Apply normalized ontology names during graph builds"
```

---

### Task 4: Regression verification for runtime paths

**Files:**
- Test: `codex-bridge/providers/codex.test.js`
- Test: `scripts/windows-launcher.test.mjs`

- [ ] **Step 1: Re-run existing Node regressions**

Run:
```bash
node --test codex-bridge/providers/codex.test.js scripts/windows-launcher.test.mjs
```

Expected: PASS.

- [ ] **Step 2: Smoke-check backend startup logic still uses runtime env overrides**

Run:
```bash
uv run python -m unittest backend.tests.test_config_env_precedence
```

Expected: PASS.

- [ ] **Step 3: Commit only if new changes were needed**

```bash
git add .
git commit -m "Keep runtime regressions green after ontology normalization"
```

---

### Task 5: Manual end-to-end verification of the original failure path

**Files:**
- Modify: none expected
- Verify: runtime only

- [ ] **Step 1: Start the stack with the known-good local launcher**

Run:
```bash
cmd /c run.bat
```

Expected: launcher starts frontend/backend/bridge on available ports.

- [ ] **Step 2: Verify service health on the selected ports**

Run (adjust ports to whatever `run.bat` prints):
```bash
node scripts/health-check.mjs
```

Expected: frontend/backend/bridge all OK.

- [ ] **Step 3: Reproduce ontology generation + graph build with the same input that previously stalled at 15%**

Expected:
- ontology generation still succeeds
- graph build progresses beyond ontology apply
- no Zep 400 naming-format error appears in backend log

- [ ] **Step 4: Capture evidence**

Save or note:
- backend log showing graph build progressed past 15%
- `/api/graph/task/<task_id>` eventually reaches completed
- `/api/graph/project/<project_id>` shows non-failed final status

- [ ] **Step 5: Final commit**

```bash
git add backend/app/services/ontology_normalizer.py backend/app/services/graph_builder.py backend/app/api/graph.py backend/tests/test_ontology_normalizer.py
git commit -m "Prevent Zep ontology naming failures during graph build"
```

---

## Self-Review

- Spec coverage: this plan covers deterministic normalization, validation, graph cleanup, and regression verification. It intentionally does not cover UI display-name work or prompt refactors.
- Placeholder scan: all code-touching steps include concrete file paths, commands, and code snippets.
- Type consistency: the plan consistently uses `normalize_ontology_for_zep(ontology)` as the runtime entry point and expects normalized `entity_types`/`edge_types` with remapped `source_targets`.
