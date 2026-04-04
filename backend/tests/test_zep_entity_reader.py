import contextlib
import importlib
import sys
import types
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"
SERVICES_DIR = APP_DIR / "services"
TARGET_MODULE = "backend.app.services.zep_entity_reader"
_SHIMMED_MODULES = (
    "backend",
    "backend.app",
    "backend.app.services",
    "zep_cloud",
    "zep_cloud.client",
    TARGET_MODULE,
)


@contextlib.contextmanager
def _temporary_package_shims():
    previous_modules = {name: sys.modules.get(name) for name in _SHIMMED_MODULES}

    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(BACKEND_DIR)]
    sys.modules["backend"] = backend_pkg

    backend_app = types.ModuleType("backend.app")
    backend_app.__path__ = [str(APP_DIR)]
    sys.modules["backend.app"] = backend_app

    backend_services = types.ModuleType("backend.app.services")
    backend_services.__path__ = [str(SERVICES_DIR)]
    sys.modules["backend.app.services"] = backend_services

    zep_cloud = types.ModuleType("zep_cloud")
    zep_cloud.__path__ = []
    zep_cloud.InternalServerError = RuntimeError
    sys.modules["zep_cloud"] = zep_cloud

    zep_cloud_client = types.ModuleType("zep_cloud.client")

    class _FakeZep:
        def __init__(self, *args, **kwargs):
            pass

    zep_cloud_client.Zep = _FakeZep
    sys.modules["zep_cloud.client"] = zep_cloud_client
    sys.modules.pop(TARGET_MODULE, None)

    try:
        yield
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


def _load_reader_module():
    with _temporary_package_shims():
        return importlib.import_module(TARGET_MODULE)


def _make_reader(module, nodes):
    reader = module.ZepEntityReader.__new__(module.ZepEntityReader)
    reader.get_all_nodes = lambda graph_id: nodes
    reader.get_all_edges = lambda graph_id: []
    return reader


class ZepEntityReaderFilteringTest(unittest.TestCase):
    def test_strict_mode_skips_unlabeled_nodes_and_reports_readiness(self):
        module = _load_reader_module()
        reader = _make_reader(
            module,
            nodes=[
                {
                    "uuid": "actor-1",
                    "name": "김민수",
                    "labels": ["Entity", "개인"],
                    "summary": "개인 투자자",
                    "attributes": {"role": "개인 투자자", "confidence": 0.9},
                },
                {
                    "uuid": "actor-2",
                    "name": "온체인 투자자 박지훈",
                    "labels": [],
                    "summary": "커뮤니티에서 활동하는 투자자",
                    "attributes": {"role": "투자자"},
                },
                {
                    "uuid": "metric-1",
                    "name": "RSI 지표",
                    "labels": [],
                    "summary": "ratio based signal",
                    "attributes": {"kind": "indicator"},
                },
            ],
        )

        filtered = reader.filter_defined_entities(
            graph_id="graph-1",
            enrich_with_edges=False,
        )

        self.assertEqual([entity.uuid for entity in filtered.entities], ["actor-1"])
        self.assertEqual(filtered.entities[0].name, "김민수")
        self.assertEqual(filtered.entities[0].labels, ["Entity", "개인"])
        self.assertEqual(
            filtered.entities[0].attributes,
            {"role": "개인 투자자", "confidence": 0.9},
        )
        self.assertNotIn("derived_entity_type", filtered.entities[0].attributes)
        self.assertEqual(filtered.readiness["match_mode"], "strict")
        self.assertEqual(filtered.readiness["total_nodes"], 3)
        self.assertEqual(filtered.readiness["matched_entities"], 1)
        self.assertEqual(filtered.readiness["labels_present_count"], 1)
        self.assertAlmostEqual(filtered.readiness["labels_present_ratio"], 1 / 3)
        self.assertEqual(filtered.readiness["relaxed_candidate_count"], 1)
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["entity_type_mismatch"],
            0,
        )
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["missing_actor_labels"],
            2,
        )
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["non_actor_text"],
            0,
        )

    def test_relaxed_mode_accepts_actor_like_nodes_and_derives_entity_type(self):
        module = _load_reader_module()
        reader = _make_reader(
            module,
            nodes=[
                {
                    "uuid": "actor-1",
                    "name": "개인 투자자 민수",
                    "labels": [],
                    "summary": "시장 분석을 공유하는 투자자",
                    "attributes": {"bio": "장기 투자자"},
                },
                {
                    "uuid": "metric-1",
                    "name": "RSI indicator",
                    "labels": [],
                    "summary": "signal ratio strategy",
                    "attributes": {"category": "지표"},
                },
            ],
        )

        filtered = reader.filter_defined_entities(
            graph_id="graph-1",
            enrich_with_edges=False,
            match_mode="relaxed",
        )

        self.assertEqual([entity.uuid for entity in filtered.entities], ["actor-1"])
        self.assertEqual(filtered.entities[0].attributes["derived_entity_type"], "개인")
        self.assertEqual(filtered.entity_types, {"개인"})
        self.assertEqual(filtered.readiness["match_mode"], "relaxed")
        self.assertEqual(filtered.readiness["matched_entities"], 1)
        self.assertEqual(filtered.readiness["labels_present_count"], 0)
        self.assertEqual(filtered.readiness["relaxed_candidate_count"], 1)
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["entity_type_mismatch"],
            0,
        )
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["missing_actor_labels"],
            0,
        )
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["non_actor_text"],
            1,
        )

    def test_relaxed_mode_keeps_actor_match_when_technical_terms_are_incidental(self):
        module = _load_reader_module()
        reader = _make_reader(
            module,
            nodes=[
                {
                    "uuid": "actor-1",
                    "name": "개인 투자자 민수",
                    "labels": [],
                    "summary": "RSI 지표 기반 전략을 쓰는 개인 투자자",
                    "attributes": {"bio": "커뮤니티 운영 경험"},
                },
            ],
        )

        filtered = reader.filter_defined_entities(
            graph_id="graph-1",
            enrich_with_edges=False,
            match_mode="relaxed",
        )

        self.assertEqual([entity.uuid for entity in filtered.entities], ["actor-1"])
        self.assertEqual(filtered.entities[0].attributes["derived_entity_type"], "개인")
        self.assertEqual(filtered.readiness["relaxed_candidate_count"], 1)
        self.assertEqual(
            filtered.readiness["rejection_reasons"]["non_actor_text"],
            0,
        )

    def test_relaxed_mode_prefers_organizational_signal_over_generic_investor_term(self):
        module = _load_reader_module()
        reader = _make_reader(
            module,
            nodes=[
                {
                    "uuid": "actor-1",
                    "name": "기관 투자자 A",
                    "labels": [],
                    "summary": "기관 투자자 A는 시장을 주도한다",
                    "attributes": {"role": "기관 투자자"},
                },
            ],
        )

        filtered = reader.filter_defined_entities(
            graph_id="graph-1",
            enrich_with_edges=False,
            match_mode="relaxed",
        )

        self.assertEqual([entity.uuid for entity in filtered.entities], ["actor-1"])
        self.assertEqual(filtered.entities[0].attributes["derived_entity_type"], "조직")
        self.assertEqual(filtered.entity_types, {"조직"})


if __name__ == "__main__":
    unittest.main()
