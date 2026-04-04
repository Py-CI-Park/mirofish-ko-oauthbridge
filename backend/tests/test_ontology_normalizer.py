import contextlib
import importlib
import sys
import types
import unittest
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1] / "app"
SERVICES_DIR = APP_DIR / "services"
TARGET_MODULE = "backend.app.services.ontology_normalizer"
_SHIMMED_MODULES = ("backend.app", "backend.app.services", TARGET_MODULE)


@contextlib.contextmanager
def _temporary_package_shims():
    # Keep backend.app startup side effects out of this red-state scaffold while
    # still importing the future helper by its planned module path.
    previous_modules = {name: sys.modules.get(name) for name in _SHIMMED_MODULES}

    backend_app = types.ModuleType("backend.app")
    backend_app.__path__ = [str(APP_DIR)]
    sys.modules["backend.app"] = backend_app

    backend_services = types.ModuleType("backend.app.services")
    backend_services.__path__ = [str(SERVICES_DIR)]
    sys.modules["backend.app.services"] = backend_services

    sys.modules.pop(TARGET_MODULE, None)

    try:
        yield
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _load_normalizer():
    with _temporary_package_shims():
        try:
            module = importlib.import_module(TARGET_MODULE)
        except ModuleNotFoundError as exc:
            if exc.name != TARGET_MODULE:
                raise
            return None, exc

        try:
            return module.normalize_ontology_for_zep, None
        except AttributeError as exc:
            return None, exc


def _normalize(ontology):
    normalize_ontology_for_zep, import_error = _load_normalizer()
    if normalize_ontology_for_zep is None:
        raise AssertionError(
            "normalize_ontology_for_zep is unavailable: "
            f"{import_error!r}"
        )
    return normalize_ontology_for_zep(ontology)


class OntologyNormalizerTest(unittest.TestCase):
    def test_normalizes_entity_and_edge_names_for_zep(self):
        ontology = {
            "entity_types": [
                {
                    "name": "\uac1c\uc778 \ud22c\uc790\uc790",
                    "attributes": [],
                    "examples": [],
                },
                {
                    "name": "\uae30\uad00 \ud22c\uc790\uc790",
                    "attributes": [],
                    "examples": [],
                },
            ],
            "edge_types": [
                {
                    "name": "\uc815\ubcf4 \uacf5\uc720",
                    "attributes": [],
                    "source_targets": [
                        {
                            "source": "\uac1c\uc778 \ud22c\uc790\uc790",
                            "target": "\uae30\uad00 \ud22c\uc790\uc790",
                        }
                    ],
                }
            ],
        }

        normalized = _normalize(ontology)

        self.assertEqual(normalized["entity_types"][0]["name"], "Entity1")
        self.assertEqual(normalized["entity_types"][1]["name"], "Entity2")
        self.assertEqual(normalized["edge_types"][0]["name"], "RELATION")
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

        normalized = _normalize(ontology)

        self.assertEqual(normalized["entity_types"][0]["name"], "Investor")
        self.assertEqual(normalized["entity_types"][1]["name"], "Investor2")

    def test_keeps_entity_names_globally_unique_across_base_collisions(self):
        ontology = {
            "entity_types": [
                {"name": "Investor", "attributes": [], "examples": []},
                {"name": "Investor", "attributes": [], "examples": []},
                {"name": "Investor2", "attributes": [], "examples": []},
            ],
            "edge_types": [],
        }

        normalized = _normalize(ontology)

        self.assertEqual(
            [entity["name"] for entity in normalized["entity_types"]],
            ["Investor", "Investor3", "Investor2"],
        )

    def test_keeps_edge_names_globally_unique_across_base_collisions(self):
        ontology = {
            "entity_types": [{"name": "Investor", "attributes": [], "examples": []}],
            "edge_types": [
                {"name": "related to", "attributes": [], "source_targets": []},
                {"name": "related to", "attributes": [], "source_targets": []},
                {"name": "RELATED_TO_2", "attributes": [], "source_targets": []},
            ],
        }

        normalized = _normalize(ontology)

        self.assertEqual(
            [edge["name"] for edge in normalized["edge_types"]],
            ["RELATED_TO", "RELATED_TO_A", "RELATED_TO_B"],
        )

    def test_edge_names_strip_digits_and_use_letter_only_suffixes(self):
        ontology = {
            "entity_types": [{"name": "Investor", "attributes": [], "examples": []}],
            "edge_types": [
                {"name": "connected 2 investor", "attributes": [], "source_targets": []},
                {"name": "connected investor", "attributes": [], "source_targets": []},
                {"name": "123", "attributes": [], "source_targets": []},
                {"name": None, "attributes": [], "source_targets": []},
            ],
        }

        normalized = _normalize(ontology)

        self.assertEqual(
            [edge["name"] for edge in normalized["edge_types"]],
            ["CONNECTED_INVESTOR", "CONNECTED_INVESTOR_A", "RELATION", "RELATION_A"],
        )
        for edge in normalized["edge_types"]:
            self.assertRegex(edge["name"], r"^[A-Z_]+$")

    def test_raises_when_duplicate_entity_reference_is_ambiguous(self):
        ontology = {
            "entity_types": [
                {"name": "Investor", "attributes": [], "examples": []},
                {"name": "Investor", "attributes": [], "examples": []},
            ],
            "edge_types": [
                {
                    "name": "backs",
                    "attributes": [],
                    "source_targets": [{"source": "Investor", "target": "Investor"}],
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "Ambiguous ontology entity reference"):
            _normalize(ontology)

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
            _normalize(ontology)

    def test_raises_when_source_targets_is_not_a_list(self):
        ontology = {
            "entity_types": [{"name": "Investor", "attributes": [], "examples": []}],
            "edge_types": [
                {
                    "name": "RELATES TO",
                    "attributes": [],
                    "source_targets": {"source": "Investor", "target": "Investor"},
                }
            ],
        }

        with self.assertRaisesRegex(ValueError, "source_targets must be a list"):
            _normalize(ontology)


if __name__ == "__main__":
    unittest.main()
