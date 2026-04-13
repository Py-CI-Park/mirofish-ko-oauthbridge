import contextlib
import importlib
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from flask import Blueprint, Flask


BACKEND_DIR = Path(__file__).resolve().parents[1]
APP_DIR = BACKEND_DIR / "app"
SERVICES_DIR = APP_DIR / "services"
API_DIR = APP_DIR / "api"
MODELS_DIR = APP_DIR / "models"
UTILS_DIR = APP_DIR / "utils"
SIM_MANAGER_MODULE = "backend.app.services.simulation_manager"
SIM_API_MODULE = "backend.app.api.simulation"
TASK_MODULE = "backend.app.models.task"
_SHIMMED_MODULES = (
    "backend",
    "backend.app",
    "backend.app.api",
    "backend.app.api.simulation",
    "backend.app.config",
    "backend.app.models",
    "backend.app.models.project",
    "backend.app.models.task",
    "backend.app.services",
    "backend.app.services.oasis_profile_generator",
    "backend.app.services.simulation_config_generator",
    "backend.app.services.simulation_manager",
    "backend.app.services.simulation_runner",
    "backend.app.services.zep_entity_reader",
    "backend.app.utils",
    "backend.app.utils.logger",
)


def _make_filtered_entities(filtered_count, readiness, entity_types=None, entities=None, total_count=0):
    return SimpleNamespace(
        entities=list(entities or []),
        entity_types=set(entity_types or []),
        total_count=total_count,
        filtered_count=filtered_count,
        readiness=dict(readiness),
    )


def _write_prepared_artifacts(base_dir: Path, simulation_id: str, state):
    sim_dir = base_dir / simulation_id
    sim_dir.mkdir(parents=True, exist_ok=True)
    (sim_dir / "state.json").write_text(
        json.dumps(state.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (sim_dir / "simulation_config.json").write_text(
        json.dumps({"agent_configs": [], "time_config": {}, "event_config": {}}),
        encoding="utf-8",
    )
    (sim_dir / "reddit_profiles.json").write_text(
        json.dumps([{"name": "agent-1"}]),
        encoding="utf-8",
    )
    (sim_dir / "twitter_profiles.csv").write_text(
        "name\nagent-1\n",
        encoding="utf-8",
    )


@contextlib.contextmanager
def _temporary_package_shims(temp_dir: Path):
    previous_modules = {name: sys.modules.get(name) for name in _SHIMMED_MODULES}

    backend_pkg = types.ModuleType("backend")
    backend_pkg.__path__ = [str(BACKEND_DIR)]
    sys.modules["backend"] = backend_pkg

    backend_app = types.ModuleType("backend.app")
    backend_app.__path__ = [str(APP_DIR)]
    sys.modules["backend.app"] = backend_app

    backend_api = types.ModuleType("backend.app.api")
    backend_api.__path__ = [str(API_DIR)]
    backend_api.graph_bp = Blueprint("graph", __name__)
    backend_api.simulation_bp = Blueprint("simulation", __name__)
    backend_api.report_bp = Blueprint("report", __name__)
    sys.modules["backend.app.api"] = backend_api

    backend_models = types.ModuleType("backend.app.models")
    backend_models.__path__ = [str(MODELS_DIR)]
    sys.modules["backend.app.models"] = backend_models

    backend_services = types.ModuleType("backend.app.services")
    backend_services.__path__ = [str(SERVICES_DIR)]
    sys.modules["backend.app.services"] = backend_services

    backend_utils = types.ModuleType("backend.app.utils")
    backend_utils.__path__ = [str(UTILS_DIR)]
    sys.modules["backend.app.utils"] = backend_utils

    config_module = types.ModuleType("backend.app.config")

    class Config:
        ZEP_API_KEY = "test-zep-key"
        OASIS_SIMULATION_DATA_DIR = str(temp_dir)

    config_module.Config = Config
    sys.modules["backend.app.config"] = config_module

    logger_module = types.ModuleType("backend.app.utils.logger")

    class _Logger:
        def debug(self, *args, **kwargs):
            pass

        def info(self, *args, **kwargs):
            pass

        def warning(self, *args, **kwargs):
            pass

        def error(self, *args, **kwargs):
            pass

    logger_module.get_logger = lambda name: _Logger()
    sys.modules["backend.app.utils.logger"] = logger_module

    zep_reader_module = types.ModuleType("backend.app.services.zep_entity_reader")

    class ZepEntityReader:
        preview_filtered = _make_filtered_entities(0, readiness={"match_mode": "strict"})
        prepared_filtered = _make_filtered_entities(0, readiness={"match_mode": "strict"})
        calls = []

        def __init__(self, *args, **kwargs):
            pass

        def filter_defined_entities(self, graph_id, defined_entity_types=None, enrich_with_edges=True, match_mode="strict"):
            self.__class__.calls.append(
                {
                    "graph_id": graph_id,
                    "defined_entity_types": list(defined_entity_types or []),
                    "enrich_with_edges": enrich_with_edges,
                    "match_mode": match_mode,
                }
            )
            filtered = self.__class__.prepared_filtered if enrich_with_edges else self.__class__.preview_filtered
            return _make_filtered_entities(
                filtered_count=filtered.filtered_count,
                readiness=filtered.readiness,
                entity_types=filtered.entity_types,
                entities=filtered.entities,
                total_count=filtered.total_count,
            )

    zep_reader_module.ZepEntityReader = ZepEntityReader
    zep_reader_module.FilteredEntities = SimpleNamespace
    sys.modules["backend.app.services.zep_entity_reader"] = zep_reader_module

    profile_module = types.ModuleType("backend.app.services.oasis_profile_generator")

    class OasisProfileGenerator:
        def __init__(self, *args, **kwargs):
            pass

        def generate_profiles_from_entities(self, *args, **kwargs):
            return []

        def save_profiles(self, *args, **kwargs):
            return None

    profile_module.OasisProfileGenerator = OasisProfileGenerator
    profile_module.OasisAgentProfile = SimpleNamespace
    sys.modules["backend.app.services.oasis_profile_generator"] = profile_module

    config_generator_module = types.ModuleType("backend.app.services.simulation_config_generator")

    class SimulationParameters:
        def __init__(self):
            self.generation_reasoning = "stub"

        def to_json(self):
            return json.dumps({"generated": True})

    class SimulationConfigGenerator:
        def generate_config(self, *args, **kwargs):
            return SimulationParameters()

    config_generator_module.SimulationConfigGenerator = SimulationConfigGenerator
    config_generator_module.SimulationParameters = SimulationParameters
    sys.modules["backend.app.services.simulation_config_generator"] = config_generator_module

    runner_module = types.ModuleType("backend.app.services.simulation_runner")

    class SimulationRunner:
        pass

    class RunnerStatus:
        pass

    runner_module.SimulationRunner = SimulationRunner
    runner_module.RunnerStatus = RunnerStatus
    sys.modules["backend.app.services.simulation_runner"] = runner_module

    project_module = types.ModuleType("backend.app.models.project")

    class ProjectManager:
        project = SimpleNamespace(simulation_requirement="Investigate failure handling")
        extracted_text = "document body"

        @classmethod
        def get_project(cls, project_id):
            return cls.project

        @classmethod
        def get_extracted_text(cls, project_id):
            return cls.extracted_text

    project_module.ProjectManager = ProjectManager
    sys.modules["backend.app.models.project"] = project_module

    sys.modules.pop(TASK_MODULE, None)
    sys.modules.pop(SIM_MANAGER_MODULE, None)
    sys.modules.pop(SIM_API_MODULE, None)

    try:
        yield
    finally:
        for name, previous in previous_modules.items():
            if previous is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = previous


@contextlib.contextmanager
def _loaded_test_environment():
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir = Path(temp_dir_name)
        with _temporary_package_shims(temp_dir):
            task_module = importlib.import_module(TASK_MODULE)
            task_module.TaskManager._instance = None
            sim_manager_module = importlib.import_module(SIM_MANAGER_MODULE)
            sim_manager_module.SimulationManager.SIMULATION_DATA_DIR = str(temp_dir)
            sim_api_module = importlib.import_module(SIM_API_MODULE)

            app = Flask(__name__)
            app.register_blueprint(sys.modules["backend.app.api"].simulation_bp, url_prefix="/api/simulation")

            yield SimpleNamespace(
                app=app,
                temp_dir=temp_dir,
                task_module=task_module,
                sim_manager_module=sim_manager_module,
                sim_api_module=sim_api_module,
                reader_class=sys.modules["backend.app.services.zep_entity_reader"].ZepEntityReader,
                project_manager=sys.modules["backend.app.models.project"].ProjectManager,
            )


class _ImmediateThread:
    def __init__(self, target=None, daemon=None, **kwargs):
        self._target = target
        self.daemon = daemon

    def start(self):
        if self._target:
            self._target()


class SimulationPrepareFailureStatusTest(unittest.TestCase):
    def test_prepare_failure_serializes_readiness_and_filter_mode(self):
        readiness = {
            "match_mode": "relaxed",
            "total_nodes": 4,
            "matched_entities": 0,
            "labels_present_count": 0,
            "labels_present_ratio": 0.0,
            "relaxed_candidate_count": 0,
            "rejection_reasons": {
                "entity_type_mismatch": 0,
                "missing_actor_labels": 4,
                "non_actor_text": 0,
            },
        }

        with _loaded_test_environment() as env:
            env.reader_class.calls = []
            env.reader_class.preview_filtered = _make_filtered_entities(
                filtered_count=0,
                readiness=readiness,
                entity_types=[],
                total_count=4,
            )
            env.reader_class.prepared_filtered = _make_filtered_entities(
                filtered_count=0,
                readiness=readiness,
                entity_types=[],
                total_count=4,
            )

            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-1", "graph-1")

            result_state = manager.prepare_simulation(
                simulation_id=created.simulation_id,
                simulation_requirement="Find social actors",
                document_text="context",
                entity_match_mode="relaxed",
            )

            self.assertEqual(result_state.status, env.sim_manager_module.SimulationStatus.FAILED)
            self.assertEqual(result_state.entity_filter_mode, "relaxed")
            self.assertEqual(result_state.entity_readiness, readiness)
            self.assertEqual(result_state.failure_stage, "prepare")
            self.assertEqual(result_state.failure_kind, "entity_matching")
            self.assertIn("No matching entities", result_state.error)

            state_file = env.temp_dir / created.simulation_id / "state.json"
            state_json = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertEqual(state_json["status"], "failed")
            self.assertEqual(state_json["entity_filter_mode"], "relaxed")
            self.assertEqual(state_json["entity_readiness"], readiness)
            self.assertEqual(state_json["failure_stage"], "prepare")
            self.assertEqual(state_json["failure_kind"], "entity_matching")
            self.assertEqual(result_state.to_simple_dict()["entity_filter_mode"], "relaxed")
            self.assertEqual(result_state.to_simple_dict()["entity_readiness"], readiness)
            self.assertEqual(result_state.to_simple_dict()["failure_stage"], "prepare")
            self.assertEqual(result_state.to_simple_dict()["failure_kind"], "entity_matching")

    def test_prepare_endpoint_marks_task_failed_and_status_reports_failed_simulation(self):
        readiness = {
            "match_mode": "relaxed",
            "total_nodes": 2,
            "matched_entities": 0,
            "labels_present_count": 0,
            "labels_present_ratio": 0.0,
            "relaxed_candidate_count": 0,
            "rejection_reasons": {
                "entity_type_mismatch": 0,
                "missing_actor_labels": 2,
                "non_actor_text": 0,
            },
        }

        with _loaded_test_environment() as env:
            env.reader_class.calls = []
            env.reader_class.preview_filtered = _make_filtered_entities(
                filtered_count=0,
                readiness=readiness,
                entity_types=[],
                total_count=2,
            )
            env.reader_class.prepared_filtered = _make_filtered_entities(
                filtered_count=0,
                readiness=readiness,
                entity_types=[],
                total_count=2,
            )

            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-2", "graph-2")

            with env.app.test_client() as client, mock.patch("threading.Thread", _ImmediateThread):
                prepare_response = client.post(
                    "/api/simulation/prepare",
                    json={
                        "simulation_id": created.simulation_id,
                        "entity_match_mode": "relaxed",
                    },
                )

                self.assertEqual(prepare_response.status_code, 200)
                prepare_payload = prepare_response.get_json()
                task_id = prepare_payload["data"]["task_id"]

                task = env.task_module.TaskManager().get_task(task_id)
                self.assertEqual(task.status, env.task_module.TaskStatus.FAILED)
                self.assertIsNone(task.result)
                self.assertIn("No matching entities", task.error)

                refreshed_state = env.sim_manager_module.SimulationManager().get_simulation(created.simulation_id)
                self.assertEqual(refreshed_state.status, env.sim_manager_module.SimulationStatus.FAILED)
                self.assertEqual(refreshed_state.entity_filter_mode, "relaxed")
                self.assertEqual(refreshed_state.entity_readiness, readiness)

                status_response = client.post(
                    "/api/simulation/prepare/status",
                    json={"simulation_id": created.simulation_id},
                )

            self.assertEqual([call["match_mode"] for call in env.reader_class.calls], ["relaxed", "relaxed"])
            self.assertEqual(status_response.status_code, 200)
            status_payload = status_response.get_json()
            self.assertTrue(status_payload["success"])
            self.assertEqual(status_payload["data"]["status"], "failed")
            self.assertFalse(status_payload["data"]["already_prepared"])
            self.assertIn("No matching entities", status_payload["data"]["error"])
            self.assertEqual(status_payload["data"]["entity_filter_mode"], "relaxed")
            self.assertEqual(status_payload["data"]["entity_readiness"], readiness)
            self.assertEqual(status_payload["data"]["failure_stage"], "prepare")
            self.assertEqual(status_payload["data"]["failure_kind"], "entity_matching")

    def test_realtime_config_reports_failed_generation_state(self):
        readiness = {
            "match_mode": "strict",
            "total_nodes": 3,
            "matched_entities": 0,
            "labels_present_count": 0,
            "labels_present_ratio": 0.0,
            "relaxed_candidate_count": 1,
            "rejection_reasons": {
                "entity_type_mismatch": 0,
                "missing_actor_labels": 3,
                "non_actor_text": 0,
            },
        }

        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-3", "graph-3")
            state = manager.get_simulation(created.simulation_id)
            state.status = env.sim_manager_module.SimulationStatus.FAILED
            state.error = "No matching entities were found."
            state.entity_filter_mode = "strict"
            state.entity_readiness = readiness
            state.failure_stage = "prepare"
            state.failure_kind = "entity_matching"
            state.config_generated = False
            manager._save_simulation_state(state)

            with env.app.test_client() as client:
                response = client.get(f"/api/simulation/{created.simulation_id}/config/realtime")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertFalse(payload["data"]["is_generating"])
            self.assertEqual(payload["data"]["generation_stage"], "failed")
            self.assertEqual(payload["data"]["failure_reason"], "No matching entities were found.")
            self.assertEqual(payload["data"]["entity_filter_mode"], "strict")
            self.assertEqual(payload["data"]["entity_readiness"], readiness)
            self.assertEqual(payload["data"]["failure_stage"], "prepare")
            self.assertEqual(payload["data"]["failure_kind"], "entity_matching")

    def test_prepare_status_prefers_prepared_result_when_failed_state_has_complete_artifacts(self):
        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-4", "graph-4")
            state = manager.get_simulation(created.simulation_id)
            state.status = env.sim_manager_module.SimulationStatus.FAILED
            state.config_generated = True
            state.error = "Runtime execution failed after prepare completed."
            manager._save_simulation_state(state)
            _write_prepared_artifacts(env.temp_dir, created.simulation_id, state)

            with env.app.test_client() as client:
                response = client.post(
                    "/api/simulation/prepare/status",
                    json={"simulation_id": created.simulation_id},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["status"], "ready")
            self.assertTrue(payload["data"]["already_prepared"])
            self.assertEqual(payload["data"]["prepare_info"]["status"], "failed")

    def test_prepare_status_with_failed_task_id_only_includes_failure_diagnostics(self):
        readiness = {
            "match_mode": "relaxed",
            "total_nodes": 5,
            "matched_entities": 0,
            "labels_present_count": 0,
            "labels_present_ratio": 0.0,
            "relaxed_candidate_count": 0,
            "rejection_reasons": {
                "entity_type_mismatch": 0,
                "missing_actor_labels": 5,
                "non_actor_text": 0,
            },
        }

        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-5", "graph-5")
            state = manager.get_simulation(created.simulation_id)
            state.status = env.sim_manager_module.SimulationStatus.FAILED
            state.error = "No matching entities were found for simulation preparation."
            state.entity_filter_mode = "relaxed"
            state.entity_readiness = readiness
            manager._save_simulation_state(state)

            task_manager = env.task_module.TaskManager()
            task_id = task_manager.create_task(
                task_type="simulation_prepare",
                metadata={"simulation_id": created.simulation_id},
            )
            task_manager.fail_task(task_id, state.error)

            with env.app.test_client() as client:
                response = client.post(
                    "/api/simulation/prepare/status",
                    json={"task_id": task_id},
                )

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["status"], "failed")
            self.assertEqual(payload["data"]["task_id"], task_id)
            self.assertEqual(payload["data"]["failure_reason"], state.error)
            self.assertEqual(payload["data"]["entity_filter_mode"], "relaxed")
            self.assertEqual(payload["data"]["entity_readiness"], readiness)
            self.assertEqual(payload["data"]["failure_stage"], "prepare")
            self.assertEqual(payload["data"]["failure_kind"], "entity_matching")

    def test_prepare_rejects_invalid_entity_match_mode_at_request_boundary(self):
        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-6", "graph-6")
            env.reader_class.calls = []

            with env.app.test_client() as client:
                response = client.post(
                    "/api/simulation/prepare",
                    json={
                        "simulation_id": created.simulation_id,
                        "entity_match_mode": "invalid-mode",
                    },
                )

            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertFalse(payload["success"])
            self.assertIn("entity_match_mode", payload["error"])
            self.assertEqual(env.reader_class.calls, [])

    def test_prepare_rejects_non_string_entity_match_mode_at_request_boundary(self):
        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-8", "graph-8")
            env.reader_class.calls = []

            with env.app.test_client() as client:
                response = client.post(
                    "/api/simulation/prepare",
                    json={
                        "simulation_id": created.simulation_id,
                        "entity_match_mode": True,
                    },
                )

            self.assertEqual(response.status_code, 400)
            payload = response.get_json()
            self.assertFalse(payload["success"])
            self.assertIn("entity_match_mode", payload["error"])
            self.assertEqual(env.reader_class.calls, [])

    def test_realtime_config_reports_config_generation_failure_kind(self):
        readiness = {
            "match_mode": "strict",
            "total_nodes": 6,
            "matched_entities": 4,
        }

        with _loaded_test_environment() as env:
            manager = env.sim_manager_module.SimulationManager()
            created = manager.create_simulation("project-7", "graph-7")
            state = manager.get_simulation(created.simulation_id)
            state.status = env.sim_manager_module.SimulationStatus.FAILED
            state.error = "LLM config generation crashed."
            state.entity_filter_mode = "strict"
            state.entity_readiness = readiness
            state.failure_stage = "config"
            state.failure_kind = "config_generation"
            state.config_generated = False
            manager._save_simulation_state(state)

            with env.app.test_client() as client:
                response = client.get(f"/api/simulation/{created.simulation_id}/config/realtime")

            self.assertEqual(response.status_code, 200)
            payload = response.get_json()
            self.assertTrue(payload["success"])
            self.assertEqual(payload["data"]["generation_stage"], "failed")
            self.assertEqual(payload["data"]["failure_stage"], "config")
            self.assertEqual(payload["data"]["failure_kind"], "config_generation")
            self.assertEqual(payload["data"]["failure_reason"], "LLM config generation crashed.")


if __name__ == "__main__":
    unittest.main()
